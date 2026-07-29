"""agent 生图任务化入参 schema。"""
from __future__ import annotations

from pydantic import BaseModel


class AgentImageTaskSubmit(BaseModel):
    prompt: str
    model: str | None = None
    size: str | None = "auto"
    n: int | None = 1
    quality: str | None = "auto"
    customer_id: int | None = None
