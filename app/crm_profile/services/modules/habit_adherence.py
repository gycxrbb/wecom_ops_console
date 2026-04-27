"""Habit adherence module — 14-day execution profiling.

Sources: customer_habits, customer_checkin_records, customer_obstacles.
"""
from __future__ import annotations

import logging

from ...schemas.context import ModulePayload

_log = logging.getLogger(__name__)

MODULE_KEY = "habit_adherence_14d"


def load(conn, customer_id: int) -> ModulePayload:
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt, COALESCE(MAX(current_streak), 0) AS max_streak "
                "FROM customer_habits WHERE customer_id = %s AND status = 1",
                (customer_id,),
            )
            habit_row = cur.fetchone()

        if not habit_row or habit_row["cnt"] == 0:
            return ModulePayload(key=MODULE_KEY, status="empty", payload={})

        active_habits_count = int(habit_row["cnt"])
        current_streak_max = int(habit_row["max_streak"])

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN checkin_status = 1 THEN 1 ELSE 0 END) AS completed "
                "FROM customer_checkin_records "
                "WHERE customer_id = %s AND checkin_date >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)",
                (customer_id,),
            )
            checkin_row = cur.fetchone()

        total_days = int(checkin_row["total"] or 0)
        completed_days = int(checkin_row["completed"] or 0)
        failed_days = total_days - completed_days
        rate = f"{round(completed_days / total_days * 100)}%" if total_days > 0 else "0%"

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(if_then_plan, '') AS if_then_plan "
                "FROM customer_obstacles "
                "WHERE customer_id = %s ORDER BY id DESC LIMIT 3",
                (customer_id,),
            )
            obstacle_rows = cur.fetchall()

        top_obstacles = [r["if_then_plan"][:120] for r in obstacle_rows if r["if_then_plan"]]
        if_then_summary = "; ".join(top_obstacles)[:200] if top_obstacles else None

        return ModulePayload(
            key=MODULE_KEY,
            status="ok",
            payload={
                "active_habits_count": active_habits_count,
                "avg_checkin_completion_rate_14d": rate,
                "failed_checkin_days_14d": failed_days,
                "current_streak_max": current_streak_max,
                "top_obstacles": top_obstacles,
                "if_then_plan_summary": if_then_summary,
            },
            source_tables=["customer_habits", "customer_checkin_records", "customer_obstacles"],
            freshness="14d",
            warnings=[],
        )
    except Exception:
        _log.exception("habit_adherence failed for customer %s", customer_id)
        return ModulePayload(key=MODULE_KEY, status="error", payload={}, warnings=["模块加载异常"])
