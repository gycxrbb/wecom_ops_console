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
from ..services.crm_global_ranking import generate_global_overview

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
    enabled_scenes: list[str] = []
    include_last_week_breakdown: bool = False


class GlobalRankingReq(BaseModel):
    crm_group_ids: list[int]
    top_n: int = 10
    speech_style: str = 'professional'


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

@router.get('/insight-scenes')
def list_insight_scenes(request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    from ..services.crm_speech_templates import TEMPLATES
    scene_labels = {
        'top_leader': '头部领先 (TOP3)', 'top_six': '前六冲刺', 'top_ten': '前十竞争',
        'consistent': '连续活跃', 'surge': '积分暴涨', 'comeback': '强势回归',
        'dropout_recovery': '掉队归队', 'rapid_progress': '进步飞快',
        'reverse_bottom': '后段激励 (绿草莓奖)', 'lurker_remind': '潜水提醒',
        'daily_remind': '每日氛围', 'group_pk': '社群 PK',
    }
    return [
        {'key': key, 'label': scene_labels.get(key, key), 'styles': list(tmpl.keys())}
        for key, tmpl in TEMPLATES.items()
    ]


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
        enabled_scenes=req.enabled_scenes or None,
        include_last_week_breakdown=req.include_last_week_breakdown,
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


@router.post('/preview-global-ranking')
def preview_global_ranking(req: GlobalRankingReq, request: Request, db: Session = Depends(get_db)):
    """生成跨群全局排行消息（20 社群 PK + 跨群 TOP10），发送到指定单个群"""
    get_current_user(request, db)

    crm_group_names = crm_group_directory.fetch_crm_group_names(req.crm_group_ids)
    result = generate_global_overview(
        crm_group_ids=req.crm_group_ids,
        crm_group_names=crm_group_names,
        top_n=req.top_n,
        speech_style=req.speech_style,
    )
    if not result:
        return {'ok': False, 'message': '无有效积分数据'}
    return {'ok': True, 'data': result}


# ── 自动排行推送配置 ──────────────────────────────────────────

class AutoRankingConfigReq(BaseModel):
    id: int | None = None
    name: str
    enabled: bool = True
    crm_group_ids: list[int]
    target_local_group_id: int
    must_scene_keys: list[str] = ['top_leader', 'top_six']
    extra_scene_pool: list[str] = []
    scene_count: int = 3
    speech_style: str = 'professional'
    include_breakdown_on_monday: bool = True
    skip_weekends: bool = False
    skip_dates: list[str] = []
    push_hour: int = 0
    push_minute: int = 0


@router.get('/auto-ranking-configs')
def list_auto_ranking_configs(request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    from ..models_auto_ranking import AutoRankingConfig
    configs = db.query(AutoRankingConfig).order_by(AutoRankingConfig.id.desc()).all()
    return {'items': [_serialize_config(c) for c in configs]}


@router.post('/auto-ranking-configs')
def upsert_auto_ranking_config(req: AutoRankingConfigReq, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user.role != 'admin':
        from fastapi import HTTPException
        raise HTTPException(403, '仅管理员可配置')
    import json
    from ..models_auto_ranking import AutoRankingConfig
    if req.id:
        cfg = db.query(AutoRankingConfig).get(req.id)
        if not cfg:
            from fastapi import HTTPException
            raise HTTPException(404, '配置不存在')
    else:
        cfg = AutoRankingConfig()
        db.add(cfg)
    cfg.name = req.name
    cfg.enabled = 1 if req.enabled else 0
    cfg.crm_group_ids_json = json.dumps(req.crm_group_ids)
    cfg.target_local_group_id = req.target_local_group_id
    cfg.must_scene_keys_json = json.dumps(req.must_scene_keys)
    cfg.extra_scene_pool_json = json.dumps(req.extra_scene_pool)
    cfg.scene_count = req.scene_count
    cfg.speech_style = req.speech_style
    cfg.include_breakdown_on_monday = 1 if req.include_breakdown_on_monday else 0
    cfg.skip_weekends = 1 if req.skip_weekends else 0
    cfg.skip_dates_json = json.dumps(req.skip_dates)
    cfg.push_hour = req.push_hour
    cfg.push_minute = req.push_minute
    db.commit()
    db.refresh(cfg)
    # Re-register cron job to pick up changes
    from ..services.scheduler_service import schedule_service
    schedule_service._register_auto_ranking_job()
    return _serialize_config(cfg)


@router.delete('/auto-ranking-configs/{config_id}')
def delete_auto_ranking_config(config_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user.role != 'admin':
        from fastapi import HTTPException
        raise HTTPException(403, '仅管理员可操作')
    from ..models_auto_ranking import AutoRankingConfig
    cfg = db.query(AutoRankingConfig).get(config_id)
    if cfg:
        db.delete(cfg)
        db.commit()
    return {'ok': True}


def _serialize_config(cfg):
    import json
    return {
        'id': cfg.id,
        'name': cfg.name,
        'enabled': bool(cfg.enabled),
        'crm_group_ids': json.loads(cfg.crm_group_ids_json or '[]'),
        'target_local_group_id': cfg.target_local_group_id,
        'must_scene_keys': json.loads(cfg.must_scene_keys_json or '[]'),
        'extra_scene_pool': json.loads(cfg.extra_scene_pool_json or '[]'),
        'scene_count': cfg.scene_count,
        'speech_style': cfg.speech_style,
        'include_breakdown_on_monday': bool(cfg.include_breakdown_on_monday),
        'skip_weekends': bool(cfg.skip_weekends),
        'skip_dates': json.loads(cfg.skip_dates_json or '[]'),
        'push_hour': cfg.push_hour or 0,
        'push_minute': cfg.push_minute or 0,
        'last_run_at': str(cfg.last_run_at) if cfg.last_run_at else None,
        'last_error': cfg.last_error or '',
    }
