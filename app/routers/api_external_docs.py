from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import get_current_user, require_permission
from ..route_helper import UnifiedResponseRoute, _dt
from ..models_external_docs import ExternalDocTerm
from ..schemas.external_docs import (
    ResolveLinkRequest, ResourceCreate, ResourceUpdate,
    BindingCreate, BindingUpdate, QuickAddRequest,
    WorkspaceCreate, WorkspaceUpdate, OpenRequest,
)
from ..services import external_doc_service, external_doc_workspace_service, external_doc_governance_service

router = APIRouter(
    prefix='/api/v1/external-docs',
    tags=['external-docs'],
    route_class=UnifiedResponseRoute,
)


def _s(r):
    return external_doc_service._serialize_resource(r)


def _sb(b):
    return external_doc_service._serialize_binding(b)


def _sw(ws, db=None):
    return external_doc_workspace_service._serialize_workspace(ws, db=db)


# ── Resolve Link ──

@router.post('/resources/resolve-link')
def resolve_link(body: ResolveLinkRequest, request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    return external_doc_service.resolve_link(body.url)


# ── Quick Add ──

@router.post('/quick-add')
def quick_add(body: QuickAddRequest, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_permission(user, 'sop')
    try:
        return external_doc_service.quick_add(db, body, user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Resources ──

@router.get('/resources')
def list_resources(request: Request, db: Session = Depends(get_db), keyword: str | None = None, status: str | None = None):
    get_current_user(request, db)
    items = external_doc_service.list_resources(db, keyword=keyword, status=status)
    return [_s(r) for r in items]


@router.get('/resources/recent-opened')
def list_recent_opened_resources(request: Request, db: Session = Depends(get_db), limit: int = 8):
    user = get_current_user(request, db)
    return external_doc_service.list_recent_opened_resources(db, user.id, limit=limit)


@router.get('/home/summary')
def home_summary(request: Request, db: Session = Depends(get_db)):
    """首页聚合数据：工作台列表、最近打开、当前阶段文档、治理摘要。"""
    user = get_current_user(request, db)
    workspaces = external_doc_workspace_service.list_workspaces(db)
    ws_data = external_doc_workspace_service.batch_enrich_workspaces(db, workspaces)
    uid = user.id
    my_ws = [w for w in ws_data if w['workspace_type'] not in ('template_hub', 'inbox')
             and (w.get('owner_user_id') == uid or w.get('created_by') == uid)]
    recent = external_doc_service.list_recent_opened_resources(db, user.id, limit=8)
    current_stage = external_doc_workspace_service.get_home_current_stage_docs(db, user.id, limit=6)
    gov = external_doc_governance_service.get_governance_queue(db)
    return {
        'my_workspaces': my_ws,
        'recent_docs': recent,
        'current_stage_docs': current_stage,
        'governance': gov,
    }


@router.post('/resources')
def create_resource(body: ResourceCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_permission(user, 'sop')
    r = external_doc_service.create_resource(db, body, user.id)
    return _s(r)


@router.get('/resources/{resource_id}')
def get_resource(resource_id: int, request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    r = external_doc_service.get_resource(db, resource_id)
    if not r:
        raise HTTPException(404, '资源不存在')
    return _s(r)


@router.put('/resources/{resource_id}')
def update_resource(resource_id: int, body: ResourceUpdate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_permission(user, 'sop')
    r = external_doc_service.update_resource(db, resource_id, body, user.id)
    if not r:
        raise HTTPException(404, '资源不存在')
    return _s(r)


@router.post('/resources/{resource_id}/open')
def open_resource(resource_id: int, body: OpenRequest, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    result = external_doc_service.record_open(db, resource_id, user.id, body.workspace_id, body.client_type)
    if not result:
        raise HTTPException(404, '资源不存在')
    return result


# ── Bindings ──

@router.get('/bindings/flat')
def list_bindings_flat(
    request: Request, db: Session = Depends(get_db),
    workspace_id: int | None = None, stage_term_id: int | None = None,
    relation_role: str | None = None, keyword: str | None = None,
    page: int = 1, page_size: int = 20,
):
    get_current_user(request, db)
    return external_doc_service.list_bindings_flat(
        db, workspace_id=workspace_id, stage_term_id=stage_term_id,
        relation_role=relation_role, keyword=keyword,
        page=page, page_size=page_size,
    )


@router.post('/bindings')
def create_binding(body: BindingCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_permission(user, 'sop')
    try:
        b = external_doc_service.create_binding(db, body, user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _sb(b)


@router.put('/bindings/{binding_id}')
def update_binding(binding_id: int, body: BindingUpdate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_permission(user, 'sop')
    b = external_doc_service.update_binding(db, binding_id, body, user.id)
    if not b:
        raise HTTPException(404, '绑定不存在')
    return _sb(b)


@router.delete('/bindings/{binding_id}')
def delete_binding(binding_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_permission(user, 'sop')
    if not external_doc_service.delete_binding(db, binding_id):
        raise HTTPException(404, '绑定不存在')
    return {'ok': True}


# ── Workspaces ──

@router.get('/workspaces')
def list_workspaces(request: Request, db: Session = Depends(get_db), workspace_type: str | None = None):
    get_current_user(request, db)
    user = get_current_user(request, db)
    items = external_doc_workspace_service.list_workspaces(db, owner_user_id=user.id, workspace_type=workspace_type)
    all_items = external_doc_workspace_service.list_workspaces(db, workspace_type=workspace_type)
    # merge: user's workspaces first, then others
    user_ws_ids = {ws.id for ws in items}
    combined = items + [ws for ws in all_items if ws.id not in user_ws_ids]
    return external_doc_workspace_service.batch_enrich_workspaces(db, combined)


@router.post('/workspaces')
def create_workspace(body: WorkspaceCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_permission(user, 'sop')
    ws = external_doc_workspace_service.create_workspace(db, body, user.id)
    return _sw(ws, db)


@router.get('/workspaces/{workspace_id}')
def get_workspace(workspace_id: int, request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    ws = external_doc_workspace_service.get_workspace(db, workspace_id)
    if not ws:
        raise HTTPException(404, '工作台不存在')
    return _sw(ws, db)


@router.put('/workspaces/{workspace_id}')
def update_workspace(workspace_id: int, body: WorkspaceUpdate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_permission(user, 'sop')
    ws = external_doc_workspace_service.update_workspace(db, workspace_id, body, user.id)
    if not ws:
        raise HTTPException(404, '工作台不存在')
    return _sw(ws, db)


@router.delete('/workspaces/{workspace_id}')
def delete_workspace(workspace_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_permission(user, 'sop')
    if not external_doc_workspace_service.delete_workspace(db, workspace_id):
        raise HTTPException(404, '工作台不存在')
    return {'ok': True}


@router.get('/workspaces/{workspace_id}/overview')
def workspace_overview(workspace_id: int, request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    result = external_doc_workspace_service.get_workspace_overview(db, workspace_id)
    if not result:
        raise HTTPException(404, '工作台不存在')
    return result


# ── Terms ──

@router.get('/terms')
def list_terms(request: Request, db: Session = Depends(get_db), dimension: str | None = None):
    get_current_user(request, db)
    q = db.query(ExternalDocTerm).filter(ExternalDocTerm.is_active == 1)
    if dimension:
        q = q.filter(ExternalDocTerm.dimension == dimension)
    terms = q.order_by(ExternalDocTerm.sort_order, ExternalDocTerm.id).all()
    return [
        {'id': t.id, 'dimension': t.dimension, 'code': t.code, 'label': t.label,
         'scope_type': t.scope_type, 'sort_order': t.sort_order, 'is_active': bool(t.is_active)}
        for t in terms
    ]


# ── Governance ──

@router.get('/governance/queue')
def governance_queue(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_permission(user, 'sop')
    return external_doc_governance_service.get_governance_queue(db)
