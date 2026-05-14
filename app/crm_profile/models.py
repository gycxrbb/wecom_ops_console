"""Local ORM models for CRM AI audit tables."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class CrmAiSession(Base):
    __tablename__ = "crm_ai_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    local_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    crm_admin_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    crm_customer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_scene: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    scene_key: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    output_style: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    prompt_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())


class CrmAiMessage(Base):
    __tablename__ = "crm_ai_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    requires_medical_review: Mapped[bool] = mapped_column(Boolean, default=False)
    safety_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    regenerated_from_message_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    quoted_message_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    request_params_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())


class CrmAiContextSnapshot(Base):
    __tablename__ = "crm_ai_context_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    context_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    compact_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    used_modules: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    prompt_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    scene_key: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    output_style: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    selected_expansions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    health_window_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cache_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())


class CrmAiGuardrailEvent(Base):
    __tablename__ = "crm_ai_guardrail_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())


class CustomerAiProfileNote(Base):
    """Per-customer long-term supplementary info maintained by coaches for AI context."""
    __tablename__ = "crm_ai_profile_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crm_customer_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    communication_style_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_focus_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_barrier_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lifestyle_background_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    coach_strategy_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preferred_scene_hint: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())


class CrmAiAttachment(Base):
    """AI chat attachment — uploaded image/PDF for Vision analysis."""
    __tablename__ = "crm_ai_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attachment_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    message_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    crm_customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    uploaded_by: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    storage_provider: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_public_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    storage_local_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    vision_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vision_model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    vision_tokens: Mapped[int] = mapped_column(Integer, default=0)
    processing_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    analysis_retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())


class CrmAiMessageFeedback(Base):
    """Coach feedback (like/dislike) on an AI assistant message."""
    __tablename__ = "crm_ai_message_feedback"
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feedback_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_message_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    crm_customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    coach_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    crm_admin_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rating: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reason_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_question_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_answer_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    customer_reply_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scene_key: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    output_style: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    prompt_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="new")
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class CrmAiProfileCache(Base):
    """Shared cached CustomerProfileContextV1 snapshot for AI prepare paths."""
    __tablename__ = "crm_ai_profile_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cache_key: Mapped[str] = mapped_column(String(96), unique=True, nullable=False, index=True)
    crm_customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    health_window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    context_json: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    stale_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_hit_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
