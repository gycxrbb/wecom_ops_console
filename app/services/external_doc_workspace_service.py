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


def delete_workspace(db: Session, workspace_id: int) -> bool:
    ws = db.query(ExternalDocWorkspace).get(workspace_id)
    if not ws:
        return False
    # deactivate all bindings under this workspace
    db.query(ExternalDocBinding).filter(
        ExternalDocBinding.workspace_id == workspace_id,
        ExternalDocBinding.status == 'active',
    ).update({'status': 'inactive'})
    db.delete(ws)
    db.commit()
    return True


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

    # batch fetch owner names + updated_by names
    from ..models import User
    user_ids = {r.owner_user_id for r in resources_map.values() if r.owner_user_id}
    user_ids |= {b.updated_by for b in bindings if b.updated_by}
    user_names: dict[int, str] = {}
    if user_ids:
        for u in db.query(User).filter(User.id.in_(user_ids)):
            user_names[u.id] = u.display_name or u.username

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
            'owner_name': user_names.get(resource.owner_user_id, '') if resource.owner_user_id else '',
            'updated_by_name': user_names.get(b.updated_by, '') if b.updated_by else '',
            'updated_at': _dt(b.updated_at),
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
                'owner_name': user_names.get(r.owner_user_id, '') if r.owner_user_id else '',
                'updated_by_name': user_names.get(b.updated_by, '') if b.updated_by else '',
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
    from ..models import User

    my_ws = db.query(ExternalDocWorkspace).filter(
        ExternalDocWorkspace.owner_user_id == user_id,
        ExternalDocWorkspace.current_stage_term_id.isnot(None),
    ).all()
    if not my_ws:
        return []

    # batch collect all binding ids and resource ids
    all_bindings = []
    ws_map: dict[int, ExternalDocWorkspace] = {}
    for ws in my_ws:
        ws_map[ws.id] = ws
        bindings = db.query(ExternalDocBinding).filter(
            ExternalDocBinding.workspace_id == ws.id,
            ExternalDocBinding.primary_stage_term_id == ws.current_stage_term_id,
            ExternalDocBinding.relation_role == 'official',
            ExternalDocBinding.status == 'active',
        ).limit(3).all()
        all_bindings.extend(bindings)

    if not all_bindings:
        return []

    # batch fetch resources
    resource_ids = {b.resource_id for b in all_bindings}
    resources_map: dict[int, ExternalDocResource] = {}
    for r in db.query(ExternalDocResource).filter(ExternalDocResource.id.in_(resource_ids)):
        resources_map[r.id] = r

    # batch fetch owner names + updated_by names
    from ..models import User
    user_ids = {r.owner_user_id for r in resources_map.values() if r.owner_user_id}
    user_ids |= {b.updated_by for b in all_bindings if b.updated_by}
    user_names: dict[int, str] = {}
    if user_ids:
        for u in db.query(User).filter(User.id.in_(user_ids)):
            user_names[u.id] = u.display_name or u.username

    # batch fetch stage labels
    stage_ids = {ws.current_stage_term_id for ws in my_ws if ws.current_stage_term_id}
    stage_labels: dict[int, str] = {}
    if stage_ids:
        for t in db.query(ExternalDocTerm).filter(ExternalDocTerm.id.in_(stage_ids)):
            stage_labels[t.id] = t.label

    results = []
    for b in all_bindings:
        r = resources_map.get(b.resource_id)
        if not r:
            continue
        ws = ws_map.get(b.workspace_id)
        stage_label = stage_labels.get(ws.current_stage_term_id, '') if ws and ws.current_stage_term_id else ''
        results.append({
            'resource_id': r.id, 'title': r.title, 'doc_type': r.doc_type,
            'open_url': r.open_url, 'verification_status': r.verification_status,
            'summary': r.summary or '',
            'workspace_id': b.workspace_id, 'workspace_name': ws.name if ws else '',
            'stage_label': stage_label,
            'relation_role': b.relation_role,
            'is_primary': bool(b.is_primary), 'remark': b.remark or '',
            'owner_name': user_names.get(r.owner_user_id, '') if r.owner_user_id else '',
            'updated_by_name': user_names.get(b.updated_by, '') if b.updated_by else '',
            'updated_at': _dt(b.updated_at),
        })
        if len(results) >= limit:
            break
    return results
