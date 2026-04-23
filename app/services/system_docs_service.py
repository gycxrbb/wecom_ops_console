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
SYSTEM_DOCS_DRAFTS_DIR = SYSTEM_DOCS_DIR / '_drafts'

DEFAULT_CATEGORY = '基础上手'
DEFAULT_DIFFICULTY = 'beginner'
ALLOWED_DIFFICULTIES = {'beginner', 'intermediate', 'advanced', 'admin'}
ALLOWED_STATUSES = {'draft', 'published'}
_log = logging.getLogger(__name__)


def _ensure_system_docs_dir() -> None:
    SYSTEM_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    SYSTEM_DOCS_DRAFTS_DIR.mkdir(parents=True, exist_ok=True)


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


def _normalize_difficulty(value: str) -> str:
    normalized = str(value or '').strip().lower()
    if normalized in ALLOWED_DIFFICULTIES:
        return normalized
    return DEFAULT_DIFFICULTY


def _normalize_recommended_slugs(value: object) -> list[str]:
    if isinstance(value, str):
        candidates = re.split(r'[\s,，]+', value)
    elif isinstance(value, list):
        candidates = value
    else:
        candidates = []

    normalized: list[str] = []
    for candidate in candidates:
        slug = str(candidate or '').strip()
        if not slug:
            continue
        safe_slug = _slugify(slug)
        if safe_slug and safe_slug not in normalized:
            normalized.append(safe_slug)
    return normalized


def _normalize_status(value: str) -> str:
    normalized = str(value or '').strip().lower()
    if normalized in ALLOWED_STATUSES:
        return normalized
    return 'published'


def _normalize_entry(entry: dict, index: int) -> dict:
    slug = _safe_slug(str(entry.get('slug') or ''), fallback_prefix='doc')
    filename = str(entry.get('filename') or f'{index + 1:02d}-{slug}.md').strip()
    draft_filename = str(entry.get('draft_filename') or f'{slug}.md').strip()
    if not filename.endswith('.md'):
        filename = f'{filename}.md'
    if not draft_filename.endswith('.md'):
        draft_filename = f'{draft_filename}.md'
    return {
        'slug': slug,
        'title': str(entry.get('title') or slug).strip() or slug,
        'category': str(entry.get('category') or DEFAULT_CATEGORY).strip() or DEFAULT_CATEGORY,
        'author': str(entry.get('author') or '').strip(),
        'summary': str(entry.get('summary') or '').strip(),
        'cover_image': str(entry.get('cover_image') or '').strip(),
        'difficulty': _normalize_difficulty(str(entry.get('difficulty') or DEFAULT_DIFFICULTY)),
        'recommended_slugs': _normalize_recommended_slugs(entry.get('recommended_slugs')),
        'status': _normalize_status(str(entry.get('status') or 'published')),
        'published_at': str(entry.get('published_at') or '').strip(),
        'draft_updated_at': str(entry.get('draft_updated_at') or '').strip(),
        'order': int(entry.get('order') or index + 1),
        'filename': filename,
        'draft_filename': draft_filename,
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


def _draft_path(filename: str) -> Path:
    return SYSTEM_DOCS_DRAFTS_DIR / filename


def _entry_with_runtime_fields(entry: dict) -> dict:
    path = _doc_path(entry['filename'])
    draft_path = _draft_path(entry.get('draft_filename') or f'{entry["slug"]}.md')
    updated_at = entry.get('updated_at') or _now_iso()
    draft_updated_at = str(entry.get('draft_updated_at') or '').strip()
    if path.exists():
        updated_at = datetime.utcfromtimestamp(path.stat().st_mtime).replace(microsecond=0).isoformat() + 'Z'
    if draft_path.exists():
        draft_updated_at = datetime.utcfromtimestamp(draft_path.stat().st_mtime).replace(microsecond=0).isoformat() + 'Z'
    published_exists = path.exists()
    draft_exists = draft_path.exists()
    status = _normalize_status(entry.get('status') or ('published' if published_exists else 'draft'))
    if not published_exists and draft_exists:
        status = 'draft'
    return {
        **entry,
        'updated_at': updated_at,
        'published_at': str(entry.get('published_at') or updated_at if published_exists else '').strip(),
        'draft_updated_at': draft_updated_at,
        'exists': published_exists,
        'published_exists': published_exists,
        'draft_exists': draft_exists,
        'has_draft': draft_exists,
        'status': status,
    }


def _resolve_recommended_docs(entries: list[dict], slugs: list[str], current_slug: str) -> list[dict]:
    entry_by_slug = {entry['slug']: _entry_with_runtime_fields(entry) for entry in entries}
    resolved: list[dict] = []
    for slug in slugs:
        if slug == current_slug:
            continue
        candidate = entry_by_slug.get(slug)
        if not candidate:
            continue
        resolved.append(candidate)
    return resolved


def _read_content(path: Path) -> str:
    if not path.exists():
        return ''
    return path.read_text(encoding='utf-8')


def _get_content_for_mode(entry: dict, *, mode: str) -> str:
    runtime_entry = _entry_with_runtime_fields(entry)
    published_path = _doc_path(entry['filename'])
    draft_path = _draft_path(entry.get('draft_filename') or f'{entry["slug"]}.md')
    if mode == 'draft' and runtime_entry['draft_exists']:
        return _read_content(draft_path)
    if runtime_entry['published_exists']:
        return _read_content(published_path)
    if runtime_entry['draft_exists']:
        return _read_content(draft_path)
    return ''


def list_system_docs(*, include_unpublished: bool = False) -> dict:
    entries = [_entry_with_runtime_fields(entry) for entry in _load_meta_entries()]
    if not include_unpublished:
        entries = [entry for entry in entries if entry['status'] == 'published']
    categories = sorted({entry['category'] for entry in entries})
    return {
        'categories': categories,
        'docs': entries,
    }


def get_system_doc(slug: str, *, mode: str = 'published', include_unpublished: bool = False) -> dict:
    entries = _load_meta_entries()
    for entry in entries:
        if entry['slug'] != slug:
            continue
        runtime_entry = _entry_with_runtime_fields(entry)
        if not include_unpublished and runtime_entry['status'] != 'published':
            raise FileNotFoundError(f'系统教学文档不存在: {slug}')
        content = _get_content_for_mode(entry, mode='draft' if mode == 'draft' else 'published')
        if not content:
            raise FileNotFoundError(f'系统教学文档不存在: {entry["filename"]}')
        return {
            **runtime_entry,
            'recommended_docs': _resolve_recommended_docs(entries, entry.get('recommended_slugs', []), slug),
            'editor_mode': 'draft' if mode == 'draft' and runtime_entry['draft_exists'] else 'published',
            'content': content,
        }
    raise FileNotFoundError(f'系统教学文档不存在: {slug}')


def _build_search_excerpt(content: str, query: str, *, window: int = 88) -> str:
    normalized_content = re.sub(r'\s+', ' ', content or '').strip()
    if not normalized_content:
        return ''
    if not query:
        return normalized_content[: window * 2]
    lower_content = normalized_content.lower()
    lower_query = query.lower()
    hit = lower_content.find(lower_query)
    if hit < 0:
        return normalized_content[: window * 2]
    start = max(0, hit - window)
    end = min(len(normalized_content), hit + len(query) + window)
    prefix = '...' if start > 0 else ''
    suffix = '...' if end < len(normalized_content) else ''
    return prefix + normalized_content[start:end] + suffix


def search_system_docs(query: str, *, include_unpublished: bool = False) -> dict:
    normalized_query = str(query or '').strip()
    if not normalized_query:
        return {'query': '', 'total': 0, 'docs': []}

    hits: list[dict] = []
    for entry in _load_meta_entries():
        runtime_entry = _entry_with_runtime_fields(entry)
        if not include_unpublished and runtime_entry['status'] != 'published':
            continue
        content_mode = 'draft' if include_unpublished and (runtime_entry['status'] == 'draft' or runtime_entry['has_draft']) else 'published'
        content = _get_content_for_mode(entry, mode=content_mode)
        search_fields = {
            'title': entry['title'],
            'summary': entry['summary'],
            'category': entry['category'],
            'slug': entry['slug'],
            'content': content,
        }
        matched_fields = [
            field
            for field, value in search_fields.items()
            if normalized_query.lower() in str(value or '').lower()
        ]
        if not matched_fields:
            continue
        hits.append(
            {
                **runtime_entry,
                'matched_fields': matched_fields,
                'snippet': _build_search_excerpt(content or entry.get('summary') or entry['title'], normalized_query),
            }
        )

    hits.sort(key=lambda item: (item['order'], item['title']))
    return {'query': normalized_query, 'total': len(hits), 'docs': hits}


def _ensure_unique_slug(entries: list[dict], normalized_slug: str, current_slug: str | None = None) -> None:
    for entry in entries:
        if entry['slug'] == normalized_slug and entry['slug'] != current_slug:
            raise ValueError('文档 slug 已存在')


def _draft_filename_for_slug(slug: str) -> str:
    return f'{slug}.md'


def save_system_doc(
    current_slug: str | None,
    *,
    title: str,
    slug: str,
    category: str,
    author: str,
    summary: str,
    cover_image: str,
    difficulty: str,
    recommended_slugs: list[str] | None,
    content: str,
    order: int | None = None,
    save_mode: str = 'publish',
) -> dict:
    entries = _load_meta_entries()
    normalized_slug = _safe_slug(slug or title, fallback_prefix='doc')
    target_index = -1
    entry: dict | None = None

    if current_slug:
        for index, candidate in enumerate(entries):
            if candidate['slug'] == current_slug:
                target_index = index
                entry = candidate
                break
        if entry is None:
            raise FileNotFoundError('文档不存在')

    _ensure_unique_slug(entries, normalized_slug, current_slug)
    normalized_save_mode = 'draft' if str(save_mode or '').strip().lower() == 'draft' else 'publish'
    now_iso = _now_iso()

    if entry is None:
        next_order = order if order and order > 0 else len(entries) + 1
        entry = _normalize_entry(
            {
                'slug': normalized_slug,
                'title': title.strip() or normalized_slug,
                'category': category.strip() or DEFAULT_CATEGORY,
                'author': author.strip(),
                'summary': summary.strip(),
                'cover_image': cover_image.strip(),
                'difficulty': _normalize_difficulty(difficulty),
                'recommended_slugs': _normalize_recommended_slugs(recommended_slugs or []),
                'order': next_order,
                'filename': f'{next_order:02d}-{normalized_slug}.md',
                'draft_filename': _draft_filename_for_slug(normalized_slug),
                'updated_at': now_iso,
                'status': 'draft' if normalized_save_mode == 'draft' else 'published',
                'published_at': now_iso if normalized_save_mode == 'publish' else '',
                'draft_updated_at': now_iso if normalized_save_mode == 'draft' else '',
            },
            len(entries),
        )
        entries.append(entry)
        target_index = len(entries) - 1

    old_published_path = _doc_path(entry['filename'])
    old_draft_path = _draft_path(entry.get('draft_filename') or _draft_filename_for_slug(entry['slug']))
    new_filename = entry['filename']
    new_draft_filename = entry.get('draft_filename') or _draft_filename_for_slug(entry['slug'])
    if normalized_slug != entry['slug']:
        new_filename = f'{int(entry["order"]):02d}-{normalized_slug}.md'
        new_draft_filename = _draft_filename_for_slug(normalized_slug)

    new_published_path = _doc_path(new_filename)
    new_draft_path = _draft_path(new_draft_filename)
    if old_published_path != new_published_path and old_published_path.exists():
        old_published_path.rename(new_published_path)
    if old_draft_path != new_draft_path and old_draft_path.exists():
        old_draft_path.rename(new_draft_path)

    current_runtime = _entry_with_runtime_fields(entry)
    if normalized_save_mode == 'draft':
        new_draft_path.write_text(content, encoding='utf-8')
        status = 'draft' if not current_runtime['published_exists'] else 'published'
        published_at = entry.get('published_at') or (current_runtime['updated_at'] if current_runtime['published_exists'] else '')
        draft_updated_at = now_iso
    else:
        new_published_path.write_text(content, encoding='utf-8')
        if new_draft_path.exists():
            new_draft_path.unlink()
        status = 'published'
        published_at = now_iso
        draft_updated_at = ''

    entry.update(
        {
            'slug': normalized_slug,
            'title': title.strip() or normalized_slug,
            'category': category.strip() or DEFAULT_CATEGORY,
            'author': author.strip(),
            'summary': summary.strip(),
            'cover_image': cover_image.strip(),
            'difficulty': _normalize_difficulty(difficulty),
            'recommended_slugs': _normalize_recommended_slugs(recommended_slugs or []),
            'order': int(order or entry['order'] or target_index + 1),
            'filename': new_filename,
            'draft_filename': new_draft_filename,
            'updated_at': now_iso,
            'status': status,
            'published_at': str(published_at or '').strip(),
            'draft_updated_at': str(draft_updated_at or '').strip(),
        }
    )
    entries[target_index] = entry
    _save_meta_entries(entries)
    _log.info(
        '系统教学文档已保存: mode=%s slug=%s title=%s status=%s',
        normalized_save_mode,
        normalized_slug,
        entry['title'],
        entry['status'],
    )
    return get_system_doc(
        normalized_slug,
        mode='draft' if normalized_save_mode == 'draft' else 'published',
        include_unpublished=True,
    )


def create_system_doc(
    *,
    title: str,
    slug: str,
    category: str,
    author: str,
    summary: str,
    cover_image: str,
    difficulty: str,
    recommended_slugs: list[str] | None,
    content: str,
    order: int | None = None,
    save_mode: str = 'publish',
) -> dict:
    return save_system_doc(
        None,
        title=title,
        slug=slug,
        category=category,
        author=author,
        summary=summary,
        cover_image=cover_image,
        difficulty=difficulty,
        recommended_slugs=recommended_slugs,
        content=content,
        order=order,
        save_mode=save_mode,
    )


def update_system_doc(
    current_slug: str,
    *,
    title: str,
    slug: str,
    category: str,
    author: str,
    summary: str,
    cover_image: str,
    difficulty: str,
    recommended_slugs: list[str] | None,
    content: str,
    order: int | None = None,
    save_mode: str = 'publish',
) -> dict:
    return save_system_doc(
        current_slug,
        title=title,
        slug=slug,
        category=category,
        author=author,
        summary=summary,
        cover_image=cover_image,
        difficulty=difficulty,
        recommended_slugs=recommended_slugs,
        content=content,
        order=order,
        save_mode=save_mode,
    )


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
    draft_path = _draft_path(target_entry.get('draft_filename') or _draft_filename_for_slug(target_entry['slug']))
    if path.exists():
        path.unlink()
    if draft_path.exists():
        draft_path.unlink()
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
    object_key = f'qiwei/docs/images/{date_part}/{safe_stem}-{uuid4().hex[:12]}{suffix}'
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
