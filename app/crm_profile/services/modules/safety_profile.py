"""Safety profile module — health conditions & restrictions from customer_info."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime

from ...schemas.context import ModulePayload

_log = logging.getLogger(__name__)

MODULE_KEY = "safety_profile"

_FIELDS = (
    "health_condition, health_condition_user, genetic_history, allergies, "
    "medical_history, sport_injuries, recipel, doctor_recipel, "
    "food_recipel, sport_recipel, sleep_recipel, nutrition_recipel"
)
_META_FIELDS = "id, created_at, updated_at, archived_at, is_archived"
_SELECT_FIELDS = f"{_META_FIELDS}, {_FIELDS}"


def _safe_str(val) -> str | None:
    if val is None:
        return None
    text = str(val).strip()
    return text if text else None


def _flatten_value(v) -> str | None:
    """Recursively flatten a JSON value into readable text."""
    if v is None:
        return None
    if isinstance(v, str):
        text = v.strip()
        return text if text else None
    if isinstance(v, (int, float, bool)):
        return str(v)
    if isinstance(v, dict):
        parts = []
        for k, val in v.items():
            child = _flatten_value(val)
            if child:
                label = str(k).replace("_", " ").title()
                parts.append(f"{label}: {child}")
        return "；".join(parts) if parts else None
    if isinstance(v, list):
        parts = [_flatten_value(item) for item in v]
        parts = [p for p in parts if p]
        return "；".join(parts) if parts else None
    return str(v)


def _extract_text(val) -> str | None:
    """Extract readable text from a value that might be JSON."""
    raw = _safe_str(val)
    if raw is None:
        return None
    try:
        obj = json.loads(raw)
        return _flatten_value(obj)
    except (json.JSONDecodeError, TypeError):
        return raw


def _iso_datetime(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _format_snapshot_label(raw: dict) -> str:
    reference = raw.get("updated_at") or raw.get("archived_at") or raw.get("created_at")
    iso = _iso_datetime(reference)
    if iso:
        return iso.split(" ")[0]
    return f"记录 #{raw.get('id')}"


def _snapshot_meta(raw: dict) -> dict:
    is_current = raw.get("is_archived") in (0, None)
    reference_time = _iso_datetime(raw.get("updated_at") or raw.get("archived_at") or raw.get("created_at"))
    return {
        "snapshot_id": raw.get("id"),
        "label": _format_snapshot_label(raw),
        "reference_time": reference_time,
        "is_current": is_current,
        "is_archived": bool(raw.get("is_archived") == 1),
    }


def list_snapshots(conn, customer_id: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_META_FIELDS}
            FROM customer_info
            WHERE customer_id = %s
            ORDER BY
              CASE WHEN is_archived = 0 OR is_archived IS NULL THEN 0 ELSE 1 END,
              COALESCE(updated_at, archived_at, created_at) DESC,
              id DESC
            """,
            (customer_id,),
        )
        rows = cur.fetchall()

    snapshots = []
    for row in rows:
        meta = _snapshot_meta(dict(row))
        meta["display_label"] = (
            f"当前档案（{meta['label']}）"
            if meta["is_current"]
            else f"{meta['label']} 历史档案"
        )
        snapshots.append(meta)
    return snapshots


def _fetch_snapshot_row(conn, customer_id: int, snapshot_id: int | None) -> dict | None:
    if snapshot_id is not None:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_SELECT_FIELDS}
                FROM customer_info
                WHERE customer_id = %s AND id = %s
                LIMIT 1
                """,
                (customer_id, snapshot_id),
            )
            row = cur.fetchone()
        return dict(row) if row else None

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_SELECT_FIELDS}
            FROM customer_info
            WHERE customer_id = %s AND (is_archived = 0 OR is_archived IS NULL)
            ORDER BY id DESC
            LIMIT 1
            """,
            (customer_id,),
        )
        row = cur.fetchone()

    if row:
        return dict(row)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_SELECT_FIELDS}
            FROM customer_info
            WHERE customer_id = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (customer_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def load(conn, customer_id: int, snapshot_id: int | None = None) -> ModulePayload:
    warnings: list[str] = []

    raw = _fetch_snapshot_row(conn, customer_id, snapshot_id)
    if not raw:
        return ModulePayload(key=MODULE_KEY, status="empty", payload={}, warnings=[])

    snapshot_meta = _snapshot_meta(raw)
    if snapshot_id is None and snapshot_meta["is_archived"]:
        warnings.append("使用归档记录，非最新档案")
    if snapshot_id is not None and snapshot_meta["is_archived"]:
        warnings.append("当前正在查看历史档案")

    # Build health_condition_summary
    parts = []
    for k in ("health_condition", "health_condition_user", "genetic_history"):
        v = _extract_text(raw.get(k))
        if v:
            parts.append(v)
    health_condition_summary = "；".join(parts) if parts else None

    # Build prescription_summary from multiple recipel fields
    rx_parts = []
    labels = {
        "recipel": "综合处方", "doctor_recipel": "医生处方",
        "food_recipel": "饮食处方", "sport_recipel": "运动处方",
        "sleep_recipel": "睡眠处方", "nutrition_recipel": "营养处方",
    }
    for k, label in labels.items():
        v = _extract_text(raw.get(k))
        if v:
            rx_parts.append(f"【{label}】{v}")
    prescription_summary = "\n".join(rx_parts) if rx_parts else None

    # Contraindications from sport_injuries + medical_history
    contra_parts = []
    for k in ("sport_injuries", "medical_history"):
        v = _extract_text(raw.get(k))
        if v:
            contra_parts.append(v)
    contraindications = "；".join(contra_parts) if contra_parts else None

    # Missing critical fields
    critical = [
        ("health_condition", "健康状况"),
        ("allergies", "过敏信息"),
        ("sport_injuries", "运动损伤"),
    ]
    missing = [label for key, label in critical if not _safe_str(raw.get(key))]
    if missing:
        warnings.append(f"缺失关键字段：{'、'.join(missing)}")

    # Derive risk_level
    has_condition = bool(_safe_str(raw.get("health_condition")))
    has_allergies = bool(_safe_str(raw.get("allergies")))
    has_injuries = bool(_safe_str(raw.get("sport_injuries")))
    if has_condition and (has_allergies or has_injuries):
        risk_level = "high"
    elif has_condition or has_allergies or has_injuries:
        risk_level = "medium"
    else:
        risk_level = "low"

    return ModulePayload(
        key=MODULE_KEY,
        status="ok",
        payload={
            "health_condition_summary": health_condition_summary,
            "medical_history": _extract_text(raw.get("medical_history")),
            "genetic_history": _extract_text(raw.get("genetic_history")),
            "allergies": _extract_text(raw.get("allergies")),
            "sport_injuries": _extract_text(raw.get("sport_injuries")),
            "prescription_summary": prescription_summary,
            "contraindications": contraindications,
            "risk_level": risk_level,
            "missing_critical_fields": missing if missing else None,
            "snapshot": snapshot_meta,
        },
        source_tables=["customer_info"],
        freshness="latest" if snapshot_meta["is_current"] else "historical",
        warnings=warnings,
    )
