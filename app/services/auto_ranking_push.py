"""自动积分排行推送服务 — 读取配置、生成排行消息、推送到目标群。"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time as _time
from datetime import datetime, date, timedelta

from zoneinfo import ZoneInfo

from ..database import SessionLocal
from ..models import Group, Message, MessageLog
from ..models_auto_ranking import AutoRankingConfig
from ..services.crm_points_ranking import preview_ranking_batch
from ..services.crm_group_directory import fetch_crm_group_names
from ..services.wecom import WeComService
from ..routers.api import resolve_group_webhook
from .auto_ranking_sender import create_send_record, mark_send_success, mark_send_failure

_log = logging.getLogger(__name__)
_tz = ZoneInfo('Asia/Shanghai')

_COOLDOWN_SECONDS = 300  # 同一配置 5 分钟内不重复执行
_MAX_RETRY_ROUNDS = 2    # 失败条目最多重试 2 轮
_PER_MSG_RETRIES = 3     # 单条消息最多重试 3 次
_PER_MSG_DELAY = 2.0     # 普通重试间隔
_RATE_LIMIT_DELAY = 30.0 # 限流重试间隔


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
    """执行一次自动排行推送。返回 {sent, skipped, failed, error}。"""
    now = datetime.now(_tz)

    # 计算目标推送时间（cron 提前 1 分钟触发，需处理跨午夜场景）
    push_hour = cfg.push_hour or 0
    push_minute = cfg.push_minute or 0
    target_time = now.replace(hour=push_hour, minute=push_minute, second=0, microsecond=0)
    if target_time <= now - timedelta(minutes=1):
        target_time += timedelta(days=1)

    # 用目标推送时间的日期做判断（解决 00:00 推送时 cron 23:59 触发的日期偏差）
    today = target_time.date()

    # 冷却期检查：距上次执行不足 5 分钟则跳过，防止 misfire 重复触发
    if cfg.last_run_at:
        elapsed = (datetime.now(_tz) - cfg.last_run_at.replace(tzinfo=_tz)).total_seconds()
        if elapsed < _COOLDOWN_SECONDS:
            _log.info('自动排行 %s: 跳过，距上次执行仅 %.0fs (< %ds)', cfg.name, elapsed, _COOLDOWN_SECONDS)
            return {'sent': 0, 'skipped': 0, 'error': '', 'cooldown': True}

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
            rank_metric=cfg.rank_metric or 'current_points',
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

    # 预生成完成，等待至准点再发送（cron 提前 1 分钟触发）
    wait_seconds = (target_time - datetime.now(_tz)).total_seconds()
    if 0 < wait_seconds < 120:
        _log.info('自动排行 %s: 预生成完成，等待 %.1fs 至准点 %02d:%02d 推送', cfg.name, wait_seconds, push_hour, push_minute)
        await asyncio.sleep(wait_seconds)

    # 发送
    db = SessionLocal()
    sent = 0
    failed = 0
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

        pending_items = [i for i in items if not i.get('skipped') and i.get('content_json')]
        total_count = len(pending_items)
        send_start = _time.time()

        async def _send_batch(batch_items: list[dict], retry_round: int = 0) -> tuple[int, int, str, list[dict]]:
            """发送一批消息，返回 (sent, failed, last_error, failed_items)。"""
            _sent, _failed, _err = 0, 0, ''
            _failed_items: list[dict] = []
            for item in batch_items:
                msg_record = create_send_record(
                    db=db, group_id=target_group.id,
                    msg_type=item.get('msg_type', 'markdown'),
                    content_json=item['content_json'], config_id=cfg.id,
                    retry_round=retry_round,
                )
                last_exc: Exception | None = None
                for attempt in range(1, _PER_MSG_RETRIES + 1):
                    try:
                        payload, response = await WeComService.send(
                            webhook=webhook, msg_type=item.get('msg_type', 'markdown'),
                            content=item['content_json'], group_key=str(target_group.id),
                        )
                        _sent += 1
                        mark_send_success(db, msg_record, payload=payload, response=response)
                        last_exc = None
                        break
                    except Exception as exc:
                        last_exc = exc
                        error_str = str(exc).lower()
                        if '45009' in error_str or 'freq' in error_str or '限流' in error_str:
                            _log.warning('自动排行 %s: 限流，等待 %.0fs (attempt %d/%d)',
                                         cfg.name, _RATE_LIMIT_DELAY, attempt, _PER_MSG_RETRIES)
                            await asyncio.sleep(_RATE_LIMIT_DELAY)
                        elif attempt < _PER_MSG_RETRIES:
                            _log.warning('自动排行 %s: 发送失败，%.1fs 后重试 (attempt %d/%d): %s',
                                         cfg.name, _PER_MSG_DELAY, attempt, _PER_MSG_RETRIES, exc)
                            await asyncio.sleep(_PER_MSG_DELAY)
                if last_exc is not None:
                    _failed += 1
                    _err = str(last_exc)[:200]
                    _failed_items.append(item)
                    _log.warning('自动排行 %s: 推送失败（已重试 %d 次）- %s',
                                 cfg.name, _PER_MSG_RETRIES, last_exc)
                    db.rollback()
                    mark_send_failure(db, msg_record, str(last_exc)[:255], payload=None)
                else:
                    await asyncio.sleep(1.2)
            return _sent, _failed, _err, _failed_items

        # ── 首轮发送 ──
        sent, failed, last_error, failed_items = await _send_batch(pending_items)

        # ── 容错重试：只重发失败条目 ──
        retry_round = 0
        while failed > 0 and retry_round < _MAX_RETRY_ROUNDS:
            retry_round += 1
            _log.info('自动排行 %s: 第 %d 轮重试（%d 条失败），等待 61s 释放限流窗口',
                      cfg.name, retry_round, len(failed_items))
            await asyncio.sleep(61)

            # 重试通知
            try:
                await WeComService.send(webhook, 'text', {
                    'content': f'⚠️ 积分排行推送存在 {len(failed_items)} 条失败，正在第 {retry_round} 次重试'
                }, group_key=f'auto-ranking-retry-{cfg.id}')
            except Exception as exc:
                _log.warning('自动排行 %s: 重试通知发送失败: %s', cfg.name, exc)

            # 只重发失败条目
            r_sent, r_failed, r_err, failed_items = await _send_batch(failed_items, retry_round=retry_round)
            sent += r_sent
            failed = r_failed
            if r_err:
                last_error = r_err
            _log.info('自动排行 %s: 第 %d 轮重试完成，本轮成功 %d 仍失败 %d',
                      cfg.name, retry_round, r_sent, r_failed)

        # ── 推送完成通知 ──
        if sent > 0:
            elapsed = _time.time() - send_start
            from .batch_summary import _build_summary_markdown
            md = _build_summary_markdown(
                title=cfg.name, success_count=sent, total_count=total_count,
                failed_count=failed, group_names=[target_group.name],
                elapsed_sec=elapsed,
            )
            try:
                await WeComService.send(
                    webhook=webhook, msg_type='markdown',
                    content={'content': md}, group_key=str(target_group.id),
                )
            except Exception as exc:
                _log.warning('自动排行 %s: 推送完成通知发送失败: %s', cfg.name, exc)
    finally:
        db.close()

    return {'sent': sent, 'skipped': len(items) - sent - failed, 'failed': failed, 'error': last_error}


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
