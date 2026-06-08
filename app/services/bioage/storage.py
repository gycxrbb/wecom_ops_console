"""bioage 结果持久化。"""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from .models import BioageCalculation


def save_calculation(
    db: Session,
    customer_id: int,
    calc_result: dict,
    input_snapshot: dict | None = None,
    gender: int = 0,
    triggered_by: str = "manual",
) -> BioageCalculation:
    """将计算结果写入 bioage_calculations 表。"""
    row = BioageCalculation(
        customer_id=customer_id,
        param_version=calc_result.get("param_version", "v2.0-draft"),
        chronological_age=calc_result["chronological_age"],
        gender=gender,
        checkup_date=input_snapshot.get("checkup_date") if input_snapshot else None,
        checkup_age_days=calc_result.get("checkup_age_days"),
        bp_window_days=calc_result.get("bp_window_days"),
        bp_record_count=calc_result.get("bp_record_count"),
        biological_age=calc_result["biological_age"],
        age_acceleration=calc_result["age_acceleration"],
        n_biomarkers=calc_result["n_biomarkers"],
        total_biomarkers=calc_result.get("total_biomarkers", 8),
        confidence=calc_result.get("confidence", "medium"),
        age_weight_applied=1 if calc_result.get("age_weight_applied") else 0,
        dim_scores=_to_json(calc_result.get("dim_scores")),
        contributions=_to_json(calc_result.get("contributions")),
        missing_codes=_to_json(calc_result.get("missing_codes")),
        input_snapshot=_to_json(input_snapshot),
        warnings=_to_json(calc_result.get("warnings")),
        triggered_by=triggered_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_llm_result(
    db: Session,
    calculation_id: int,
    llm_reading: str,
    llm_actions: list[str] | None = None,
    llm_coach_note: str | None = None,
) -> BioageCalculation | None:
    """更新 LLM 解读结果。"""
    row = db.query(BioageCalculation).filter(BioageCalculation.id == calculation_id).first()
    if not row:
        return None
    row.llm_reading = llm_reading
    row.llm_actions = _to_json(llm_actions)
    row.llm_coach_note = llm_coach_note
    row.llm_generated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def _to_json(data) -> str | None:
    if data is None:
        return None
    return json.dumps(data, ensure_ascii=False, default=str)
