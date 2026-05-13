"""CRM 积分指标服务 — 周/月积分聚合查询

从 point_logs 表按时间窗口聚合客户和群组的净积分变化。
净增量公式：type=0 获得 → +num，type=1 消费 → -num。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from .crm_group_directory import _get_connection, _return_connection

_log = logging.getLogger(__name__)


# ── 时间窗口计算 ──────────────────────────────────────────────

def get_week_range() -> tuple[datetime, datetime]:
    """返回本周起止时间（周一 00:00 ~ 下周一 00:00，Asia/Shanghai）。"""
    import zoneinfo
    tz = zoneinfo.ZoneInfo('Asia/Shanghai')
    now = datetime.now(tz)
    monday = now.date() - timedelta(days=now.weekday())
    start = datetime(monday.year, monday.month, monday.day, tzinfo=tz)
    end = start + timedelta(weeks=1)
    # 返回 naive datetime（MySQL DATETIME 无时区信息，CRM 库存的是 CST）
    return start.replace(tzinfo=None), end.replace(tzinfo=None)


def get_month_range() -> tuple[datetime, datetime]:
    """返回本月起止时间（1日 00:00 ~ 下月1日 00:00，Asia/Shanghai）。"""
    import zoneinfo
    tz = zoneinfo.ZoneInfo('Asia/Shanghai')
    now = datetime.now(tz)
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        next_month = first_day.replace(year=now.year + 1, month=1)
    else:
        next_month = first_day.replace(month=now.month + 1)
    return first_day.replace(tzinfo=None), next_month.replace(tzinfo=None)


# ── 净积分 SQL 片段 ──────────────────────────────────────────

_NET_SQL = (
    "SUM(CASE WHEN pl.type = 0 THEN COALESCE(pl.num, 0) "
    "WHEN pl.type = 1 THEN -COALESCE(pl.num, 0) ELSE 0 END)"
)


# ── 批量查询函数 ─────────────────────────────────────────────

def fetch_customer_period_points(
    customer_ids: list[int],
    start: datetime,
    end: datetime,
) -> dict[int, float]:
    """批量查询指定客户在时间窗口内的净积分变化。

    Returns:
        {customer_id: net_points_change}
    """
    if not customer_ids:
        return {}

    result: dict[int, float] = {cid: 0.0 for cid in customer_ids}
    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            # 分批查询，每批最多 500 个 ID，避免 SQL 过长
            batch_size = 500
            for i in range(0, len(customer_ids), batch_size):
                batch = customer_ids[i:i + batch_size]
                placeholders = ','.join(['%s'] * len(batch))
                cur.execute(
                    f"SELECT pl.customer_id, {_NET_SQL} AS net_points "
                    f"FROM point_logs pl "
                    f"WHERE pl.customer_id IN ({placeholders}) "
                    f"AND pl.created_at >= %s AND pl.created_at < %s "
                    f"GROUP BY pl.customer_id",
                    (*batch, start, end),
                )
                for row in cur.fetchall():
                    result[row['customer_id']] = float(row['net_points'] or 0)
    except Exception as exc:
        _log.warning('CRM 客户周期积分查询失败: %s', exc)
    finally:
        if conn:
            _return_connection(conn)
    return result


def fetch_customer_period_points_dual(
    customer_ids: list[int],
    week_start: datetime,
    week_end: datetime,
    month_start: datetime,
    month_end: datetime,
) -> tuple[dict[int, float], dict[int, float]]:
    """批量查询客户周/月净积分变化，使用一次条件聚合完成。"""
    if not customer_ids:
        return {}, {}

    week_result: dict[int, float] = {customer_id: 0.0 for customer_id in customer_ids}
    month_result: dict[int, float] = {customer_id: 0.0 for customer_id in customer_ids}
    lower_bound = min(week_start, month_start)
    upper_bound = max(week_end, month_end)

    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            batch_size = 500
            for i in range(0, len(customer_ids), batch_size):
                batch = customer_ids[i:i + batch_size]
                placeholders = ','.join(['%s'] * len(batch))
                cur.execute(
                    f"""
                    SELECT
                        pl.customer_id,
                        SUM(
                            CASE
                                WHEN pl.created_at >= %s AND pl.created_at < %s
                                THEN CASE WHEN pl.type = 0 THEN COALESCE(pl.num, 0)
                                          WHEN pl.type = 1 THEN -COALESCE(pl.num, 0)
                                          ELSE 0 END
                                ELSE 0
                            END
                        ) AS week_points,
                        SUM(
                            CASE
                                WHEN pl.created_at >= %s AND pl.created_at < %s
                                THEN CASE WHEN pl.type = 0 THEN COALESCE(pl.num, 0)
                                          WHEN pl.type = 1 THEN -COALESCE(pl.num, 0)
                                          ELSE 0 END
                                ELSE 0
                            END
                        ) AS month_points
                    FROM point_logs pl
                    WHERE pl.customer_id IN ({placeholders})
                      AND pl.created_at >= %s AND pl.created_at < %s
                    GROUP BY pl.customer_id
                    """,
                    (week_start, week_end, month_start, month_end, *batch, lower_bound, upper_bound),
                )
                for row in cur.fetchall():
                    customer_id = row['customer_id']
                    week_result[customer_id] = float(row.get('week_points') or 0)
                    month_result[customer_id] = float(row.get('month_points') or 0)
    except Exception as exc:
        _log.warning('CRM 客户周/月积分联合查询失败: %s', exc)
    finally:
        if conn:
            _return_connection(conn)
    return week_result, month_result


def fetch_group_period_points(
    group_ids: list[int],
    start: datetime,
    end: datetime,
) -> dict[int, float]:
    """批量查询指定群组在时间窗口内的净积分变化（通过 customer_groups JOIN 聚合）。

    Returns:
        {group_id: net_points_change}
    """
    if not group_ids:
        return {}

    result: dict[int, float] = {gid: 0.0 for gid in group_ids}
    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            batch_size = 500
            for i in range(0, len(group_ids), batch_size):
                batch = group_ids[i:i + batch_size]
                placeholders = ','.join(['%s'] * len(batch))
                cur.execute(
                    f"SELECT cg.group_id, {_NET_SQL} AS net_points "
                    f"FROM point_logs pl "
                    f"INNER JOIN customer_groups cg ON cg.customer_id = pl.customer_id "
                    f"WHERE cg.group_id IN ({placeholders}) "
                    f"AND pl.created_at >= %s AND pl.created_at < %s "
                    f"GROUP BY cg.group_id",
                    (*batch, start, end),
                )
                for row in cur.fetchall():
                    result[row['group_id']] = float(row['net_points'] or 0)
    except Exception as exc:
        _log.warning('CRM 群组周期积分查询失败: %s', exc)
    finally:
        if conn:
            _return_connection(conn)
    return result


def fetch_group_period_points_dual(
    group_ids: list[int],
    week_start: datetime,
    week_end: datetime,
    month_start: datetime,
    month_end: datetime,
) -> tuple[dict[int, float], dict[int, float]]:
    """批量查询群组周/月净积分变化，使用一次条件聚合完成。"""
    if not group_ids:
        return {}, {}

    week_result: dict[int, float] = {group_id: 0.0 for group_id in group_ids}
    month_result: dict[int, float] = {group_id: 0.0 for group_id in group_ids}
    lower_bound = min(week_start, month_start)
    upper_bound = max(week_end, month_end)

    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            batch_size = 500
            for i in range(0, len(group_ids), batch_size):
                batch = group_ids[i:i + batch_size]
                placeholders = ','.join(['%s'] * len(batch))
                cur.execute(
                    f"""
                    SELECT
                        cg.group_id,
                        SUM(
                            CASE
                                WHEN pl.created_at >= %s AND pl.created_at < %s
                                THEN CASE WHEN pl.type = 0 THEN COALESCE(pl.num, 0)
                                          WHEN pl.type = 1 THEN -COALESCE(pl.num, 0)
                                          ELSE 0 END
                                ELSE 0
                            END
                        ) AS week_points,
                        SUM(
                            CASE
                                WHEN pl.created_at >= %s AND pl.created_at < %s
                                THEN CASE WHEN pl.type = 0 THEN COALESCE(pl.num, 0)
                                          WHEN pl.type = 1 THEN -COALESCE(pl.num, 0)
                                          ELSE 0 END
                                ELSE 0
                            END
                        ) AS month_points
                    FROM point_logs pl
                    INNER JOIN customer_groups cg ON cg.customer_id = pl.customer_id
                    WHERE cg.group_id IN ({placeholders})
                      AND pl.created_at >= %s AND pl.created_at < %s
                    GROUP BY cg.group_id
                    """,
                    (week_start, week_end, month_start, month_end, *batch, lower_bound, upper_bound),
                )
                for row in cur.fetchall():
                    group_id = row['group_id']
                    week_result[group_id] = float(row.get('week_points') or 0)
                    month_result[group_id] = float(row.get('month_points') or 0)
    except Exception as exc:
        _log.warning('CRM 群组周/月积分联合查询失败: %s', exc)
    finally:
        if conn:
            _return_connection(conn)
    return week_result, month_result


# ── 上周积分明细拆分查询 ─────────────────────────────────────

def get_last_week_range() -> tuple[datetime, datetime]:
    """返回上周起止时间（上周一 00:00 ~ 本周一 00:00，Asia/Shanghai）。"""
    import zoneinfo
    tz = zoneinfo.ZoneInfo('Asia/Shanghai')
    now = datetime.now(tz)
    this_monday = now.date() - timedelta(days=now.weekday())
    last_monday = this_monday - timedelta(weeks=1)
    start = datetime(last_monday.year, last_monday.month, last_monday.day, tzinfo=tz)
    end = datetime(this_monday.year, this_monday.month, this_monday.day, tzinfo=tz)
    return start.replace(tzinfo=None), end.replace(tzinfo=None)


# 三大分类的 CASE WHEN 条件
_APP_SQL = (
    "SUM(CASE WHEN (pl.category = 1 AND pl.des LIKE '%%habit_checkin%%') "
    "OR (pl.category = 1 AND pl.des LIKE '%%issue%%') "
    "OR (pl.category = 1 AND pl.des LIKE '%%courseId%%') "
    "OR (pl.category = 1 AND pl.des LIKE '%%weight_checkin%%') "
    "OR (pl.category = 3 AND pl.des LIKE '%%meal_upload%%') "
    "THEN CASE WHEN pl.type = 0 THEN COALESCE(pl.num, 0) "
    "WHEN pl.type = 1 THEN -COALESCE(pl.num, 0) ELSE 0 END ELSE 0 END)"
)

_COMMUNITY_SQL = (
    "SUM(CASE WHEN pl.category = 5 "
    "THEN CASE WHEN pl.type = 0 THEN COALESCE(pl.num, 0) "
    "WHEN pl.type = 1 THEN -COALESCE(pl.num, 0) ELSE 0 END ELSE 0 END)"
)

_LIVE_SQL = (
    "SUM(CASE WHEN pl.category = 8 "
    "THEN CASE WHEN pl.type = 0 THEN COALESCE(pl.num, 0) "
    "WHEN pl.type = 1 THEN -COALESCE(pl.num, 0) ELSE 0 END ELSE 0 END)"
)


def fetch_customer_last_week_breakdown_bulk(
    customer_ids: list[int],
) -> dict[int, dict[str, float]]:
    """批量查询指定客户上周积分的三大类拆分明细。

    Returns:
        {customer_id: {'app': float, 'community': float, 'live': float}}
    """
    if not customer_ids:
        return {}

    start, end = get_last_week_range()
    result: dict[int, dict[str, float]] = {
        cid: {'app': 0.0, 'community': 0.0, 'live': 0.0} for cid in customer_ids
    }

    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            batch_size = 500
            for i in range(0, len(customer_ids), batch_size):
                batch = customer_ids[i:i + batch_size]
                placeholders = ','.join(['%s'] * len(batch))
                cur.execute(
                    f"""
                    SELECT
                        pl.customer_id,
                        {_APP_SQL} AS app_points,
                        {_COMMUNITY_SQL} AS community_points,
                        {_LIVE_SQL} AS live_points
                    FROM point_logs pl
                    WHERE pl.customer_id IN ({placeholders})
                      AND pl.created_at >= %s AND pl.created_at < %s
                      AND pl.category IN (1, 3, 5, 8)
                    GROUP BY pl.customer_id
                    """,
                    (*batch, start, end),
                )
                for row in cur.fetchall():
                    cid = row['customer_id']
                    result[cid] = {
                        'app': float(row.get('app_points') or 0),
                        'community': float(row.get('community_points') or 0),
                        'live': float(row.get('live_points') or 0),
                    }
    except Exception as exc:
        _log.warning('CRM 客户上周积分明细查询失败: %s', exc)
    finally:
        if conn:
            _return_connection(conn)
    return result


# ── 自定义当月周期（基于 groups.start_time） ────────────────────

def get_group_custom_month_range(start_time: datetime) -> tuple[datetime, datetime]:
    """根据群的 start_time，计算当前所在的 30 天周期范围。

    每 30 天为一个周期，从 start_time 起算。返回 (period_start, period_end)。
    """
    import zoneinfo
    tz = zoneinfo.ZoneInfo('Asia/Shanghai')
    now = datetime.now(tz)

    # 确保 start_time 是 naive datetime (CST)
    st = start_time.replace(tzinfo=None) if start_time.tzinfo else start_time

    # now 也用 naive datetime 做比较（CST 本地时间）
    now_naive = now.replace(tzinfo=None)

    period_start = st
    while period_start + timedelta(days=30) <= now_naive:
        period_start += timedelta(days=30)

    period_end = period_start + timedelta(days=30)
    return period_start, period_end
