from __future__ import annotations
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..models_external_docs import (
    ExternalDocResource, ExternalDocBinding, ExternalDocWorkspace,
)
from ..route_helper import _dt


def get_governance_queue(db: Session) -> dict:
    return {
        'needs_sorting': _get_needs_sorting(db),
        'needs_verification': _get_needs_verification(db),
        'duplicate_primary_docs': _get_duplicate_primary(db),
        'missing_official_docs': _get_missing_official(db),
    }


def _get_needs_sorting(db: Session) -> list[dict]:
    """没有活跃绑定的资源（孤儿资源）。"""
    bound_ids = select(ExternalDocBinding.resource_id).where(
        ExternalDocBinding.status == 'active',
    )
    orphans = db.query(ExternalDocResource).filter(
        ExternalDocResource.status == 'active',
        ExternalDocResource.id.notin_(bound_ids),
    ).all()
    return [
        {'resource_id': r.id, 'title': r.title, 'canonical_url': r.canonical_url,
         'doc_type': r.doc_type, 'summary': r.summary or '',
         'created_at': _dt(r.created_at)}
        for r in orphans
    ]


def _get_needs_verification(db: Session) -> list[dict]:
    """校验状态不为 verified 的活跃资源。"""
    resources = db.query(ExternalDocResource).filter(
        ExternalDocResource.status == 'active',
        ExternalDocResource.verification_status.in_(['unverified', 'need_check', 'broken']),
    ).all()
    return [
        {'resource_id': r.id, 'title': r.title, 'canonical_url': r.canonical_url,
         'verification_status': r.verification_status,
         'doc_type': r.doc_type,
         'updated_at': _dt(r.updated_at)}
        for r in resources
    ]


def _get_duplicate_primary(db: Session) -> list[dict]:
    """同一工作台+阶段下有多个 is_primary=1 的绑定。"""
    dupes = db.query(
        ExternalDocBinding.workspace_id,
        ExternalDocBinding.primary_stage_term_id,
        func.count(ExternalDocBinding.id).label('cnt'),
    ).filter(
        ExternalDocBinding.is_primary == 1,
        ExternalDocBinding.status == 'active',
        ExternalDocBinding.workspace_id.isnot(None),
        ExternalDocBinding.primary_stage_term_id.isnot(None),
    ).group_by(
        ExternalDocBinding.workspace_id,
        ExternalDocBinding.primary_stage_term_id,
    ).having(func.count(ExternalDocBinding.id) > 1).all()

    results = []
    for ws_id, stage_id, cnt in dupes:
        ws = db.query(ExternalDocWorkspace).get(ws_id)
        results.append({
            'workspace_id': ws_id,
            'workspace_name': ws.name if ws else '未知',
            'primary_stage_term_id': stage_id,
            'duplicate_count': cnt,
        })
    return results


def _get_missing_official(db: Session) -> list[dict]:
    """running 状态的工作台，但缺少 official 绑定。"""
    running_ws = db.query(ExternalDocWorkspace).filter(
        ExternalDocWorkspace.status == 'running',
    ).all()
    results = []
    for ws in running_ws:
        has_official = db.query(ExternalDocBinding).filter(
            ExternalDocBinding.workspace_id == ws.id,
            ExternalDocBinding.relation_role == 'official',
            ExternalDocBinding.status == 'active',
        ).first()
        if not has_official:
            results.append({
                'workspace_id': ws.id, 'workspace_name': ws.name,
                'workspace_type': ws.workspace_type,
                'current_stage_term_id': ws.current_stage_term_id,
            })
    return results
