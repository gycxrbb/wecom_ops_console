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
from .query_compiler import compile_query, QueryIntent
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


def _apply_tag_boosts(
    hits: list[dict],
    query_intent: QueryIntent,
    *,
    goal_boost: float = 0.05,
    qtype_boost: float = 0.04,
    scene_boost: float = 0.03,
) -> list[dict]:
    """Boost scores for hits matching query intent tags."""
    goal_set = set(query_intent.customer_goals or [])
    qtype_set = set(query_intent.question_types or [])
    scene_set = set(query_intent.intervention_scenes or [])

    for hit in hits:
        payload = hit.get("payload", {})
        boost = 0.0
        if goal_set and goal_set & set(payload.get("customer_goal", [])):
            boost += goal_boost
        if qtype_set and qtype_set & set(payload.get("question_type", [])):
            boost += qtype_boost
        if scene_set and scene_set & set(payload.get("intervention_scene", [])):
            boost += scene_boost
        if boost:
            hit["score"] = hit["score"] + boost
            hit["tag_boost"] = round(boost, 3)
    return hits


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
            output_style=output_style,
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
    output_style: str,
    session_id: str | None,
    message_id: str | None,
) -> RagBundle:
    t0 = time.time()

    # 1. Query compilation — structured intent extraction
    query_intent = compile_query(message, scene_key)
    intent_json_str = json.dumps({"domain": query_intent.domain, "negative_scenes": query_intent.negative_scenes}, ensure_ascii=False)
    qi_json_str = json.dumps({
        "domain": query_intent.domain,
        "customer_goals": query_intent.customer_goals,
        "intervention_scenes": query_intent.intervention_scenes,
        "question_types": query_intent.question_types,
        "max_safety_level": query_intent.max_safety_level,
    }, ensure_ascii=False)

    # 2. Build query from compiled intent
    query_text = query_intent.query_text

    # 3. Embed query
    vectors = await embed_texts([query_text])
    if not vectors:
        return RagBundle(rag_status="unavailable")
    query_vector = vectors[0]

    # 4. Build Qdrant filters from query intent
    filters: dict[str, Any] = {"content_kind": ["script", "text", "knowledge_card"]}
    must_not: dict[str, Any] = {"semantic_quality": ["weak", "stale"]}

    # Scene-based positive filter
    scene_values: list[str] | None = None
    if query_intent.intervention_scenes:
        scene_values = query_intent.intervention_scenes
    else:
        mapped_scene = _SCENE_MAP.get(scene_key)
        if mapped_scene:
            scene_values = [mapped_scene]
    if scene_values:
        filters["intervention_scene"] = scene_values

    # Domain exclusion: when nutrition intent detected, exclude points_operation scenes
    if query_intent.domain == "nutrition" and query_intent.negative_scenes:
        must_not["intervention_scene"] = query_intent.negative_scenes

    # Safety level cap
    if query_intent.max_safety_level:
        _SAFETY_ORDER = ["general", "nutrition_education", "medical_sensitive", "doctor_review", "contraindicated"]
        max_idx = _SAFETY_ORDER.index(query_intent.max_safety_level) if query_intent.max_safety_level in _SAFETY_ORDER else 4
        filters["safety_level"] = _SAFETY_ORDER[:max_idx + 1]

    # 5. Phase 1: Search scripts/knowledge cards for prompt injection
    raw_hits = await search(
        query_vector, top_k=settings.rag_top_k,
        filters=filters, must_not=must_not or None,
    )

    # 5a. Fallback: drop scene filter if too strict (most data may lack intervention_scene)
    if not raw_hits and scene_values:
        broad_filters = {k: v for k, v in filters.items() if k != "intervention_scene"}
        _log.info("RAG scene filter returned 0 hits, retrying without intervention_scene filter")
        raw_hits = await search(
            query_vector, top_k=settings.rag_top_k,
            filters=broad_filters, must_not=must_not or None,
        )

    # 5b. Apply tag-based score boosts (customer_goal, question_type, intervention_scene)
    if raw_hits:
        _apply_tag_boosts(raw_hits, query_intent)

    # 5c. Phase 2: Search materials for recommended_assets only
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
                "semantic_text": resource.semantic_text[:500] if resource and resource.semantic_text else "",
                "tag_boost": hit.get("tag_boost", 0.0),
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

    # 6b. Rerank if enabled
    if settings.rag_rerank_enabled and enriched_hits:
        from .reranker import rerank_hits
        enriched_hits = await rerank_hits(
            query_vector, enriched_hits, top_n=settings.rag_rerank_top_n,
        )

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
                tag_boost=hit.get("tag_boost", 0.0),
            ))
    finally:
        db.close()

    # 10. Build recommended assets from phase 2 material hits
    recommended_assets = await _build_recommended_assets(material_source_ids, output_style=output_style)

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
            "tag_boost": h.get("tag_boost", 0.0),
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
        query_intent_json=qi_json_str,
        rerank_scores_json=json.dumps([
            {"id": h["id"], "score": h.get("score"), "rerank_score": h.get("rerank_score"), "filter_reason": h["filter_reason"]}
            for h in enriched_hits
        ], ensure_ascii=False) if settings.rag_rerank_enabled else None,
    )

    return RagBundle(
        sources=sources,
        recommended_assets=recommended_assets,
        rag_status="ok",
        context_text=context_text,
    )


async def _build_recommended_assets(
    material_ids: list[int],
    *,
    output_style: str = "coach_brief",
) -> list[RagRecommendedAsset]:
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

        # In customer_reply mode, prioritize customer-visible assets
        if output_style == "customer_reply" and assets:
            assets.sort(key=lambda a: (0 if a.customer_sendable else 1))

        return assets
    finally:
        db.close()
