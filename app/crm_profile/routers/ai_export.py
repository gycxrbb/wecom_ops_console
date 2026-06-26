"""AI coach reply export endpoints."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from ...database import get_db
from ...route_helper import UnifiedResponseRoute
from ...security import get_current_user, require_permission
from ..schemas.api import AiExportRequest
from ..services.ai_export import build_ai_reply_export
from ..services.permission import assert_can_view

router = APIRouter(route_class=UnifiedResponseRoute)


@router.post("/{customer_id}/ai/export")
def export_ai_reply(
    customer_id: int,
    body: AiExportRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Export one AI assistant reply as a formatted docx or editable-text pdf."""
    user = get_current_user(request, db)
    require_permission(user, "crm_profile")
    assert_can_view(user, customer_id)
    try:
        exported = build_ai_reply_export(
            content=body.content,
            export_format=body.format,
            title=body.title,
            customer_name=body.customer_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    encoded_name = quote(exported.filename)
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
            "Cache-Control": "no-store",
        },
    )
