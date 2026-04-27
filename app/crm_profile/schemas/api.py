"""Request / response Pydantic models for CRM profile endpoints."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from .context import ModulePayload


# ---------- Search ----------

class CustomerSearchItem(BaseModel):
    id: int
    name: str
    gender: int | None = None
    birthday: str | None = None
    points: int | None = 0
    total_points: int | None = 0
    status: int | None = 1


# ---------- List (with filters) ----------

class CustomerListItem(BaseModel):
    id: int
    name: str
    gender: int | None = None
    birthday: str | None = None
    points: int | None = 0
    total_points: int | None = 0
    status: int | None = 1
    channel_name: str | None = None
    coach_names: str | None = None
    group_names: str | None = None
    city: str | None = None
    created_at: str | None = None


class CustomerListResponse(BaseModel):
    items: list[CustomerListItem] = []
    total: int = 0
    page: int = 1
    page_size: int = 20


class FilterOption(BaseModel):
    value: int
    label: str


class FilterOptionsResponse(BaseModel):
    coaches: list[FilterOption] = []
    groups: list[FilterOption] = []
    channels: list[FilterOption] = []


class CustomerListWithFiltersResponse(CustomerListResponse):
    """Extended response that optionally carries filter options (first load)."""
    filters: FilterOptionsResponse | None = None


# ---------- Profile ----------

class ProfileResponse(BaseModel):
    customer_id: int
    cards: list[ModulePayload] = []
    available_actions: list[str] = ["view_profile"]
    ai_chat_enabled: bool = False
    ai_chat_reason: str | None = None


class SafetySnapshotItem(BaseModel):
    snapshot_id: int
    label: str
    display_label: str
    reference_time: str | None = None
    is_current: bool = False
    is_archived: bool = False


class SafetySnapshotListResponse(BaseModel):
    customer_id: int
    items: list[SafetySnapshotItem] = []


class SafetySnapshotDetailResponse(BaseModel):
    customer_id: int
    snapshot: SafetySnapshotItem
    card: ModulePayload


# ---------- AI Profile Note ----------

class AiProfileNoteRequest(BaseModel):
    communication_style_note: str | None = None
    current_focus_note: str | None = None
    execution_barrier_note: str | None = None
    lifestyle_background_note: str | None = None
    coach_strategy_note: str | None = None
    preferred_scene_hint: str | None = None


class AiProfileNoteResponse(BaseModel):
    crm_customer_id: int
    status: str = "active"
    communication_style_note: str | None = None
    current_focus_note: str | None = None
    execution_barrier_note: str | None = None
    lifestyle_background_note: str | None = None
    coach_strategy_note: str | None = None
    preferred_scene_hint: str | None = None
    updated_at: str | None = None


class SceneOption(BaseModel):
    key: str
    label: str


class AiConfigResponse(BaseModel):
    scenes: list[SceneOption] = []
    profile_note: AiProfileNoteResponse | None = None
    prompt_version: str = ""
    expansion_options: dict[str, str] = {}


# ---------- AI Chat ----------

class AiChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    scene_key: str = "qa_support"
    entry_scene: str = "customer_profile"
    selected_expansions: list[str] | None = None
    output_style: str = "coach_brief"
    health_window_days: int = 7


class AiChatResponse(BaseModel):
    session_id: str
    message_id: str = ""
    answer: str
    safety_notes: list[str] = []
    missing_data_notes: list[str] = []
    used_modules: list[str] = []
    token_usage: dict[str, int] = {}
    requires_medical_review: bool = False
    safety_result: dict | None = None
    prompt_version: str = ""
    scene_key: str = ""


class AiSessionSummaryItem(BaseModel):
    session_id: str
    entry_scene: str | None = None
    scene_key: str | None = None
    started_at: str | None = None
    last_message_at: str | None = None
    message_count: int = 0
    last_message_preview: str = ""


class AiSessionListResponse(BaseModel):
    customer_id: int
    items: list[AiSessionSummaryItem] = []


class AiSessionMessageItem(BaseModel):
    message_id: str
    role: str
    content: str = ""
    created_at: str | None = None
    requires_medical_review: bool = False
    token_usage: dict[str, int] = {}


class AiSessionDetailResponse(BaseModel):
    customer_id: int
    session: AiSessionSummaryItem
    messages: list[AiSessionMessageItem] = []
    scene_key: str | None = None
    output_style: str | None = None
    prompt_version: str | None = None


# ---------- AI Preload ----------

class AiPreloadRequest(BaseModel):
    health_window_days: int = 7
    wait_ms: int = 0

class AiPreloadResponse(BaseModel):
    customer_id: int
    status: str
    cache_key: str
    health_window_days: int = 7
    ready: bool = False
    source: str = ""
    generated_at: str | None = None
    expires_at: str | None = None
    stale_expires_at: str | None = None
    message: str = ""


class AiCacheStatusResponse(AiPreloadResponse):
    pass
