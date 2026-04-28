"""CSV import for material RAG — validates, matches materials, builds semantic text, writes rag_resources + Qdrant."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..models import AssetFolder, Material
from ..models_rag import RagResource, RagChunk
from ..rag.chunker import chunk_text, compute_hash
from ..rag.embedding_client import embed_texts_batch
from ..rag.vector_store import upsert_chunks
from ..rag.vocabulary import resolve_code, get_valid_codes, resolve_tag_values
from .speech_template_import import decode_csv_bytes, split_tag_values, normalize_code, parse_csv_text

_log = logging.getLogger(__name__)

_REQUIRED_FIELDS = ("title", "summary", "status", "rag_enabled", "content_kind", "visibility", "safety_level", "copyright_status")


def _validate_row(row: dict[str, str], line_no: int) -> tuple[list[str], str | None]:
    """Returns (errors, skip_reason). If skip_reason is set, row should be skipped."""
    errors: list[str] = []
    source_type = normalize_code(row.get("source_type"))
    if source_type and source_type != "material":
        errors.append(f"第 {line_no} 行 source_type 不是 material")
        return errors, None

    for field in _REQUIRED_FIELDS:
        if not (row.get(field) or "").strip():
            errors.append(f"第 {line_no} 行缺少必填字段 {field}")
    if errors:
        return errors, None

    status = normalize_code(row.get("status"))
    if status != "approved" and status != "active":
        return errors, "not_approved"

    rag_enabled = normalize_code(row.get("rag_enabled"))
    if rag_enabled not in ("yes", "true", "1"):
        return errors, "rag_disabled"

    copyright_status = normalize_code(row.get("copyright_status"))
    if copyright_status == "unknown":
        return errors, "copyright_unknown"

    content_kind = normalize_code(row.get("content_kind"))
    if content_kind in ("image", "meme") and not (row.get("alt_text") or "").strip():
        errors.append(f"第 {line_no} 行图片类型缺少 alt_text")
    if content_kind == "video" and not ((row.get("transcript") or "").strip() or (row.get("alt_text") or "").strip()):
        errors.append(f"第 {line_no} 行视频类型缺少 transcript 或 alt_text")

    # Vocabulary validation
    if content_kind and content_kind not in get_valid_codes("content_kind"):
        errors.append(f"第 {line_no} 行 content_kind 无效: {content_kind}")
    vis_raw = row.get("visibility") or ""
    if vis_raw and not resolve_code("visibility", normalize_code(vis_raw)):
        errors.append(f"第 {line_no} 行 visibility 无效: {vis_raw}")
    sl_raw = row.get("safety_level") or ""
    if sl_raw and not resolve_code("safety_level", normalize_code(sl_raw)):
        errors.append(f"第 {line_no} 行 safety_level 无效: {sl_raw}")

    return errors, None


def _match_material(db: Session, row: dict[str, str]) -> Material | None:
    """Match CSV row to a material by priority: material_ref > file_hash > file_name."""
    material_ref = (row.get("material_ref") or "").strip()
    if material_ref:
        if material_ref.startswith("materials.id="):
            try:
                mat_id = int(material_ref.split("=")[1])
                return db.query(Material).filter(Material.id == mat_id).first()
            except (ValueError, IndexError):
                pass

    file_hash = (row.get("file_hash") or "").strip()
    if file_hash:
        mat = db.query(Material).filter(Material.file_hash == file_hash).first()
        if mat:
            return mat

    file_name = (row.get("file_name") or row.get("source_filename") or "").strip()
    if file_name:
        mat = db.query(Material).filter(Material.source_filename == file_name).first()
        if mat:
            return mat

    # Fallback: match by folder_name + file_name
    folder_name = (row.get("folder_name") or "").strip()
    if folder_name and file_name:
        folder = db.query(AssetFolder).filter(AssetFolder.name == folder_name).first()
        if folder:
            mat = db.query(Material).filter(
                Material.source_filename == file_name,
                Material.folder_id == folder.id,
                Material.enabled == 1,
            ).first()
            if mat:
                return mat

    return None


def _build_semantic_text(row: dict[str, str]) -> str:
    """Build semantic text from CSV fields per §10.1."""
    _LABELS = {"customer_goal": "适用目标", "intervention_scene": "干预场景", "question_type": "问题类型"}
    parts = []
    for key, label in [("title", "标题"), ("summary", "摘要")]:
        val = (row.get(key) or "").strip()
        if val:
            parts.append(f"{label}: {val}")

    content_desc = (row.get("alt_text") or row.get("transcript") or "").strip()
    if content_desc:
        parts.append(f"内容说明: {content_desc}")

    usage = (row.get("usage_note") or "").strip()
    if usage:
        parts.append(f"使用场景: {usage}")

    for key, label in _LABELS.items():
        vals = resolve_tag_values(key, row.get(key))
        if vals:
            parts.append(f"{label}: {', '.join(vals)}")

    tags = split_tag_values(row.get("tags"))
    if tags:
        parts.append(f"标签: {', '.join(tags)}")
    return "\n".join(parts)


def _compute_quality(row: dict[str, str]) -> str:
    """Compute semantic quality: ok / medium / weak."""
    has_title = bool((row.get("title") or "").strip())
    has_summary = bool((row.get("summary") or "").strip())
    has_content_desc = bool((row.get("alt_text") or row.get("transcript") or "").strip())
    has_usage = bool((row.get("usage_note") or "").strip())
    has_tags = bool(split_tag_values(row.get("tags")))

    if has_title and has_summary and has_content_desc and has_usage and has_tags:
        return "ok"
    if has_title and has_summary and has_usage and has_tags:
        return "medium"
    return "weak"


def _build_payload(row: dict[str, str], resource_id: int, material_id: int, content_kind: str) -> dict:
    """Build Qdrant payload."""
    payload: dict[str, Any] = {
        "resource_id": resource_id, "source_type": "material",
        "source_id": material_id, "status": "active", "content_kind": content_kind,
    }
    for key in ("customer_goal", "intervention_scene", "question_type"):
        vals = resolve_tag_values(key, row.get(key))
        if vals:
            payload[key] = vals
    payload["visibility"] = resolve_code("visibility", normalize_code(row.get("visibility"))) or "coach_internal"
    payload["safety_level"] = resolve_code("safety_level", normalize_code(row.get("safety_level"))) or "general"
    payload["semantic_quality"] = _compute_quality(row)
    return payload


async def import_material_rag_rows(
    db: Session,
    rows: list[dict[str, str]],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Import material RAG rows from CSV. Returns stats."""
    stats: dict[str, Any] = {
        "created": 0, "updated": 0, "skipped": 0, "errors": [],
        "rows": [],
    }

    try:
        for index, row in enumerate(rows, start=2):
            errors, skip_reason = _validate_row(row, index)
            if errors:
                stats["errors"].extend(errors)
            if skip_reason:
                stats["skipped"] += 1
                stats["rows"].append({"title": row.get("title", ""), "action": "skipped", "skip_reason": skip_reason})
                continue
            if errors:
                stats["skipped"] += 1
                continue

            title = (row.get("title") or "").strip()
            content_kind = normalize_code(row.get("content_kind")) or "file"
            visibility = resolve_code("visibility", normalize_code(row.get("visibility"))) or "coach_internal"
            safety_level = resolve_code("safety_level", normalize_code(row.get("safety_level"))) or "general"
            quality = _compute_quality(row)

            # Match to material
            material = _match_material(db, row)
            if not material:
                stats["skipped"] += 1
                stats["rows"].append({"title": title, "action": "skipped", "skip_reason": "material_not_found"})
                continue

            # Check storage status
            if material.storage_status != "ready":
                stats["skipped"] += 1
                stats["rows"].append({"title": title, "action": "skipped", "skip_reason": "storage_not_ready"})
                continue

            # Assign folder if CSV has folder_name and material has no folder
            folder_name_col = (row.get("folder_name") or "").strip()
            if folder_name_col and material.folder_id is None:
                folder = db.query(AssetFolder).filter(AssetFolder.name == folder_name_col).first()
                if folder:
                    material.folder_id = folder.id

            # Customer-sendable downgrade check
            customer_sendable = normalize_code(row.get("customer_sendable")) in ("yes", "true", "1")
            has_public = bool((row.get("public_url") or "").strip()) or bool((material.public_url or "").strip())
            if customer_sendable and visibility != "customer_visible":
                stats["errors"].append(f"第 {index} 行 customer_sendable=yes 但 visibility 不是 customer_visible")
                stats["skipped"] += 1
                continue
            if visibility == "customer_visible" and not has_public:
                stats["errors"].append(f"第 {index} 行 customer_visible 素材缺少 materials.public_url")
                stats["skipped"] += 1
                continue
            if visibility == "customer_visible" and safety_level in {"medical_sensitive", "doctor_review", "contraindicated"}:
                stats["errors"].append(f"第 {index} 行医疗敏感/医生审核/禁忌素材不能设为 customer_visible")
                stats["skipped"] += 1
                continue

            # Build semantic text
            semantic_text = _build_semantic_text(row)
            source_hash = compute_hash(semantic_text)
            if not semantic_text.strip():
                stats["skipped"] += 1
                stats["rows"].append({"title": title, "action": "skipped", "skip_reason": "empty_semantic_text"})
                continue

            # Find or create rag_resource
            existing = db.query(RagResource).filter_by(
                source_type="material", source_id=material.id,
            ).first()

            if existing and existing.source_hash == source_hash:
                stats["skipped"] += 1
                stats["rows"].append({"title": title, "action": "skipped", "skip_reason": "unchanged"})
                continue

            # Chunk + embed
            chunks = chunk_text(semantic_text, chunk_size=settings.rag_chunk_size, overlap=settings.rag_chunk_overlap)
            if not chunks:
                stats["skipped"] += 1
                continue

            vectors = await embed_texts_batch(chunks)
            if len(vectors) != len(chunks):
                stats["errors"].append(f"第 {index} 行 embedding 数量不匹配")
                stats["skipped"] += 1
                continue

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
                    source_type="material",
                    source_id=material.id,
                    title=title,
                    semantic_text=semantic_text,
                    source_hash=source_hash,
                    content_kind=content_kind,
                    visibility=visibility,
                    safety_level=safety_level,
                    status="active",
                    semantic_quality=quality,
                )
                db.add(resource)
                db.flush()
                resource_id = resource.id
                action = "created"

            # Write chunks + Qdrant
            payload = _build_payload(row, resource_id, material.id, content_kind)
            points = []
            for idx, (chunk_val, vector) in enumerate(zip(chunks, vectors)):
                point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"rag:{resource_id}:{idx}"))
                chunk_hash = compute_hash(chunk_val)
                db.add(RagChunk(
                    resource_id=resource_id,
                    chunk_index=idx,
                    chunk_text=chunk_val,
                    chunk_hash=chunk_hash,
                    vector_point_id=point_id,
                    embedding_model=settings.rag_embedding_model,
                    embedding_dimension=settings.rag_embedding_dimension,
                    status="active",
                ))
                points.append({"id": point_id, "vector": vector, "payload": payload})

            await upsert_chunks(points)
            db.commit()
            stats[action] += 1
            stats["rows"].append({
                "title": title, "action": action,
                "material_id": material.id, "quality": quality,
            })

        if dry_run:
            db.rollback()
    except Exception:
        db.rollback()
        raise

    return stats


def import_material_rag_csv(db: Session, csv_text: str, *, dry_run: bool = False):
    """Sync wrapper for import_material_rag_rows — parses CSV then calls async."""
    import asyncio
    rows = parse_csv_text(csv_text)
    return asyncio.get_event_loop().run_until_complete(
        import_material_rag_rows(db, rows, dry_run=dry_run)
    )
