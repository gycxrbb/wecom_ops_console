"""AI session management endpoints — list, detail, rename, pin, delete, auto-title."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ...database import get_db
from ...route_helper import UnifiedResponseRoute
from ...security import get_current_user, require_permission
from ..schemas.api import (
    AiAutoTitleResponse,
    AiSessionDeleteResponse,
    AiSessionDetailResponse,
    AiSessionListResponse,
    AiSessionUpdateRequest,
    AiSessionUpdateResponse,
)
from ..services import audit as audit_service
from ..services.permission import assert_can_view

router = APIRouter(route_class=UnifiedResponseRoute)


@router.get("/{customer_id}/ai/sessions", response_model=AiSessionListResponse)
def list_ai_sessions(
    customer_id: int,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, max_length=60),
    db: Session = Depends(get_db),
):
    """Return recent AI conversation sessions for the customer."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)
    return {
        "customer_id": customer_id,
        "items": audit_service.load_customer_sessions(customer_id, limit=limit, keyword=keyword),
    }


@router.get("/{customer_id}/ai/sessions/{session_id}", response_model=AiSessionDetailResponse)
def get_ai_session_detail(
    customer_id: int,
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Return one stored AI conversation with chronological messages."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)
    detail = audit_service.load_session_detail(customer_id, session_id)
    if not detail:
        raise HTTPException(404, "未找到对应的历史对话")

    from ..services.feedback import load_feedbacks_for_messages
    assistant_ids = [m["message_id"] for m in detail["messages"] if m["role"] == "assistant"]
    feedbacks = load_feedbacks_for_messages(db, assistant_ids, user.id)
    for m in detail["messages"]:
        if m["role"] == "assistant":
            fb = feedbacks.get(m["message_id"])
            m["feedback"] = {"rating": fb.rating, "feedback_id": fb.feedback_id} if fb else None
        else:
            m["feedback"] = None

    return {
        "customer_id": customer_id,
        "session": detail["session"],
        "messages": detail["messages"],
        "scene_key": detail["session"].get("scene_key"),
        "output_style": detail["session"].get("output_style"),
        "prompt_version": detail["session"].get("prompt_version"),
    }


@router.patch("/{customer_id}/ai/sessions/{session_id}", response_model=AiSessionUpdateResponse)
def update_ai_session(
    customer_id: int,
    session_id: str,
    body: AiSessionUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Rename or pin/unpin a session."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)

    from ..services.ai._session_admin import rename_session, toggle_pin
    from ..models import CrmAiSession

    session = db.query(CrmAiSession).filter(
        CrmAiSession.session_id == session_id,
        CrmAiSession.crm_customer_id == customer_id,
        CrmAiSession.is_deleted == False,  # noqa: E712
    ).first()
    if not session:
        raise HTTPException(404, "未找到对应的历史对话")
    if session.local_user_id != user.id and user.role != 'admin':
        raise HTTPException(403, "只能管理自己的对话")

    if body.title is not None:
        rename_session(session_id, body.title)
    if body.is_pinned is not None:
        toggle_pin(session_id, body.is_pinned)

    db.refresh(session)
    display = session.title or session.auto_title or ""
    return {
        "session_id": session_id,
        "title": session.title,
        "auto_title": session.auto_title,
        "is_pinned": bool(session.is_pinned),
        "display_title": display,
    }


@router.delete("/{customer_id}/ai/sessions/{session_id}", response_model=AiSessionDeleteResponse)
def delete_ai_session(
    customer_id: int,
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Soft-delete a session."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)

    from ..services.ai._session_admin import soft_delete_session
    from ..models import CrmAiSession

    session = db.query(CrmAiSession).filter(
        CrmAiSession.session_id == session_id,
        CrmAiSession.crm_customer_id == customer_id,
        CrmAiSession.is_deleted == False,  # noqa: E712
    ).first()
    if not session:
        raise HTTPException(404, "未找到对应的历史对话")
    if session.local_user_id != user.id and user.role != 'admin':
        raise HTTPException(403, "只能删除自己的对话")

    soft_delete_session(session_id)
    return {"session_id": session_id, "deleted": True}


@router.post("/{customer_id}/ai/sessions/{session_id}/auto-title", response_model=AiAutoTitleResponse)
def trigger_auto_title(
    customer_id: int,
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Force regenerate AI auto-title for a session."""
    import asyncio
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)

    from ..models import CrmAiSession
    from ..services.ai._auto_title import generate_auto_title

    session = db.query(CrmAiSession).filter(
        CrmAiSession.session_id == session_id,
        CrmAiSession.crm_customer_id == customer_id,
    ).first()
    if not session:
        raise HTTPException(404, "未找到对应的历史对话")

    # Clear existing auto_title to force regeneration
    session.auto_title = None
    db.commit()

    title = asyncio.get_event_loop().run_until_complete(generate_auto_title(session_id))
    return {"session_id": session_id, "auto_title": title}
