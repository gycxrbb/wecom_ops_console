"""Visual job endpoints — create, status, confirm, regenerate, feedback."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from ..schemas.jobs import (
    CreateJobRequest,
    FeedbackRequest,
    JobDetailResponse,
    JobResponse,
    VisualConfirmRequest,
    VisualConfirmResponse,
)
from ..schemas.visual import VisualDecision
from ..services import job_service

router = APIRouter()


def _require_admin(request: Request, db: Session):
    return get_current_user(request, db)


@router.post("/jobs/confirm", response_model=VisualConfirmResponse)
async def confirm_visual(
    body: VisualConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Coach confirms or declines visual generation for a low-confidence topic."""
    _require_admin(request, db)

    if not body.confirmed:
        return VisualConfirmResponse(status="declined", topic=body.topic)

    decision = VisualDecision(
        need_visual=True,
        confidence=body.confidence,
        decision_mode="manual_confirm",
        visual_type=body.visual_type,
        topic=body.topic,
        safety_level=body.safety_level,
    )
    job = await job_service.create_job(
        session_id=body.session_id,
        customer_id=body.customer_id,
        decision=decision,
        trigger_mode="manual_confirm",
        db=db,
    )
    return VisualConfirmResponse(
        status="confirmed",
        topic=body.topic,
        job_id=job.job_id if job else None,
    )


@router.post("/jobs", response_model=JobResponse)
async def create_job(
    body: CreateJobRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create a visual generation job."""
    _require_admin(request, db)

    import json
    decision_data = json.loads(body.decision_data_json) if body.decision_data_json else {}
    decision = VisualDecision(
        need_visual=True,
        confidence=body.confidence,
        decision_mode="auto_async_generate",
        visual_type=body.visual_type,
        topic=body.topic,
        safety_level=body.safety_level,
        **{k: v for k, v in decision_data.items()
           if k in ("reason", "confirm_question", "score_factors", "audience")},
    )

    job = await job_service.create_job(
        session_id=body.session_id,
        customer_id=body.customer_id,
        decision=decision,
        trigger_mode="auto",
        db=db,
    )
    if not job:
        return JobResponse(job_id="", status="rejected", topic=body.topic)
    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        topic=job.topic,
        created_at=job.created_at.isoformat() if job.created_at else None,
    )


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
def get_job_status(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Poll job status."""
    _require_admin(request, db)
    result = job_service.get_job_with_asset(job_id, db)
    if not result:
        return JobDetailResponse(job_id=job_id, status="not_found", topic="")
    return JobDetailResponse(**result)


@router.post("/jobs/{job_id}/regenerate", response_model=JobResponse)
async def regenerate_visual(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Regenerate visual from a previous job."""
    _require_admin(request, db)
    new_job = await job_service.regenerate_job(job_id, db)
    if not new_job:
        return JobResponse(job_id="", status="not_found", topic="")
    return JobResponse(
        job_id=new_job.job_id,
        status=new_job.status,
        topic=new_job.topic,
        created_at=new_job.created_at.isoformat() if new_job.created_at else None,
    )


@router.post("/jobs/{job_id}/feedback")
def record_feedback(
    job_id: str,
    body: FeedbackRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Record like/dislike feedback on a visual asset."""
    _require_admin(request, db)
    ok = job_service.record_feedback(job_id, body.feedback, db)
    return {"status": "ok" if ok else "not_found"}


@router.post("/jobs/{job_id}/hide")
def hide_visual(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Hide a visual asset."""
    _require_admin(request, db)
    ok = job_service.hide_asset(job_id, db)
    return {"status": "ok" if ok else "not_found"}
