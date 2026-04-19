"""跨群全局排行消息生成

生成跨所有 CRM 群的总体排行：全局 TOP10 个人 + 社群 PK 排名。
发送到运营人员指定的单个目标群。
"""
from __future__ import annotations

import logging
from typing import Any

from .crm_group_directory import fetch_crm_group_members_bulk, crm_group_enabled
from .crm_speech_templates import get_speech

_log = logging.getLogger(__name__)

_MEDALS = {1: '🥇', 2: '🥈', 3: '🥉'}


def generate_global_overview(
    crm_group_ids: list[int],
    crm_group_names: dict[int, str],
    top_n: int = 10,
    speech_style: str = 'professional',
) -> dict[str, Any] | None:
    """生成跨群全局排行消息（20 社群 PK + 跨群 TOP10 个人）"""
    if not crm_group_enabled():
        return None

    group_members_map = fetch_crm_group_members_bulk(crm_group_ids)

    # 收集所有成员，附带群信息
    all_members: list[dict] = []
    group_summaries: list[dict] = []
    for gid in crm_group_ids:
        payload = group_members_map.get(gid)
        if not payload:
            continue
        gname = crm_group_names.get(gid, payload.get('group_name', f'群#{gid}'))
        members = [m for m in payload.get('members', []) if float(m.get('current_points', 0) or 0) > 0]
        if not members:
            continue
        g_total = sum(float(m.get('current_points', 0) or 0) for m in members)
        g_week = sum(float(m.get('week_points', 0) or 0) for m in members)
        g_month = sum(float(m.get('month_points', 0) or 0) for m in members)
        group_summaries.append({
            'group_id': gid, 'group_name': gname,
            'current_points': g_total, 'week_points': g_week, 'month_points': g_month,
            'member_count': len(members),
        })
        for m in members:
            m['_group_name'] = gname
            m['_group_id'] = gid
            all_members.append(m)

    if not all_members:
        return None

    # ── 跨群个人 TOP10 ──
    all_members.sort(key=lambda m: float(m.get('current_points', 0) or 0), reverse=True)
    top_members = all_members[:top_n]

    lines = ['🏆 首钢减重项目 — 跨群总排行']
    lines.append('')
    lines.append(f'👥 覆盖 {len(group_summaries)} 个社群，{len(all_members)} 位活跃成员')
    lines.append('')
    lines.append('🌟 全局个人 TOP10:')
    for i, m in enumerate(top_members, 1):
        medal = _MEDALS.get(i, f'{i}.')
        name = m.get('name') or f'未命名#{m["id"]}'
        pts = float(m.get('current_points', 0) or 0)
        gname = m.get('_group_name', '')
        lines.append(f'{medal} {name}（{gname}）{pts:.0f}分')

    # ── 社群 PK 排名 ──
    group_summaries.sort(key=lambda g: g['current_points'], reverse=True)
    lines.append('')
    lines.append('🏟️ 社群 PK 排名:')
    for i, g in enumerate(group_summaries, 1):
        medal = _MEDALS.get(i, f'{i}.')
        lines.append(
            f'{medal} {g["group_name"]} 总{g["current_points"]:.0f}分 '
            f'（{g["member_count"]}人，本周+{g["week_points"]:.0f}）'
        )

    # ── 全局洞察话术 ──
    pk_speech = get_speech('group_pk', speech_style)
    if pk_speech:
        lines.append('')
        lines.append(pk_speech)

    return {
        'msg_type': 'markdown',
        'content_json': {'content': '\n'.join(lines)},
        'group_count': len(group_summaries),
        'member_count': len(all_members),
        'top_members': [
            {
                'name': m.get('name', ''),
                'group': m.get('_group_name', ''),
                'points': float(m.get('current_points', 0) or 0),
            }
            for m in top_members
        ],
        'group_ranking': group_summaries,
    }
