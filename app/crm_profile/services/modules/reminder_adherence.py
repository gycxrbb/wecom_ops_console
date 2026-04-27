"""Reminder adherence module — reminder profiling.

Sources: customer_reminders.
"""
from __future__ import annotations

import logging

from ...schemas.context import ModulePayload

_log = logging.getLogger(__name__)

MODULE_KEY = "reminder_adherence_14d"

_BUSINESS_TYPE_MAP = {
    0: "其他", 1: "饮水", 2: "运动", 3: "睡眠",
    4: "饮食", 5: "血糖", 6: "体重", 7: "服药", 8: "冥想",
}


def load(conn, customer_id: int) -> ModulePayload:
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt, "
                "COALESCE(SUM(triggered_count), 0) AS total_triggers, "
                "MAX(last_triggered_at) AS last_at "
                "FROM customer_reminders WHERE customer_id = %s AND status = 1",
                (customer_id,),
            )
            summary_row = cur.fetchone()

        if not summary_row or summary_row["cnt"] == 0:
            return ModulePayload(key=MODULE_KEY, status="empty", payload={})

        active_count = int(summary_row["cnt"])
        trigger_total = int(summary_row["total_triggers"])
        last_at = str(summary_row["last_at"])[:19] if summary_row["last_at"] else None

        with conn.cursor() as cur:
            cur.execute(
                "SELECT business_type, COUNT(*) AS cnt, COALESCE(SUM(triggered_count), 0) AS triggers "
                "FROM customer_reminders "
                "WHERE customer_id = %s AND status = 1 GROUP BY business_type",
                (customer_id,),
            )
            type_rows = cur.fetchall()

        by_type = []
        for r in type_rows:
            bt = int(r["business_type"])
            by_type.append({
                "type": _BUSINESS_TYPE_MAP.get(bt, f"类型{bt}"),
                "count": int(r["cnt"]),
                "triggers": int(r["triggers"]),
            })

        from datetime import datetime
        follow_rate = "0%"
        if last_at:
            try:
                last_dt = datetime.strptime(last_at[:10], "%Y-%m-%d")
                days = max((datetime.now() - last_dt).days, 1)
                days = min(days, 14)
                follow_rate = f"{round(trigger_total / days / active_count * 100)}%" if active_count > 0 else "0%"
                if int(follow_rate.rstrip("%")) > 100:
                    follow_rate = "100%"
            except ValueError:
                pass

        return ModulePayload(
            key=MODULE_KEY,
            status="ok",
            payload={
                "active_reminder_count": active_count,
                "reminders_by_business_type": by_type,
                "trigger_count_total": trigger_total,
                "last_triggered_at": last_at,
                "estimated_follow_through_rate": follow_rate,
            },
            source_tables=["customer_reminders"],
            freshness="14d",
            warnings=[],
        )
    except Exception:
        _log.exception("reminder_adherence failed for customer %s", customer_id)
        return ModulePayload(key=MODULE_KEY, status="error", payload={}, warnings=["模块加载异常"])
