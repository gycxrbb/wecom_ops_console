"""供应商配置仓储：CRUD。写入时加密 api_key；读出不解密（出参脱敏在 router 层）。每次写操作触发缓存失效。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.security import encrypt_webhook

from ..models import ImageGenProvider
from ..schemas.providers import ProviderCreate, ProviderUpdate
from .provider_chain import invalidate_cache

_UPDATABLE_FIELDS = (
    "name",
    "provider_kind",
    "default_model",
    "agent_model",
    "priority",
    "enabled",
    "timeout_seconds",
    "max_retries",
    "extra_json",
)


def list_providers(db: Session) -> list[ImageGenProvider]:
    return (
        db.query(ImageGenProvider)
        .order_by(ImageGenProvider.priority.asc(), ImageGenProvider.id.asc())
        .all()
    )


def create_provider(db: Session, body: ProviderCreate) -> ImageGenProvider:
    row = ImageGenProvider(
        name=body.name,
        provider_kind=body.provider_kind,
        base_url=body.base_url.rstrip("/"),
        api_key_encrypted=encrypt_webhook(body.api_key),
        default_model=body.default_model,
        agent_model=body.agent_model or None,
        priority=body.priority,
        enabled=body.enabled,
        timeout_seconds=body.timeout_seconds,
        max_retries=body.max_retries,
        extra_json=body.extra_json or "{}",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    invalidate_cache()
    return row


def update_provider(db: Session, provider_id: int, body: ProviderUpdate) -> ImageGenProvider | None:
    row = db.query(ImageGenProvider).filter(ImageGenProvider.id == provider_id).first()
    if not row:
        return None
    for field in _UPDATABLE_FIELDS:
        val = getattr(body, field)
        if val is not None:
            setattr(row, field, val)
    if body.base_url is not None:
        row.base_url = body.base_url.rstrip("/")
    if body.api_key:
        row.api_key_encrypted = encrypt_webhook(body.api_key)
    db.commit()
    db.refresh(row)
    invalidate_cache()
    return row


def delete_provider(db: Session, provider_id: int) -> bool:
    row = db.query(ImageGenProvider).filter(ImageGenProvider.id == provider_id).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    invalidate_cache()
    return True
