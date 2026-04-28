"""Resource indexer — index speech templates and materials into RAG."""
from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy.orm import Session

from ..config import settings
from ..models import SpeechTemplate, Material
from ..models import SpeechCategory
from ..models_rag import RagResource, RagChunk
from .chunker import chunk_text, compute_hash
from .embedding_client import embed_texts_batch
from .vector_store import upsert_chunks

_log = logging.getLogger(__name__)

_TAG_LABELS = {
    "customer_goal": "目标",
    "intervention_scene": "场景",
    "question_type": "问题类型",
}


def _parse_metadata(template: SpeechTemplate) -> dict:
    """Parse metadata_json from speech template."""
    raw = getattr(template, "metadata_json", None)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _build_semantic_text_speech(
    template: SpeechTemplate,
    category_l1: str = "",
    category_l2: str = "",
) -> str:
    parts = []
    if template.label:
        parts.append(template.label)
    if template.content:
        parts.append(template.content)

    # Inject metadata tags into semantic text for richer vector representation
    meta = _parse_metadata(template)
    summary = meta.get("summary")
    if summary:
        parts.append(summary)
    for key, label in _TAG_LABELS.items():
        values = meta.get(key)
        if values:
            if isinstance(values, list):
                parts.append(f"{label}: {', '.join(values)}")
            else:
                parts.append(f"{label}: {values}")

    if template.scene_key:
        parts.append(f"场景: {template.scene_key}")
    if template.style:
        parts.append(f"风格: {template.style}")
    if category_l1:
        parts.append(f"大类: {category_l1}")
    if category_l2:
        parts.append(f"子类: {category_l2}")
    return "\n".join(parts)


def _build_payload_from_metadata(meta: dict, category_l1: str = "", category_l2: str = "") -> dict:
    """Build Qdrant payload fields from parsed metadata."""
    payload_tags: dict[str, list[str]] = {}
    for key in ("customer_goal", "intervention_scene", "question_type"):
        values = meta.get(key)
        if values:
            if isinstance(values, list):
                payload_tags[key] = values
            else:
                payload_tags[key] = [str(values)]

    extra = {}
    if meta.get("safety_level"):
        extra["safety_level"] = meta["safety_level"]
    if meta.get("visibility"):
        extra["visibility"] = meta["visibility"]
    if category_l1:
        extra["category_l1"] = category_l1
    if category_l2:
        extra["category_l2"] = category_l2
    return {**payload_tags, **extra}


async def index_speech_templates(db: Session) -> dict:
    """Index all speech templates. Returns stats: {indexed, skipped, errors}."""
    stats = {"indexed": 0, "skipped": 0, "errors": 0}
    templates = db.query(SpeechTemplate).filter(SpeechTemplate.deleted_at.is_(None)).all()

    # Pre-load category names for resolution
    cat_l2_map: dict[int, str] = {}
    cat_l1_map: dict[int, str] = {}
    for cat in db.query(SpeechCategory).filter(SpeechCategory.deleted_at.is_(None)).all():
        if cat.level == 2 and cat.parent_id:
            cat_l2_map[cat.id] = cat.name
            cat_l1_map[cat.parent_id] = ""  # will be filled below
    for cat in db.query(SpeechCategory).filter(SpeechCategory.deleted_at.is_(None)).all():
        if cat.level == 1 and cat.id in cat_l1_map:
            cat_l1_map[cat.id] = cat.name

    for tpl in templates:
        try:
            # Resolve category
            category_l1 = ""
            category_l2 = ""
            if tpl.category_id and tpl.category_id in cat_l2_map:
                category_l2 = cat_l2_map[tpl.category_id]
                cat = tpl.category
                if cat and cat.parent_id and cat.parent_id in cat_l1_map:
                    category_l1 = cat_l1_map[cat.parent_id]

            semantic_text = _build_semantic_text_speech(tpl, category_l1, category_l2)
            source_hash = compute_hash(semantic_text)

            existing = db.query(RagResource).filter_by(
                source_type="speech_template", source_id=tpl.id
            ).first()

            if existing and existing.source_hash == source_hash:
                stats["skipped"] += 1
                continue

            chunks = chunk_text(semantic_text, chunk_size=settings.rag_chunk_size, overlap=settings.rag_chunk_overlap)
            if not chunks:
                continue

            vectors = await embed_texts_batch(chunks)
            if len(vectors) != len(chunks):
                stats["errors"] += 1
                continue

            # Parse metadata for enriched payload
            meta = _parse_metadata(tpl)
            meta_payload = _build_payload_from_metadata(meta, category_l1, category_l2)

            title = tpl.label or f"话术 #{tpl.id}"
            safety_level = meta.get("safety_level", "general")
            visibility = meta.get("visibility", "coach_internal")

            if existing:
                existing.title = title
                existing.semantic_text = semantic_text
                existing.source_hash = source_hash
                existing.status = "active"
                existing.content_kind = "script"
                existing.semantic_quality = "ok"
                existing.safety_level = safety_level
                existing.visibility = visibility
                resource_id = existing.id
                db.query(RagChunk).filter_by(resource_id=resource_id).delete()
            else:
                resource = RagResource(
                    source_type="speech_template",
                    source_id=tpl.id,
                    title=title,
                    semantic_text=semantic_text,
                    source_hash=source_hash,
                    content_kind="script",
                    visibility=visibility,
                    safety_level=safety_level,
                    status="active",
                    semantic_quality="ok",
                )
                db.add(resource)
                db.flush()
                resource_id = resource.id

            points = []
            for idx, (chunk_text_val, vector) in enumerate(zip(chunks, vectors)):
                point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"rag:{resource_id}:{idx}"))
                chunk_hash = compute_hash(chunk_text_val)
                db.add(RagChunk(
                    resource_id=resource_id,
                    chunk_index=idx,
                    chunk_text=chunk_text_val,
                    chunk_hash=chunk_hash,
                    vector_point_id=point_id,
                    embedding_model=settings.rag_embedding_model,
                    embedding_dimension=settings.rag_embedding_dimension,
                    status="active",
                ))
                points.append({
                    "id": point_id,
                    "vector": vector,
                    "payload": {
                        "resource_id": resource_id,
                        "source_type": "speech_template",
                        "source_id": tpl.id,
                        "status": "active",
                        "content_kind": "script",
                        "safety_level": safety_level,
                        "visibility": visibility,
                        **meta_payload,
                    },
                })

            await upsert_chunks(points)
            db.commit()
            stats["indexed"] += 1
        except Exception:
            _log.exception("Failed to index speech_template %s", tpl.id)
            db.rollback()
            stats["errors"] += 1

    return stats


async def index_materials(db: Session) -> dict:
    """Sync material RAG resources — disable orphans, auto-index materials with rag_meta_json."""
    stats = {"synced": 0, "disabled": 0, "indexed": 0, "errors": 0}

    # Phase 1: disable orphan rag_resources
    rag_resources = db.query(RagResource).filter(
        RagResource.source_type == "material",
        RagResource.status == "active",
    ).all()

    for rag_res in rag_resources:
        try:
            mat = db.query(Material).filter(Material.id == rag_res.source_id).first()
            if not mat or mat.enabled != 1 or mat.deleted_at is not None or mat.storage_status != "ready":
                rag_res.status = "disabled"
                db.commit()
                stats["disabled"] += 1
            else:
                stats["synced"] += 1
        except Exception:
            _log.exception("Failed to sync material rag_resource %s", rag_res.id)
            db.rollback()
            stats["errors"] += 1

    # Phase 2: auto-index materials with rag_meta_json but no rag_resource
    from ..services.material_rag_service import save_rag_meta_and_index, load_rag_meta

    materials_with_meta = db.query(Material).filter(
        Material.rag_meta_json != '',
        Material.rag_meta_json.isnot(None),
        Material.enabled == 1,
        Material.storage_status == 'ready',
    ).all()

    existing_source_ids = {r.source_id for r in db.query(RagResource).filter(
        RagResource.source_type == "material",
    ).all()}

    for mat in materials_with_meta:
        if mat.id in existing_source_ids:
            continue
        try:
            rag_meta = load_rag_meta(mat)
            if not rag_meta.get("rag_enabled", True):
                continue
            await save_rag_meta_and_index(db, mat.id, rag_meta)
            stats["indexed"] += 1
        except Exception:
            _log.exception("Failed to auto-index material %s", mat.id)
            db.rollback()
            stats["errors"] += 1

    return stats
