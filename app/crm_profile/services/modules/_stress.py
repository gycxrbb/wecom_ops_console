"""Stress and medication aggregation."""
from __future__ import annotations

import json
import logging
from typing import Any

_log = logging.getLogger(__name__)

from ._registry import STRESS_HIGH as STRESS_HIGH_THRESHOLD


def build_stress_summary(stress_rows: list[dict], health_records: list[dict]) -> dict | None:
    """Aggregate stress from customer_stress points + customer_health.stress/medication.

    Returns dict with:
      - stress_avg, stress_high_days, stress_days (from points)
      - medication (from customer_health JSON, latest non-null)
      - stress_text (from customer_health.stress, latest non-null)
    or None if no data from either source.
    """
    has_points_data = False
    result: dict[str, Any] = {}

    # 1. Aggregate from customer_stress.points
    daily_stats: list[dict] = []
    for row in stress_rows:
        pts = _parse_points(row.get("points"))
        if not pts:
            continue
        vals = [p.get("val") for p in pts if p.get("val") is not None]
        if not vals:
            continue
        daily_stats.append({
            "date": row.get("date", ""),
            "avg": round(sum(vals) / len(vals), 0),
        })

    if daily_stats:
        all_avgs = [d["avg"] for d in daily_stats]
        result["stress_avg"] = int(round(sum(all_avgs) / len(all_avgs)))
        result["stress_days"] = len(daily_stats)
        result["stress_high_days"] = sum(1 for d in daily_stats if d["avg"] >= STRESS_HIGH_THRESHOLD)
        has_points_data = True

    # 2. Latest stress text and medication from customer_health
    for rec in reversed(health_records):
        stress_text = rec.get("stress")
        if stress_text:
            result["stress_text"] = stress_text
            has_points_data = True
            break

    medication = _extract_latest_medication(health_records)
    if medication:
        result["medication"] = medication
        has_points_data = True

    if not has_points_data:
        return None

    result["source"] = "customer_stress+customer_health"
    return result


def _extract_latest_medication(records: list[dict]) -> Any:
    """Get the latest non-null medication JSON from customer_health rows."""
    for rec in reversed(records):
        raw = rec.get("medication")
        if not raw:
            continue
        try:
            med = json.loads(raw) if isinstance(raw, str) else raw
            if med:
                return med
        except (json.JSONDecodeError, TypeError):
            return raw
    return None


def _parse_points(raw: Any) -> list[dict] | None:
    """Safely parse the points JSON field."""
    if raw is None:
        return None
    try:
        pts = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(pts, list):
            return pts
    except (json.JSONDecodeError, TypeError):
        pass
    return None
