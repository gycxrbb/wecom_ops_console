"""Pydantic schemas for material RAG metadata."""
from __future__ import annotations

from pydantic import BaseModel


class RagMetaUpdate(BaseModel):
    summary: str = ''
    alt_text: str = ''
    transcript: str = ''
    usage_note: str = ''
    customer_goal: list[str] = []
    intervention_scene: list[str] = []
    question_type: list[str] = []
    visibility: str = 'coach_internal'
    safety_level: str = 'general'
    copyright_status: str = 'unknown'
    customer_sendable: bool = False
    rag_enabled: bool = True
