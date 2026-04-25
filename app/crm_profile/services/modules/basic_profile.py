"""Basic profile module — customers table core fields."""
from __future__ import annotations

import logging
from datetime import date

from ...schemas.context import ModulePayload

_log = logging.getLogger(__name__)

MODULE_KEY = "basic_profile"


def load(conn, customer_id: int) -> ModulePayload:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, title, gender, birthday,
                   height, weight, status, tags,
                   current_plan_id, is_cgm, compliance_level,
                   points, total_points, severity, survey_done,
                   created_at, updated_at
            FROM customers
            WHERE id = %s
            """,
            (customer_id,),
        )
        row = cur.fetchone()

    if not row:
        return ModulePayload(key=MODULE_KEY, status="empty", payload={})

    raw = dict(row)

    # Derived: age from birthday
    age = None
    if raw.get("birthday"):
        bday = raw["birthday"]
        if isinstance(bday, date):
            today = date.today()
            age = today.year - bday.year - ((today.month, today.day) < (bday.month, bday.day))

    # CRM stores height/weight ×100 (170cm → 17000, 65kg → 6500)
    raw_height = raw.get("height") or 0
    raw_weight = raw.get("weight") or 0
    height_cm = round(raw_height / 100, 1) if raw_height else None
    weight_kg = round(raw_weight / 100, 1) if raw_weight else None

    # Derived: BMI from height (cm) + weight (kg)
    bmi = None
    if height_cm and height_cm > 0 and weight_kg and weight_kg > 0:
        height_m = height_cm / 100.0
        bmi = round(weight_kg / (height_m * height_m), 1)

    # Map CRM status code to text
    _STATUS_MAP = {0: "未知", 1: "服务中", 2: "暂停", 3: "已结束", 4: "已归档"}
    crm_status = _STATUS_MAP.get(raw.get("status"), "未知")

    # Map gender code
    _GENDER_MAP = {0: "未知", 1: "男", 2: "女"}
    gender_text = _GENDER_MAP.get(raw.get("gender"), "未知")

    return ModulePayload(
        key=MODULE_KEY,
        status="ok",
        payload={
            "display_name": raw.get("name") or raw.get("title") or "",
            "gender": gender_text,
            "age": age,
            "height_cm": height_cm,
            "weight_kg": weight_kg,
            "bmi": bmi,
            "crm_status": crm_status,
            "tags": raw.get("tags"),
            "current_plan_id": raw.get("current_plan_id"),
            "has_cgm": bool(raw.get("is_cgm")),
            "compliance_level": raw.get("compliance_level"),
            "severity": raw.get("severity"),
            "points": raw.get("points", 0),
            "total_points": raw.get("total_points", 0),
        },
        source_tables=["customers"],
        freshness="today",
        warnings=[],
    )
