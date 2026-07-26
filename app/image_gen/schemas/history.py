"""agent 模式出图后回调写历史的请求 schema。"""
from __future__ import annotations

from pydantic import BaseModel


class HistoryCallbackRequest(BaseModel):
    customer_id: int | None = None
    prompt: str = ""
    model: str | None = None
    provider_name: str | None = None
    size: str | None = None
    quality: str | None = None
    status: str = "success"  # success | failed
    image_b64: str | None = None  # 成功时的 base64 图片
    latency_ms: int = 0
    error_code: str | None = None
    error_message: str | None = None
