"""Health summary module — supports 7/14/30 day windows.

Backward-compatible: MODULE_KEY stays ``health_summary_7d``.
Real window is read from ``payload.window_days``.
"""
from __future__ import annotations

import logging

from ...schemas.context import ModulePayload
from ._health_summary_const import MODULE_KEY, clamp_window
from ._loaders import (
    fetch_health_rows, fetch_glucose_rows, fetch_last_record_dates,
    fetch_sleep_rows, fetch_sport_rows, fetch_heartrate_rows, fetch_stress_rows,
    fetch_customer_height,
)
from ._summarize import build_base_summary, build_trend_flags, build_data_quality
from ._glucose import build_glucose_highlights
from ._meals import build_meal_highlights
from ._sleep import build_sleep_highlights
from ._exercise import build_exercise_highlights
from ._heartrate import build_heartrate_summary
from ._nutrition import build_nutrition_summary
from ._stress import build_stress_summary

_log = logging.getLogger(__name__)

_ALL_SOURCE_TABLES = [
    "customer_health", "customer_glucose", "customer_sleep",
    "customer_sport", "customer_heartrate", "customer_stress",
]


def load(conn, customer_id: int, *, window_days: int = 7) -> ModulePayload:
    """Load health summary for *customer_id* over *window_days*.

    Only 7/14/30 are accepted; other values fall back to 7.
    """
    w = clamp_window(window_days)

    # 1. Fetch daily health rows
    records = fetch_health_rows(conn, customer_id, w)

    # 2. Fetch glucose rows (independent of customer_health)
    glucose_rows, err = _safe_fetch(fetch_glucose_rows, conn, customer_id, w)
    warnings = [err] if err else []

    # 3. Fetch extended data sources
    sleep_rows, err = _safe_fetch(fetch_sleep_rows, conn, customer_id, w)
    if err: warnings.append(err)
    sport_rows, err = _safe_fetch(fetch_sport_rows, conn, customer_id, w)
    if err: warnings.append(err)
    heartrate_rows, err = _safe_fetch(fetch_heartrate_rows, conn, customer_id, w)
    if err: warnings.append(err)
    stress_rows, err = _safe_fetch(fetch_stress_rows, conn, customer_id, w)
    if err: warnings.append(err)

    # 4. If no data from any source, return stale-data hint
    all_rows = [records, glucose_rows, sleep_rows, sport_rows, heartrate_rows, stress_rows]
    if not any(all_rows):
        last_dates = fetch_last_record_dates(conn, customer_id)
        stale_payload: dict = {"window_days": w}
        if last_dates["health"] or last_dates["glucose"]:
            stale_payload["stale_hint"] = _build_stale_hint(last_dates, w)
            stale_payload["last_health_date"] = last_dates["health"]
            stale_payload["last_glucose_date"] = last_dates["glucose"]
            return ModulePayload(
                key=MODULE_KEY, status="partial", payload=stale_payload,
                source_tables=_ALL_SOURCE_TABLES, freshness=f"{w}d", warnings=[],
            )
        return ModulePayload(
            key=MODULE_KEY, status="empty", payload=stale_payload,
            source_tables=_ALL_SOURCE_TABLES, freshness=f"{w}d", warnings=[],
        )

    # 5. Base summary (backward-compatible fields) — works even if records is empty
    height_cm = None
    try:
        height_cm = fetch_customer_height(conn, customer_id)
    except Exception:
        _log.warning("Height fetch failed for customer %s", customer_id, exc_info=True)
    payload = build_base_summary(records, w, height_cm=height_cm)

    # 6. Glucose aggregation
    try:
        glucose_summary, glucose_highlights = build_glucose_highlights(glucose_rows)
        if glucose_summary:
            payload.update({
                "glucose_avg": glucose_summary["glucose_avg"],
                "glucose_peak": glucose_summary["glucose_peak"],
                "glucose_low": glucose_summary["glucose_low"],
                "glucose_days": glucose_summary["glucose_days"],
                "glucose_high_days": glucose_summary["glucose_high_days"],
                "glucose_low_days": glucose_summary["glucose_low_days"],
            })
        payload["glucose_highlights"] = glucose_highlights
    except Exception:
        _log.warning("Glucose aggregation failed for customer %s", customer_id, exc_info=True)
        payload["glucose_highlights"] = []

    # 7. Meals from customer_health JSON fields — isolated
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

    # 8. Sleep structure (P1)
    _safe_merge(payload, "sleep_detail", build_sleep_highlights, sleep_rows)

    # 9. Exercise (P1)
    _safe_merge(payload, "exercise_detail", build_exercise_highlights, sport_rows)

    # 10. Heart rate (P1)
    _safe_merge(payload, "heart_rate", build_heartrate_summary, heartrate_rows)

    # 11. Nutrition (P2 — from existing customer_health fields)
    _safe_merge(payload, "nutrition", build_nutrition_summary, records)

    # 12. Stress & medication (P2)
    try:
        stress_result = build_stress_summary(stress_rows, records)
        if stress_result:
            payload["stress_detail"] = stress_result
    except Exception:
        _log.warning("Stress aggregation failed for customer %s", customer_id, exc_info=True)

    # 13. Trend flags & data quality
    payload["trend_flags"] = build_trend_flags(records, payload)
    payload["data_quality"] = build_data_quality(records, w)

    # 14. Source priority: detail modules override top-level fields
    # Sleep: customer_sleep > customer_health
    if payload.get("sleep_detail"):
        sd = payload["sleep_detail"]
        payload["sleep_avg_min"] = sd["sleep_avg_min"]
        avg_h = round(sd["sleep_avg_min"] / 60, 1)
        payload["sleep"] = f"均值 {avg_h}h"

    # Steps: customer_sport > customer_health
    if payload.get("exercise_detail") and payload["exercise_detail"].get("exercise_avg_steps"):
        ed = payload["exercise_detail"]
        payload["step_avg"] = ed["exercise_avg_steps"]
        payload["activity"] = f"日均 {ed['exercise_avg_steps']} 步"

    status = "ok" if records else "partial"
    return ModulePayload(
        key=MODULE_KEY, status=status, payload=payload,
        source_tables=_ALL_SOURCE_TABLES, freshness=f"{w}d", warnings=warnings,
    )


def _safe_fetch(fetch_fn, conn, customer_id: int, window_days: int) -> tuple[list[dict], str | None]:
    """Fetch with graceful fallback on error. Returns (rows, error_msg)."""
    try:
        return fetch_fn(conn, customer_id, window_days), None
    except Exception:
        name = fetch_fn.__name__
        _log.warning("%s failed for customer %s", name, customer_id, exc_info=True)
        return [], f"{name} 加载失败"


def _safe_merge(payload: dict, key: str, build_fn, *args) -> None:
    """Build and merge into payload, swallow errors."""
    try:
        result = build_fn(*args)
        if result:
            payload[key] = result
    except Exception:
        _log.warning("%s failed", build_fn.__name__, exc_info=True)


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
