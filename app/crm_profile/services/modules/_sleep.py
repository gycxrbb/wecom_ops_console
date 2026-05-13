"""Sleep structure aggregation from customer_sleep."""
from __future__ import annotations

from typing import Any


def build_sleep_highlights(records: list[dict]) -> dict | None:
    """Aggregate sleep rows into a structured summary.

    Returns dict with:
      - sleep_avg_min, sleep_avg_deep_min, sleep_avg_rem_min
      - sleep_avg_score, sleep_avg_rhr, sleep_record_days
    or None if no data.
    """
    if not records:
        return None

    total_mins = [r["total_min"] for r in records if r.get("total_min") is not None]
    deep_mins = [r["deep_time"] for r in records if r.get("deep_time") is not None]
    rem_mins = [r["rem"] for r in records if r.get("rem") is not None]
    scores = [r["score"] for r in records if r.get("score") is not None]
    rhrs = [r["rhr"] for r in records if r.get("rhr") is not None]

    if not total_mins:
        return None

    result: dict[str, Any] = {
        "sleep_record_days": len(total_mins),
        "sleep_avg_min": int(round(sum(total_mins) / len(total_mins))),
    }
    if deep_mins:
        result["sleep_avg_deep_min"] = int(round(sum(deep_mins) / len(deep_mins)))
    if rem_mins:
        result["sleep_avg_rem_min"] = int(round(sum(rem_mins) / len(rem_mins)))
    if scores:
        result["sleep_avg_score"] = int(round(sum(scores) / len(scores)))
    if rhrs:
        result["sleep_avg_rhr"] = int(round(sum(rhrs) / len(rhrs)))

    # Source metadata for traceability
    result["source"] = "customer_sleep"

    return result
