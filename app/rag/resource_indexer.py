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
    category_l3: str = "",
    category_code: str = "",
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

    usage_note = meta.get("usage_note")
    if usage_note:
        parts.append(f"使用场景: {usage_note}")
    tags = meta.get("tags")
    if tags and isinstance(tags, list):
        parts.append(f"标签: {', '.join(tags)}")
    if template.scene_key:
        parts.append(f"场景: {template.scene_key}")
    if template.style:
        parts.append(f"风格: {template.style}")
    if category_l1:
        parts.append(f"大类: {category_l1}")
    if category_l2:
        parts.append(f"子类: {category_l2}")
    if category_l3:
        parts.append(f"三级分类: {category_l3}")
    if category_code:
        parts.append(f"分类代码: {category_code}")
    return "\n".join(parts)


def _build_payload_from_metadata(meta: dict, category_l1: str = "", category_l2: str = "", category_l3: str = "", category_code: str = "") -> dict:
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
    if category_l3:
        extra["category_l3"] = category_l3
    if category_code:
        extra["category_code"] = category_code
    return {**payload_tags, **extra}


async def index_speech_templates(db: Session) -> dict:
    """Index all speech templates. Returns stats: {indexed, skipped, errors}."""
    stats = {"indexed": 0, "skipped": 0, "errors": 0}
    templates = db.query(SpeechTemplate).filter(SpeechTemplate.deleted_at.is_(None)).all()

    # Pre-load category names for resolution (L3 → L2 → L1)
    cat_by_id: dict[int, SpeechCategory] = {}
    for cat in db.query(SpeechCategory).filter(SpeechCategory.deleted_at.is_(None)).all():
        cat_by_id[cat.id] = cat

    def _resolve_cat(category_id: int | None) -> tuple[str, str, str, str]:
        if not category_id or category_id not in cat_by_id:
            return "", "", "", ""
        c = cat_by_id[category_id]
        code = c.code or ""
        if c.level == 3:
            l3_name = c.name
            l2 = cat_by_id.get(c.parent_id)
            l2_name = l2.name if l2 else ""
            l1_name = ""
            if l2 and l2.parent_id:
                l1 = cat_by_id.get(l2.parent_id)
                l1_name = l1.name if l1 else ""
            return l1_name, l2_name, l3_name, code
        elif c.level == 2:
            l2_name = c.name
            l1_name = ""
            if c.parent_id:
                l1 = cat_by_id.get(c.parent_id)
                l1_name = l1.name if l1 else ""
            return l1_name, l2_name, "", code
        return "", "", "", ""

    for tpl in templates:
        try:
            category_l1, category_l2, category_l3, category_code = _resolve_cat(tpl.category_id)

            semantic_text = _build_semantic_text_speech(tpl, category_l1, category_l2, category_l3, category_code)
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
            meta_payload = _build_payload_from_metadata(meta, category_l1, category_l2, category_l3, category_code)

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


async def index_single_speech_template(db: Session, template_id: int) -> dict:
    """Incrementally index a single speech template."""
    tpl = db.query(SpeechTemplate).get(template_id)
    if not tpl or tpl.deleted_at:
        return {"indexed": 0, "error": "not found"}

    # Resolve L3 → L2 → L1 + code
    cat_l1, cat_l2, cat_l3, cat_code = "", "", "", ""
    if tpl.category_id:
        cat = db.query(SpeechCategory).get(tpl.category_id)
        if cat:
            cat_code = cat.code or ""
            if cat.level == 3:
                cat_l3 = cat.name
                parent = db.query(SpeechCategory).get(cat.parent_id) if cat.parent_id else None
                if parent:
                    cat_l2 = parent.name
                    grandparent = db.query(SpeechCategory).get(parent.parent_id) if parent.parent_id else None
                    if grandparent:
                        cat_l1 = grandparent.name
            elif cat.level == 2:
                cat_l2 = cat.name
                parent = db.query(SpeechCategory).get(cat.parent_id) if cat.parent_id else None
                if parent:
                    cat_l1 = parent.name

    semantic_text = _build_semantic_text_speech(tpl, cat_l1, cat_l2, cat_l3, cat_code)
    source_hash = compute_hash(semantic_text)

    existing = db.query(RagResource).filter_by(
        source_type="speech_template", source_id=tpl.id
    ).first()

    if existing and existing.source_hash == source_hash:
        return {"indexed": 0, "skipped": True}

    chunks = chunk_text(semantic_text, chunk_size=settings.rag_chunk_size, overlap=settings.rag_chunk_overlap)
    if not chunks:
        return {"indexed": 0, "error": "empty content"}

    vectors = await embed_texts_batch(chunks)
    if len(vectors) != len(chunks):
        return {"indexed": 0, "error": "embedding mismatch"}

    meta = _parse_metadata(tpl)
    meta_payload = _build_payload_from_metadata(meta, cat_l1, cat_l2, cat_l3, cat_code)
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
            source_type="speech_template", source_id=tpl.id,
            title=title, semantic_text=semantic_text, source_hash=source_hash,
            content_kind="script", visibility=visibility, safety_level=safety_level,
            status="active", semantic_quality="ok",
        )
        db.add(resource)
        db.flush()
        resource_id = resource.id

    points = []
    for idx, (chunk_text_val, vector) in enumerate(zip(chunks, vectors)):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"rag:{resource_id}:{idx}"))
        chunk_hash = compute_hash(chunk_text_val)
        db.add(RagChunk(
            resource_id=resource_id, chunk_index=idx, chunk_text=chunk_text_val,
            chunk_hash=chunk_hash, vector_point_id=point_id,
            embedding_model=settings.rag_embedding_model,
            embedding_dimension=settings.rag_embedding_dimension, status="active",
        ))
        points.append({
            "id": point_id, "vector": vector,
            "payload": {
                "resource_id": resource_id, "source_type": "speech_template",
                "source_id": tpl.id, "status": "active", "content_kind": "script",
                "safety_level": safety_level, "visibility": visibility, **meta_payload,
            },
        })

    await upsert_chunks(points)
    db.commit()
    return {"indexed": 1, "chunks": len(points)}


async def index_materials(db: Session) -> dict:
    """Sync material RAG resources — disable orphans, detect stale, auto-index materials with rag_meta_json."""
    stats = {"synced": 0, "disabled": 0, "stale": 0, "indexed": 0, "errors": 0}

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

    # Phase 1b: detect stale resources (source hash mismatch)
    from ..services.material_rag_service import load_rag_meta
    from ..services.material_rag_service import _build_semantic_text as _build_mat_semantic
    for rag_res in db.query(RagResource).filter(
        RagResource.source_type == "material",
        RagResource.status == "active",
    ).all():
        try:
            mat = db.query(Material).filter(Material.id == rag_res.source_id).first()
            if not mat or not mat.rag_meta_json:
                continue
            rag_meta = load_rag_meta(mat)
            current_text = _build_mat_semantic(rag_meta, mat)
            if current_text:
                current_hash = compute_hash(current_text)
                if current_hash != rag_res.source_hash:
                    rag_res.semantic_quality = "stale"
                    stats["stale"] += 1
        except Exception:
            pass
    if stats["stale"]:
        db.commit()
        _log.info("Marked %s stale material RAG resources", stats["stale"])

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
