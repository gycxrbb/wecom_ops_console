"""Health summary module — supports 7/14/30 day windows.

Backward-compatible: MODULE_KEY stays ``health_summary_7d``.
Real window is read from ``payload.window_days``.
"""
from __future__ import annotations

import logging

from ...schemas.context import ModulePayload
from ._health_summary_const import MODULE_KEY, clamp_window
from ._loaders import fetch_health_rows, fetch_glucose_rows, fetch_last_record_dates
from ._summarize import build_base_summary, build_trend_flags, build_data_quality
from ._glucose import build_glucose_highlights
from ._meals import build_meal_highlights

_log = logging.getLogger(__name__)


def load(conn, customer_id: int, *, window_days: int = 7) -> ModulePayload:
    """Load health summary for *customer_id* over *window_days*.

    Only 7/14/30 are accepted; other values fall back to 7.
    """
    w = clamp_window(window_days)

    # 1. Fetch daily health rows
    records = fetch_health_rows(conn, customer_id, w)

    # 2. Fetch glucose rows (independent of customer_health)
    glucose_rows = []
    try:
        glucose_rows = fetch_glucose_rows(conn, customer_id, w)
    except Exception:
        _log.warning("Glucose fetch failed for customer %s", customer_id, exc_info=True)

    # 3. If no data from either source in the window, return stale-data hint
    if not records and not glucose_rows:
        last_dates = fetch_last_record_dates(conn, customer_id)
        stale_payload: dict = {"window_days": w}
        if last_dates["health"] or last_dates["glucose"]:
            stale_payload["stale_hint"] = _build_stale_hint(last_dates, w)
            stale_payload["last_health_date"] = last_dates["health"]
            stale_payload["last_glucose_date"] = last_dates["glucose"]
            return ModulePayload(
                key=MODULE_KEY, status="partial", payload=stale_payload,
                source_tables=["customer_health", "customer_glucose"],
                freshness=f"{w}d", warnings=[],
            )
        return ModulePayload(
            key=MODULE_KEY, status="empty", payload=stale_payload,
            source_tables=["customer_health", "customer_glucose"],
            freshness=f"{w}d", warnings=[],
        )

    # 4. Base summary (backward-compatible fields) — works even if records is empty
    payload = build_base_summary(records, w)

    # 5. Glucose aggregation
    try:
        glucose_summary, glucose_highlights = build_glucose_highlights(glucose_rows)
        if glucose_summary:
            payload.update({
                "glucose_avg": glucose_summary["glucose_avg"],
                "glucose_peak": glucose_summary["glucose_peak"],
                "glucose_days": glucose_summary["glucose_days"],
                "glucose_high_days": glucose_summary["glucose_high_days"],
            })
        payload["glucose_highlights"] = glucose_highlights
    except Exception:
        _log.warning("Glucose aggregation failed for customer %s", customer_id, exc_info=True)
        payload["glucose_highlights"] = []

    # 6. Meals from customer_health JSON fields — isolated
    try:
        meal_summary, meal_highlights = build_meal_highlights(records)
        if meal_summary:
            payload.update({
                "meal_record_days": meal_summary.get("meal_record_days"),
                "meal_complete_days": meal_summary.get("meal_complete_days"),
                "water_avg_ml": meal_summary.get("water_avg_ml"),
                "water_on_target_days": meal_summary.get("water_on_target_days"),
            })
        payload["meal_highlights"] = meal_highlights
    except Exception:
        _log.warning("Meal aggregation failed for customer %s", customer_id, exc_info=True)
        payload["meal_highlights"] = []

    # 7. Trend flags & data quality
    payload["trend_flags"] = build_trend_flags(records, payload)
    payload["data_quality"] = build_data_quality(records, w)

    status = "ok" if records else "partial"
    return ModulePayload(
        key=MODULE_KEY, status=status, payload=payload,
        source_tables=["customer_health", "customer_glucose"],
        freshness=f"{w}d", warnings=[],
    )


def _build_stale_hint(last_dates: dict, window_days: int) -> str:
    """Build a human-readable hint about stale data."""
    parts = []
    if last_dates.get("health"):
        parts.append(f"健康记录止于 {last_dates['health']}")
    if last_dates.get("glucose"):
        parts.append(f"血糖记录止于 {last_dates['glucose']}")
    if not parts:
        return f"近{window_days}天无任何健康数据记录"
    return f"近{window_days}天无新增记录（" + "，".join(parts) + "）"
