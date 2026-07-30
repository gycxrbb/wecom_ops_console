"""内部提示词上传 schema。category 承载职业分类（健康教练/运营/开发/管理层）。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class PromptCreate(BaseModel):
    title: str = Field("", max_length=128)
    body: str = Field(..., min_length=1)
    category: str = Field("", max_length=32)
    tags: list[str] = Field(default_factory=list)
    scope: str = Field("shared", max_length=16)
    cover_url: str = Field("", max_length=512)


class PromptUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    scope: str | None = None
    cover_url: str | None = None
    enabled: bool | None = None
