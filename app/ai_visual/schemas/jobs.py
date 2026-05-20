"""Request / response schemas for visual job endpoints."""
from __future__ import annotations

from pydantic import BaseModel


class VisualConfirmRequest(BaseModel):
    session_id: str = ""
    customer_id: int | None = None
    topic: str
    confirmed: bool
    visual_type: str = "health_education_card"
    safety_level: str = "nutrition_education"
    confidence: float = 0.0


class VisualConfirmResponse(BaseModel):
    status: str  # "confirmed" | "declined"
    topic: str
    job_id: str | None = None


class CreateJobRequest(BaseModel):
    session_id: str = ""
    customer_id: int | None = None
    topic: str
    visual_type: str = "health_education_card"
    safety_level: str = "nutrition_education"
    confidence: float = 0.0
    decision_data_json: str = "{}"


class JobResponse(BaseModel):
    job_id: str
    status: str
    topic: str
    created_at: str | None = None


class JobDetailResponse(BaseModel):
    job_id: str
    status: str
    topic: str
    confidence: float = 0.0
    safety_level: str = "nutrition_education"
    visual_type: str = "health_education_card"
    preview_url: str | None = None
    asset_id: str | None = None
    sendable: bool = False
    error_message: str | None = None
    created_at: str | None = None
    generated_at: str | None = None


class FeedbackRequest(BaseModel):
    feedback: str  # "like" | "dislike"
