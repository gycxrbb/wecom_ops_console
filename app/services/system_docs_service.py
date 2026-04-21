from __future__ import annotations

import json
import logging
import mimetypes
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from ..config import BASE_DIR
from .storage import UploadPayload, storage_facade

SYSTEM_DOCS_DIR = BASE_DIR / 'docs' / 'system_teaching'
SYSTEM_DOCS_META_PATH = SYSTEM_DOCS_DIR / '_meta.json'

DEFAULT_CATEGORY = '基础上手'
_log = logging.getLogger(__name__)


def _ensure_system_docs_dir() -> None:
    SYSTEM_DOCS_DIR.mkdir(parents=True, exist_ok=True)


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', value or '')
    ascii_text = normalized.encode('ascii', 'ignore').decode('ascii').lower()
    ascii_text = re.sub(r'[^a-z0-9]+', '-', ascii_text).strip('-')
    return ascii_text


def _safe_slug(value: str, *, fallback_prefix: str = 'doc') -> str:
    slug = _slugify(value)
    if slug:
        return slug
    return f'{fallback_prefix}-{uuid4().hex[:8]}'


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _normalize_entry(entry: dict, index: int) -> dict:
    slug = _safe_slug(str(entry.get('slug') or ''), fallback_prefix='doc')
    filename = str(entry.get('filename') or f'{index + 1:02d}-{slug}.md').strip()
    if not filename.endswith('.md'):
        filename = f'{filename}.md'
    return {
        'slug': slug,
        'title': str(entry.get('title') or slug).strip() or slug,
        'category': str(entry.get('category') or DEFAULT_CATEGORY).strip() or DEFAULT_CATEGORY,
        'summary': str(entry.get('summary') or '').strip(),
        'order': int(entry.get('order') or index + 1),
        'filename': filename,
        'updated_at': str(entry.get('updated_at') or _now_iso()),
    }


def _load_meta_entries() -> list[dict]:
    _ensure_system_docs_dir()
    if not SYSTEM_DOCS_META_PATH.exists():
        return []
    try:
        payload = json.loads(SYSTEM_DOCS_META_PATH.read_text(encoding='utf-8'))
    except Exception:
        return []

    if isinstance(payload, dict):
        raw_entries = payload.get('docs', [])
    else:
        raw_entries = payload

    if not isinstance(raw_entries, list):
        return []
    return [_normalize_entry(entry or {}, index) for index, entry in enumerate(raw_entries)]


def _save_meta_entries(entries: list[dict]) -> None:
    _ensure_system_docs_dir()
    normalized = [_normalize_entry(entry, index) for index, entry in enumerate(entries)]
    normalized.sort(key=lambda item: (item['order'], item['title']))
    for index, entry in enumerate(normalized, start=1):
        entry['order'] = index
    SYSTEM_DOCS_META_PATH.write_text(
        json.dumps({'docs': normalized}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def _doc_path(filename: str) -> Path:
    return SYSTEM_DOCS_DIR / filename


def _entry_with_runtime_fields(entry: dict) -> dict:
    path = _doc_path(entry['filename'])
    updated_at = entry.get('updated_at') or _now_iso()
    if path.exists():
        updated_at = datetime.utcfromtimestamp(path.stat().st_mtime).replace(microsecond=0).isoformat() + 'Z'
    return {
        **entry,
        'updated_at': updated_at,
        'exists': path.exists(),
    }


def list_system_docs() -> dict:
    entries = [_entry_with_runtime_fields(entry) for entry in _load_meta_entries()]
    categories = sorted({entry['category'] for entry in entries})
    return {
        'categories': categories,
        'docs': entries,
    }


def get_system_doc(slug: str) -> dict:
    for entry in _load_meta_entries():
        if entry['slug'] != slug:
            continue
        path = _doc_path(entry['filename'])
        if not path.exists():
            raise FileNotFoundError(f'系统教学文档不存在: {entry["filename"]}')
        content = path.read_text(encoding='utf-8')
        return {
            **_entry_with_runtime_fields(entry),
            'content': content,
        }
    raise FileNotFoundError(f'系统教学文档不存在: {slug}')


def create_system_doc(
    *,
    title: str,
    slug: str,
    category: str,
    summary: str,
    content: str,
    order: int | None = None,
) -> dict:
    entries = _load_meta_entries()
    normalized_slug = _safe_slug(slug or title, fallback_prefix='doc')
    if any(entry['slug'] == normalized_slug for entry in entries):
        raise ValueError('文档 slug 已存在')

    next_order = order if order and order > 0 else len(entries) + 1
    filename = f'{next_order:02d}-{normalized_slug}.md'
    path = _doc_path(filename)
    path.write_text(content, encoding='utf-8')

    entry = {
        'slug': normalized_slug,
        'title': title.strip() or normalized_slug,
        'category': category.strip() or DEFAULT_CATEGORY,
        'summary': summary.strip(),
        'order': next_order,
        'filename': filename,
        'updated_at': _now_iso(),
    }
    entries.append(entry)
    _save_meta_entries(entries)
    _log.info('系统教学文档已创建: slug=%s title=%s category=%s', normalized_slug, entry['title'], entry['category'])
    return get_system_doc(normalized_slug)


def update_system_doc(
    current_slug: str,
    *,
    title: str,
    slug: str,
    category: str,
    summary: str,
    content: str,
    order: int | None = None,
) -> dict:
    entries = _load_meta_entries()
    normalized_slug = _safe_slug(slug or title, fallback_prefix='doc')
    target_index = -1
    for index, entry in enumerate(entries):
        if entry['slug'] == current_slug:
            target_index = index
            break
    if target_index < 0:
        raise FileNotFoundError('文档不存在')
    if normalized_slug != current_slug and any(entry['slug'] == normalized_slug for entry in entries):
        raise ValueError('文档 slug 已存在')

    entry = entries[target_index]
    old_path = _doc_path(entry['filename'])
    new_filename = entry['filename']
    if normalized_slug != current_slug:
        new_filename = f'{entry["order"]:02d}-{normalized_slug}.md'
    new_path = _doc_path(new_filename)

    if old_path != new_path and old_path.exists():
        old_path.rename(new_path)

    new_path.write_text(content, encoding='utf-8')
    entry.update(
        {
            'slug': normalized_slug,
            'title': title.strip() or normalized_slug,
            'category': category.strip() or DEFAULT_CATEGORY,
            'summary': summary.strip(),
            'order': int(order or entry['order'] or target_index + 1),
            'filename': new_filename,
            'updated_at': _now_iso(),
        }
    )
    _save_meta_entries(entries)
    _log.info(
        '系统教学文档已更新: old_slug=%s new_slug=%s title=%s category=%s',
        current_slug,
        normalized_slug,
        entry['title'],
        entry['category'],
    )
    return get_system_doc(normalized_slug)


def delete_system_doc(slug: str) -> None:
    entries = _load_meta_entries()
    target_index = -1
    target_entry: dict | None = None
    for index, entry in enumerate(entries):
        if entry['slug'] == slug:
            target_index = index
            target_entry = entry
            break
    if target_index < 0 or target_entry is None:
        raise FileNotFoundError('文档不存在')

    path = _doc_path(target_entry['filename'])
    if path.exists():
        path.unlink()
    del entries[target_index]
    _save_meta_entries(entries)
    _log.info(
        '系统教学文档已删除: slug=%s title=%s filename=%s',
        target_entry['slug'],
        target_entry['title'],
        target_entry['filename'],
    )


def upload_system_doc_image(
    *,
    content: bytes,
    filename: str,
    mime_type: str | None = None,
    article_slug: str = '',
) -> dict:
    mime = mime_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    suffix = Path(filename).suffix.lower() or mimetypes.guess_extension(mime) or '.bin'
    safe_stem = _safe_slug(Path(filename).stem or article_slug or 'image', fallback_prefix='image')
    date_part = datetime.utcnow().strftime('%Y/%m/%d')
    object_key = f'qiwei/docs/{date_part}/{safe_stem}-{uuid4().hex[:12]}{suffix}'
    result = storage_facade.upload(
        UploadPayload(
            content=content,
            filename=filename,
            mime_type=mime,
            object_key=object_key,
        )
    )
    _log.info(
        '系统教学图片已上传: article_slug=%s filename=%s object_key=%s provider=%s size=%s',
        article_slug or '-',
        filename,
        result.object_key,
        result.provider,
        result.file_size,
    )
    return {
        'url': result.public_url,
        'object_key': result.object_key,
        'filename': result.original_filename,
        'mime_type': result.mime_type,
        'file_size': result.file_size,
        'markdown': f'![{Path(filename).stem or "图片"}]({result.public_url})',
    }
