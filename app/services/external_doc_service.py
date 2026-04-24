from __future__ import annotations
import hashlib
import logging
import re
from datetime import datetime

from sqlalchemy.orm import Session
from ..models_external_docs import (
    ExternalDocResource, ExternalDocBinding, ExternalDocOpenLog,
)
from ..route_helper import _dt

_log = logging.getLogger(__name__)

# ── Feishu URL parsing ──

_FEISHU_PATTERNS = [
    (re.compile(r'/docx/([A-Za-z0-9]+)'), 'doc', 'docx'),
    (re.compile(r'/sheets/([A-Za-z0-9]+)'), 'sheet', 'sheets'),
    (re.compile(r'/bitable/([A-Za-z0-9]+)'), 'bitable', 'bitable'),
    (re.compile(r'/wiki/([A-Za-z0-9]+)'), 'wiki', 'wiki'),
    (re.compile(r'/drive/folder/([A-Za-z0-9]+)'), 'folder', 'drive/folder'),
]


def resolve_link(url: str) -> dict:
    if not url or not url.strip():
        return {'ok': False, 'platform': 'unknown', 'doc_type': 'unknown',
                'source_doc_token': '', 'canonical_url': '', 'open_url': '',
                'title_hint': '', 'needs_manual_title': True, 'warnings': ['URL 为空']}
    url = url.strip()
    for pattern, doc_type, path_segment in _FEISHU_PATTERNS:
        m = pattern.search(url)
        if m:
            token = m.group(1)
            # extract domain from original url
            domain_match = re.match(r'(https?://[^/]+)', url)
            domain = domain_match.group(1) if domain_match else 'https://feishu.cn'
            canonical = f'{domain}/{path_segment}/{token}'
            return {
                'ok': True, 'platform': 'feishu', 'doc_type': doc_type,
                'source_doc_token': token, 'canonical_url': canonical,
                'open_url': canonical, 'title_hint': '',
                'needs_manual_title': True, 'warnings': [],
            }
    return {
        'ok': False, 'platform': 'unknown', 'doc_type': 'unknown',
        'source_doc_token': '', 'canonical_url': url, 'open_url': url,
        'title_hint': '', 'needs_manual_title': True,
        'warnings': ['无法识别为飞书链接，请手动填写信息'],
    }


# ── Helpers ──

def _compute_url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _serialize_resource(r: ExternalDocResource) -> dict:
    return {
        'id': r.id, 'title': r.title,
        'canonical_url': r.canonical_url, 'open_url': r.open_url,
        'source_platform': r.source_platform, 'doc_type': r.doc_type,
        'status': r.status, 'verification_status': r.verification_status,
        'summary': r.summary,
        'last_opened_at': _dt(r.last_opened_at),
        'created_at': _dt(r.created_at), 'updated_at': _dt(r.updated_at),
    }


def _serialize_binding(b: ExternalDocBinding) -> dict:
    return {
        'id': b.id, 'resource_id': b.resource_id,
        'workspace_id': b.workspace_id,
        'primary_stage_term_id': b.primary_stage_term_id,
        'deliverable_term_id': b.deliverable_term_id,
        'relation_role': b.relation_role,
        'is_primary': bool(b.is_primary), 'status': b.status,
        'remark': b.remark, 'sort_order': b.sort_order,
        'created_at': _dt(b.created_at), 'updated_at': _dt(b.updated_at),
    }


def _ensure_primary_official_conflict(
    db: Session,
    workspace_id: int | None,
    primary_stage_term_id: int | None,
    relation_role: str,
    is_primary: bool,
    exclude_binding_id: int | None = None,
) -> None:
    if not (is_primary and relation_role == 'official'):
        return

    q = db.query(ExternalDocBinding).filter(
        ExternalDocBinding.workspace_id == workspace_id,
        ExternalDocBinding.primary_stage_term_id == primary_stage_term_id,
        ExternalDocBinding.relation_role == 'official',
        ExternalDocBinding.is_primary == 1,
        ExternalDocBinding.status == 'active',
    )
    if exclude_binding_id is not None:
        q = q.filter(ExternalDocBinding.id != exclude_binding_id)
    conflict = q.first()
    if conflict:
        raise ValueError('同一项目阶段下已存在“当前在用”文档')


# ── Resource CRUD ──

def find_or_create_resource(db: Session, data, user_id: int) -> tuple[ExternalDocResource, str]:
    """去重：先按 (source_platform, source_doc_token, doc_type)，再按 canonical_url_hash。"""
    dedupe_mode = 'created'
    resource = None

    if data.source_doc_token:
        resource = db.query(ExternalDocResource).filter(
            ExternalDocResource.source_platform == data.source_platform,
            ExternalDocResource.source_doc_token == data.source_doc_token,
            ExternalDocResource.doc_type == data.doc_type,
        ).first()
        if resource:
            dedupe_mode = 'matched_by_source_token'

    if not resource:
        url_hash = _compute_url_hash(data.canonical_url)
        resource = db.query(ExternalDocResource).filter(
            ExternalDocResource.canonical_url_hash == url_hash,
        ).first()
        if resource:
            dedupe_mode = 'matched_by_url_hash'

    if not resource:
        resource = ExternalDocResource(
            title=data.title,
            canonical_url=data.canonical_url,
            canonical_url_hash=_compute_url_hash(data.canonical_url),
            open_url=data.open_url,
            source_platform=data.source_platform,
            source_doc_token=data.source_doc_token,
            doc_type=data.doc_type,
            summary=data.summary,
            owner_user_id=data.owner_user_id,
            maintainer_user_id=data.maintainer_user_id,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(resource)
        db.flush()

    return resource, dedupe_mode


def create_resource(db: Session, data, user_id: int) -> ExternalDocResource:
    resource = ExternalDocResource(
        title=data.title,
        canonical_url=data.canonical_url,
        canonical_url_hash=_compute_url_hash(data.canonical_url),
        open_url=data.open_url,
        source_platform=data.source_platform,
        source_doc_token=data.source_doc_token,
        doc_type=data.doc_type,
        summary=data.summary,
        owner_user_id=data.owner_user_id,
        maintainer_user_id=data.maintainer_user_id,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


def update_resource(db: Session, resource_id: int, data, user_id: int) -> ExternalDocResource | None:
    resource = db.query(ExternalDocResource).get(resource_id)
    if not resource:
        return None
    for field in ('title', 'summary', 'status', 'verification_status', 'owner_user_id', 'maintainer_user_id'):
        val = getattr(data, field, None)
        if val is not None:
            setattr(resource, field, val)
    resource.updated_by = user_id
    db.commit()
    db.refresh(resource)
    return resource


def get_resource(db: Session, resource_id: int) -> ExternalDocResource | None:
    return db.query(ExternalDocResource).get(resource_id)


def list_resources(db: Session, keyword: str | None = None, status: str | None = None) -> list[ExternalDocResource]:
    q = db.query(ExternalDocResource)
    if status:
        q = q.filter(ExternalDocResource.status == status)
    if keyword:
        q = q.filter(ExternalDocResource.title.ilike(f'%{keyword}%'))
    return q.order_by(ExternalDocResource.updated_at.desc()).all()


def list_recent_opened_resources(db: Session, user_id: int, limit: int = 8) -> list[ExternalDocResource]:
    logs = db.query(ExternalDocOpenLog).filter(
        ExternalDocOpenLog.opened_by == user_id,
    ).order_by(ExternalDocOpenLog.opened_at.desc()).all()

    if not logs:
        return []

    recent_ids: list[int] = []
    seen: set[int] = set()
    for log in logs:
        if log.resource_id in seen:
            continue
        seen.add(log.resource_id)
        recent_ids.append(log.resource_id)
        if len(recent_ids) >= limit:
            break

    if not recent_ids:
        return []

    resources = db.query(ExternalDocResource).filter(
        ExternalDocResource.id.in_(recent_ids),
        ExternalDocResource.status == 'active',
    ).all()
    resource_map = {r.id: r for r in resources}
    return [resource_map[rid] for rid in recent_ids if rid in resource_map]


# ── Binding CRUD ──

def create_binding(db: Session, data, user_id: int) -> ExternalDocBinding:
    resource = db.query(ExternalDocResource).get(data.resource_id)
    if not resource:
        raise ValueError('资源不存在')

    _ensure_primary_official_conflict(
        db,
        data.workspace_id,
        data.primary_stage_term_id,
        data.relation_role,
        data.is_primary,
    )

    binding = ExternalDocBinding(
        resource_id=data.resource_id,
        workspace_id=data.workspace_id,
        primary_stage_term_id=data.primary_stage_term_id,
        deliverable_term_id=data.deliverable_term_id,
        relation_role=data.relation_role,
        is_primary=1 if data.is_primary else 0,
        remark=data.remark,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(binding)
    db.commit()
    db.refresh(binding)
    return binding


def update_binding(db: Session, binding_id: int, data, user_id: int) -> ExternalDocBinding | None:
    binding = db.query(ExternalDocBinding).get(binding_id)
    if not binding:
        return None
    next_relation_role = data.relation_role if data.relation_role is not None else binding.relation_role
    next_stage_term_id = data.primary_stage_term_id if data.primary_stage_term_id is not None else binding.primary_stage_term_id
    next_is_primary = bool(data.is_primary) if data.is_primary is not None else bool(binding.is_primary)
    _ensure_primary_official_conflict(
        db,
        binding.workspace_id,
        next_stage_term_id,
        next_relation_role,
        next_is_primary,
        exclude_binding_id=binding.id,
    )

    for field in ('relation_role', 'primary_stage_term_id', 'deliverable_term_id', 'status', 'remark'):
        val = getattr(data, field, None)
        if val is not None:
            setattr(binding, field, val)
    if data.is_primary is not None:
        binding.is_primary = 1 if data.is_primary else 0
    binding.updated_by = user_id
    db.commit()
    db.refresh(binding)
    return binding


def delete_binding(db: Session, binding_id: int) -> bool:
    binding = db.query(ExternalDocBinding).get(binding_id)
    if not binding:
        return False
    binding.status = 'inactive'
    db.commit()
    return True


def list_bindings(db: Session, workspace_id: int | None = None, resource_id: int | None = None) -> list[ExternalDocBinding]:
    q = db.query(ExternalDocBinding).filter(ExternalDocBinding.status == 'active')
    if workspace_id is not None:
        q = q.filter(ExternalDocBinding.workspace_id == workspace_id)
    if resource_id is not None:
        q = q.filter(ExternalDocBinding.resource_id == resource_id)
    return q.order_by(ExternalDocBinding.sort_order, ExternalDocBinding.id).all()


# ── Quick Add (transactional) ──

def quick_add(db: Session, request, user_id: int) -> dict:
    try:
        resource, dedupe_mode = find_or_create_resource(db, request.resource, user_id)

        existing = db.query(ExternalDocBinding).filter(
            ExternalDocBinding.resource_id == resource.id,
            ExternalDocBinding.workspace_id == request.binding.workspace_id,
            ExternalDocBinding.status == 'active',
        ).first()
        if existing:
            if request.open_after_save:
                _record_open(db, resource.id, user_id, request.binding.workspace_id)
            else:
                db.commit()
            return {
                'resource': {**_serialize_resource(resource), 'dedupe_mode': dedupe_mode},
                'binding': _serialize_binding(existing),
                'open_url': resource.open_url if request.open_after_save else None,
            }

        _ensure_primary_official_conflict(
            db,
            request.binding.workspace_id,
            request.binding.primary_stage_term_id,
            request.binding.relation_role,
            request.binding.is_primary,
        )

        binding = ExternalDocBinding(
            resource_id=resource.id,
            workspace_id=request.binding.workspace_id,
            primary_stage_term_id=request.binding.primary_stage_term_id,
            deliverable_term_id=request.binding.deliverable_term_id,
            relation_role=request.binding.relation_role,
            is_primary=1 if request.binding.is_primary else 0,
            remark=request.binding.remark,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(binding)
        db.flush()

        open_url = None
        if request.open_after_save:
            open_url = resource.open_url
            _record_open(db, resource.id, user_id, request.binding.workspace_id, auto_commit=False)

        db.commit()
        db.refresh(binding)
        db.refresh(resource)
        return {
            'resource': {**_serialize_resource(resource), 'dedupe_mode': dedupe_mode},
            'binding': _serialize_binding(binding),
            'open_url': open_url,
        }
    except Exception:
        db.rollback()
        raise


# ── Open ──

def _record_open(
    db: Session,
    resource_id: int,
    user_id: int,
    workspace_id: int | None = None,
    client_type: str = 'web',
    auto_commit: bool = True,
) -> None:
    log = ExternalDocOpenLog(
        resource_id=resource_id, workspace_id=workspace_id,
        opened_by=user_id, client_type=client_type,
    )
    db.add(log)
    resource = db.query(ExternalDocResource).get(resource_id)
    if resource:
        resource.last_opened_at = datetime.utcnow()
    if auto_commit:
        db.commit()


def record_open(db: Session, resource_id: int, user_id: int, workspace_id: int | None = None, client_type: str = 'web') -> dict | None:
    resource = db.query(ExternalDocResource).get(resource_id)
    if not resource:
        return None
    _record_open(db, resource_id, user_id, workspace_id, client_type=client_type)
    return {'open_url': resource.open_url, 'opened_at': _dt(datetime.utcnow())}
