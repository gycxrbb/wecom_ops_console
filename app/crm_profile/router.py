"""CRM Customer 360 Profile HTTP endpoints."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..route_helper import UnifiedResponseRoute
from ..security import get_current_user, require_permission
from ..sse_debug_log import get_sse_logger
from .services.cache import get as cache_get, put as cache_put, FILTER_OPTIONS_TTL
from .services.profile_context_cache import ensure_profile_context, get_profile_cache_status, normalize_window_days
from .schemas.api import (
    CustomerSearchItem, CustomerListItem, CustomerListResponse,
    CustomerListWithFiltersResponse,
    FilterOption, FilterOptionsResponse,
    ProfileResponse,
    SafetySnapshotListResponse, SafetySnapshotDetailResponse,
    AiProfileNoteRequest, AiProfileNoteResponse, AiConfigResponse, SceneOption,
    AiChatRequest, AiChatResponse,
    AiSessionListResponse, AiSessionDetailResponse,
    AiPreloadRequest, AiPreloadResponse, AiCacheStatusResponse,
    AiFeedbackRequest, AiFeedbackResponse,
    AiFeedbackListItem, AiFeedbackListResponse,
    AiFeedbackDetailResponse, AiFeedbackStatusUpdateRequest,
    AiFeedbackStatsResponse,
)
from .models import CustomerAiProfileNote
from .services.permission import assert_can_view, resolve_visible_customers
from .services import audit as audit_service
from .services.modules import safety_profile as safety_profile_module
from .services.context_builder import build_context_text as _build_context_text

_log = logging.getLogger(__name__)
_sse_log = get_sse_logger()

router = APIRouter(
    prefix="/api/v1/crm-customers",
    tags=["crm-customers"],
    route_class=UnifiedResponseRoute,
)


def _load_filter_options(conn) -> dict:
    """Shared helper: load coaches / groups / channels dropdown options."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, COALESCE(real_name, nick_name, username) AS label "
            "FROM admins ORDER BY id"
        )
        coaches = [{"value": r["id"], "label": r["label"] or f"Admin#{r['id']}"} for r in cur.fetchall()]

    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM `groups` ORDER BY id DESC")
        groups = [{"value": r["id"], "label": r["name"] or f"Group#{r['id']}"} for r in cur.fetchall()]

    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM channels WHERE is_del = 0 OR is_del IS NULL ORDER BY id")
        channels = [{"value": r["id"], "label": r["name"] or f"Channel#{r['id']}"} for r in cur.fetchall()]

    return {"coaches": coaches, "groups": groups, "channels": channels}


@router.get("/filters", response_model=FilterOptionsResponse)
def get_filter_options(
    request: Request,
    db: Session = Depends(get_db),
):
    """Return available filter options: coaches, groups, channels."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    from ..clients.crm_db import get_connection, return_connection

    cached = cache_get("filter_options")
    if cached:
        return cached

    conn = get_connection()
    try:
        result = _load_filter_options(conn)
        cache_put("filter_options", result, FILTER_OPTIONS_TTL)
        return result
    finally:
        return_connection(conn)


@router.get("/list", response_model=CustomerListWithFiltersResponse)
def list_customers(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str = Query("", max_length=100),
    coach_id: int | None = Query(None),
    group_id: int | None = Query(None),
    channel_id: int | None = Query(None),
    include_filters: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Paginated customer list with optional filters.

    Pass include_filters=1 on first load to get filter dropdown options
    in the same response, avoiding an extra round trip.
    """
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    from ..clients.crm_db import get_connection, return_connection

    list_cache_key = f"list:{user.id}:{page}:{page_size}:{q}:{coach_id}:{group_id}:{channel_id}:{include_filters}"
    cached = cache_get(list_cache_key)
    if cached:
        return cached

    conn = get_connection()
    try:
        visible = resolve_visible_customers(user)

        wheres: list[str] = []
        where_params: list = []
        joins: list[str] = []
        join_params: list = []

        if coach_id is not None:
            joins.append(
                "JOIN customer_staff cs_f ON cs_f.customer_id = c.id "
                "AND cs_f.admin_id = %s AND (cs_f.end_at IS NULL OR cs_f.end_at > NOW())"
            )
            join_params.append(coach_id)

        if group_id is not None:
            joins.append(
                "JOIN customer_groups cg_f ON cg_f.customer_id = c.id AND cg_f.group_id = %s"
            )
            join_params.append(group_id)

        if q.strip():
            wheres.append("c.name LIKE %s")
            where_params.append(f"%{q.strip()}%")

        if visible:
            placeholders = ",".join(["%s"] * len(visible))
            wheres.append(f"c.id IN ({placeholders})")
            where_params.extend(visible)

        if channel_id is not None:
            wheres.append("c.channel_id = %s")
            where_params.append(channel_id)

        join_clause = " ".join(joins)
        where_clause = (" WHERE " + " AND ".join(wheres)) if wheres else ""
        params = join_params + where_params

        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(DISTINCT c.id) AS cnt FROM customers c {join_clause}{where_clause}",
                params,
            )
            total = cur.fetchone()["cnt"]

        offset = (page - 1) * page_size
        data_params = list(params)
        data_sql = f"""
            SELECT c.id, c.name, c.gender, c.birthday, c.points, c.total_points,
                   c.status, c.city, c.created_at, c.channel_id,
                   ch.name AS channel_name,
                   (SELECT GROUP_CONCAT(
                       COALESCE(a.real_name, a.nick_name, a.username) SEPARATOR '、'
                    ) FROM customer_staff cs
                      JOIN admins a ON a.id = cs.admin_id
                     WHERE cs.customer_id = c.id
                       AND (cs.end_at IS NULL OR cs.end_at > NOW())
                   ) AS coach_names,
                   (SELECT GROUP_CONCAT(g.name SEPARATOR '、')
                      FROM customer_groups cg
                      JOIN `groups` g ON g.id = cg.group_id
                     WHERE cg.customer_id = c.id
                   ) AS group_names
            FROM customers c
            LEFT JOIN channels ch ON ch.id = c.channel_id
            {join_clause}
            {where_clause}
            GROUP BY c.id
            ORDER BY (
                (c.gender IS NOT NULL) +
                (c.birthday IS NOT NULL) +
                (c.channel_id IS NOT NULL) +
                (COALESCE(c.points, 0) > 0) +
                (c.city IS NOT NULL AND c.city != '') +
                (EXISTS(SELECT 1 FROM customer_staff cs2
                        WHERE cs2.customer_id = c.id
                          AND (cs2.end_at IS NULL OR cs2.end_at > NOW()))) +
                (EXISTS(SELECT 1 FROM customer_groups cg2
                        WHERE cg2.customer_id = c.id))
            ) DESC, c.id DESC
            LIMIT %s OFFSET %s
        """
        data_params.extend([page_size, offset])

        with conn.cursor() as cur:
            cur.execute(data_sql, data_params)
            rows = cur.fetchall()

        items = []
        for r in rows:
            item = dict(r)
            if item.get("birthday"):
                item["birthday"] = str(item["birthday"])
            if item.get("created_at"):
                item["created_at"] = str(item["created_at"])
            items.append(item)

        result: dict = {"items": items, "total": total, "page": page, "page_size": page_size}

        if include_filters:
            cached_filters = cache_get("filter_options")
            if cached_filters:
                result["filters"] = cached_filters
            else:
                fo = _load_filter_options(conn)
                cache_put("filter_options", fo, FILTER_OPTIONS_TTL)
                result["filters"] = fo

        cache_put(list_cache_key, result, 60)
        return result
    finally:
        return_connection(conn)


@router.get("/search", response_model=list[CustomerSearchItem])
def search_customers(
    request: Request,
    q: str = Query("", max_length=100),
    db: Session = Depends(get_db),
):
    """Fuzzy search customers by name. Admin sees all; coach sees only assigned."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    from ..clients.crm_db import get_connection, return_connection

    conn = get_connection()
    try:
        like = f"%{q}%"
        visible = resolve_visible_customers(user)

        with conn.cursor() as cur:
            if visible:
                placeholders = ",".join(["%s"] * len(visible))
                cur.execute(
                    f"""
                    SELECT id, name, gender, birthday, points, total_points, status
                    FROM customers
                    WHERE name LIKE %s
                      AND id IN ({placeholders})
                    ORDER BY id DESC
                    LIMIT 50
                    """,
                    (like, *visible),
                )
            else:
                cur.execute(
                    """
                    SELECT id, name, gender, birthday, points, total_points, status
                    FROM customers
                    WHERE name LIKE %s
                    ORDER BY id DESC
                    LIMIT 50
                    """,
                    (like,),
                )
            rows = cur.fetchall()

        results = []
        for r in rows:
            item = dict(r)
            if item.get("birthday"):
                item["birthday"] = str(item["birthday"])
            results.append(item)
        return results
    finally:
        return_connection(conn)


@router.get("/{customer_id}/profile", response_model=ProfileResponse)
def get_customer_profile(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    window: int = Query(7, ge=7, le=30),
    refresh: bool = Query(False),
):
    """Load full profile for a customer. Pass refresh=true to force cache rebuild."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)

    w = normalize_window_days(window)
    result = ensure_profile_context(customer_id, window_days=w, allow_stale=not refresh, force_refresh=refresh)
    return result.ctx


@router.post("/{customer_id}/ai/preload", response_model=AiPreloadResponse)
def preload_ai_context(
    customer_id: int,
    request: Request,
    body: AiPreloadRequest = Body(default=AiPreloadRequest()),
    db: Session = Depends(get_db),
):
    """Background-warm AI profile cache. Fire-and-forget from frontend."""
    from .services.ai_context_preload import preload_ai_context as _preload
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)
    result = _preload(customer_id, window_days=body.health_window_days, wait_ms=body.wait_ms)
    return AiPreloadResponse(customer_id=customer_id, **result)


@router.get("/{customer_id}/ai/cache-status", response_model=AiCacheStatusResponse)
def get_ai_cache_status(
    customer_id: int,
    request: Request,
    health_window_days: int = Query(7, ge=7, le=30),
    db: Session = Depends(get_db),
):
    """Return AI profile cache readiness without building CRM profile."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)
    result = get_profile_cache_status(
        customer_id,
        window_days=normalize_window_days(health_window_days),
    )
    return AiCacheStatusResponse(customer_id=customer_id, **result.__dict__)


@router.get("/{customer_id}/safety-snapshots", response_model=SafetySnapshotListResponse)
def get_safety_snapshots(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Return available safety-profile snapshots from customer_info history."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)

    from ..clients.crm_db import get_connection, return_connection

    conn = get_connection()
    try:
        items = safety_profile_module.list_snapshots(conn, customer_id)
        return {"customer_id": customer_id, "items": items}
    finally:
        return_connection(conn)


@router.get("/{customer_id}/safety-snapshots/{snapshot_id}", response_model=SafetySnapshotDetailResponse)
def get_safety_snapshot_detail(
    customer_id: int,
    snapshot_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Return one safety-profile snapshot for the selected archive date."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)

    from fastapi import HTTPException
    from ..clients.crm_db import get_connection, return_connection

    conn = get_connection()
    try:
        snapshots = safety_profile_module.list_snapshots(conn, customer_id)
        snapshot = next((item for item in snapshots if item["snapshot_id"] == snapshot_id), None)
        if not snapshot:
            raise HTTPException(404, "未找到对应的安全档案历史记录")

        card = safety_profile_module.load(conn, customer_id, snapshot_id=snapshot_id)
        return {"customer_id": customer_id, "snapshot": snapshot, "card": card}
    finally:
        return_connection(conn)


# --- AI Profile Note & Config ---

def _note_to_response(note: CustomerAiProfileNote) -> dict:
    return {
        "crm_customer_id": note.crm_customer_id,
        "status": note.status,
        "communication_style_note": note.communication_style_note,
        "current_focus_note": note.current_focus_note,
        "execution_barrier_note": note.execution_barrier_note,
        "lifestyle_background_note": note.lifestyle_background_note,
        "coach_strategy_note": note.coach_strategy_note,
        "preferred_scene_hint": note.preferred_scene_hint,
        "updated_at": str(note.updated_at) if note.updated_at else None,
    }


@router.get("/{customer_id}/ai/config", response_model=AiConfigResponse)
def get_ai_config(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Return AI config: available scenes, profile note, prompt version."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)

    from .prompts.registry import list_scenes, list_styles, get_version
    from .schemas.context import EXPANSION_MODULE_OPTIONS

    scenes = [SceneOption(key=k, label=l) for k, l in list_scenes()]
    styles = [SceneOption(key=k, label=l) for k, l in list_styles()]
    note = db.query(CustomerAiProfileNote).filter_by(crm_customer_id=customer_id).first()

    return {
        "scenes": scenes,
        "styles": styles,
        "profile_note": _note_to_response(note) if note else None,
        "prompt_version": get_version(),
        "expansion_options": EXPANSION_MODULE_OPTIONS,
        "available_models": [m.strip() for m in settings.ai_available_models.split(",") if m.strip()],
    }


@router.get("/{customer_id}/ai/profile-note", response_model=AiProfileNoteResponse)
def get_profile_note(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Get customer AI profile note."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)
    note = db.query(CustomerAiProfileNote).filter_by(crm_customer_id=customer_id).first()
    if not note:
        return {"crm_customer_id": customer_id}
    return _note_to_response(note)


@router.put("/{customer_id}/ai/profile-note", response_model=AiProfileNoteResponse)
def save_profile_note(
    customer_id: int,
    body: AiProfileNoteRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create or update customer AI profile note."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)

    _MAX_NOTE_LEN = 1500
    for field_name in ("communication_style_note", "current_focus_note",
                       "execution_barrier_note", "lifestyle_background_note",
                       "coach_strategy_note"):
        val = getattr(body, field_name, None)
        if val and len(val) > _MAX_NOTE_LEN:
            from fastapi import HTTPException
            raise HTTPException(400, f"{field_name} 超过 {_MAX_NOTE_LEN} 字上限")

    note = db.query(CustomerAiProfileNote).filter_by(crm_customer_id=customer_id).first()
    if not note:
        note = CustomerAiProfileNote(crm_customer_id=customer_id, updated_by=user.id)
        db.add(note)

    note.communication_style_note = body.communication_style_note
    note.current_focus_note = body.current_focus_note
    note.execution_barrier_note = body.execution_barrier_note
    note.lifestyle_background_note = body.lifestyle_background_note
    note.coach_strategy_note = body.coach_strategy_note
    note.preferred_scene_hint = body.preferred_scene_hint
    note.updated_by = user.id
    db.commit()
    db.refresh(note)
    from .services.cache import invalidate_prefix as cache_invalidate_prefix
    cache_invalidate_prefix(f"profile:{customer_id}")
    return _note_to_response(note)


@router.get("/{customer_id}/ai/context-preview")
def get_ai_context_preview(
    customer_id: int,
    request: Request,
    scene_key: str = Query("qa_support"),
    selected_expansions: str = Query(""),
    health_window_days: int = Query(7, ge=7, le=30),
    db: Session = Depends(get_db),
):
    """Return the assembled context text that AI would see for this customer."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)

    ctx = ensure_profile_context(
        customer_id,
        window_days=normalize_window_days(health_window_days),
        allow_stale=True,
    ).ctx
    expansions = [e.strip() for e in selected_expansions.split(",") if e.strip()] if selected_expansions else None
    context_text = _build_context_text(ctx.cards, selected_expansions=expansions)
    used_modules = [c.key for c in ctx.cards if c.status in ("ok", "partial")]
    return {
        "context_text": context_text,
        "used_modules": used_modules,
        "selected_expansions": expansions or [],
        "estimated_chars": len(context_text),
        "estimated_tokens": len(context_text) // 4,
    }


@router.get("/{customer_id}/ai/sessions", response_model=AiSessionListResponse)
def list_ai_sessions(
    customer_id: int,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return recent AI conversation sessions for the customer."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)
    return {
        "customer_id": customer_id,
        "items": audit_service.load_customer_sessions(customer_id, limit=limit),
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
        from fastapi import HTTPException
        raise HTTPException(404, "未找到对应的历史对话")

    # Attach feedback for assistant messages
    from .services.feedback import load_feedbacks_for_messages
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


# --- AI Coach (only when ai_coach_enabled) ---

_ai_coach_enabled = settings.ai_coach_enabled or (bool(settings.ai_api_key) and settings.crm_profile_enabled)

if _ai_coach_enabled:
    from .services.ai_coach import ask_ai_coach, stream_ai_coach_answer, stream_ai_coach_thinking, regenerate_ai_coach_answer
    from .services.ai_attachment import upload_attachment as _upload_attachment
    from .services.audit import mark_medical_review as _mark_medical_review

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
        import time as _time
        _t = _time.time()
        _sse_log.info("[SSE-ROUTE] chat-stream endpoint entered for customer %s", customer_id)
        user = get_current_user(request, db)
        require_permission(user, 'crm_profile')
        assert_can_view(user, customer_id)

        async def event_stream():
            _sse_log.info("[SSE-ROUTE] chat-stream yield ':connected' at %.3fs", _time.time() - _t)
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
                _sse_log.info("[SSE-ROUTE] chat-stream writing SSE event=%s at %.3fs", event.event, _time.time() - _t)
                yield _sse(event.event, event.data)
            _sse_log.info("[SSE-ROUTE] chat-stream generator finished at %.3fs", _time.time() - _t)

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
        import time as _time
        _t = _time.time()
        _sse_log.info("[SSE-ROUTE] thinking-stream endpoint entered for customer %s", customer_id)
        user = get_current_user(request, db)
        require_permission(user, 'crm_profile')
        assert_can_view(user, customer_id)

        async def event_stream():
            _sse_log.info("[SSE-ROUTE] thinking-stream yield ':connected' at %.3fs", _time.time() - _t)
            yield ": connected\n\n"
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
                _sse_log.info("[SSE-ROUTE] thinking-stream writing SSE event=%s at %.3fs", event.event, _time.time() - _t)
                yield _sse(event.event, event.data)
            _sse_log.info("[SSE-ROUTE] thinking-stream generator finished at %.3fs", _time.time() - _t)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers=_STREAM_HEADERS,
        )

    @router.post("/{customer_id}/ai/upload-attachment")
    async def ai_upload_attachment(
        customer_id: int,
        file: UploadFile = File(...),
        request: Request = None,
        db: Session = Depends(get_db),
    ):
        user = get_current_user(request, db)
        require_permission(user, 'crm_profile')
        assert_can_view(user, customer_id)
        try:
            att = await _upload_attachment(file, customer_id, user.id)
            return {
                "attachment_id": att.attachment_id,
                "filename": att.original_filename,
                "mime_type": att.mime_type,
                "file_size": att.file_size,
                "url": att.storage_public_url or None,
            }
        except ValueError as e:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=400, content={"detail": str(e)})

    @router.patch("/{customer_id}/ai/messages/{message_id}/review")
    def patch_medical_review(
        customer_id: int,
        message_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        """Mark an AI message as requiring medical review."""
        user = get_current_user(request, db)
        require_permission(user, 'crm_profile')
        assert_can_view(user, customer_id)
        found = _mark_medical_review(message_id)
        if not found:
            from fastapi import HTTPException
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
        from .services.feedback import submit_feedback
        from fastapi import HTTPException
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
        from .services.feedback import get_message_feedback
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
        user = get_current_user(request, db)
        require_permission(user, 'crm_profile')
        assert_can_view(user, customer_id)

        import time as _time
        _t = _time.time()

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

    # --- Debug: test SSE streaming directly ---
    @router.get("/_debug/sse-test")
    async def debug_sse_test():
        """Minimal SSE endpoint to verify streaming works end-to-end."""
        from .services.ai_coach import _debug_ai_stream_test
        async def gen():
            yield ": connected\n\n"
            async for evt in _debug_ai_stream_test():
                yield _sse(evt.event, evt.data)
        return StreamingResponse(gen(), media_type="text/event-stream", headers=_STREAM_HEADERS)

    # ------------------------------------------------------------------
    # Admin feedback review endpoints
    # ------------------------------------------------------------------

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
        user = get_current_user(request, db)
        if user.role != "admin":
            raise HTTPException(403, "仅管理员可访问")
        from .services.feedback import list_feedbacks_admin
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
        user = get_current_user(request, db)
        if user.role != "admin":
            raise HTTPException(403, "仅管理员可访问")
        from .services.feedback import get_feedback_stats as _stats
        stats = _stats(db, date_start=date_start, date_end=date_end)
        return AiFeedbackStatsResponse(**stats)

    @router.get("/ai/feedback/{feedback_id}", tags=["ai-feedback-admin"])
    def get_ai_feedback_detail(
        feedback_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        """Admin: get feedback detail."""
        user = get_current_user(request, db)
        if user.role != "admin":
            raise HTTPException(403, "仅管理员可访问")
        from .services.feedback import get_feedback_detail
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
        user = get_current_user(request, db)
        if user.role != "admin":
            raise HTTPException(403, "仅管理员可访问")
        from .services.feedback import update_feedback_status
        try:
            fb = update_feedback_status(db, feedback_id, status=body.status, admin_note=body.admin_note)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {"ok": True, "status": fb.status}
