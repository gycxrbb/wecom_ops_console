"""Tag service — CRUD and vocabulary sync for rag_tags."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models_rag import RagTag
from .vocabulary import VOCABULARY


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
        }
        for t in query.order_by(RagTag.dimension, RagTag.sort_order).all()
    ]


def refresh_tags_from_vocabulary(db: Session) -> dict:
    """Sync rag_tags from vocabulary module. Adds new entries, never deletes."""
    stats = {"added": 0, "existing": 0}
    existing = {(t.dimension, t.code) for t in db.query(RagTag).all()}
    for dimension, entries in VOCABULARY.items():
        for code, name, desc, sort_order in entries:
            if (dimension, code) in existing:
                stats["existing"] += 1
                continue
            db.add(RagTag(
                dimension=dimension, code=code, name=name,
                description=desc or "", sort_order=sort_order, enabled=1,
            ))
            stats["added"] += 1
    db.commit()
    return stats
