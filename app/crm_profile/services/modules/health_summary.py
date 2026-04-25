"""Health summary (7-day) module — from customer_health table."""
from __future__ import annotations

import logging

from ...schemas.context import ModulePayload

_log = logging.getLogger(__name__)

MODULE_KEY = "health_summary_7d"


def _avg(vals: list) -> float | None:
    clean = [float(v) for v in vals if v is not None]
    return round(sum(clean) / len(clean), 1) if clean else None


def _latest_or_none(records: list[dict], key: str) -> float | str | None:
    for rec in reversed(records):
        v = rec.get(key)
        if v is not None:
            return v
    return None


def load(conn, customer_id: int) -> ModulePayload:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT record_date, weight, blood_sbp, blood_dbp,
                   fbs, pbs, hba1c, water_ml, sleep_min, sleep_des,
                   step_count, symptoms, kcal, cho, fat, protein,
                   fiber, kcal_out, stress, medication
            FROM customer_health
            WHERE customer_id = %s
              AND record_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            ORDER BY record_date ASC
            """,
            (customer_id,),
        )
        rows = cur.fetchall()

    if not rows:
        return ModulePayload(key=MODULE_KEY, status="empty", payload={})

    records = []
    for r in rows:
        rec = dict(r)
        if rec.get("record_date"):
            rec["record_date"] = str(rec["record_date"])
        records.append(rec)

    # Build summary scalars — weight is stored ×100 (6500 → 65.0 kg)
    raw_weights = [rec["weight"] for rec in records if rec.get("weight") is not None]
    weights = [round(w / 100, 1) for w in raw_weights]
    sbps = [rec["blood_sbp"] for rec in records if rec.get("blood_sbp") is not None]
    dbps = [rec["blood_dbp"] for rec in records if rec.get("blood_dbp") is not None]
    fbs_list = [rec["fbs"] for rec in records if rec.get("fbs") is not None]
    pbs_list = [rec["pbs"] for rec in records if rec.get("pbs") is not None]
    steps = [rec["step_count"] for rec in records if rec.get("step_count") is not None]
    sleep_mins = [rec["sleep_min"] for rec in records if rec.get("sleep_min") is not None]
    kcals = [rec["kcal"] for rec in records if rec.get("kcal") is not None]

    bp_summary = None
    if sbps or dbps:
        parts = []
        if sbps:
            parts.append(f"收缩压 {_avg(sbps)} mmHg")
        if dbps:
            parts.append(f"舒张压 {_avg(dbps)} mmHg")
        bp_summary = " / ".join(parts)

    glucose_parts = []
    if fbs_list:
        glucose_parts.append(f"空腹 {_avg(fbs_list)} mmol/L")
    if pbs_list:
        glucose_parts.append(f"餐后 {_avg(pbs_list)} mmol/L")
    glucose_summary = "；".join(glucose_parts) if glucose_parts else None

    sleep_summary = None
    if sleep_mins:
        avg_h = round(sum(sleep_mins) / len(sleep_mins) / 60, 1)
        sleep_summary = f"均值 {avg_h}h"

    activity_summary = None
    if steps:
        activity_summary = f"日均 {int(sum(steps) / len(steps))} 步"

    diet_summary = None
    if kcals:
        diet_summary = f"日均 {_avg(kcals)} kcal"

    symptoms_list = [rec["symptoms"] for rec in records if rec.get("symptoms")]

    return ModulePayload(
        key=MODULE_KEY,
        status="ok",
        payload={
            "days": len(records),
            "weight": weights[-1] if weights else None,
            "weight_trend": f"{weights[0]} → {weights[-1]}" if len(weights) >= 2 else None,
            "blood_pressure": bp_summary,
            "glucose": glucose_summary,
            "sleep": sleep_summary,
            "activity": activity_summary,
            "diet": diet_summary,
            "symptoms": "；".join(symptoms_list) if symptoms_list else None,
        },
        source_tables=["customer_health"],
        freshness="7d",
        warnings=[],
    )
