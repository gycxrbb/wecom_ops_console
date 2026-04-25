"""Body composition (30-day) module — from body_comp table."""
from __future__ import annotations

import logging

from ...schemas.context import ModulePayload

_log = logging.getLogger(__name__)

MODULE_KEY = "body_comp_latest_30d"


def load(conn, customer_id: int) -> ModulePayload:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT date, weight, bmi, body_fat, vis_fat,
                   muscle, skeletal, body_score, body_age, heart_rate
            FROM body_comp
            WHERE customer_id = %s
              AND date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            ORDER BY date ASC
            """,
            (customer_id,),
        )
        rows = cur.fetchall()

    if not rows:
        return ModulePayload(key=MODULE_KEY, status="empty", payload={})

    records = []
    for r in rows:
        rec = dict(r)
        if rec.get("date"):
            rec["date"] = str(rec["date"])
        records.append(rec)

    latest = records[-1]

    # Build latest summary text
    parts = []
    for k, unit in [("weight", "kg"), ("bmi", ""), ("body_fat", "%"), ("vis_fat", ""),
                     ("muscle", "kg"), ("body_score", "分")]:
        v = latest.get(k)
        if v is not None:
            label_map = {"weight": "体重", "bmi": "BMI", "body_fat": "体脂率",
                         "vis_fat": "内脏脂肪", "muscle": "肌肉量", "body_score": "身体评分"}
            parts.append(f"{label_map[k]}{v}{unit}")
    latest_text = "，".join(parts) if parts else None

    # Trend: first vs last
    first = records[0]
    trend_parts = []
    for key, unit in [("weight", "kg"), ("bmi", ""), ("body_fat", "%"), ("vis_fat", ""), ("muscle", "kg")]:
        v_first = first.get(key)
        v_last = latest.get(key)
        if v_first is not None and v_last is not None:
            try:
                diff = round(float(v_last) - float(v_first), 2)
                sign = "+" if diff > 0 else ""
                label_map = {"weight": "体重", "bmi": "BMI", "body_fat": "体脂率",
                             "vis_fat": "内脏脂肪", "muscle": "肌肉量"}
                trend_parts.append(f"{label_map[key]}{sign}{diff}{unit}")
            except (TypeError, ValueError):
                pass
    trend_text = "，".join(trend_parts) if trend_parts else None

    return ModulePayload(
        key=MODULE_KEY,
        status="ok",
        payload={
            "days": len(records),
            "latest": latest_text,
            "trend": trend_text,
        },
        source_tables=["body_comp"],
        freshness="30d",
        warnings=[],
    )
