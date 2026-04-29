"""Tag service — CRUD, vocabulary sync, and cache management for rag_tags."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ..models_rag import RagTag
from . import tag_cache
from .vocabulary import VOCABULARY, VISIBILITY_ALIASES, SAFETY_LEVEL_ALIASES, TAG_ALIASES


def get_tags_by_dimension(db: Session, dimension: str | None = None) -> list[dict]:
    query = db.query(RagTag).filter(RagTag.enabled == 1)
    if dimension:
        query = query.filter(RagTag.dimension == dimension)
    return [
        {
            "id": t.id,
            "dimension": t.dimension,
            "code": t.code,
            "name": t.name,
            "description": t.description or "",
            "sort_order": t.sort_order,
            "aliases": json.loads(t.aliases) if t.aliases else [],
        }
        for t in query.order_by(RagTag.dimension, RagTag.sort_order).all()
    ]


def create_tag(
    db: Session,
    *,
    dimension: str,
    code: str,
    name: str,
    description: str = "",
    sort_order: int = 0,
    aliases: list[str] | None = None,
) -> RagTag:
    existing = db.query(RagTag).filter(
        RagTag.dimension == dimension, RagTag.code == code
    ).first()
    if existing:
        raise ValueError(f"Tag already exists: {dimension}.{code}")

    tag = RagTag(
        dimension=dimension,
        code=code,
        name=name,
        description=description,
        sort_order=sort_order,
        enabled=1,
        aliases=json.dumps(aliases or [], ensure_ascii=False),
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    tag_cache.reload_from_db(db)
    return tag


def update_tag(
    db: Session,
    tag_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    sort_order: int | None = None,
    aliases: list[str] | None = None,
    enabled: bool | None = None,
) -> RagTag:
    tag = db.query(RagTag).filter(RagTag.id == tag_id).first()
    if not tag:
        raise ValueError(f"Tag not found: {tag_id}")

    if name is not None:
        tag.name = name
    if description is not None:
        tag.description = description
    if sort_order is not None:
        tag.sort_order = sort_order
    if aliases is not None:
        tag.aliases = json.dumps(aliases, ensure_ascii=False)
    if enabled is not None:
        tag.enabled = 1 if enabled else 0

    db.commit()
    db.refresh(tag)
    tag_cache.reload_from_db(db)
    return tag


def disable_tag(db: Session, tag_id: int) -> RagTag:
    return update_tag(db, tag_id, enabled=False)


def enable_tag(db: Session, tag_id: int) -> RagTag:
    return update_tag(db, tag_id, enabled=True)


def refresh_tags_from_vocabulary(db: Session) -> dict:
    """Sync rag_tags from vocabulary module. Per-code upsert, never deletes."""
    stats = {"added": 0, "existing": 0, "aliases_updated": 0}
    existing = {(t.dimension, t.code): t for t in db.query(RagTag).all()}

    for dimension, entries in VOCABULARY.items():
        for code, name, desc, sort_order in entries:
            key = (dimension, code)
            aliases_json = _build_seed_aliases(dimension, code)

            if key in existing:
                tag = existing[key]
                if aliases_json and not tag.aliases:
                    tag.aliases = aliases_json
                    stats["aliases_updated"] += 1
                stats["existing"] += 1
            else:
                db.add(RagTag(
                    dimension=dimension,
                    code=code,
                    name=name,
                    description=desc or "",
                    sort_order=sort_order,
                    enabled=1,
                    aliases=aliases_json,
                ))
                stats["added"] += 1

    db.commit()
    tag_cache.reload_from_db(db)
    return stats


def _build_seed_aliases(dimension: str, code: str) -> str:
    """Collect all aliases that map to this (dimension, code) from vocabulary alias dicts."""
    aliases: list[str] = []

    if dimension == "visibility":
        for alias, target in VISIBILITY_ALIASES.items():
            if target == code:
                aliases.append(alias)
    elif dimension == "safety_level":
        for alias, target in SAFETY_LEVEL_ALIASES.items():
            if target == code:
                aliases.append(alias)

    dim_aliases = TAG_ALIASES.get(dimension, {})
    for alias, target in dim_aliases.items():
        if target == code:
            aliases.append(alias)

    return json.dumps(aliases, ensure_ascii=False) if aliases else ""
