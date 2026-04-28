"""RAG retriever — orchestrates embedding, vector search, and result assembly."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from ..config import settings
from ..database import SessionLocal
from ..models import Material
from ..models_rag import RagResource
from .embedding_client import embed_texts
from .intent_rules import recognize_intent
from .schemas import RagBundle, RagSource, RagRecommendedAsset
from .vector_store import search, is_available
from .audit import write_retrieval_log

_log = logging.getLogger(__name__)

_SCENE_MAP = {
    "qa_support": "qa_support",
    "meal_review": "meal_review",
    "meal_checkin": "meal_checkin",
    "abnormal_intervention": "obstacle_breaking",
    "period_review": "period_review",
    "long_term_maintenance": "maintenance",
}


async def retrieve_rag_context(
    *,
    customer_id: int,
    message: str,
    scene_key: str,
    output_style: str,
    profile_context: Any = None,
    session_id: str | None = None,
    message_id: str | None = None,
) -> RagBundle:
    """Main retrieval entry — query → embed → search → bucket → return."""
    if not settings.rag_enabled:
        return RagBundle(rag_status="ok")

    if not is_available():
        return RagBundle(rag_status="unavailable")

    try:
        return await _do_retrieve(
            customer_id=customer_id,
            message=message,
            scene_key=scene_key,
            session_id=session_id,
            message_id=message_id,
        )
    except Exception:
        _log.exception("RAG retrieval failed")
        return RagBundle(rag_status="unavailable")


async def _do_retrieve(
    *,
    customer_id: int,
    message: str,
    scene_key: str,
    session_id: str | None,
    message_id: str | None,
) -> RagBundle:
    t0 = time.time()

    # 1. Intent recognition
    intent = recognize_intent(message, scene_key)
    intent_json_str = json.dumps(intent, ensure_ascii=False)

    # 2. Build query
    query_text = f"{scene_key} {message}"

    # 3. Embed query
    vectors = await embed_texts([query_text])
    if not vectors:
        return RagBundle(rag_status="unavailable")
    query_vector = vectors[0]

    # 4. Build Qdrant filters
    filters: dict[str, Any] = {"content_kind": ["script", "text", "knowledge_card"]}
    must_not: dict[str, Any] = {}

    # Scene-based positive filter using _SCENE_MAP
    mapped_scene = _SCENE_MAP.get(scene_key)
    if mapped_scene:
        filters["intervention_scene"] = [mapped_scene]

    # Domain exclusion: when nutrition intent detected, exclude points_operation scenes
    if intent["domain"] == "nutrition" and intent["negative_scenes"]:
        must_not["intervention_scene"] = intent["negative_scenes"]

    # 5. Phase 1: Search scripts/knowledge cards for prompt injection
    raw_hits = await search(
        query_vector, top_k=settings.rag_top_k,
        filters=filters, must_not=must_not or None,
    )

    # 5b. Phase 2: Search materials for recommended_assets only
    material_filters: dict[str, Any] = {"content_kind": ["image", "video", "meme", "file"]}
    raw_material_hits = await search(
        query_vector, top_k=6,
        filters=material_filters, must_not=must_not or None,
    )

    latency_ms = int((time.time() - t0) * 1000)

    if not raw_hits:
        write_retrieval_log(
            session_id=session_id, message_id=message_id,
            customer_id=customer_id, query_text=query_text[:500],
            latency_ms=latency_ms, intent_json=intent_json_str,
        )
        return RagBundle(rag_status="no_hit")

    # 6. Build enriched hit records with titles (for filtering & audit)
    db = SessionLocal()
    enriched_hits: list[dict] = []
    material_source_ids: list[int] = []
    try:
        for hit in raw_hits[:settings.rag_rerank_top_n]:
            payload = hit.get("payload", {})
            resource_id = payload.get("resource_id")
            resource = db.query(RagResource).filter_by(id=resource_id).first() if resource_id else None
            title = resource.title if resource else f"资源#{resource_id}"

            enriched_hits.append({
                "id": hit.get("id"),
                "score": hit.get("score", 0.0),
                "payload": payload,
                "title": title,
                "resource_id": resource_id or 0,
                "source_type": payload.get("source_type", ""),
                "source_id": payload.get("source_id", 0),
                "filter_reason": None,
            })

        # Collect material IDs from phase 2 hits
        for hit in raw_material_hits[:3]:
            payload = hit.get("payload", {})
            source_id = payload.get("source_id")
            if source_id and hit.get("score", 0) >= settings.rag_min_score:
                material_source_ids.append(source_id)
    finally:
        db.close()

    # 7. Apply score gates
    top_score = enriched_hits[0]["score"] if enriched_hits else 0.0
    min_score = settings.rag_min_score
    relative_threshold = top_score * settings.rag_relative_score_ratio

    for hit in enriched_hits:
        score = hit["score"]
        if score < min_score:
            hit["filter_reason"] = "below_min_score"
        elif score < relative_threshold:
            hit["filter_reason"] = "below_relative_score"

    # 8. Separate visible vs filtered
    visible = [h for h in enriched_hits if not h["filter_reason"]]
    visible = visible[:settings.rag_max_visible_sources]

    # 9. Build sources from visible hits
    db = SessionLocal()
    sources: list[RagSource] = []
    try:
        for hit in visible:
            resource_id = hit["resource_id"]
            resource = db.query(RagResource).filter_by(id=resource_id).first() if resource_id else None
            snippet = ""
            if resource and resource.semantic_text:
                snippet = resource.semantic_text[:200]

            sources.append(RagSource(
                resource_id=resource_id,
                source_type=hit["source_type"],
                title=hit["title"],
                snippet=snippet,
                score=round(hit["score"], 4),
                content_kind=hit["payload"].get("content_kind", "text"),
                safety_level=hit["payload"].get("safety_level", "general"),
            ))
    finally:
        db.close()

    # 10. Build recommended assets from phase 2 material hits
    recommended_assets = await _build_recommended_assets(material_source_ids)

    # 11. Build context text for prompt injection
    context_parts = []
    for src in sources:
        context_parts.append(f"[{src.content_kind}] {src.title}\n{src.snippet}")
    context_text = "\n\n".join(context_parts) if context_parts else ""

    # 12. Audit — enriched hit_json with title and filter_reason
    audit_material_hits = [
        {"id": h.get("id"), "source_id": h.get("payload", {}).get("source_id"), "score": round(h.get("score", 0), 4)}
        for h in raw_material_hits[:6]
    ]
    audit_hits = [
        {
            "id": h["id"],
            "resource_id": h["resource_id"],
            "title": h["title"],
            "score": round(h["score"], 4),
            "filter_reason": h["filter_reason"],
        }
        for h in enriched_hits
    ]
    write_retrieval_log(
        session_id=session_id, message_id=message_id,
        customer_id=customer_id, query_text=query_text[:500],
        filter_json=json.dumps({**filters, "must_not": must_not} if must_not else filters),
        hit_json=json.dumps({"phase1": audit_hits, "material": audit_material_hits, "material_ids": material_source_ids}, ensure_ascii=False),
        latency_ms=latency_ms,
        intent_json=intent_json_str,
    )

    return RagBundle(
        sources=sources,
        recommended_assets=recommended_assets,
        rag_status="ok",
        context_text=context_text,
    )


async def _build_recommended_assets(material_ids: list[int]) -> list[RagRecommendedAsset]:
    if not material_ids:
        return []

    db = SessionLocal()
    try:
        materials = db.query(Material).filter(
            Material.id.in_(material_ids),
            Material.enabled == 1,
            Material.storage_status == "ready",
            Material.deleted_at.is_(None),
        ).all()

        # Also fetch rag_resource for visibility/safety_level
        rag_resources = {
            r.source_id: r
            for r in db.query(RagResource).filter(
                RagResource.source_type == "material",
                RagResource.source_id.in_(material_ids),
            ).all()
        }

        assets = []
        for mat in materials:
            rag_res = rag_resources.get(mat.id)
            resource_id = rag_res.id if rag_res else 0
            visibility = rag_res.visibility if rag_res else "coach_internal"
            safety_level = rag_res.safety_level if rag_res else "general"
            summary = rag_res.semantic_text[:100] if rag_res and rag_res.semantic_text else ""

            assets.append(RagRecommendedAsset(
                material_id=mat.id,
                title=mat.name,
                material_type=mat.material_type,
                source_filename=mat.source_filename or mat.name,
                preview_url=mat.public_url or mat.url or None,
                download_url=mat.public_url or mat.url or None,
                public_url=mat.public_url or None,
                reason=summary or "与当前问题相关",
                visibility=visibility,
                safety_level=safety_level,
                customer_sendable=visibility == "customer_visible",
                resource_id=resource_id,
            ))
        return assets
    finally:
        db.close()
