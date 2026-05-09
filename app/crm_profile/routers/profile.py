"""Customer profile, safety snapshots, AI preload and cache-status endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ...database import get_db
from ...route_helper import UnifiedResponseRoute
from ...security import get_current_user, require_permission
from ..schemas.api import (
    AiPreloadRequest, AiPreloadResponse, AiCacheStatusResponse,
    SafetySnapshotListResponse, SafetySnapshotDetailResponse,
)
from ..services.permission import assert_can_view
from ..services.profile_context_cache import ensure_profile_context, get_profile_cache_status, normalize_window_days
from ..services.modules import safety_profile as safety_profile_module

router = APIRouter(route_class=UnifiedResponseRoute)


@router.get("/{customer_id}/profile")
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
    from ..services.ai_context_preload import preload_ai_context as _preload
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

    from ...clients.crm_db import get_connection, return_connection

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

    from ...clients.crm_db import get_connection, return_connection

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
