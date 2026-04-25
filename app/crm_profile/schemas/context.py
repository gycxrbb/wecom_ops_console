"""Customer profile context & module payload schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from .enums import ModuleStatus, SourceStatus


class ModulePayload(BaseModel):
    """Single module result returned by each loader."""
    key: str
    status: ModuleStatus = "ok"
    payload: dict = {}
    source_tables: list[str] = []
    freshness: str | None = None
    warnings: list[str] = []
    estimated_tokens: int = 0


class SourceStatusEntry(BaseModel):
    module: str
    status: SourceStatus = "ok"
    warning: str | None = None


class ContextBuildPlan(BaseModel):
    required_modules: list[str] = ["basic_profile", "safety_profile"]
    summary_modules: list[str] = [
        "goals_preferences", "health_summary_7d",
        "body_comp_latest_30d", "points_engagement_14d", "service_scope",
    ]
    expansion_modules: list[str] = []


class CustomerProfileContextV1(BaseModel):
    """Top-level profile envelope returned to the frontend."""
    schema_version: str = "customer_profile_context.v1"
    customer_id: int
    generated_at: datetime | None = None
    cards: list[ModulePayload] = []
    source_status: list[SourceStatusEntry] = []
    available_actions: list[str] = ["view_profile"]
    ai_chat_enabled: bool = False
    ai_chat_reason: str | None = None
    build_plan: ContextBuildPlan | None = None
