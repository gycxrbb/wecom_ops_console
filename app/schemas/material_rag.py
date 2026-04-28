"""Pydantic schemas for material RAG metadata."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from ..rag.vocabulary import resolve_code


class RagMetaUpdate(BaseModel):
    summary: str = ''
    alt_text: str = ''
    transcript: str = ''
    usage_note: str = ''
    customer_goal: list[str] = Field(default_factory=list)
    intervention_scene: list[str] = Field(default_factory=list)
    question_type: list[str] = Field(default_factory=list)
    visibility: str = 'coach_internal'
    safety_level: str = 'general'
    copyright_status: str = 'unknown'
    customer_sendable: bool = False
    rag_enabled: bool = True

    @field_validator('visibility')
    @classmethod
    def _validate_visibility(cls, v: str) -> str:
        if v in ('coach_internal', 'customer_visible'):
            return v
        # Backward compatibility: map old value
        if v in ('customer_sendable', 'public'):
            return 'customer_visible'
        return 'coach_internal'

    @field_validator('safety_level')
    @classmethod
    def _validate_safety_level(cls, v: str) -> str:
        return resolve_code('safety_level', v) or 'general'

    @field_validator('customer_goal', 'intervention_scene', 'question_type')
    @classmethod
    def _normalize_tag_list(cls, values: list[str], info) -> list[str]:
        normalized: list[str] = []
        for item in values or []:
            code = resolve_code(info.field_name, str(item))
            if code and code not in normalized:
                normalized.append(code)
        return normalized

    @model_validator(mode='after')
    def _sync_customer_sendable(self) -> 'RagMetaUpdate':
        self.customer_sendable = self.visibility == 'customer_visible'
        return self
