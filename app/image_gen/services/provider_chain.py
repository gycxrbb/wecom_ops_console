"""供应商 failover chain：按 priority 读取 enabled providers（解密 api_key 为明文）。

direct_orchestrator 已按列表顺序遍历，任一成功即返回。
P0：单供应商仅一轮。P1：在 direct_orchestrator 引入 _is_failover_eligible，
仅对基础设施错误（超时/5xx/transport）切换下一个供应商，4xx（prompt 策略违规）不切换。
进程内 TTL 缓存，CRUD 时 invalidate。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.security import decrypt_webhook

from ..models import ImageGenProvider

_log = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30
_cache: dict[str, tuple[float, list["ProviderConfig"]]] = {"providers": (0.0, [])}


@dataclass
class ProviderConfig:
    """已解密的供应商运行时配置（api_key 明文仅存在于内存，不落盘/不下发）。"""

    id: int
    name: str
    provider_kind: str
    base_url: str
    api_key: str
    default_model: str
    timeout_seconds: int
    max_retries: int
    priority: int
    agent_model: str | None = None  # 配了才参与 agent /responses（用此推理模型）；None=仅图片


class NoProviderConfigured(Exception):
    """没有任何 enabled 供应商。"""


def _row_to_config(row: ImageGenProvider) -> ProviderConfig:
    return ProviderConfig(
        id=row.id,
        name=row.name,
        provider_kind=row.provider_kind or "openai_compatible",
        base_url=(row.base_url or "").rstrip("/"),
        api_key=decrypt_webhook(row.api_key_encrypted or ""),
        default_model=row.default_model or "gpt-image-2",
        timeout_seconds=row.timeout_seconds or 1500,
        max_retries=row.max_retries if (row.max_retries or 0) > 0 else 2,
        priority=row.priority or 0,
        agent_model=(row.agent_model or None) if hasattr(row, "agent_model") else None,
    )


def load_providers(db: Session, *, force: bool = False) -> list[ProviderConfig]:
    """读取 enabled providers（按 priority ASC, id ASC）。进程内 TTL 缓存。"""
    now = time.time()
    cached_at, cached = _cache["providers"]
    if not force and cached and (now - cached_at) < _CACHE_TTL_SECONDS:
        return cached

    rows = (
        db.query(ImageGenProvider)
        .filter(ImageGenProvider.enabled.is_(True))
        .order_by(ImageGenProvider.priority.asc(), ImageGenProvider.id.asc())
        .all()
    )
    configs = [_row_to_config(r) for r in rows]
    _cache["providers"] = (now, configs)
    return configs


def invalidate_cache() -> None:
    _cache["providers"] = (0.0, [])
