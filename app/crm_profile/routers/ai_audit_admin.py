"""Admin invocation audit endpoints for AI coach calls."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ...database import get_db
from ...route_helper import UnifiedResponseRoute
from ...security import get_current_user
from ..schemas.api import (
    InvocationListItem, InvocationListResponse,
    InvocationDetailResponse, InvocationStatsResponse,
)
from ..services.invocation_audit import (
    query_invocations, get_invocation_detail, get_invocation_stats,
    get_invocation_trends, get_invocation_breakdown, find_invocation_by_message_id,
)

router = APIRouter(route_class=UnifiedResponseRoute)


def _require_admin(request: Request, db: Session):
    user = get_current_user(request, db)
    if user.role != "admin":
        raise HTTPException(403, "仅管理员可访问")
    return user


@router.get("/ai/invocations/stats")
def invocation_stats(
    request: Request,
    db: Session = Depends(get_db),
    date_start: str | None = Query(None),
    date_end: str | None = Query(None),
):
    _require_admin(request, db)
    return get_invocation_stats(date_start=date_start, date_end=date_end)


@router.get("/ai/invocations/trends")
def invocation_trends(
    request: Request,
    db: Session = Depends(get_db),
    days: int = Query(14, ge=1, le=90),
    date_start: str | None = Query(None),
    date_end: str | None = Query(None),
):
    _require_admin(request, db)
    return get_invocation_trends(days=days, date_start=date_start, date_end=date_end)


@router.get("/ai/invocations/breakdown")
def invocation_breakdown(
    request: Request,
    db: Session = Depends(get_db),
    dimension: str = Query("model", regex="^(model|error_code|scene|provider)$"),
    date_start: str | None = Query(None),
    date_end: str | None = Query(None),
):
    _require_admin(request, db)
    return get_invocation_breakdown(dimension=dimension, date_start=date_start, date_end=date_end)


@router.get("/ai/invocations")
def list_invocations(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    error_code: str | None = Query(None),
    crm_customer_id: int | None = Query(None),
    local_user_id: int | None = Query(None),
    primary_model: str | None = Query(None),
    scene_key: str | None = Query(None),
    session_id: str | None = Query(None),
    date_start: str | None = Query(None),
    date_end: str | None = Query(None),
):
    _require_admin(request, db)
    items, total = query_invocations(
        page=page, page_size=page_size,
        status=status, error_code=error_code,
        crm_customer_id=crm_customer_id,
        local_user_id=local_user_id,
        primary_model=primary_model,
        scene_key=scene_key,
        session_id=session_id,
        date_start=date_start, date_end=date_end,
    )
    return InvocationListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/ai/invocations/{call_id}")
def invocation_detail(
    call_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_admin(request, db)
    detail = get_invocation_detail(call_id)
    if not detail:
        raise HTTPException(404, "调用记录不存在")
    return detail


@router.get("/ai/invocations/lookup/by-message")
def lookup_by_message(
    request: Request,
    db: Session = Depends(get_db),
    message_id: str = Query(...),
):
    """Find invocation call_id by assistant_message_id."""
    _require_admin(request, db)
    call_id = find_invocation_by_message_id(message_id)
    if not call_id:
        raise HTTPException(404, "未找到关联调用记录")
    return {"call_id": call_id}
