from __future__ import annotations
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session
from ..models_external_docs import (
    ExternalDocWorkspace, ExternalDocBinding, ExternalDocResource, ExternalDocTerm,
)
from ..models import User
from ..route_helper import _dt

_log = logging.getLogger(__name__)


def _serialize_workspace(ws: ExternalDocWorkspace, db: Session | None = None, doc_counts: dict | None = None, stage_labels: dict | None = None, user_names: dict | None = None) -> dict:
    owner_name = ''
    if ws.owner_user_id:
        if user_names and ws.owner_user_id in user_names:
            owner_name = user_names[ws.owner_user_id]
        elif db:
            u = db.query(User).get(ws.owner_user_id)
            owner_name = u.display_name or u.username if u else ''
    stage_label = ''
    if ws.current_stage_term_id:
        if stage_labels and ws.current_stage_term_id in stage_labels:
            stage_label = stage_labels[ws.current_stage_term_id]
        elif db:
            t = db.query(ExternalDocTerm).get(ws.current_stage_term_id)
            stage_label = t.label if t else ''
    count = 0
    if doc_counts and ws.id in doc_counts:
        count = doc_counts[ws.id]
    elif db:
        count = db.query(func.count(ExternalDocBinding.id)).filter(
            ExternalDocBinding.workspace_id == ws.id,
            ExternalDocBinding.status == 'active',
        ).scalar() or 0
    return {
        'id': ws.id, 'name': ws.name, 'workspace_type': ws.workspace_type,
        'status': ws.status, 'owner_user_id': ws.owner_user_id,
        'owner_name': owner_name, 'created_by': ws.created_by,
        'current_stage_term_id': ws.current_stage_term_id,
        'current_stage_label': stage_label,
        'doc_count': count,
        'description': ws.description,
        'biz_line': ws.biz_line, 'client_name': ws.client_name,
        'start_date': ws.start_date, 'end_date': ws.end_date,
        'created_at': _dt(ws.created_at), 'updated_at': _dt(ws.updated_at),
    }


def list_workspaces(db: Session, owner_user_id: int | None = None, workspace_type: str | None = None) -> list[ExternalDocWorkspace]:
    q = db.query(ExternalDocWorkspace)
    if owner_user_id is not None:
        q = q.filter(ExternalDocWorkspace.owner_user_id == owner_user_id)
    if workspace_type:
        q = q.filter(ExternalDocWorkspace.workspace_type == workspace_type)
    return q.order_by(ExternalDocWorkspace.updated_at.desc()).all()


def create_workspace(db: Session, data, user_id: int) -> ExternalDocWorkspace:
    ws = ExternalDocWorkspace(
        name=data.name,
        workspace_type=data.workspace_type,
        biz_line=data.biz_line,
        client_name=data.client_name,
        owner_user_id=data.owner_user_id if data.owner_user_id else user_id,
        description=data.description,
        start_date=data.start_date,
        end_date=data.end_date,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


def update_workspace(db: Session, workspace_id: int, data, user_id: int) -> ExternalDocWorkspace | None:
    ws = db.query(ExternalDocWorkspace).get(workspace_id)
    if not ws:
        return None
    for field in ('name', 'workspace_type', 'status', 'owner_user_id', 'current_stage_term_id', 'description'):
        val = getattr(data, field, None)
        if val is not None:
            setattr(ws, field, val)
    ws.updated_by = user_id
    db.commit()
    db.refresh(ws)
    return ws


def get_workspace(db: Session, workspace_id: int) -> ExternalDocWorkspace | None:
    return db.query(ExternalDocWorkspace).get(workspace_id)


def get_workspace_overview(db: Session, workspace_id: int) -> dict | None:
    ws = db.query(ExternalDocWorkspace).get(workspace_id)
    if not ws:
        return None

    bindings = db.query(ExternalDocBinding).filter(
        ExternalDocBinding.workspace_id == workspace_id,
        ExternalDocBinding.status == 'active',
    ).all()

    # collect resource ids and term ids
    resource_ids = {b.resource_id for b in bindings}
    term_ids = {b.primary_stage_term_id for b in bindings if b.primary_stage_term_id}
    term_ids |= {b.deliverable_term_id for b in bindings if b.deliverable_term_id}

    # bulk fetch resources and terms
    resources_map: dict[int, ExternalDocResource] = {}
    if resource_ids:
        for r in db.query(ExternalDocResource).filter(ExternalDocResource.id.in_(resource_ids)):
            resources_map[r.id] = r

    terms_map: dict[int, ExternalDocTerm] = {}
    if term_ids:
        for t in db.query(ExternalDocTerm).filter(ExternalDocTerm.id.in_(term_ids)):
            terms_map[t.id] = t

    # group bindings by stage then by role
    stages_dict: dict[int | None, dict] = {}
    for b in bindings:
        stage_key = b.primary_stage_term_id
        if stage_key not in stages_dict:
            term_info = None
            if stage_key and stage_key in terms_map:
                t = terms_map[stage_key]
                term_info = {'id': t.id, 'code': t.code, 'label': t.label, 'sort_order': t.sort_order}
            stages_dict[stage_key] = {
                'term': term_info,
                'official_docs': [], 'support_docs': [],
                'candidate_docs': [], 'archive_docs': [],
            }
        stage = stages_dict[stage_key]
        resource = resources_map.get(b.resource_id)
        if not resource:
            continue
        doc_item = {
            **_serialize_resource_simple(resource),
            'binding_id': b.id, 'relation_role': b.relation_role,
            'is_primary': bool(b.is_primary), 'remark': b.remark,
            'deliverable_term_id': b.deliverable_term_id,
            'deliverable_label': terms_map[b.deliverable_term_id].label if b.deliverable_term_id and b.deliverable_term_id in terms_map else '',
            'workspace_name': ws.name,
            'stage_label': terms_map[stage_key].label if stage_key and stage_key in terms_map else '',
        }
        role_key = f'{b.relation_role}_docs'
        if role_key in stage:
            stage[role_key].append(doc_item)
        else:
            stage['support_docs'].append(doc_item)

    stages_list = list(stages_dict.values())
    stages_list.sort(key=lambda s: (s['term']['sort_order'] if s['term'] else 999))

    # recent updates: last 5 bindings by updated_at
    recent = sorted(bindings, key=lambda b: b.updated_at or b.created_at, reverse=True)[:5]
    recent_updates = []
    for b in recent:
        r = resources_map.get(b.resource_id)
        if r:
            recent_updates.append({
                'resource_title': r.title, 'binding_id': b.id,
                'relation_role': b.relation_role,
                'updated_at': _dt(b.updated_at),
            })

    # governance flags
    flags = []
    has_official = any(b.relation_role == 'official' for b in bindings)
    if ws.status == 'running' and not has_official:
        flags.append({'type': 'missing_official_doc', 'label': '当前阶段还没设置“当前在用”文档'})

    return {
        'workspace': _serialize_workspace(ws, db=db),
        'stages': stages_list,
        'recent_updates': recent_updates,
        'governance_flags': flags,
    }


def _serialize_resource_simple(r: ExternalDocResource) -> dict:
    return {
        'id': r.id, 'title': r.title, 'doc_type': r.doc_type,
        'status': r.status, 'verification_status': r.verification_status,
        'open_url': r.open_url, 'summary': r.summary or '',
        'owner_user_id': r.owner_user_id,
        'updated_at': _dt(r.updated_at),
    }


def batch_enrich_workspaces(db: Session, workspaces: list[ExternalDocWorkspace]) -> list[dict]:
    """批量序列化工作台列表，避免 N+1 查询。"""
    ws_ids = [ws.id for ws in workspaces]
    owner_ids = list({ws.owner_user_id for ws in workspaces if ws.owner_user_id})
    stage_ids = list({ws.current_stage_term_id for ws in workspaces if ws.current_stage_term_id})

    user_names: dict[int, str] = {}
    if owner_ids:
        for u in db.query(User).filter(User.id.in_(owner_ids)):
            user_names[u.id] = u.display_name or u.username

    stage_labels: dict[int, str] = {}
    if stage_ids:
        for t in db.query(ExternalDocTerm).filter(ExternalDocTerm.id.in_(stage_ids)):
            stage_labels[t.id] = t.label

    doc_counts: dict[int, int] = {}
    if ws_ids:
        rows = db.query(
            ExternalDocBinding.workspace_id,
            func.count(ExternalDocBinding.id),
        ).filter(
            ExternalDocBinding.workspace_id.in_(ws_ids),
            ExternalDocBinding.status == 'active',
        ).group_by(ExternalDocBinding.workspace_id).all()
        doc_counts = {r[0]: r[1] for r in rows}

    return [
        _serialize_workspace(ws, doc_counts=doc_counts, stage_labels=stage_labels, user_names=user_names)
        for ws in workspaces
    ]


def get_home_current_stage_docs(db: Session, user_id: int, limit: int = 6) -> list[dict]:
    """取用户负责的工作台中，当前阶段的 official 文档。"""
    my_ws = db.query(ExternalDocWorkspace).filter(
        ExternalDocWorkspace.owner_user_id == user_id,
        ExternalDocWorkspace.status == 'running',
        ExternalDocWorkspace.current_stage_term_id.isnot(None),
    ).all()
    if not my_ws:
        return []

    results = []
    for ws in my_ws:
        bindings = db.query(ExternalDocBinding).filter(
            ExternalDocBinding.workspace_id == ws.id,
            ExternalDocBinding.primary_stage_term_id == ws.current_stage_term_id,
            ExternalDocBinding.relation_role == 'official',
            ExternalDocBinding.status == 'active',
        ).limit(3).all()

        stage_term = db.query(ExternalDocTerm).get(ws.current_stage_term_id) if ws.current_stage_term_id else None
        stage_label = stage_term.label if stage_term else ''

        for b in bindings:
            r = db.query(ExternalDocResource).get(b.resource_id)
            if r:
                results.append({
                    'resource_id': r.id, 'title': r.title, 'doc_type': r.doc_type,
                    'open_url': r.open_url,
                    'workspace_id': ws.id, 'workspace_name': ws.name,
                    'stage_label': stage_label,
                    'relation_role': b.relation_role,
                })
                if len(results) >= limit:
                    return results
    return results
