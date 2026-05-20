"""Helper: emit visual decision SSE events during answer stream.

Separated from __init__.py to keep the main stream function under size limits.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from ._types import AiStreamEvent

_log = logging.getLogger(__name__)


@dataclass
class _DecisionHolder:
    """Mutable container to pass the decision back to the caller."""
    decision: object | None = None


async def _run_visual_decision(
    *,
    message: str,
    scene_key: str,
    rag_sources: list[dict] | None,
    safety_card: object | None,
    holder: _DecisionHolder | None = None,
) -> AiStreamEvent | None:
    """Assess visual need and return the SSE event (or None).

    Designed to run as a concurrent task alongside the LLM stream.
    The caller yields the returned event at a convenient point.
    """
    from app.ai_visual.services.decision import assess_visual_need_async

    decision = await assess_visual_need_async(
        message=message,
        scene_key=scene_key,
        rag_sources=rag_sources,
        safety_card=safety_card,
    )

    _log.info("Visual decision: need=%s, mode=%s, conf=%.2f, topic=%s",
              decision.need_visual, decision.decision_mode, decision.confidence, decision.topic)

    if holder is not None:
        holder.decision = decision

    if not decision.need_visual:
        return None

    data = {
        "need_visual": True,
        "confidence": decision.confidence,
        "decision_mode": decision.decision_mode,
        "topic": decision.topic,
        "reason": decision.reason,
        "safety_level": decision.safety_level,
        "visual_type": decision.visual_type,
    }
    if decision.score_factors:
        data["score_factors"] = decision.score_factors

    if decision.decision_mode == "manual_confirm" and decision.confirm_question:
        return AiStreamEvent(event="visual_confirm_required", data={
            "topic": decision.topic,
            "confidence": decision.confidence,
            "confirm_question": decision.confirm_question,
            "safety_level": decision.safety_level,
        })

    return AiStreamEvent(event="visual_decision", data=data)


async def _emit_visual_decision(
    *,
    message: str,
    scene_key: str,
    rag_sources: list[dict] | None,
    safety_card: object | None,
    holder: _DecisionHolder | None = None,
) -> AsyncIterator[AiStreamEvent]:
    """Assess visual need and yield appropriate SSE events.

    If holder is provided, stores the VisualDecision in holder.decision
    for the caller to use after the answer stream completes.
    """
    from app.ai_visual.services.decision import assess_visual_need_async

    decision = await assess_visual_need_async(
        message=message,
        scene_key=scene_key,
        rag_sources=rag_sources,
        safety_card=safety_card,
    )

    _log.info("Visual decision: need=%s, mode=%s, conf=%.2f, topic=%s",
              decision.need_visual, decision.decision_mode, decision.confidence, decision.topic)

    if holder is not None:
        holder.decision = decision

    if not decision.need_visual:
        return

    data = {
        "need_visual": True,
        "confidence": decision.confidence,
        "decision_mode": decision.decision_mode,
        "topic": decision.topic,
        "reason": decision.reason,
        "safety_level": decision.safety_level,
        "visual_type": decision.visual_type,
    }
    if decision.score_factors:
        data["score_factors"] = decision.score_factors

    yield AiStreamEvent(event="visual_decision", data=data)

    if decision.decision_mode == "manual_confirm" and decision.confirm_question:
        yield AiStreamEvent(event="visual_confirm_required", data={
            "topic": decision.topic,
            "confidence": decision.confidence,
            "confirm_question": decision.confirm_question,
            "safety_level": decision.safety_level,
        })


async def _maybe_create_visual_job(
    *,
    decision: object,
    session_id: str,
    customer_id: int | None,
    rag_sources: list[dict] | None,
    scene_key: str,
    audit_call_id: str | None = None,
    audit_step_index: int = 2,
) -> AiStreamEvent | None:
    """Create a visual job for auto_async_generate decisions.

    Called after the answer stream completes, so answer_text is available.
    Returns a visual_job event to yield, or None.
    """
    if not decision or getattr(decision, "decision_mode", None) != "auto_async_generate":
        return None

    try:
        from app.database import SessionLocal
        from app.ai_visual.services.job_service import create_job

        db = SessionLocal()
        try:
            job = await create_job(
                session_id=session_id,
                customer_id=customer_id,
                decision=decision,
                rag_sources=rag_sources,
                scene_key=scene_key,
                trigger_mode="auto",
                db=db,
                audit_call_id=audit_call_id,
                audit_step_index=audit_step_index,
            )
            if not job:
                return None
            data = {
                "job_id": job.job_id,
                "status": job.status,
                "topic": job.topic,
            }
            if job.error_code:
                data["error_code"] = job.error_code
            if job.error_message:
                data["error_message"] = job.error_message
            return AiStreamEvent(event="visual_job", data=data)
        finally:
            db.close()
    except Exception as e:
        _log.warning("Visual job creation failed: %s", e, exc_info=True)
        return None
