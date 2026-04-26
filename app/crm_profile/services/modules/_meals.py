"""Meal JSON parsing and water aggregation from customer_health rows."""
from __future__ import annotations

import json
import logging
from typing import Any

from ._health_summary_const import WATER_TARGET_ML

_log = logging.getLogger(__name__)

_MEAL_KEYS = ("breakfast_data", "lunch_data", "dinner_data", "snack_data")
_MEAL_TYPE_MAP = {
    "breakfast_data": "breakfast",
    "lunch_data": "lunch",
    "dinner_data": "dinner",
    "snack_data": "snack",
}


def build_meal_highlights(
    records: list[dict],
) -> tuple[dict | None, list[dict]]:
    """Parse meal/water data from customer_health rows.

    Returns (summary_or_None, highlights_for_last_3_days).
    summary keys: meal_record_days, meal_complete_days, water_avg_ml, water_on_target_days
    highlights: list of {"date", "meals": [{"type", "name", "kcal", "time"}]}
    """
    if not records:
        return None, []

    water_vals: list[float] = []
    water_on_target = 0
    meal_record_days = 0
    meal_complete_days = 0
    meal_rows: list[dict] = []  # for building highlights

    for rec in records:
        day_meals: list[dict] = []
        has_any = False
        complete = True

        for key in _MEAL_KEYS:
            parsed = _safe_parse_meal(rec.get(key))
            mtype = _MEAL_TYPE_MAP[key]
            if parsed is not None:
                has_any = True
                day_meals.append({
                    "type": mtype,
                    "name": parsed.get("name") or parsed.get("des") or "",
                    "kcal": _to_float(parsed.get("kcal")),
                    "time": parsed.get("time") or "",
                })
            elif key != "snack_data":
                # snack is optional; breakfast/lunch/dinner missing = incomplete
                complete = False

        if has_any:
            meal_record_days += 1
            if complete:
                meal_complete_days += 1
            meal_rows.append({"date": rec.get("record_date", ""), "meals": day_meals})

        # Water
        w = rec.get("water_ml")
        if w is not None:
            water_vals.append(float(w))
            if float(w) >= WATER_TARGET_ML:
                water_on_target += 1

    if meal_record_days == 0 and not water_vals:
        return None, []

    summary: dict = {}
    if meal_record_days > 0:
        summary["meal_record_days"] = meal_record_days
        summary["meal_complete_days"] = meal_complete_days
    if water_vals:
        summary["water_avg_ml"] = round(sum(water_vals) / len(water_vals), 0)
        summary["water_on_target_days"] = water_on_target

    # Highlights: last 3 days with meal data
    highlights = meal_rows[-3:] if meal_rows else []

    return summary if summary else None, highlights


def _safe_parse_meal(raw: Any) -> dict | None:
    """Try to parse a meal JSON field; return None on any failure."""
    if raw is None:
        return None
    try:
        obj = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, list) and obj:
            # some rows store an array with one element
            first = obj[0]
            return first if isinstance(first, dict) else None
    except (json.JSONDecodeError, TypeError, IndexError):
        pass
    return None


def _to_float(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
