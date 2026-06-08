"""生物年龄 Pydantic 请求/响应模型。"""

from datetime import date, datetime

from pydantic import BaseModel, Field


# ── 请求 ──

class CalculateRequest(BaseModel):
    customer_id: int
    param_version: str = "v2.0-draft"


# ── 响应 ──

class BiomarkerInfo(BaseModel):
    available: bool
    value: float | None = None
    unit: str | None = None
    date: str | None = None


class DataReadinessResponse(BaseModel):
    customer_id: int
    has_birthday: bool = False
    has_gender: bool = False
    has_checkup: bool = False
    latest_checkup_date: str | None = None
    checkup_age_days: int | None = None
    bp_records_last_7d: int = 0
    biomarkers: dict[str, BiomarkerInfo] = {}
    n_available: int = 0
    total: int = 8
    can_calculate: bool = False
    confidence: str = "low"
    missing: list[str] = []


class DimensionScore(BaseModel):
    glucose: float | None = None
    vascular: float | None = None
    metabolic: float | None = None
    hepatorenal: float | None = None
    skeletal: float | None = None


class CalculationResult(BaseModel):
    id: int
    customer_id: int
    param_version: str
    chronological_age: float
    biological_age: float
    age_acceleration: float
    n_biomarkers: int
    total_biomarkers: int = 8
    confidence: str
    age_weight_applied: bool = False
    dim_scores: DimensionScore | None = None
    contributions: dict[str, float] | None = None
    missing_codes: list[str] | None = None
    warnings: list[str] | None = None
    input_snapshot: dict | None = None
    llm_reading: str | None = None
    llm_actions: list[str] | None = None
    llm_coach_note: str | None = None
    triggered_by: str | None = "manual"
    created_at: str | None = None


class HistoryResponse(BaseModel):
    history: list[CalculationResult]
    trend: dict | None = None
    version_changes: list[dict] = []


class BioageSummaryItem(BaseModel):
    customer_id: int
    customer_name: str = ""
    latest_ba: float | None = None
    latest_baa: float | None = None
    latest_date: str | None = None
    confidence: str | None = None
    alert: bool = False
    baa_change: float | None = None
