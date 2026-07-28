"""供应商配置请求/响应 schema。api_key 永不出参，仅以脱敏串返回。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderCreate(BaseModel):
    name: str = Field(..., max_length=64)
    provider_kind: str = Field("openai_compatible", max_length=32)
    base_url: str = Field(..., max_length=255)
    api_key: str = Field(..., min_length=1)
    default_model: str = Field("gpt-image-2", max_length=128)
    agent_model: str | None = Field(None, max_length=128)
    priority: int = 0
    enabled: bool = True
    timeout_seconds: int = 1500
    max_retries: int = 2
    extra_json: str = "{}"


class ProviderUpdate(BaseModel):
    name: str | None = Field(None, max_length=64)
    provider_kind: str | None = Field(None, max_length=32)
    base_url: str | None = Field(None, max_length=255)
    api_key: str | None = None  # None = 不修改；非空 = 覆盖
    default_model: str | None = Field(None, max_length=128)
    agent_model: str | None = Field(None, max_length=128)  # None=不改；""=清空（仅图片）；串=设
    priority: int | None = None
    enabled: bool | None = None
    timeout_seconds: int | None = None
    max_retries: int | None = None
    extra_json: str | None = None


class ProviderOut(BaseModel):
    id: int
    name: str
    provider_kind: str
    base_url: str
    default_model: str
    agent_model: str | None
    priority: int
    enabled: bool
    timeout_seconds: int
    max_retries: int
    api_key_masked: str
