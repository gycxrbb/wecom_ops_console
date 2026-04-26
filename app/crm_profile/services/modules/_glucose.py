"""Blood-glucose aggregation from customer_glucose.points."""
from __future__ import annotations

import json
import logging
from typing import Any

from ._health_summary_const import GLUCOSE_HIGH_THRESHOLD, GLUCOSE_LOW_THRESHOLD

_log = logging.getLogger(__name__)


def build_glucose_highlights(
    glucose_rows: list[dict],
) -> tuple[dict | None, list[dict]]:
    """Aggregate glucose rows into a summary dict + highlights list.

    Returns (summary_or_None, highlights).
    summary keys: glucose_avg, glucose_peak, glucose_low, glucose_days,
                  glucose_high_days, glucose_low_days
    highlights: up to 2 dicts with the highest amplitude —
                {"date", "peak", "peak_time", "amplitude"}
    """
    if not glucose_rows:
        return None, []

    daily_stats: list[dict[str, Any]] = []

    for row in glucose_rows:
        pts = _parse_points(row.get("points"))
        if not pts:
            continue
        vals = [p.get("val") for p in pts if p.get("val") is not None]
        if not vals:
            continue

        day_max = max(vals)
        day_min = min(vals)
        peak_pt = next((p for p in pts if p.get("val") == day_max), None)

        daily_stats.append({
            "date": row.get("date", ""),
            "min": day_min,
            "max": day_max,
            "avg": round(sum(vals) / len(vals), 1),
            "amplitude": round(day_max - day_min, 1),
            "peak_time": peak_pt.get("time", "") if peak_pt else "",
        })

    if not daily_stats:
        return None, []

    all_avgs = [d["avg"] for d in daily_stats]
    all_maxs = [d["max"] for d in daily_stats]
    all_mins = [d["min"] for d in daily_stats]

    summary = {
        "glucose_avg": round(sum(all_avgs) / len(all_avgs), 1),
        "glucose_peak": round(max(all_maxs), 1),
        "glucose_low": round(min(all_mins), 1),
        "glucose_days": len(daily_stats),
        "glucose_high_days": sum(1 for d in daily_stats if d["max"] >= GLUCOSE_HIGH_THRESHOLD),
        "glucose_low_days": sum(1 for d in daily_stats if d["min"] <= GLUCOSE_LOW_THRESHOLD),
    }

    # Top 1-2 days by amplitude
    by_amp = sorted(daily_stats, key=lambda d: d["amplitude"], reverse=True)
    highlights = [
        {
            "date": d["date"],
            "peak": d["max"],
            "peak_time": d["peak_time"],
            "amplitude": d["amplitude"],
        }
        for d in by_amp[:2]
    ]

    return summary, highlights


def _parse_points(raw: Any) -> list[dict] | None:
    """Safely parse the points JSON field."""
    if raw is None:
        return None
    try:
        pts = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(pts, list):
            return pts
    except (json.JSONDecodeError, TypeError):
        _log.debug("Failed to parse glucose points: %s...", str(raw)[:80])
    return None
