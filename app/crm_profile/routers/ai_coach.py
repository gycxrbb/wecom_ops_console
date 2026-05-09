"""AI coach chat, streaming, feedback, and regenerate endpoints."""
from __future__ import annotations

import json
import time

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...route_helper import UnifiedResponseRoute
from ...security import get_current_user, require_permission
from ...sse_debug_log import get_sse_logger
from ..schemas.api import AiChatRequest, AiChatResponse, AiFeedbackRequest, AiFeedbackResponse
from ..services.permission import assert_can_view

router = APIRouter(route_class=UnifiedResponseRoute)

_sse_log = get_sse_logger()


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


_STREAM_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post("/{customer_id}/ai/chat", response_model=AiChatResponse)
async def ai_chat(
    customer_id: int,
    body: AiChatRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Ask AI coach a question about a customer."""
    from ..services.ai import ask_ai_coach

    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)
    result = await ask_ai_coach(
        customer_id,
        body.message,
        session_id=body.session_id,
        local_user_id=user.id,
        crm_admin_id=getattr(user, 'crm_admin_id', None),
        scene_key=body.scene_key,
        entry_scene=body.entry_scene,
        selected_expansions=body.selected_expansions,
        output_style=body.output_style,
        health_window_days=body.health_window_days,
        attachment_ids=body.attachment_ids,
        quoted_message_id=body.quoted_message_id,
        model=body.model,
    )
    return result


@router.post("/{customer_id}/ai/chat-stream")
async def ai_chat_stream(
    customer_id: int,
    body: AiChatRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Stream the final AI answer for a customer conversation."""
    from ..services.ai import stream_ai_coach_answer

    _t = time.time()
    _sse_log.info("[SSE-ROUTE] chat-stream endpoint entered for customer %s", customer_id)
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)

    async def event_stream():
        _sse_log.info("[SSE-ROUTE] chat-stream yield ':connected' at %.3fs", time.time() - _t)
        yield ": connected\n\n"
        async for event in stream_ai_coach_answer(
            customer_id,
            body.message,
            session_id=body.session_id,
            local_user_id=user.id,
            crm_admin_id=getattr(user, 'crm_admin_id', None),
            scene_key=body.scene_key,
            entry_scene=body.entry_scene,
            output_style=body.output_style,
            selected_expansions=body.selected_expansions,
            health_window_days=body.health_window_days,
            attachment_ids=body.attachment_ids,
            quoted_message_id=body.quoted_message_id,
            model=body.model,
        ):
            _sse_log.info("[SSE-ROUTE] chat-stream writing SSE event=%s at %.3fs", event.event, time.time() - _t)
            yield _sse(event.event, event.data)
        _sse_log.info("[SSE-ROUTE] chat-stream generator finished at %.3fs", time.time() - _t)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_STREAM_HEADERS,
    )


@router.post("/{customer_id}/ai/thinking-stream")
async def ai_thinking_stream(
    customer_id: int,
    body: AiChatRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Stream the UI-visible thinking summary for the current turn."""
    from ..services.ai import stream_ai_coach_thinking

    _t = time.time()
    _sse_log.info("[SSE-ROUTE] thinking-stream endpoint entered for customer %s", customer_id)

    async def event_stream():
        _sse_log.info("[SSE-ROUTE] thinking-stream yield ':connected' at %.3fs", time.time() - _t)
        yield ": connected\n\n"
        try:
            user = get_current_user(request, db)
            require_permission(user, 'crm_profile')
            assert_can_view(user, customer_id)
        except Exception as exc:
            _sse_log.info("[SSE-ROUTE] thinking-stream auth failed at %.3fs: %s", time.time() - _t, exc)
            yield _sse("error", {"message": str(exc) or "认证失败", "code": "auth_error"})
            return
        async for event in stream_ai_coach_thinking(
            customer_id,
            body.message,
            session_id=body.session_id,
            scene_key=body.scene_key,
            output_style=body.output_style,
            selected_expansions=body.selected_expansions,
            health_window_days=body.health_window_days,
            attachment_ids=body.attachment_ids,
        ):
            _sse_log.info("[SSE-ROUTE] thinking-stream writing SSE event=%s at %.3fs", event.event, time.time() - _t)
            yield _sse(event.event, event.data)
        _sse_log.info("[SSE-ROUTE] thinking-stream generator finished at %.3fs", time.time() - _t)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_STREAM_HEADERS,
    )


@router.patch("/{customer_id}/ai/messages/{message_id}/review")
def patch_medical_review(
    customer_id: int,
    message_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Mark an AI message as requiring medical review."""
    from ..services.audit import mark_medical_review as _mark_medical_review

    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)
    found = _mark_medical_review(message_id)
    if not found:
        raise HTTPException(404, "消息不存在")
    return {"ok": True}


@router.post("/{customer_id}/ai/messages/{message_id}/feedback")
def submit_ai_feedback(
    customer_id: int,
    message_id: str,
    body: AiFeedbackRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Submit or update feedback (like/dislike) for an AI message."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)
    from ..services.feedback import submit_feedback
    try:
        fb = submit_feedback(
            db,
            customer_id=customer_id,
            message_id=message_id,
            coach_user_id=user.id,
            crm_admin_id=getattr(user, 'crm_admin_id', None),
            rating=body.rating,
            reason_category=body.reason_category,
            reason_text=body.reason_text,
            expected_answer=body.expected_answer,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return AiFeedbackResponse(
        feedback_id=fb.feedback_id,
        message_id=fb.message_id,
        rating=fb.rating,
        status=fb.status,
        created_at=str(fb.created_at) if fb.created_at else "",
    )


@router.get("/{customer_id}/ai/messages/{message_id}/feedback")
def get_ai_feedback(
    customer_id: int,
    message_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Get current user's feedback for an AI message."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)
    from ..services.feedback import get_message_feedback
    fb = get_message_feedback(db, message_id, user.id)
    if not fb:
        return {"feedback": None}
    return {
        "feedback": {
            "rating": fb.rating,
            "feedback_id": fb.feedback_id,
        }
    }


@router.post("/{customer_id}/ai/messages/{message_id}/regenerate")
async def regenerate_ai_message(
    customer_id: int,
    message_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Regenerate an AI answer for the same question, keeping the old answer."""
    from ..services.ai import regenerate_ai_coach_answer

    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)

    async def event_stream():
        yield ": connected\n\n"
        async for event in regenerate_ai_coach_answer(
            customer_id,
            message_id,
            local_user_id=user.id,
            crm_admin_id=getattr(user, 'crm_admin_id', None),
        ):
            yield _sse(event.event, event.data)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_STREAM_HEADERS,
    )


@router.get("/_debug/sse-test")
async def debug_sse_test():
    """Minimal SSE endpoint to verify streaming works end-to-end."""
    from ..services.ai import _debug_ai_stream_test

    async def gen():
        yield ": connected\n\n"
        async for evt in _debug_ai_stream_test():
            yield _sse(evt.event, evt.data)
    return StreamingResponse(gen(), media_type="text/event-stream", headers=_STREAM_HEADERS)
