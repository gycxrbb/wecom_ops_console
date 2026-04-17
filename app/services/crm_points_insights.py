"""CRM 积分洞察服务

从 point_logs 识别运营场景：头部领先、连续活跃、突然爆发、回归用户等。
供排行消息生成时追加场景化话术。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any

from .crm_group_directory import _get_connection

_log = logging.getLogger(__name__)

# ── _fetch_recent_logs 结果缓存（120 秒） ──
_logs_cache: dict[tuple, tuple[float, list]] = {}
_LOGS_CACHE_TTL = 120


def _fetch_recent_logs(customer_ids: list[int], days: int = 14) -> list[dict]:
    """查询最近 N 天的积分流水（仅正向 type=0），带 120 秒缓存"""
    if not customer_ids:
        return []

    cache_key = (tuple(sorted(customer_ids)), days)
    now = time.time()
    if cache_key in _logs_cache:
        ts, rows = _logs_cache[cache_key]
        if now - ts < _LOGS_CACHE_TTL:
            return rows

    since = datetime.utcnow() - timedelta(days=days)
    placeholders = ','.join(['%s'] * len(customer_ids))
    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT customer_id, type, num, des, category, created_at "
                f"FROM point_logs "
                f"WHERE customer_id IN ({placeholders}) "
                f"AND type = 0 AND created_at >= %s "
                f"ORDER BY customer_id, created_at DESC",
                (*customer_ids, since),
            )
            rows = cur.fetchall()
        _logs_cache[cache_key] = (now, rows)
        # 清理过期缓存
        if len(_logs_cache) > 200:
            stale = [k for k, (ts, _) in _logs_cache.items() if now - ts > _LOGS_CACHE_TTL]
            for k in stale:
                del _logs_cache[k]
        return rows
    except Exception as exc:
        _log.warning('积分流水查询失败: %s', exc)
        return []
    finally:
        if conn:
            conn.close()


def _count_active_days(logs: list[dict], customer_id: int) -> int:
    """统计有正向流水的天数"""
    dates = set()
    for log in logs:
        if log['customer_id'] == customer_id and log.get('created_at'):
            dates.add(log['created_at'].date())
    return len(dates)


def _sum_period_points(logs: list[dict], customer_id: int, days: int) -> float:
    """统计最近 N 天净积分"""
    cutoff = datetime.utcnow() - timedelta(days=days)
    return sum(
        float(log.get('num', 0) or 0)
        for log in logs
        if log['customer_id'] == customer_id
        and log.get('created_at')
        and log['created_at'] >= cutoff
    )


def _parse_activity_types(logs: list[dict], customer_id: int) -> dict[str, int]:
    """解析 des 字段提取活动类型频次"""
    category_map = {
        1: '完成任务', 2: '运动打卡', 3: '饮食记录',
        4: '健康监测', 5: '社群互动', 6: '系统调整',
    }
    des_keywords = {
        'weight_checkin': '体重打卡',
        'habit_checkin': '习惯打卡',
        'meal_upload': '餐食上传',
        'course': '看课学习',
        'issue': '提交阻碍',
    }
    counts: dict[str, int] = {}
    for log in logs:
        if log['customer_id'] != customer_id:
            continue
        # category 优先
        cat = log.get('category', 0) or 0
        if cat in category_map:
            label = category_map[cat]
            counts[label] = counts.get(label, 0) + 1
        # des 关键词补充
        des = log.get('des', '') or ''
        for kw, label in des_keywords.items():
            if kw in des:
                counts[label] = counts.get(label, 0) + 1
    return counts


def detect_individual_insights(
    members: list[dict],
    ranked_list: list[dict],
) -> list[dict]:
    """识别个人级别的洞察场景

    Args:
        members: 群成员列表（含 current_points, week_points, month_points）
        ranked_list: 按 current_points 降序排列的成员列表

    Returns:
        洞察列表，每个元素 {customer_id, customer_name, scenes, activity_types}
    """
    if not members:
        return []

    ranked_customer_ids = []
    seen_customer_ids: set[int] = set()
    for member in ranked_list:
        customer_id = int(member['id'])
        if customer_id in seen_customer_ids:
            continue
        seen_customer_ids.add(customer_id)
        ranked_customer_ids.append(customer_id)

    id_to_name = {m['id']: m.get('name', f'未命名#{m["id"]}') for m in members}
    id_to_points = {m['id']: m for m in members}

    started_at = time.perf_counter()
    logs = _fetch_recent_logs(ranked_customer_ids, days=14)
    if not logs:
        return []

    # 按客户分组日志
    logs_by_cust: dict[int, list] = {}
    for log in logs:
        cid = log['customer_id']
        logs_by_cust.setdefault(cid, []).append(log)

    total = len(ranked_list)
    insights = []

    for i, m in enumerate(ranked_list):
        cid = m['id']
        scenes: list[dict] = []
        cust_logs = logs_by_cust.get(cid, [])

        # 场景1: 头部领先
        rank = i + 1
        if rank <= 3:
            scenes.append({'key': 'top_leader', 'label': '头部领先', 'detail': f'当前排名第{rank}'})
        elif rank <= 6:
            scenes.append({'key': 'top_six', 'label': '前六冲刺', 'detail': f'当前排名第{rank}'})
        elif rank <= 10:
            scenes.append({'key': 'top_ten', 'label': '前十竞争', 'detail': f'当前排名第{rank}'})

        # 场景2: 连续稳定活跃
        active_days = _count_active_days(cust_logs, cid)
        if active_days >= 7:
            scenes.append({'key': 'consistent', 'label': '连续活跃', 'detail': f'近14天活跃{active_days}天'})

        # 场景3: 异常增长/突然爆发
        recent_3 = _sum_period_points(cust_logs, cid, 3)
        recent_7 = _sum_period_points(cust_logs, cid, 7)
        baseline_avg = recent_7 / 7 if recent_7 > 0 else 0
        if recent_3 > 0 and baseline_avg > 0 and (recent_3 / 3) > baseline_avg * 2:
            scenes.append({'key': 'surge', 'label': '积分暴涨', 'detail': f'近3天+{recent_3:.0f}，日均显著高于前7天'})

        # 场景4: 久未活跃后回归
        recent_3_active = _count_active_days(cust_logs, cid) if _sum_period_points(cust_logs, cid, 3) > 0 else 0
        if recent_3_active > 0:
            older_logs = [l for l in cust_logs
                          if l.get('created_at')
                          and l['created_at'] < datetime.utcnow() - timedelta(days=3)]
            older_active = _count_active_days(older_logs, cid)
            if older_active == 0:
                scenes.append({'key': 'comeback', 'label': '强势回归', 'detail': '沉寂后重新活跃'})

        if not scenes:
            continue

        activity_types = _parse_activity_types(cust_logs, cid)
        insights.append({
            'customer_id': cid,
            'customer_name': id_to_name.get(cid, ''),
            'current_points': float(id_to_points.get(cid, {}).get('current_points', 0) or 0),
            'rank': rank,
            'scenes': scenes,
            'activity_types': activity_types,
        })

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    if elapsed_ms >= 1000:
        _log.info(
            '积分洞察分析完成: ranked_members=%d logs=%d insights=%d elapsed_ms=%d',
            len(ranked_customer_ids),
            len(logs),
            len(insights),
            elapsed_ms,
        )

    return insights


def detect_group_insights(
    groups_data: list[dict],
) -> list[dict]:
    """识别群组级别的洞察场景

    Args:
        groups_data: 群列表（含 current_points_sum, week_points_sum, month_points_sum）

    Returns:
        群洞察列表
    """
    if not groups_data:
        return []

    sorted_groups = sorted(groups_data, key=lambda g: float(g.get('current_points_sum', 0) or 0), reverse=True)
    insights = []

    for i, g in enumerate(sorted_groups):
        rank = i + 1
        scenes: list[dict] = []
        week_pts = float(g.get('week_points_sum', 0) or 0)
        month_pts = float(g.get('month_points_sum', 0) or 0)

        if rank <= 3:
            scenes.append({'key': 'group_top', 'label': '群组领先', 'detail': f'群排行第{rank}'})
        if week_pts > 0:
            scenes.append({'key': 'group_active_week', 'label': '本周活跃群', 'detail': f'本周+{week_pts:.0f}分'})
        if not scenes:
            continue

        insights.append({
            'group_id': g.get('id'),
            'group_name': g.get('name', ''),
            'rank': rank,
            'scenes': scenes,
            'current_points_sum': float(g.get('current_points_sum', 0) or 0),
            'week_points_sum': week_pts,
            'month_points_sum': month_pts,
        })

    return insights
