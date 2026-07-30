"""内部提示词仓储：CRUD。列表 JOIN User 取贡献者展示。

ImageGenPrompt 表承载：category=职业分类，owner_user_id=贡献者，scope=system|private|shared。
可见性：system+shared 全员可见；private 仅 owner。
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app import models

from ..schemas.prompts import PromptCreate, PromptUpdate

_UPDATABLE_FIELDS = ("title", "category", "scope", "cover_url", "enabled")


def _contributor_of(db: Session, owner_id: int | None) -> dict[str, Any] | None:
    if not owner_id:
        return None
    user = db.query(models.User).filter(models.User.id == owner_id).first()
    if not user:
        return None
    return {
        "id": user.id,
        "display_name": user.display_name or user.username,
        "avatar_url": user.avatar_url or "",
    }


def _serialize(row: models.ImageGenPrompt, contributor: dict | None = None) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title or "",
        "body": row.body or "",
        "category": row.category or "",
        "tags": json.loads(row.tags_json or "[]"),
        "scope": row.scope or "shared",
        "cover_url": row.cover_url or "",
        "enabled": bool(row.enabled),
        "contributor": contributor,
        "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else None,
    }


def list_prompts(db: Session, *, category: str | None = None, operator_id: int | None = None):
    q = db.query(models.ImageGenPrompt).filter(models.ImageGenPrompt.enabled.is_(True))
    # system + shared 全员可见；private 仅 owner
    q = q.filter(
        (models.ImageGenPrompt.scope != "private")
        | (
            (models.ImageGenPrompt.scope == "private")
            & (models.ImageGenPrompt.owner_user_id == operator_id)
        )
    )
    if category:
        q = q.filter(models.ImageGenPrompt.category == category)
    return q.order_by(models.ImageGenPrompt.created_at.desc()).all()


def serialize_with_contributor(db: Session, row: models.ImageGenPrompt) -> dict[str, Any]:
    return _serialize(row, _contributor_of(db, row.owner_user_id))


def create_prompt(db: Session, body: PromptCreate, owner_id: int) -> models.ImageGenPrompt:
    row = models.ImageGenPrompt(
        title=body.title,
        body=body.body,
        category=body.category,
        cover_url=body.cover_url,
        scope=body.scope or "shared",
        owner_user_id=owner_id,
        tags_json=json.dumps(body.tags or [], ensure_ascii=False),
        enabled=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_prompt(
    db: Session, prompt_id: int, body: PromptUpdate
) -> models.ImageGenPrompt | None:
    row = db.query(models.ImageGenPrompt).filter(models.ImageGenPrompt.id == prompt_id).first()
    if not row:
        return None
    for field in _UPDATABLE_FIELDS:
        val = getattr(body, field)
        if val is not None:
            setattr(row, field, val)
    if body.body is not None:
        row.body = body.body
    if body.tags is not None:
        row.tags_json = json.dumps(body.tags, ensure_ascii=False)
    db.commit()
    db.refresh(row)
    return row


def delete_prompt(db: Session, prompt_id: int) -> bool:
    row = db.query(models.ImageGenPrompt).filter(models.ImageGenPrompt.id == prompt_id).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def get_prompt(db: Session, prompt_id: int) -> models.ImageGenPrompt | None:
    return db.query(models.ImageGenPrompt).filter(models.ImageGenPrompt.id == prompt_id).first()
