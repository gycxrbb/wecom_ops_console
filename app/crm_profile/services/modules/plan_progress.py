"""Plan progress module — 14-day plan & todo profiling.

Sources: customer_plans, customer_todos.
"""
from __future__ import annotations

import logging

from ...schemas.context import ModulePayload

_log = logging.getLogger(__name__)

MODULE_KEY = "plan_progress_14d"


def load(conn, customer_id: int) -> ModulePayload:
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, status, start_date, total_days, pause_date, resume_date "
                "FROM customer_plans "
                "WHERE customer_id = %s AND status IN (0, 1) ORDER BY id DESC LIMIT 1",
                (customer_id,),
            )
            plan_row = cur.fetchone()

        if not plan_row:
            return ModulePayload(
                key=MODULE_KEY, status="empty",
                payload={"current_plan_status": "无计划"},
            )

        plan_id = plan_row["id"]
        plan_status_code = int(plan_row["status"])
        status_map = {0: "进行中", 1: "已完成"}
        plan_status = status_map.get(plan_status_code, "未知")

        total_days = int(plan_row["total_days"] or 0)
        start_date = plan_row["start_date"]
        if start_date and total_days > 0:
            from datetime import date
            if isinstance(start_date, str):
                from datetime import datetime as dt
                start_date = dt.strptime(start_date, "%Y-%m-%d").date()
            elapsed = (date.today() - start_date).days + 1
            day_progress = f"第 {min(elapsed, total_days)}/{total_days} 天"
        else:
            day_progress = None

        pause_resume = None
        parts = []
        if plan_row["pause_date"]:
            pd = str(plan_row["pause_date"])[:10]
            parts.append(f"暂停于 {pd[5:]}")
        if plan_row["resume_date"]:
            rd = str(plan_row["resume_date"])[:10]
            parts.append(f"恢复于 {rd[5:]}")
        if parts:
            pause_resume = "，".join(parts)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN status = 2 THEN 1 ELSE 0 END) AS done, "
                "SUM(CASE WHEN status = 3 THEN 1 ELSE 0 END) AS paused, "
                "SUM(CASE WHEN status = 0 AND orig_date < CURDATE() THEN 1 ELSE 0 END) AS overdue "
                "FROM customer_todos "
                "WHERE customer_id = %s AND plan_id = %s "
                "AND orig_date >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)",
                (customer_id, plan_id),
            )
            todo_row = cur.fetchone()

        todo_total = int(todo_row["total"] or 0)
        todo_done = int(todo_row["done"] or 0)
        todo_overdue = int(todo_row["overdue"] or 0)
        todo_rate = f"{round(todo_done / todo_total * 100)}%" if todo_total > 0 else "0%"

        return ModulePayload(
            key=MODULE_KEY,
            status="ok",
            payload={
                "current_plan_title": plan_row["title"],
                "current_plan_status": plan_status,
                "plan_day_progress": day_progress,
                "todo_completion_rate_14d": todo_rate,
                "overdue_todo_count": todo_overdue,
                "pause_resume_events": pause_resume,
            },
            source_tables=["customer_plans", "customer_todos"],
            freshness="14d",
            warnings=[],
        )
    except Exception:
        _log.exception("plan_progress failed for customer %s", customer_id)
        return ModulePayload(key=MODULE_KEY, status="error", payload={}, warnings=["模块加载异常"])
