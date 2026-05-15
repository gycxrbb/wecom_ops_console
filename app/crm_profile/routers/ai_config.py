"""AI config, profile notes, and context preview endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...route_helper import UnifiedResponseRoute
from ...security import get_current_user, require_permission
from ..models import CustomerAiProfileNote
from ..schemas.api import (
    AiProfileNoteRequest, AiProfileNoteResponse, AiConfigResponse, SceneOption,
)
from ..services.permission import assert_can_view
from ..services.profile_context_cache import ensure_profile_context, normalize_window_days
from ..services.context_builder import build_context_text as _build_context_text

router = APIRouter(route_class=UnifiedResponseRoute)


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

    from ..prompts.registry import list_scenes, list_styles, get_version
    from ..schemas.context import EXPANSION_MODULE_OPTIONS

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
    from ..services.cache import invalidate_prefix as cache_invalidate_prefix
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
