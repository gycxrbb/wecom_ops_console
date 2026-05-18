"""Diagnostic API endpoints for AI coach health checks."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ...database import get_db
from ...route_helper import UnifiedResponseRoute
from ...security import get_current_user
from ..services.ai_diagnostics import diagnose

router = APIRouter(route_class=UnifiedResponseRoute)


def _require_admin(request: Request, db: Session):
    user = get_current_user(request, db)
    if user.role != "admin":
        raise HTTPException(403, "仅管理员可访问")
    return user


@router.get("/ai/diagnostics")
async def run_diagnostics(
    request: Request,
    db: Session = Depends(get_db),
):
    _require_admin(request, db)
    report = await diagnose()
    return report.to_dict()
