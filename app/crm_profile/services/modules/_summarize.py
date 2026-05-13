"""Base summary builder (backward-compatible fields) + trend flags + data quality."""
from __future__ import annotations

from ._health_summary_const import WATER_TARGET_ML, WEIGHT_DIVISOR

# Precision registry — each metric's unit and decimal places for structured output.
FIELD_FORMATS = {
    "weight": {"unit": "kg", "precision": 2},
    "blood_pressure_avg_sbp": {"unit": "mmHg", "precision": 0},
    "blood_pressure_avg_dbp": {"unit": "mmHg", "precision": 0},
    "fbs_avg": {"unit": "mmol/L", "precision": 1},
    "pbs_avg": {"unit": "mmol/L", "precision": 1},
    "water_avg_ml": {"unit": "ml", "precision": 0},
    "kcal_avg": {"unit": "kcal", "precision": 0},
    "sleep_avg_min": {"unit": "min", "precision": 0},
    "step_avg": {"unit": "步", "precision": 0},
}


def _avg(vals: list) -> float | None:
    clean = [float(v) for v in vals if v is not None]
    return round(sum(clean) / len(clean), 1) if clean else None


def _latest_or_none(records: list[dict], key: str) -> float | str | None:
    for rec in reversed(records):
        v = rec.get(key)
        if v is not None:
            return v
    return None


def build_base_summary(records: list[dict], window_days: int, height_cm: float | None = None) -> dict:
    """Build the backward-compatible payload from customer_health rows."""
    raw_weights = [rec["weight"] for rec in records if rec.get("weight") is not None]
    weights = [round(w / WEIGHT_DIVISOR, 2) for w in raw_weights]
    sbps = [rec["blood_sbp"] for rec in records if rec.get("blood_sbp") is not None]
    dbps = [rec["blood_dbp"] for rec in records if rec.get("blood_dbp") is not None]
    fbs_list = [rec["fbs"] for rec in records if rec.get("fbs") is not None]
    pbs_list = [rec["pbs"] for rec in records if rec.get("pbs") is not None]
    steps = [rec["step_count"] for rec in records if rec.get("step_count") not in (None, 0)]
    sleep_mins = [rec["sleep_min"] for rec in records if rec.get("sleep_min") not in (None, 0)]
    kcals = [rec["kcal"] for rec in records if rec.get("kcal") is not None]
    hba1c_list = [rec["hba1c"] for rec in records if rec.get("hba1c") is not None]

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

    result = {
        "days": len(records),
        "window_days": window_days,
        # Backward-compatible string fields
        "weight": weights[-1] if weights else None,
        "weight_trend": f"{weights[0]} → {weights[-1]}" if len(weights) >= 2 else None,
        "blood_pressure": bp_summary,
        "glucose": glucose_summary,
        "sleep": sleep_summary,
        "activity": activity_summary,
        "diet": diet_summary,
        "symptoms": "；".join(symptoms_list) if symptoms_list else None,
        # Structured numeric fields
        "blood_pressure_avg_sbp": int(round(sum(sbps) / len(sbps))) if sbps else None,
        "blood_pressure_avg_dbp": int(round(sum(dbps) / len(dbps))) if dbps else None,
        "fbs_avg": _avg(fbs_list),
        "pbs_avg": _avg(pbs_list),
        "kcal_avg": int(round(sum(kcals) / len(kcals))) if kcals else None,
        "sleep_avg_min": int(round(sum(sleep_mins) / len(sleep_mins))) if sleep_mins else None,
        "step_avg": int(round(sum(steps) / len(steps))) if steps else None,
        "hba1c_latest": _avg(hba1c_list[-1:]) if hba1c_list else None,
        "hba1c_avg": _avg(hba1c_list) if hba1c_list else None,
    }

    # BMI from latest weight + height
    latest_weight = weights[-1] if weights else None
    if latest_weight and height_cm and height_cm > 0:
        height_m = height_cm / 100.0
        result["bmi"] = round(latest_weight / (height_m * height_m), 1)

    return result


def build_trend_flags(records: list[dict], payload: dict) -> list[str]:
    """Generate up to 5 trend flag strings."""
    flags: list[str] = []

    # Weight direction
    raw_weights = [rec["weight"] for rec in records if rec.get("weight") is not None]
    if len(raw_weights) >= 2:
        w_start = round(raw_weights[0] / WEIGHT_DIVISOR, 2)
        w_end = round(raw_weights[-1] / WEIGHT_DIVISOR, 2)
        diff = w_end - w_start
        if diff < -0.5:
            flags.append(f"体重下降趋势（{w_start}→{w_end} kg）")
        elif diff > 0.5:
            flags.append(f"体重上升趋势（{w_start}→{w_end} kg）")

    # Water below target
    water_vals = [rec["water_ml"] for rec in records if rec.get("water_ml") is not None]
    if water_vals and sum(1 for w in water_vals if w < WATER_TARGET_ML) > len(water_vals) * 0.5:
        flags.append("饮水达标率偏低")

    # Glucose high days
    gh = payload.get("glucose_high_days", 0)
    if gh and gh > 0:
        flags.append(f"血糖偏高天数 {gh} 天")

    return flags[:5]


def build_data_quality(records: list[dict], window_days: int) -> dict:
    """Compute data quality metrics."""
    total = len(records)
    missing_weight = sum(1 for r in records if r.get("weight") is None)
    missing_water = sum(1 for r in records if r.get("water_ml") is None)
    return {
        "total_record_days": total,
        "expected_days": window_days,
        "missing_weight_days": missing_weight,
        "missing_water_days": missing_water,
    }
