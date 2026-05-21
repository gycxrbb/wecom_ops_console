"""Visual job lifecycle orchestration — create, execute, query, regenerate."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid

from sqlalchemy.orm import Session

from ..models import AiVisualAsset, AiVisualJob
from ..schemas.visual import VisualDecision
from .brief_builder import build_visual_brief
from .job_executor import execute_job_background
from .prompt_builder import build_image_prompt
from app.config import settings

_log = logging.getLogger(__name__)


async def create_job(
    *,
    session_id: str | None,
    customer_id: int | None,
    decision: VisualDecision,
    rag_sources: list[dict] | None = None,
    scene_key: str = "qa_support",
    trigger_mode: str = "auto",
    db: Session,
    audit_call_id: str | None = None,
    audit_step_index: int = 2,
) -> AiVisualJob | None:
    """Create a queued visual job and schedule background execution."""
    # Rate limit: max jobs per session
    if session_id:
        existing = (
            db.query(AiVisualJob)
            .filter(AiVisualJob.session_id == session_id, AiVisualJob.status.in_(["queued", "generating"]))
            .count()
        )
        if existing >= settings.ai_visual_max_jobs_per_session:
            _log.warning("Max visual jobs reached for session %s", session_id)
            return None

    job_id = uuid.uuid4().hex[:16]
    _log.info("[Visual] create_job start: topic=%s, mode=%s, conf=%.2f, trigger=%s",
              decision.topic, decision.decision_mode, decision.confidence, trigger_mode)

    # Build brief
    brief = build_visual_brief(decision=decision, rag_sources=rag_sources, scene_key=scene_key)
    # Embed rag_sources and user question for LLM prompt generation in background task
    brief["_rag_sources"] = rag_sources or []
    brief["_user_question"] = decision.topic  # topic is extracted from user message
    _log.info("[Visual] brief built: title=%s, key_points=%d, style=%s",
              brief.get("title"), len(brief.get("key_points", [])), brief.get("style_hint"))

    # Build prompt — safety check
    prompt = build_image_prompt(brief)
    if prompt is None:
        _log.warning("[Visual] SAFETY BLOCK on prompt for topic: %s", decision.topic)
        job = AiVisualJob(
            job_id=job_id, session_id=session_id, customer_id=customer_id,
            trigger_mode=trigger_mode, status="failed", visual_type=decision.visual_type,
            topic=decision.topic, safety_level=decision.safety_level, confidence=decision.confidence,
            decision_data_json=_serialize_decision(decision),
            brief_json=json.dumps(brief, ensure_ascii=False),
            model=settings.ai_visual_model, provider=settings.ai_visual_provider,
            error_code="safety_block", error_message="生成的 prompt 未通过安全检查",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    job = AiVisualJob(
        job_id=job_id, session_id=session_id, customer_id=customer_id,
        trigger_mode=trigger_mode, status="queued", visual_type=decision.visual_type,
        topic=decision.topic, safety_level=decision.safety_level, confidence=decision.confidence,
        decision_data_json=_serialize_decision(decision),
        brief_json=json.dumps(brief, ensure_ascii=False),
        prompt_text=prompt, model=settings.ai_visual_model, provider=settings.ai_visual_provider,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    _log.info("[Visual] job %s created (status=queued), scheduling background execution", job_id)

    # Fire-and-forget background execution
    asyncio.create_task(execute_job_background(
        job_id,
        audit_call_id=audit_call_id,
        audit_step_index=audit_step_index,
    ))
    return job


def get_job(job_id: str, db: Session) -> AiVisualJob | None:
    return db.query(AiVisualJob).filter(AiVisualJob.job_id == job_id).first()


def get_job_with_asset(job_id: str, db: Session) -> dict | None:
    """Return job + asset info for frontend polling."""
    job = get_job(job_id, db)
    if not job:
        return None
    asset = (
        db.query(AiVisualAsset)
        .filter(AiVisualAsset.job_id == job_id, AiVisualAsset.hidden == False)  # noqa: E712
        .first()
    )
    return _job_to_response(job, asset)


def get_jobs_by_session(session_id: str, db: Session) -> list[AiVisualJob]:
    return (
        db.query(AiVisualJob)
        .filter(AiVisualJob.session_id == session_id)
        .order_by(AiVisualJob.created_at.desc())
        .all()
    )


async def regenerate_job(job_id: str, db: Session) -> AiVisualJob | None:
    """Create a new job from an existing job's decision data."""
    old_job = get_job(job_id, db)
    if not old_job:
        return None

    decision = _deserialize_decision(old_job.decision_data_json)
    if not decision:
        return None

    new_job = await create_job(
        session_id=old_job.session_id,
        customer_id=old_job.customer_id,
        decision=decision,
        scene_key="qa_support",
        trigger_mode="regenerate",
        db=db,
    )
    if new_job:
        old_job.retry_count += 1
        db.commit()
    return new_job


def record_feedback(job_id: str, feedback: str, db: Session) -> bool:
    asset = db.query(AiVisualAsset).filter(AiVisualAsset.job_id == job_id).first()
    if not asset:
        return False
    asset.feedback = feedback
    db.commit()
    return True


def hide_asset(job_id: str, db: Session) -> bool:
    asset = db.query(AiVisualAsset).filter(AiVisualAsset.job_id == job_id).first()
    if not asset:
        return False
    asset.hidden = True
    db.commit()
    return True


# ── Serialization helpers ─────────────────────────────────────────────


def _serialize_decision(d: VisualDecision) -> str:
    return json.dumps({
        "need_visual": d.need_visual, "confidence": d.confidence,
        "decision_mode": d.decision_mode, "visual_type": d.visual_type,
        "topic": d.topic, "audience": d.audience, "reason": d.reason,
        "safety_level": d.safety_level, "confirm_question": d.confirm_question,
        "score_factors": d.score_factors,
    }, ensure_ascii=False)


def _deserialize_decision(raw: str) -> VisualDecision | None:
    try:
        data = json.loads(raw)
        return VisualDecision(**{k: v for k, v in data.items() if k in VisualDecision.__dataclass_fields__})
    except Exception:
        return None


def _job_to_response(job: AiVisualJob, asset: AiVisualAsset | None) -> dict:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "topic": job.topic,
        "confidence": job.confidence,
        "safety_level": job.safety_level,
        "visual_type": job.visual_type,
        "preview_url": asset.storage_public_url if asset else None,
        "asset_id": asset.asset_id if asset else None,
        "sendable": job.status == "ready" and not settings.ai_visual_auto_sendable is False,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "generated_at": job.generated_at.isoformat() if job.generated_at else None,
    }
