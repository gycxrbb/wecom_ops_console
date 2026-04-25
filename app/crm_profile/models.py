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
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())


class CrmAiContextSnapshot(Base):
    __tablename__ = "crm_ai_context_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    context_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    compact_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    used_modules: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
