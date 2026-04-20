"""积分排行消息生成服务

按 CRM 群组生成 markdown 格式的积分排行消息，供发送中心批量推送。
"""
from __future__ import annotations

import logging
import time
from typing import Any

from .crm_group_directory import fetch_crm_group_members, fetch_crm_group_members_bulk, crm_group_enabled
from .crm_points_insights import detect_individual_insights_bulk
from .crm_speech_templates import build_insight_speech
from .crm_1v1_actions import generate_1v1_actions

_log = logging.getLogger(__name__)

# 奖牌 emoji
_MEDALS = {1: '🥇', 2: '🥈', 3: '🥉'}
_INSIGHT_MEMBER_LIMIT = 20

# 话术风格模板
_SPEECH_TEMPLATES = {
    'professional': '继续加油！坚持就是胜利！💪',
    'encouraging': '每一分都是努力的见证，继续前行！🌟',
    'competitive': '排名持续更新中，谁能笑到最后？🔥',
}


def _format_rank_line(rank: int, name: str, points: float, week_pts: float = 0) -> str:
    """格式化单行排行"""
    medal = _MEDALS.get(rank)
    prefix = medal if medal else f'{rank}.'
    week_info = f'（本周+{week_pts:.0f}）' if week_pts > 0 else ''
    return f'{prefix} {name} {points:.0f}分{week_info}'


def _build_skipped_item(crm_group_id: int, crm_group_name: str, reason: str) -> dict[str, Any]:
    return {
        'crm_group_id': crm_group_id,
        'crm_group_name': crm_group_name,
        'skipped': True,
        'skip_reason': reason,
        'msg_type': 'markdown',
        'content_json': None,
        'member_count': 0,
        'local_group_id': None,
        'local_group_name': None,
        'has_binding': False,
    }


def _generate_group_ranking_message_from_members(
    crm_group_id: int,
    crm_group_name: str,
    members: list[dict[str, Any]],
    top_n: int = 50,
    rank_metric: str = 'current_points',
    include_week_month: bool = True,
    speech_style: str = 'professional',
    insights: list[dict] | None = None,
) -> dict[str, Any] | None:
    if not members:
        return None

    positive_members = [member for member in members if float(member.get('current_points', 0) or 0) > 0]
    if not positive_members:
        return None

    positive_members.sort(key=lambda member: float(member.get(rank_metric, 0) or 0), reverse=True)
    ranked_members = positive_members[:top_n]

    group_current = sum(float(member.get('current_points', 0) or 0) for member in positive_members)
    group_week = sum(float(member.get('week_points', 0) or 0) for member in positive_members)
    group_month = sum(float(member.get('month_points', 0) or 0) for member in positive_members)

    lines = [f'📊 {crm_group_name}']
    if include_week_month:
        lines.append(f'群总分: {group_current:.0f}（本周+{group_week:.0f}，本月+{group_month:.0f}）')
    else:
        lines.append(f'群总分: {group_current:.0f}')

    lines.append('')
    lines.append('🏆 成员排行榜:')

    for index, member in enumerate(ranked_members, start=1):
        lines.append(
            _format_rank_line(
                index,
                member.get('name') or f'未命名成员#{member["id"]}',
                float(member.get('current_points', 0) or 0),
                float(member.get('week_points', 0) or 0),
            )
        )

    speech = _SPEECH_TEMPLATES.get(speech_style, _SPEECH_TEMPLATES['professional'])
    if insights is None:
        insight_candidates = ranked_members[:_INSIGHT_MEMBER_LIMIT]
        from .crm_points_insights import detect_individual_insights
        insights = detect_individual_insights(ranked_members, insight_candidates)
    insight_speeches = []
    for insight in insights[:5]:
        insight_speeches.extend(build_insight_speech(insight, speech_style, max_speeches=1))

    if insight_speeches:
        lines.append('')
        lines.append('💡 亮点:')
        for speech_line in insight_speeches:
            lines.append(f'• {speech_line}')

    lines.append('')
    lines.append(speech)

    return {
        'crm_group_id': crm_group_id,
        'crm_group_name': crm_group_name,
        'msg_type': 'markdown',
        'content_json': {'content': '\n'.join(lines)},
        'member_count': len(ranked_members),
        'group_current_points': group_current,
        'group_week_points': group_week,
        'group_month_points': group_month,
        'insights': insights,
        'insight_speeches': insight_speeches,
    }


def generate_group_ranking_message(
    crm_group_id: int,
    crm_group_name: str,
    top_n: int = 50,
    rank_metric: str = 'current_points',
    include_week_month: bool = True,
    speech_style: str = 'professional',
) -> dict[str, Any] | None:
    """为单个 CRM 群组生成积分排行消息

    Returns:
        成功返回消息字典，无正积分成员时返回 None
    """
    result = fetch_crm_group_members(crm_group_id)
    return _generate_group_ranking_message_from_members(
        crm_group_id=crm_group_id,
        crm_group_name=crm_group_name,
        members=result.get('members', []),
        top_n=top_n,
        rank_metric=rank_metric,
        include_week_month=include_week_month,
        speech_style=speech_style,
    )


def preview_ranking_batch(
    crm_group_ids: list[int],
    crm_group_names: dict[int, str],
    top_n: int = 50,
    rank_metric: str = 'current_points',
    include_week_month: bool = True,
    speech_style: str = 'professional',
    skip_empty_groups: bool = True,
    enabled_scenes: list[str] | None = None,
) -> dict[str, Any]:
    """批量预览积分排行消息。

    这里优先使用批量群成员查询，避免逐群调用带来的 N+1 CRM 查询开销。
    """
    started_at = time.perf_counter()
    if not crm_group_enabled():
        return {
            'items': [],
            'diagnostics': {
                'requested_group_count': len(crm_group_ids),
                'returned_item_count': 0,
                'skipped_group_count': 0,
                'load_members_ms': 0,
                'generate_items_ms': 0,
                'total_ms': 0,
                'slow_groups': [],
            },
        }

    items = []
    load_members_started_at = time.perf_counter()
    group_members_map = fetch_crm_group_members_bulk(crm_group_ids)
    load_members_ms = int((time.perf_counter() - load_members_started_at) * 1000)

    # ── 预处理：为每群排序并收集洞察候选人 ──
    preprocessed: list[tuple[int, str, list[dict], list[dict]]] = []  # (gid, name, members, ranked)
    for gid in crm_group_ids:
        group_payload = group_members_map.get(gid)
        group_name = (
            group_payload.get('group_name')
            if group_payload
            else crm_group_names.get(gid, f'群#{gid}')
        )
        members = group_payload.get('members', []) if group_payload else []
        positive_members = [m for m in members if float(m.get('current_points', 0) or 0) > 0]
        positive_members.sort(key=lambda m: float(m.get(rank_metric, 0) or 0), reverse=True)
        ranked = positive_members[:top_n]
        preprocessed.append((gid, group_name, members, ranked))

    # ── 批量洞察：一次 point_logs 查询覆盖所有群 ──
    insights_started_at = time.perf_counter()
    scenes_set = set(enabled_scenes) if enabled_scenes else None
    groups_candidates: list[tuple[list[dict], list[dict]]] = []
    valid_indices: list[int] = []
    for idx, (gid, gname, members, ranked) in enumerate(preprocessed):
        if not ranked:
            continue
        # 扩展候选人：top N + 底部 6 名（覆盖 reverse_bottom）
        candidates = list(ranked[:_INSIGHT_MEMBER_LIMIT])
        if len(ranked) > _INSIGHT_MEMBER_LIMIT:
            candidates.extend(ranked[-6:])
        groups_candidates.append((members, candidates))
        valid_indices.append(idx)

    bulk_insights_map: dict[int, list[dict]] = {}
    insights_skipped = False
    if groups_candidates:
        try:
            bulk_results = detect_individual_insights_bulk(groups_candidates, scenes_set)
            for i, result_idx in enumerate(valid_indices):
                bulk_insights_map[result_idx] = bulk_results[i]
        except Exception as exc:
            _log.warning('批量洞察查询失败，降级为纯排行: %s', exc)
            insights_skipped = True
    insights_ms = int((time.perf_counter() - insights_started_at) * 1000)
    _log.info('批量洞察耗时: %dms (groups=%d candidates=%d)', insights_ms, len(preprocessed), len(groups_candidates))

    # ── 生成消息 ──
    build_items_started_at = time.perf_counter()
    slow_groups: list[dict[str, Any]] = []
    for idx, (gid, group_name, members, ranked) in enumerate(preprocessed):
        group_started_at = time.perf_counter()
        try:
            msg = _generate_group_ranking_message_from_members(
                crm_group_id=gid,
                crm_group_name=group_name,
                members=members,
                top_n=top_n,
                rank_metric=rank_metric,
                include_week_month=include_week_month,
                speech_style=speech_style,
                insights=bulk_insights_map.get(idx),
            )
            if msg is None:
                items.append(_build_skipped_item(gid, group_name, '该群无正积分成员'))
                continue
            items.append(
                {
                    **msg,
                    'skipped': False,
                    'local_group_id': None,
                    'local_group_name': None,
                    'has_binding': False,
                    'followup_1v1': generate_1v1_actions(
                        msg.get('insights', []),
                        crm_group_name=group_name,
                        speech_style=speech_style,
                    ),
                }
            )
        except Exception as exc:
            _log.warning('群 %d 排行生成异常: %s', gid, exc)
            items.append(_build_skipped_item(gid, group_name, f'生成异常: {exc}'))
        finally:
            elapsed_ms = int((time.perf_counter() - group_started_at) * 1000)
            if elapsed_ms >= 1000:
                slow_groups.append(
                    {
                        'crm_group_id': gid,
                        'crm_group_name': group_name,
                        'member_count': len(members),
                        'elapsed_ms': elapsed_ms,
                    }
                )

    generate_items_ms = int((time.perf_counter() - build_items_started_at) * 1000)
    total_ms = int((time.perf_counter() - started_at) * 1000)
    skipped_group_count = sum(1 for item in items if item.get('skipped'))
    diagnostics = {
        'requested_group_count': len(crm_group_ids),
        'returned_item_count': len(items),
        'skipped_group_count': skipped_group_count,
        'load_members_ms': load_members_ms,
        'insights_ms': insights_ms,
        'insights_skipped': insights_skipped,
        'generate_items_ms': generate_items_ms,
        'total_ms': total_ms,
        'slow_groups': sorted(slow_groups, key=lambda item: item['elapsed_ms'], reverse=True)[:5],
    }
    _log.info(
        'CRM 积分排行预览生成完成: groups=%d items=%d skipped=%d load_members_ms=%d generate_items_ms=%d total_ms=%d',
        diagnostics['requested_group_count'],
        diagnostics['returned_item_count'],
        diagnostics['skipped_group_count'],
        diagnostics['load_members_ms'],
        diagnostics['generate_items_ms'],
        diagnostics['total_ms'],
    )
    return {'items': items, 'diagnostics': diagnostics}
