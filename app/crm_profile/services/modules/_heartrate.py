"""Heart rate aggregation from customer_heartrate.points."""
from __future__ import annotations

import json
import logging
from typing import Any

_log = logging.getLogger(__name__)

from ._registry import HR_HIGH as HR_HIGH_THRESHOLD, HR_LOW as HR_LOW_THRESHOLD


def build_heartrate_summary(rows: list[dict]) -> dict | None:
    """Aggregate heart rate rows (date + points JSON) into a summary.

    Returns dict with:
      - hr_avg, hr_max, hr_min, hr_days
      - hr_high_days (avg >= 100), hr_low_days (avg <= 50)
      - source: "customer_heartrate"
    or None if no data.
    """
    if not rows:
        return None

    daily_stats: list[dict] = []
    for row in rows:
        pts = _parse_points(row.get("points"))
        if not pts:
            continue
        vals = [p.get("val") for p in pts if p.get("val") is not None]
        if not vals:
            continue
        daily_stats.append({
            "date": row.get("date", ""),
            "avg": round(sum(vals) / len(vals), 0),
            "max": max(vals),
            "min": min(vals),
        })

    if not daily_stats:
        return None

    all_avgs = [d["avg"] for d in daily_stats]
    all_maxs = [d["max"] for d in daily_stats]
    all_mins = [d["min"] for d in daily_stats]

    return {
        "hr_avg": int(round(sum(all_avgs) / len(all_avgs))),
        "hr_max": int(max(all_maxs)),
        "hr_min": int(min(all_mins)),
        "hr_days": len(daily_stats),
        "hr_high_days": sum(1 for d in daily_stats if d["avg"] >= HR_HIGH_THRESHOLD),
        "hr_low_days": sum(1 for d in daily_stats if d["avg"] <= HR_LOW_THRESHOLD),
        "source": "customer_heartrate",
    }


def _parse_points(raw: Any) -> list[dict] | None:
    """Safely parse the points JSON field."""
    if raw is None:
        return None
    try:
        pts = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(pts, list):
            return pts
    except (json.JSONDecodeError, TypeError):
        _log.debug("Failed to parse heartrate points: %s...", str(raw)[:80])
    return None
