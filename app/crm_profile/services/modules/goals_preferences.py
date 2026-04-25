"""Goals & preferences module — from customer_info (same record as safety)."""
from __future__ import annotations

import logging

from ...schemas.context import ModulePayload

_log = logging.getLogger(__name__)

MODULE_KEY = "goals_preferences"

_FIELDS = (
    "goals, goal_weight, goal_hr, goal_gluc, goal_bp, "
    "diet_preference, sport_preference, sport_interests, "
    "sleep_quality, remark"
)


def _safe_str(val) -> str | None:
    if val is None or str(val).strip() == "":
        return None
    return str(val).strip()


def load(conn, customer_id: int) -> ModulePayload:
    warnings: list[str] = []

    # Try non-archived first
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_FIELDS}
            FROM customer_info
            WHERE customer_id = %s AND (is_archived = 0 OR is_archived IS NULL)
            ORDER BY id DESC
            LIMIT 1
            """,
            (customer_id,),
        )
        row = cur.fetchone()

    if not row:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_FIELDS}
                FROM customer_info
                WHERE customer_id = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (customer_id,),
            )
            row = cur.fetchone()
        if row:
            warnings.append("使用归档记录，非最新档案")

    if not row:
        return ModulePayload(key=MODULE_KEY, status="empty", payload={}, warnings=[])

    raw = dict(row)

    return ModulePayload(
        key=MODULE_KEY,
        status="ok",
        payload={
            "primary_goals": _safe_str(raw.get("goals")),
            "target_weight_kg": raw.get("goal_weight"),
            "target_heart_rate": raw.get("goal_hr"),
            "target_glucose": raw.get("goal_gluc"),
            "target_blood_pressure": raw.get("goal_bp"),
            "diet": _safe_str(raw.get("diet_preference")),
            "exercise": _safe_str(raw.get("sport_preference")) or _safe_str(raw.get("sport_interests")),
            "sleep": _safe_str(raw.get("sleep_quality")),
        },
        source_tables=["customer_info"],
        freshness="latest",
        warnings=warnings,
    )
