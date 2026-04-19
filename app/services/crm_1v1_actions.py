"""1v1 私发消息自动生成服务

根据洞察结果自动生成 1v1 跟进动作列表（私发消息模板），
供运营人员确认后发送。
"""
from __future__ import annotations

import logging
from typing import Any

from .crm_speech_templates import get_speech

_log = logging.getLogger(__name__)

# ── 动作类型定义 ──
ACTION_TYPES = {
    'praise_top3': {'label': '表扬 TOP3', 'scene_key': 'top_leader'},
    'praise_consistent': {'label': '表扬连续打卡', 'scene_key': 'consistent'},
    'remind_inactive_3d': {'label': '3天未打卡提醒', 'scene_key': 'comeback'},
    'care_inactive_2w': {'label': '2周未打卡关怀', 'scene_key': 'lurker_remind'},
    'encourage_near_top6': {'label': '鼓励冲刺前6', 'scene_key': 'top_six'},
    'congratulate_winner': {'label': '获奖恭喜', 'scene_key': 'top_leader'},
    'encourage_bottom': {'label': '后段鼓励', 'scene_key': 'reverse_bottom'},
    'praise_surge': {'label': '表扬暴涨', 'scene_key': 'surge'},
    'praise_progress': {'label': '表扬进步', 'scene_key': 'rapid_progress'},
}


def _determine_action_type(
    insight: dict,
    stage_key: str = 'daily_ranking',
) -> str | None:
    """根据洞察场景和当前阶段确定 1v1 动作类型"""
    scenes = {s['key'] for s in insight.get('scenes', [])}
    rank = insight.get('rank', 999)

    # 结营当天：特殊处理
    if stage_key == 'closing_day':
        if rank <= 3:
            return 'congratulate_winner'
        if 'reverse_bottom' in scenes:
            return 'encourage_bottom'

    # 每日发榜 / 冲刺阶段
    if 'top_leader' in scenes:
        return 'praise_top3'
    if 'surge' in scenes:
        return 'praise_surge'
    if 'rapid_progress' in scenes:
        return 'praise_progress'
    if 'consistent' in scenes:
        return 'praise_consistent'
    if rank <= 8 and 'top_six' not in scenes and rank > 6:
        return 'encourage_near_top6'
    if 'comeback' in scenes:
        return 'remind_inactive_3d'
    if 'lurker_remind' in scenes:
        return 'care_inactive_2w'
    if 'reverse_bottom' in scenes:
        return 'encourage_bottom'

    return None


def generate_1v1_actions(
    insights: list[dict],
    crm_group_name: str = '',
    speech_style: str = 'professional',
    stage_key: str = 'daily_ranking',
    max_actions: int = 20,
) -> list[dict[str, Any]]:
    """根据洞察结果自动生成 1v1 跟进动作列表

    Args:
        insights: 单群的洞察结果列表
        crm_group_name: 群名（用于定位）
        speech_style: 话术风格
        stage_key: 当前运营阶段
        max_actions: 最多生成几条

    Returns:
        1v1 动作列表 [{action_type, label, target_name, target_group, message}]
    """
    actions: list[dict[str, Any]] = []

    for insight in insights:
        if len(actions) >= max_actions:
            break

        action_type = _determine_action_type(insight, stage_key)
        if not action_type:
            continue

        action_def = ACTION_TYPES.get(action_type, {})
        scene_key = action_def.get('scene_key', '')
        name = insight.get('customer_name', '')
        rank = insight.get('rank', 0)

        # 拼接活动描述
        activity_types = insight.get('activity_types', {})
        if activity_types:
            top = sorted(activity_types.items(), key=lambda x: x[1], reverse=True)[:2]
            activity_desc = '、'.join([label for label, _ in top])
        else:
            activity_desc = '积极参与'

        detail = ''
        for scene in insight.get('scenes', []):
            if scene['key'] == scene_key:
                detail = scene.get('detail', '')
                break

        message = get_speech(
            scene_key, speech_style,
            name=name, rank=rank, detail=detail, activity=activity_desc,
        )

        if not message:
            continue

        actions.append({
            'action_type': action_type,
            'label': action_def.get('label', action_type),
            'target_name': name,
            'target_group': crm_group_name,
            'message': message,
            'customer_id': insight.get('customer_id'),
            'rank': rank,
        })

    return actions
