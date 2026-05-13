"""Exercise aggregation from customer_sport."""
from __future__ import annotations

import json
import logging
from typing import Any

_log = logging.getLogger(__name__)


def build_exercise_highlights(records: list[dict]) -> dict | None:
    """Aggregate sport rows into a structured summary.

    Returns dict with:
      - exercise_record_days, exercise_avg_calories, exercise_total_calories
      - exercise_avg_steps, exercise_types (distinct type names)
    or None if no data.
    """
    if not records:
        return None

    calories_list = [r["calories"] for r in records if r.get("calories") is not None]
    steps_list = [r["total_steps"] for r in records if r.get("total_steps") is not None]
    type_names: set[str] = set()

    for rec in records:
        items = _parse_items(rec.get("items"))
        for item in items:
            name = item.get("type") or item.get("name") or item.get("sport_type")
            if name:
                type_names.add(str(name))

    if not calories_list and not steps_list:
        return None

    result: dict[str, Any] = {
        "exercise_record_days": len(records),
        "source": "customer_sport",
    }
    if calories_list:
        result["exercise_total_calories"] = int(sum(calories_list))
        result["exercise_avg_calories"] = int(round(sum(calories_list) / len(calories_list)))
    if steps_list:
        result["exercise_avg_steps"] = int(round(sum(steps_list) / len(steps_list)))
    if type_names:
        result["exercise_types"] = sorted(type_names)

    return result


def _parse_items(raw: Any) -> list[dict]:
    """Safely parse the items JSON field."""
    if raw is None:
        return []
    try:
        items = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(items, list):
            return [i for i in items if isinstance(i, dict)]
    except (json.JSONDecodeError, TypeError):
        pass
    return []
