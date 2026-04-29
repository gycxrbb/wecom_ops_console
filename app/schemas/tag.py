"""Pydantic schemas for RAG tag CRUD."""
from __future__ import annotations

from pydantic import BaseModel, Field


class TagCreate(BaseModel):
    dimension: str
    code: str
    name: str
    description: str = ''
    sort_order: int = 0
    aliases: list[str] = Field(default_factory=list)


class TagUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    sort_order: int | None = None
    aliases: list[str] | None = None
    enabled: bool | None = None
