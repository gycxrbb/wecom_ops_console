"""Shared schema for speech template metadata — single source of truth for all 3 entry points."""
from __future__ import annotations

from pydantic import BaseModel


class SpeechMetadata(BaseModel):
    summary: str | None = None
    customer_goal: list[str] = []
    intervention_scene: list[str] = []
    question_type: list[str] = []
    safety_level: str | None = None
    visibility: str | None = None
    tags: list[str] = []
    usage_note: str | None = None
    reviewer: str | None = None
    review_note: str | None = None
    content_kind: str = 'script'
