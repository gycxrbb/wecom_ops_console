"""Learning engagement module — course record profiling.

Sources: customer_course_record.
"""
from __future__ import annotations

import logging

from ...schemas.context import ModulePayload

_log = logging.getLogger(__name__)

MODULE_KEY = "learning_engagement_30d"


def load(conn, customer_id: int) -> ModulePayload:
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) AS in_progress, "
                "SUM(CASE WHEN status = 2 THEN 1 ELSE 0 END) AS completed, "
                "SUM(CASE WHEN status = 0 THEN 1 ELSE 0 END) AS not_started, "
                "COALESCE(SUM(study_seconds), 0) AS total_study_seconds, "
                "MAX(CASE WHEN status IN (1, 2) THEN updated_at ELSE NULL END) AS last_learning_at "
                "FROM customer_course_record WHERE customer_id = %s",
                (customer_id,),
            )
            row = cur.fetchone()

        if not row or row["total"] == 0:
            return ModulePayload(key=MODULE_KEY, status="empty", payload={})

        total = int(row["total"])
        in_progress = int(row["in_progress"] or 0)
        completed = int(row["completed"] or 0)
        completion_rate = f"{round(completed / total * 100)}%" if total > 0 else "0%"
        study_minutes = int(row["total_study_seconds"] or 0) // 60
        last_at = str(row["last_learning_at"])[:19] if row["last_learning_at"] else None

        return ModulePayload(
            key=MODULE_KEY,
            status="ok",
            payload={
                "course_total_assigned": total,
                "course_in_progress": in_progress,
                "course_completed": completed,
                "completion_rate": completion_rate,
                "study_minutes_30d": study_minutes,
                "last_learning_at": last_at,
            },
            source_tables=["customer_course_record"],
            freshness="30d",
            warnings=[],
        )
    except Exception:
        _log.exception("learning_engagement failed for customer %s", customer_id)
        return ModulePayload(key=MODULE_KEY, status="error", payload={}, warnings=["模块加载异常"])
