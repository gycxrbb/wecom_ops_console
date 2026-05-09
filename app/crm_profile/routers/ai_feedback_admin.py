"""Admin feedback review endpoints for AI coach messages."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ...database import get_db
from ...route_helper import UnifiedResponseRoute
from ...security import get_current_user
from ..schemas.api import (
    AiFeedbackListItem, AiFeedbackListResponse,
    AiFeedbackDetailResponse, AiFeedbackStatusUpdateRequest,
    AiFeedbackStatsResponse,
)

router = APIRouter(route_class=UnifiedResponseRoute)


def _require_admin(request: Request, db: Session):
    user = get_current_user(request, db)
    if user.role != "admin":
        raise HTTPException(403, "仅管理员可访问")
    return user


@router.get("/ai/feedback", tags=["ai-feedback-admin"])
def list_ai_feedback_admin(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    rating: str | None = Query(None),
    reason_category: str | None = Query(None),
    status: str | None = Query(None),
    scene_key: str | None = Query(None),
    coach_user_id: int | None = Query(None),
    date_start: str | None = Query(None),
    date_end: str | None = Query(None),
):
    """Admin: list all AI message feedback with filters."""
    _require_admin(request, db)
    from ..services.feedback import list_feedbacks_admin
    items, total = list_feedbacks_admin(
        db, page=page, page_size=page_size,
        rating=rating, reason_category=reason_category,
        status=status, scene_key=scene_key,
        coach_user_id=coach_user_id,
        date_start=date_start, date_end=date_end,
    )
    return AiFeedbackListResponse(
        items=[
            AiFeedbackListItem(
                feedback_id=fb.feedback_id,
                message_id=fb.message_id,
                crm_customer_id=fb.crm_customer_id,
                coach_user_id=fb.coach_user_id,
                rating=fb.rating,
                reason_category=fb.reason_category,
                scene_key=fb.scene_key,
                status=fb.status,
                user_question_snapshot=(fb.user_question_snapshot or "")[:80],
                created_at=str(fb.created_at) if fb.created_at else None,
            )
            for fb in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/ai/feedback/stats", tags=["ai-feedback-admin"])
def get_ai_feedback_stats(
    request: Request,
    db: Session = Depends(get_db),
    date_start: str | None = Query(None),
    date_end: str | None = Query(None),
):
    """Admin: feedback statistics."""
    _require_admin(request, db)
    from ..services.feedback import get_feedback_stats as _stats
    stats = _stats(db, date_start=date_start, date_end=date_end)
    return AiFeedbackStatsResponse(**stats)


@router.get("/ai/feedback/{feedback_id}", tags=["ai-feedback-admin"])
def get_ai_feedback_detail(
    feedback_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Admin: get feedback detail."""
    _require_admin(request, db)
    from ..services.feedback import get_feedback_detail
    fb = get_feedback_detail(db, feedback_id)
    if not fb:
        raise HTTPException(404, "反馈不存在")
    return AiFeedbackDetailResponse(
        feedback_id=fb.feedback_id,
        message_id=fb.message_id,
        session_id=fb.session_id,
        crm_customer_id=fb.crm_customer_id,
        coach_user_id=fb.coach_user_id,
        rating=fb.rating,
        reason_category=fb.reason_category,
        reason_text=fb.reason_text,
        expected_answer=fb.expected_answer,
        user_question_snapshot=fb.user_question_snapshot,
        ai_answer_snapshot=fb.ai_answer_snapshot,
        customer_reply_snapshot=fb.customer_reply_snapshot,
        scene_key=fb.scene_key,
        output_style=fb.output_style,
        prompt_version=fb.prompt_version,
        prompt_hash=fb.prompt_hash,
        model=fb.model,
        status=fb.status,
        admin_note=fb.admin_note,
        created_at=str(fb.created_at) if fb.created_at else None,
        updated_at=str(fb.updated_at) if fb.updated_at else None,
    )


@router.patch("/ai/feedback/{feedback_id}", tags=["ai-feedback-admin"])
def update_ai_feedback_status(
    feedback_id: str,
    body: AiFeedbackStatusUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Admin: update feedback status and/or admin note."""
    _require_admin(request, db)
    from ..services.feedback import update_feedback_status
    try:
        fb = update_feedback_status(db, feedback_id, status=body.status, admin_note=body.admin_note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "status": fb.status}
