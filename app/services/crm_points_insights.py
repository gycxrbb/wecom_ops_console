"""CRM 积分洞察服务 — 从 point_logs 识别运营场景，供排行消息追加场景化话术。"""
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
    # 分批查询避免 SQL 过长
    batch_size = 500
    all_rows: list[dict] = []
    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            for start in range(0, len(customer_ids), batch_size):
                batch = customer_ids[start:start + batch_size]
                placeholders = ','.join(['%s'] * len(batch))
                cur.execute(
                    f"SELECT customer_id, type, num, des, category, created_at "
                    f"FROM point_logs "
                    f"WHERE customer_id IN ({placeholders}) "
                    f"AND type = 0 AND created_at >= %s",
                    (*batch, since),
                )
                all_rows.extend(cur.fetchall())
        _logs_cache[cache_key] = (now, all_rows)
        if len(_logs_cache) > 200:
            stale = [k for k, (ts, _) in _logs_cache.items() if now - ts > _LOGS_CACHE_TTL]
            for k in stale:
                del _logs_cache[k]
        return all_rows
    except Exception as exc:
        _log.warning('积分流水查询失败: %s', exc)
        return []
    finally:
        if conn:
            conn.close()

def _count_active_days(logs: list[dict], cid: int) -> int:
    return len({l['created_at'].date() for l in logs if l['customer_id'] == cid and l.get('created_at')})

def _sum_period_points(logs: list[dict], cid: int, days: int) -> float:
    cutoff = datetime.utcnow() - timedelta(days=days)
    return sum(float(l.get('num', 0) or 0) for l in logs
               if l['customer_id'] == cid and l.get('created_at') and l['created_at'] >= cutoff)

def _parse_activity_types(logs: list[dict], customer_id: int) -> dict[str, int]:
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
    """识别单群的个人级别洞察场景（委托给 bulk 版本）"""
    if not members:
        return []
    results = detect_individual_insights_bulk([(members, ranked_list)])
    return results[0] if results else []

def _build_member_scenes(
    cust_logs: list[dict],
    cid: int,
    rank: int,
    total_members: int,
    current_points: float = 0,
    enabled_scenes: set[str] | None = None,
) -> list[dict]:
    """为单个成员构建洞察场景列表，enabled_scenes 为空时返回全部"""
    scenes: list[dict] = []
    now = datetime.utcnow()

    def _add(key: str, label: str, detail: str) -> None:
        if enabled_scenes is None or key in enabled_scenes:
            scenes.append({'key': key, 'label': label, 'detail': detail})

    # 场景1: 排名位置
    for threshold, key, label in [(3, 'top_leader', '头部领先'), (6, 'top_six', '前六冲刺'), (10, 'top_ten', '前十竞争')]:
        if rank <= threshold:
            _add(key, label, f'当前排名第{rank}')
            break

    # 场景2: 连续稳定活跃
    active_days = _count_active_days(cust_logs, cid)
    if active_days >= 7:
        _add('consistent', '连续活跃', f'近14天活跃{active_days}天')

    # 场景3: 异常增长/突然爆发
    recent_3 = _sum_period_points(cust_logs, cid, 3)
    recent_7 = _sum_period_points(cust_logs, cid, 7)
    baseline_avg = recent_7 / 7 if recent_7 > 0 else 0
    if recent_3 > 0 and baseline_avg > 0 and (recent_3 / 3) > baseline_avg * 2:
        _add('surge', '积分暴涨', f'近3天+{recent_3:.0f}，日均显著高于前7天')

    # 场景4: 久未活跃后回归
    recent_3_pts = _sum_period_points(cust_logs, cid, 3)
    if recent_3_pts > 0:
        older_logs = [l for l in cust_logs
                      if l.get('created_at')
                      and l['created_at'] < now - timedelta(days=3)]
        older_active = _count_active_days(older_logs, cid)
        if older_active == 0:
            _add('comeback', '强势回归', '沉寂后重新活跃')

    # 场景5: 中途掉队但重新跟上
    if recent_3_pts > 0 and active_days >= 3:
        early_logs = [l for l in cust_logs
                      if l.get('created_at')
                      and l['created_at'] >= now - timedelta(days=14)
                      and l['created_at'] < now - timedelta(days=6)]
        mid_logs = [l for l in cust_logs
                    if l.get('created_at')
                    and l['created_at'] >= now - timedelta(days=6)
                    and l['created_at'] < now - timedelta(days=3)]
        early_active = _count_active_days(early_logs, cid)
        mid_active = _count_active_days(mid_logs, cid)
        if early_active > 0 and mid_active == 0:
            _add('dropout_recovery', '掉队归队', '中断后重新跟上节奏')

    # 场景6: 积分上升明显/进步飞快
    recent_7_pts = _sum_period_points(cust_logs, cid, 7)
    prev_7_pts = sum(
        float(l.get('num', 0) or 0)
        for l in cust_logs
        if l.get('created_at')
        and now - timedelta(days=14) <= l['created_at'] < now - timedelta(days=7)
    )
    if recent_7_pts > 0 and prev_7_pts > 0:
        ratio = (recent_7_pts / 7) / (prev_7_pts / 7)
        if ratio > 1.5 and not any(s['key'] == 'surge' for s in scenes):
            _add('rapid_progress', '进步飞快', f'近7天日均积分提升{ratio:.1f}倍')

    # 场景7: 反向激励 - 后6名
    if total_members >= 10 and rank > total_members - 6:
        _add('reverse_bottom', '需要激励', f'当前排名第{rank}（后段）')

    # 场景8: 提醒观望/潜水用户
    if active_days <= 2 and current_points > 0 and rank > 10:
        _add('lurker_remind', '潜水用户', f'近14天仅活跃{active_days}天')

    return scenes

def detect_individual_insights_bulk(
    groups_candidates: list[tuple[list[dict], list[dict]]],
    enabled_scenes: set[str] | None = None,
) -> list[list[dict]]:
    """批量识别多群的个人洞察（一次 point_logs 查询）

    Args:
        groups_candidates: 每个群一个元组 (members, ranked_list)

    Returns:
        与 groups_candidates 等长的列表，每个元素是该群的洞察列表
    """
    all_customer_ids: set[int] = set()
    for members, ranked_list in groups_candidates:
        for m in ranked_list:
            all_customer_ids.add(int(m['id']))

    if not all_customer_ids:
        return [[] for _ in groups_candidates]

    started_at = time.perf_counter()
    logs = _fetch_recent_logs(sorted(all_customer_ids), days=14)

    logs_by_cust: dict[int, list] = {}
    for log in logs:
        logs_by_cust.setdefault(log['customer_id'], []).append(log)

    results: list[list[dict]] = []
    for members, ranked_list in groups_candidates:
        if not members:
            results.append([])
            continue

        id_to_name = {m['id']: m.get('name', f'未命名#{m["id"]}') for m in members}
        insights: list[dict] = []

        for i, m in enumerate(ranked_list):
            cid = m['id']
            cust_logs = logs_by_cust.get(cid, [])
            rank = i + 1

            pts = float(m.get('current_points', 0) or 0)
            scenes = _build_member_scenes(cust_logs, cid, rank, len(ranked_list), pts, enabled_scenes)
            if not scenes:
                continue

            activity_types = _parse_activity_types(cust_logs, cid)
            insights.append({
                'customer_id': cid,
                'customer_name': id_to_name.get(cid, ''),
                'current_points': pts,
                'rank': rank,
                'scenes': scenes,
                'activity_types': activity_types,
            })

        results.append(insights)

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    if elapsed_ms >= 500:
        total_insights = sum(len(r) for r in results)
        _log.info(
            '批量积分洞察完成: groups=%d customers=%d logs=%d insights=%d elapsed_ms=%d',
            len(groups_candidates), len(all_customer_ids), len(logs), total_insights, elapsed_ms,
        )

    return results

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
