"""playground 对话/任务持久化的请求结构。响应直接返回裸 dict（走 raw_proxy）。"""
from __future__ import annotations

from pydantic import BaseModel


class ConversationUpsertRequest(BaseModel):
    title: str | None = None
    auto_title: str | None = None
    data_json: str
    last_active_at: str | None = None  # ISO 时间，后端解析；空则取当前


class ConversationUpdateRequest(BaseModel):
    title: str | None = None


class TaskUpsertRequest(BaseModel):
    conversation_id: str | None = None
    data_json: str
    created_at: str | None = None  # 保留 playground 端创建时间
