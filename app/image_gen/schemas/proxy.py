"""OpenAI 兼容代理的请求 schema。响应直接返回 dict（OpenAI 结构），不定义响应模型。"""
from __future__ import annotations

from pydantic import BaseModel


class ImageGenerationRequest(BaseModel):
    # 入参对齐 OpenAI /images/generations；额外字段（response_format/background 等）忽略
    model: str | None = None
    prompt: str
    n: int | None = 1
    size: str | None = "auto"
    quality: str | None = "auto"
