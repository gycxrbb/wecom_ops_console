"""自动积分排行推送服务 — 读取配置、生成排行消息、推送到目标群。"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from datetime import datetime, date

from zoneinfo import ZoneInfo

from ..database import SessionLocal
from ..models import Group
from ..models_auto_ranking import AutoRankingConfig
from ..services.crm_points_ranking import preview_ranking_batch
from ..services.crm_group_directory import fetch_crm_group_names
from ..services.wecom import WeComService

_log = logging.getLogger(__name__)
_tz = ZoneInfo('Asia/Shanghai')


def _load_json(text: str, default=None):
    try:
        return json.loads(text) if text else default
    except (json.JSONDecodeError, TypeError):
        return default


def _select_scenes(must_keys: list[str], pool: list[str], count: int) -> list[str]:
    """从 must_keys 取全部 + 从 pool 随机补齐到 count 个。"""
    scenes = list(must_keys)
    remaining = [k for k in pool if k not in scenes]
    need = max(0, count - len(scenes))
    if remaining and need > 0:
        scenes.extend(random.sample(remaining, min(need, len(remaining))))
    return scenes


def _should_skip(cfg: AutoRankingConfig, today: date) -> bool:
    if cfg.skip_weekends and today.weekday() >= 5:
        return True
    skip_dates = _load_json(cfg.skip_dates_json, [])
    if today.isoformat() in skip_dates:
        return True
    return False


def execute_auto_ranking(cfg: AutoRankingConfig) -> dict:
    """执行一次自动排行推送。返回 {sent, skipped, error}。"""
    now = datetime.now(_tz)
    today = now.date()

    if _should_skip(cfg, today):
        _log.info('自动排行 %s: 今日跳过 (weekend/skip_date)', cfg.name)
        return {'sent': 0, 'skipped': 1, 'error': ''}

    crm_group_ids = _load_json(cfg.crm_group_ids_json, [])
    if not crm_group_ids:
        return {'sent': 0, 'skipped': 0, 'error': '无CRM群配置'}

    # 选场景
    must_keys = _load_json(cfg.must_scene_keys_json, ['top_leader', 'top_six'])
    pool = _load_json(cfg.extra_scene_pool_json, [])
    scenes = _select_scenes(must_keys, pool, cfg.scene_count or 3)

    # 周一是否开启 breakdown
    is_monday = today.weekday() == 0
    include_breakdown = bool(cfg.include_breakdown_on_monday) and is_monday

    _log.info(
        '自动排行 %s: groups=%d scenes=%s breakdown=%s',
        cfg.name, len(crm_group_ids), scenes, include_breakdown,
    )

    # 生成排行消息
    try:
        crm_group_names = fetch_crm_group_names(crm_group_ids)
        result = preview_ranking_batch(
            crm_group_ids=crm_group_ids,
            crm_group_names=crm_group_names,
            top_n=50,
            rank_metric='current_points',
            include_week_month=True,
            speech_style=cfg.speech_style or 'professional',
            skip_empty_groups=True,
            enabled_scenes=scenes or None,
            include_last_week_breakdown=include_breakdown,
        )
    except Exception as exc:
        _log.exception('自动排行 %s: 生成消息失败', cfg.name)
        return {'sent': 0, 'skipped': 0, 'error': str(exc)}

    items = result.get('items', [])
    if not items:
        return {'sent': 0, 'skipped': 0, 'error': '无有效排行消息'}

    # 发送
    db = SessionLocal()
    sent = 0
    last_error = ''
    try:
        target_group = db.query(Group).filter(
            Group.id == cfg.target_local_group_id, Group.enabled == 1
        ).first()
        if not target_group:
            return {'sent': 0, 'skipped': 0, 'error': f'目标群 {cfg.target_local_group_id} 不存在或已禁用'}

        for item in items:
            if item.get('skipped'):
                continue
            content_json = item.get('content_json')
            if not content_json:
                continue
            msg_type = item.get('msg_type', 'markdown')
            try:
                WeComService.send(
                    webhook=target_group.webhook,
                    msg_type=msg_type,
                    content=content_json,
                    group_key=str(target_group.id),
                )
                sent += 1
                time.sleep(1.2)  # 频控安全间隔
            except Exception as exc:
                last_error = str(exc)[:200]
                _log.warning('自动排行 %s: 推送失败 - %s', cfg.name, exc)
    finally:
        db.close()

    return {'sent': sent, 'skipped': len(items) - sent, 'error': last_error}


def run_all_auto_rankings() -> list[dict]:
    """读取所有 enabled 配置并执行。"""
    db = SessionLocal()
    try:
        configs = db.query(AutoRankingConfig).filter(AutoRankingConfig.enabled == 1).all()
    finally:
        db.close()

    results = []
    for cfg in configs:
        now = datetime.now(_tz)
        result = execute_auto_ranking(cfg)

        # 更新执行状态
        db2 = SessionLocal()
        try:
            c = db2.query(AutoRankingConfig).get(cfg.id)
            if c:
                c.last_run_at = now
                c.last_error = result.get('error', '')
                db2.commit()
        finally:
            db2.close()

        results.append({'id': cfg.id, 'name': cfg.name, **result})

    return results
