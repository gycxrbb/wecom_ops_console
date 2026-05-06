"""自动积分排行推送服务 — 读取配置、生成排行消息、推送到目标群。"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, date

from zoneinfo import ZoneInfo

from ..database import SessionLocal
from ..models import Group
from ..models_auto_ranking import AutoRankingConfig
from ..services.crm_points_ranking import preview_ranking_batch
from ..services.crm_group_directory import fetch_crm_group_names
from ..services.wecom import WeComService
from ..routers.api import resolve_group_webhook

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


async def execute_auto_ranking(cfg: AutoRankingConfig) -> dict:
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

        webhook = resolve_group_webhook(target_group)
        if not webhook:
            return {'sent': 0, 'skipped': 0, 'error': f'目标群 {target_group.id} 未配置 webhook'}

        for item in items:
            if item.get('skipped'):
                continue
            content_json = item.get('content_json')
            if not content_json:
                continue
            msg_type = item.get('msg_type', 'markdown')
            try:
                await WeComService.send(
                    webhook=webhook,
                    msg_type=msg_type,
                    content=content_json,
                    group_key=str(target_group.id),
                )
                sent += 1
                await asyncio.sleep(1.2)  # 频控安全间隔
            except Exception as exc:
                last_error = str(exc)[:200]
                _log.warning('自动排行 %s: 推送失败 - %s', cfg.name, exc)

        # 推送完成通知
        if sent > 0:
            now_str = datetime.now(_tz).strftime('%Y-%m-%d %H:%M')
            summary = f'【{cfg.name}】推送完成\n时间：{now_str}\n成功：{sent} 条'
            if last_error:
                summary += f'\n失败：{len(items) - sent} 条'
            try:
                await WeComService.send(
                    webhook=webhook,
                    msg_type='text',
                    content={'content': summary},
                    group_key=str(target_group.id),
                )
            except Exception:
                pass
    finally:
        db.close()

    return {'sent': sent, 'skipped': len(items) - sent, 'error': last_error}


def compute_next_runs_for_config(
    push_hour: int,
    push_minute: int,
    skip_weekends: bool,
    skip_dates: list[str],
    count: int = 3,
) -> list[str]:
    """计算未来 count 次有效执行时间（跳过周末/跳过日期）。"""
    from apscheduler.triggers.cron import CronTrigger

    trigger = CronTrigger(minute=str(push_minute), hour=str(push_hour), timezone=_tz)
    cursor = datetime.now(_tz)
    previous = None
    results: list[str] = []
    attempts = 0
    skip_set = set(skip_dates)

    while len(results) < count and attempts < count * 20:
        next_fire = trigger.get_next_fire_time(previous, cursor)
        if not next_fire:
            break
        previous = next_fire
        cursor = next_fire
        attempts += 1
        local_time = next_fire.astimezone(_tz)
        if skip_weekends and local_time.weekday() >= 5:
            continue
        if local_time.strftime('%Y-%m-%d') in skip_set:
            continue
        results.append(local_time.strftime('%Y-%m-%d %H:%M'))

    return results
