"""生物年龄 API 路由。"""

import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..route_helper import UnifiedResponseRoute
from ..schemas.bioage import (
    BioageSummaryItem, CalculationResult, CalculateRequest,
    DataReadinessResponse, DimensionScore, HistoryResponse,
)
from ..security import get_current_user, require_role
from ..services.bioage.data_collector import (
    CRMDataProvider, collect_calculation_inputs,
)
from ..services.bioage.engine import InsufficientDataError, calculate_kdm
from ..services.bioage.models import BioageCalculation
from ..services.bioage.storage import save_calculation

router = APIRouter(
    prefix="/api/v1/bioage",
    tags=["bioage"],
    route_class=UnifiedResponseRoute,
)


@router.post("/calculate")
def calculate(request: Request, body: CalculateRequest, db: Session = Depends(get_db)):
    """手动触发一次生物年龄测算。"""
    user = get_current_user(request, db)
    require_role(user, "admin")

    from ..clients.crm_db import get_connection, return_connection
    provider = CRMDataProvider(get_connection, return_connection)

    collected = collect_calculation_inputs(provider, body.customer_id, body.param_version)
    if collected["status"] != "ready":
        return {"success": False, "reason": collected.get("reason", "数据不足"), "readiness": collected.get("readiness")}

    inputs = collected["inputs"]
    try:
        result = calculate_kdm(
            age=inputs["age"],
            gender=inputs["gender"],
            biomarkers=inputs["biomarkers"],
            sbp_mean=inputs.get("sbp_mean"),
            dbp_mean=inputs.get("dbp_mean"),
            param_version=inputs["param_version"],
            checkup_age_days=inputs.get("checkup_age_days"),
            bp_window_days=inputs.get("bp_window_days"),
            bp_record_count=inputs.get("bp_record_count"),
        )
    except InsufficientDataError as e:
        return {"success": False, "reason": str(e)}

    gender_int = 1 if inputs["gender"] == "male" else 2
    row = save_calculation(db, body.customer_id, result, input_snapshot=inputs, gender=gender_int)

    return _row_to_result(row)


@router.get("/latest/{customer_id}")
def get_latest(customer_id: int, request: Request, db: Session = Depends(get_db)):
    """获取客户最新一次测算结果。"""
    user = get_current_user(request, db)
    require_role(user, "admin")

    row = BioageCalculation.get_latest_by_customer(db, customer_id)
    if not row:
        return {"success": False, "reason": "暂无测算记录"}
    return _row_to_result(row)


@router.get("/history/{customer_id}")
def get_history(customer_id: int, request: Request, db: Session = Depends(get_db)):
    """获取客户历史测算记录与趋势。"""
    user = get_current_user(request, db)
    require_role(user, "admin")

    rows = BioageCalculation.get_history_by_customer(db, customer_id)
    if not rows:
        return {"history": [], "trend": None, "version_changes": []}

    history = [_row_to_result(r) for r in rows]
    version_changes = []
    for i in range(1, len(rows)):
        if rows[i].param_version != rows[i - 1].param_version:
            version_changes.append({
                "from": rows[i - 1].param_version,
                "to": rows[i].param_version,
                "date": _fmt(rows[i].created_at),
            })

    pv_set = {r.param_version for r in rows}
    comparable = len(pv_set) == 1

    trend = {"comparable": comparable}
    if comparable and len(history) >= 2:
        latest_baa = float(history[0]["age_acceleration"])
        prev_baa = float(history[1]["age_acceleration"])
        first_baa = float(history[-1]["age_acceleration"])
        trend["last_change"] = round(latest_baa - prev_baa, 1)
        trend["total_change"] = round(latest_baa - first_baa, 1)

    return {"history": history, "trend": trend, "version_changes": version_changes}


@router.get("/data-readiness/{customer_id}")
def data_readiness(customer_id: int, request: Request, db: Session = Depends(get_db)):
    """查看客户数据完备度。"""
    user = get_current_user(request, db)
    require_role(user, "admin")

    from ..clients.crm_db import get_connection, return_connection
    provider = CRMDataProvider(get_connection, return_connection)

    basic = provider.get_customer_basic(customer_id)
    raw_biomarkers = provider.get_latest_biomarkers(customer_id)
    bp_records = provider.get_bp_records(customer_id, days=7)
    checkup_date = provider.get_latest_checkup_date(customer_id)

    resp = DataReadinessResponse(customer_id=customer_id)
    if basic:
        resp.has_birthday = basic.get("birthday") is not None
        resp.has_gender = basic.get("gender") in (1, 2)

    if checkup_date:
        resp.has_checkup = True
        resp.latest_checkup_date = checkup_date.isoformat() if checkup_date else None
        from datetime import date as date_type
        resp.checkup_age_days = (date_type.today() - checkup_date).days

    resp.bp_records_last_7d = len(bp_records)

    from ..services.bioage.data_collector import standardize_units
    std_bm = standardize_units(raw_biomarkers)
    from ..services.bioage.engine import ALL_CODES
    for code in sorted(ALL_CODES):
        if code in ("sbp", "pp"):
            continue
        if code in std_bm:
            info = raw_biomarkers.get(code, {})
            resp.biomarkers[code] = {
                "available": True,
                "value": std_bm[code],
                "unit": info.get("unit", ""),
                "date": info.get("date", ""),
            }
        else:
            resp.biomarkers[code] = {"available": False}

    resp.n_available = sum(1 for v in resp.biomarkers.values() if v.get("available"))
    if any(r.get("sbp") for r in bp_records):
        resp.n_available += 2  # sbp + pp

    from ..services.bioage.engine import assess_readiness
    from ..services.bioage.bp_aggregator import aggregate_bp
    bp_data = aggregate_bp(bp_records)
    readiness = assess_readiness(std_bm, bp_data)
    resp.can_calculate = readiness["can_calculate"]
    resp.confidence = readiness["confidence"]
    resp.missing = readiness["missing"]

    return resp


@router.get("/coach/bioage-summary")
def bioage_summary(request: Request, db: Session = Depends(get_db)):
    """教练端用户 BAA 排序列表。"""
    user = get_current_user(request, db)
    require_role(user, "admin", "coach")

    subq = (
        db.query(BioageCalculation)
        .filter(BioageCalculation.id == db.query(BioageCalculation.id)
                .filter(BioageCalculation.customer_id == BioageCalculation.customer_id)
                .order_by(BioageCalculation.created_at.desc())
                .limit(1)
                .correlate(BioageCalculation).as_scalar())
    )

    rows = (
        db.query(BioageCalculation)
        .order_by(BioageCalculation.age_acceleration.desc())
        .limit(50)
        .all()
    )

    items = []
    for row in rows:
        item = BioageSummaryItem(
            customer_id=row.customer_id,
            latest_ba=float(row.biological_age),
            latest_baa=float(row.age_acceleration),
            latest_date=_fmt(row.created_at),
            confidence=row.confidence,
        )

        prev = (
            db.query(BioageCalculation)
            .filter(
                BioageCalculation.customer_id == row.customer_id,
                BioageCalculation.id != row.id,
            )
            .order_by(BioageCalculation.created_at.desc())
            .first()
        )
        if prev:
            baa_change = round(float(row.age_acceleration) - float(prev.age_acceleration), 1)
            item.baa_change = baa_change
            item.alert = abs(baa_change) >= 2

        items.append(item)

    return items


def _row_to_result(row: BioageCalculation) -> dict:
    return {
        "id": row.id,
        "customer_id": row.customer_id,
        "param_version": row.param_version,
        "chronological_age": float(row.chronological_age),
        "biological_age": float(row.biological_age),
        "age_acceleration": float(row.age_acceleration),
        "n_biomarkers": row.n_biomarkers,
        "total_biomarkers": row.total_biomarkers,
        "confidence": row.confidence,
        "age_weight_applied": bool(row.age_weight_applied),
        "dim_scores": json.loads(row.dim_scores) if row.dim_scores else None,
        "contributions": json.loads(row.contributions) if row.contributions else None,
        "missing_codes": json.loads(row.missing_codes) if row.missing_codes else None,
        "warnings": json.loads(row.warnings) if row.warnings else None,
        "input_snapshot": json.loads(row.input_snapshot) if row.input_snapshot else None,
        "llm_reading": row.llm_reading,
        "llm_actions": json.loads(row.llm_actions) if row.llm_actions else None,
        "llm_coach_note": row.llm_coach_note,
        "triggered_by": row.triggered_by,
        "created_at": _fmt(row.created_at),
    }


def _fmt(val) -> str | None:
    if val is None:
        return None
    return val.strftime("%Y-%m-%d %H:%M:%S") if hasattr(val, "strftime") else str(val)
