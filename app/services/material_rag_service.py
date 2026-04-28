"""Service for saving material RAG metadata and indexing into Qdrant."""
from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Material
from ..models_rag import RagResource, RagChunk
from ..rag.chunker import chunk_text, compute_hash
from ..rag.embedding_client import embed_texts_batch
from ..rag.vector_store import upsert_chunks

_log = logging.getLogger(__name__)


def load_rag_meta(material: Material) -> dict:
    raw = getattr(material, "rag_meta_json", None)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _build_semantic_text(meta: dict, material: Material) -> str:
    parts = []
    if meta.get("summary"):
        parts.append(f"摘要: {meta['summary']}")
    desc = meta.get("alt_text") or meta.get("transcript") or ""
    if desc:
        parts.append(f"内容说明: {desc}")
    if meta.get("usage_note"):
        parts.append(f"使用场景: {meta['usage_note']}")
    tags = {"customer_goal": "适用目标", "intervention_scene": "干预场景", "question_type": "问题类型"}
    for key, label in tags.items():
        vals = meta.get(key, [])
        if vals:
            parts.append(f"{label}: {', '.join(vals)}")
    if material.name:
        parts.append(material.name)
    try:
        mat_tags = json.loads(material.tags or "[]")
        if mat_tags:
            parts.append("标签: " + ", ".join(mat_tags))
    except (json.JSONDecodeError, TypeError):
        pass
    return "\n".join(parts)


def _compute_quality(meta: dict) -> str:
    has_summary = bool(meta.get("summary"))
    has_desc = bool(meta.get("alt_text") or meta.get("transcript"))
    has_usage = bool(meta.get("usage_note"))
    has_tags = bool(meta.get("customer_goal") or meta.get("intervention_scene") or meta.get("question_type"))
    if has_summary and has_desc and has_usage and has_tags:
        return "ok"
    if has_summary and has_usage:
        return "medium"
    return "weak"


def _build_payload(meta: dict, resource_id: int, material_id: int, content_kind: str) -> dict:
    payload = {
        "resource_id": resource_id, "source_type": "material",
        "source_id": material_id, "status": "active", "content_kind": content_kind,
    }
    for key in ("customer_goal", "intervention_scene", "question_type"):
        vals = meta.get(key, [])
        if vals:
            payload[key] = vals
    payload["visibility"] = meta.get("visibility", "coach_internal")
    payload["safety_level"] = meta.get("safety_level", "general")
    payload["semantic_quality"] = _compute_quality(meta)
    return payload


async def save_rag_meta_and_index(db: Session, material_id: int, rag_meta: dict) -> dict:
    """Save rag_meta_json to material and create/update rag_resources + Qdrant."""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        return {"error": "material not found", "material_id": material_id}
    if material.storage_status != "ready" or material.enabled != 1:
        return {"error": "material not ready", "material_id": material_id}

    material.rag_meta_json = json.dumps(rag_meta, ensure_ascii=False)

    if not rag_meta.get("rag_enabled", True):
        existing = db.query(RagResource).filter_by(source_type="material", source_id=material_id).first()
        if existing:
            existing.status = "disabled"
            db.commit()
        return {"material_id": material_id, "rag_resource_id": None, "action": "disabled"}

    semantic_text = _build_semantic_text(rag_meta, material)
    if not semantic_text.strip():
        db.commit()
        return {"material_id": material_id, "rag_resource_id": None, "action": "empty_text"}

    source_hash = compute_hash(semantic_text)
    content_kind = rag_meta.get("content_kind") or ("image" if material.material_type == "image" else "file")
    quality = _compute_quality(rag_meta)
    visibility = rag_meta.get("visibility", "coach_internal")
    safety_level = rag_meta.get("safety_level", "general")
    title = rag_meta.get("summary", material.name)[:255] or material.name

    existing = db.query(RagResource).filter_by(source_type="material", source_id=material_id).first()
    if existing and existing.source_hash == source_hash:
        db.commit()
        return {"material_id": material_id, "rag_resource_id": existing.id, "action": "unchanged"}

    chunks = chunk_text(semantic_text, chunk_size=settings.rag_chunk_size, overlap=settings.rag_chunk_overlap)
    if not chunks:
        db.commit()
        return {"material_id": material_id, "rag_resource_id": None, "action": "no_chunks"}

    vectors = await embed_texts_batch(chunks)
    if len(vectors) != len(chunks):
        db.commit()
        return {"material_id": material_id, "rag_resource_id": None, "action": "embedding_mismatch"}

    action = "updated"
    if existing:
        existing.title = title
        existing.semantic_text = semantic_text
        existing.source_hash = source_hash
        existing.status = "active"
        existing.content_kind = content_kind
        existing.semantic_quality = quality
        existing.visibility = visibility
        existing.safety_level = safety_level
        resource_id = existing.id
        db.query(RagChunk).filter_by(resource_id=resource_id).delete()
    else:
        resource = RagResource(
            source_type="material", source_id=material_id, title=title,
            semantic_text=semantic_text, source_hash=source_hash,
            content_kind=content_kind, visibility=visibility, safety_level=safety_level,
            status="active", semantic_quality=quality,
        )
        db.add(resource)
        db.flush()
        resource_id = resource.id
        action = "created"

    payload = _build_payload(rag_meta, resource_id, material_id, content_kind)
    points = []
    for idx, (chunk_val, vector) in enumerate(zip(chunks, vectors)):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"rag:{resource_id}:{idx}"))
        chunk_hash = compute_hash(chunk_val)
        db.add(RagChunk(
            resource_id=resource_id, chunk_index=idx, chunk_text=chunk_val,
            chunk_hash=chunk_hash, vector_point_id=point_id,
            embedding_model=settings.rag_embedding_model,
            embedding_dimension=settings.rag_embedding_dimension, status="active",
        ))
        points.append({"id": point_id, "vector": vector, "payload": payload})

    ok = await upsert_chunks(points)
    if not ok:
        _log.warning("upsert_chunks failed for material %s, Qdrant point may be missing", material_id)
    db.commit()
    return {"material_id": material_id, "rag_resource_id": resource_id, "action": action, "qdrant_ok": ok}
