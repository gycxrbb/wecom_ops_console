"""Request / response Pydantic models for CRM profile endpoints."""
from __future__ import annotations

from typing import Any, Literal

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
    styles: list[SceneOption] = []
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
    attachment_ids: list[str] | None = None
    quoted_message_id: str | None = None


class AiAttachmentUploadResponse(BaseModel):
    attachment_id: str
    filename: str
    mime_type: str
    file_size: int


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
    feedback: dict | None = None


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


# ---------- AI Feedback ----------

class AiFeedbackRequest(BaseModel):
    rating: Literal["like", "dislike"]
    reason_category: str | None = None
    reason_text: str | None = None
    expected_answer: str | None = None


class AiFeedbackResponse(BaseModel):
    feedback_id: str
    message_id: str
    rating: str
    status: str
    created_at: str


# ---------- AI Feedback Admin ----------

class AiFeedbackListItem(BaseModel):
    feedback_id: str
    message_id: str
    crm_customer_id: int
    coach_user_id: int
    rating: str
    reason_category: str | None = None
    scene_key: str | None = None
    status: str
    user_question_snapshot: str | None = None
    created_at: str | None = None


class AiFeedbackListResponse(BaseModel):
    items: list[AiFeedbackListItem] = []
    total: int = 0
    page: int = 1
    page_size: int = 20


class AiFeedbackDetailResponse(BaseModel):
    feedback_id: str
    message_id: str
    session_id: str
    crm_customer_id: int
    coach_user_id: int
    rating: str
    reason_category: str | None = None
    reason_text: str | None = None
    expected_answer: str | None = None
    user_question_snapshot: str | None = None
    ai_answer_snapshot: str | None = None
    customer_reply_snapshot: str | None = None
    scene_key: str | None = None
    output_style: str | None = None
    prompt_version: str | None = None
    prompt_hash: str | None = None
    model: str | None = None
    status: str
    admin_note: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AiFeedbackStatusUpdateRequest(BaseModel):
    status: Literal["new", "reviewed", "used_for_prompt", "ignored"]
    admin_note: str | None = None


class AiFeedbackStatItem(BaseModel):
    key: str
    count: int


class AiFeedbackStatsResponse(BaseModel):
    total: int = 0
    like_count: int = 0
    dislike_count: int = 0
    dislike_rate: float = 0.0
    by_reason: list[AiFeedbackStatItem] = []
    by_scene: list[AiFeedbackStatItem] = []
    by_prompt_version: list[AiFeedbackStatItem] = []
