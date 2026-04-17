"""CRM 积分排行 API — 发送映射管理 + 排行消息预览/生成"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..route_helper import UnifiedResponseRoute
from ..security import get_current_user
from ..services import crm_group_bindings, crm_points_ranking, crm_group_directory

router = APIRouter(prefix='/api/v1/crm-points', tags=['crm-points'], route_class=UnifiedResponseRoute)
_log = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────

class BindingUpsertReq(BaseModel):
    crm_group_id: int
    crm_group_name: str = ''
    local_group_id: int
    remark: str = ''


class RankingPreviewReq(BaseModel):
    crm_group_ids: list[int]
    top_n: int = 50
    rank_metric: str = 'current_points'
    speech_style: str = 'professional'
    include_week_month: bool = True
    skip_empty_groups: bool = True


# ── 发送映射 CRUD ────────────────────────────────────────────

@router.get('/bindings')
def list_bindings(request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    return {'bindings': crm_group_bindings.list_bindings(db)}


@router.get('/local-groups')
def list_local_groups(request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    return {'groups': crm_group_bindings.get_all_local_groups(db)}


@router.post('/bindings')
def upsert_binding(req: BindingUpsertReq, request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    return crm_group_bindings.upsert_binding(
        db, req.crm_group_id, req.crm_group_name, req.local_group_id, req.remark
    )


@router.delete('/bindings/{binding_id}')
def delete_binding(binding_id: int, request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    ok = crm_group_bindings.delete_binding(db, binding_id)
    return {'ok': ok}


@router.put('/bindings/{binding_id}/toggle')
def toggle_binding(binding_id: int, request: Request, enabled: bool = Query(True), db: Session = Depends(get_db)):
    get_current_user(request, db)
    ok = crm_group_bindings.toggle_binding(db, binding_id, enabled)
    return {'ok': ok}


class BatchBindReq(BaseModel):
    crm_group_ids: list[int]
    crm_group_names: dict[int, str] = {}  # {crm_group_id: name}
    local_group_id: int


@router.post('/batch-bind')
def batch_bind(req: BatchBindReq, request: Request, db: Session = Depends(get_db)):
    """一键绑定：将多个 CRM 群统一绑定到一个本地发送群"""
    get_current_user(request, db)
    results = crm_group_bindings.batch_bind(
        db, req.crm_group_ids, req.crm_group_names, req.local_group_id,
    )
    return results


# ── 积分排行预览 ─────────────────────────────────────────────

@router.post('/preview-ranking')
def preview_ranking(req: RankingPreviewReq, request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    started_at = time.perf_counter()
    _log.info(
        'CRM 积分排行预览开始: groups=%d top_n=%d rank_metric=%s include_week_month=%s speech_style=%s skip_empty_groups=%s',
        len(req.crm_group_ids),
        req.top_n,
        req.rank_metric,
        req.include_week_month,
        req.speech_style,
        req.skip_empty_groups,
    )

    group_name_lookup_started_at = time.perf_counter()
    crm_group_names = crm_group_directory.fetch_crm_group_names(req.crm_group_ids)
    group_name_lookup_ms = int((time.perf_counter() - group_name_lookup_started_at) * 1000)

    preview_result = crm_points_ranking.preview_ranking_batch(
        crm_group_ids=req.crm_group_ids,
        crm_group_names=crm_group_names,
        top_n=req.top_n,
        rank_metric=req.rank_metric,
        include_week_month=req.include_week_month,
        speech_style=req.speech_style,
        skip_empty_groups=req.skip_empty_groups,
    )
    items = preview_result.get('items', [])
    diagnostics = dict(preview_result.get('diagnostics') or {})
    diagnostics['group_name_lookup_ms'] = group_name_lookup_ms

    binding_lookup_started_at = time.perf_counter()
    bindings_map = crm_group_bindings.get_bindings_map_by_crm_group_ids(db, req.crm_group_ids)
    for item in items:
        gid = item.get('crm_group_id')
        if gid:
            binding = bindings_map.get(gid)
            if binding and binding.get('enabled'):
                item['local_group_id'] = binding['local_group_id']
                item['local_group_name'] = binding['local_group_name']
                item['has_binding'] = True
    diagnostics['binding_lookup_ms'] = int((time.perf_counter() - binding_lookup_started_at) * 1000)
    diagnostics['total_ms'] = int((time.perf_counter() - started_at) * 1000)

    _log.info(
        'CRM 积分排行预览完成: groups=%d items=%d skipped=%d group_name_lookup_ms=%d binding_lookup_ms=%d total_ms=%d',
        len(req.crm_group_ids),
        len(items),
        diagnostics.get('skipped_group_count', 0),
        diagnostics['group_name_lookup_ms'],
        diagnostics['binding_lookup_ms'],
        diagnostics['total_ms'],
    )
    if diagnostics['total_ms'] >= 15000:
        _log.warning(
            'CRM 积分排行预览较慢: total_ms=%d slow_groups=%s',
            diagnostics['total_ms'],
            diagnostics.get('slow_groups', []),
        )

    return {'items': items, 'diagnostics': diagnostics}
