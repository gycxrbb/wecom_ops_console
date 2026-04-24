from __future__ import annotations
import logging
from sqlalchemy.orm import Session
from ..models_external_docs import (
    ExternalDocResource, ExternalDocBinding, ExternalDocTermBinding, ExternalDocTerm,
)
from .external_doc_service import resolve_link, _compute_url_hash

_log = logging.getLogger(__name__)

LEGACY_CATEGORIES = ['运营流程', '话术库', '经验库', '营养知识', '培训手册', '其他']


def migrate_sop_documents(db: Session) -> dict:
    """将 sop_documents 旧数据迁移到新表。幂等。"""
    from ..models import SopDocument

    old_docs = db.query(SopDocument).all()
    if not old_docs:
        return {'total': 0, 'migrated': 0, 'skipped': 0}

    # find or create inbox workspace
    from ..models_external_docs import ExternalDocWorkspace
    inbox = db.query(ExternalDocWorkspace).filter(
        ExternalDocWorkspace.workspace_type == 'inbox',
    ).first()
    if not inbox:
        inbox = ExternalDocWorkspace(
            name='收件箱', workspace_type='inbox', status='running',
        )
        db.add(inbox)
        db.flush()

    # load legacy_category terms
    cat_terms: dict[str, ExternalDocTerm] = {}
    for t in db.query(ExternalDocTerm).filter(ExternalDocTerm.dimension == 'legacy_category'):
        cat_terms[t.code] = t

    stats = {
        'total': len(old_docs), 'migrated': 0, 'parse_failed': 0,
        'duplicate_urls': 0, 'inbox_count': 0,
        'per_category': {c: 0 for c in LEGACY_CATEGORIES},
    }

    seen_hashes: set[str] = set()
    existing_hashes = db.query(ExternalDocResource.canonical_url_hash).all()
    for (h,) in existing_hashes:
        seen_hashes.add(h)

    for old in old_docs:
        url = (old.url or '').strip()
        if not url:
            stats['parse_failed'] += 1
            continue

        # parse url
        parsed = resolve_link(url)
        platform = parsed['platform']
        doc_type = parsed['doc_type']
        token = parsed['source_doc_token']
        canonical = parsed['canonical_url'] or url

        url_hash = _compute_url_hash(canonical)
        if url_hash in seen_hashes:
            stats['duplicate_urls'] += 1
            continue
        seen_hashes.add(url_hash)

        resource = ExternalDocResource(
            title=old.title or '未命名',
            canonical_url=canonical,
            canonical_url_hash=url_hash,
            open_url=url,
            source_platform=platform,
            source_doc_token=token or None,
            doc_type=doc_type,
            summary=old.description or '',
            status='active',
            verification_status='unverified',
            created_by=old.created_by,
        )
        db.add(resource)
        db.flush()

        binding = ExternalDocBinding(
            resource_id=resource.id,
            workspace_id=inbox.id,
            relation_role='support',
            is_primary=0,
            status='active',
            created_by=old.created_by,
        )
        db.add(binding)

        # link legacy_category term
        category = old.category or '其他'
        term = cat_terms.get(category)
        if term:
            tb = ExternalDocTermBinding(
                resource_id=resource.id,
                term_id=term.id,
                binding_type='legacy',
            )
            db.add(tb)

        stats['migrated'] += 1
        stats['inbox_count'] += 1
        if category in stats['per_category']:
            stats['per_category'][category] += 1

    db.commit()
    _log.info('SOP迁移完成: %s', stats)
    return stats
