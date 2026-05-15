"""AI attachment upload, prepare-upload, and confirm-upload endpoints."""
from __future__ import annotations

import time

from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...route_helper import UnifiedResponseRoute
from ...security import get_current_user, require_permission
from ...services.storage import storage_facade
from ..schemas.api import AiPrepareUploadRequest, AiConfirmUploadRequest
from ..services.permission import assert_can_view

router = APIRouter(route_class=UnifiedResponseRoute)

# Per-user rate limiter for prepare-upload (max 10 requests per 60s)
_prepare_rate_limit: dict[int, list[float]] = {}


def _attachment_response(att, *, deduped: bool = False) -> dict:
    return {
        "attachment_id": att.attachment_id,
        "filename": att.original_filename,
        "mime_type": att.mime_type,
        "file_size": att.file_size,
        "content_hash": getattr(att, "content_hash", "") or None,
        "url": att.storage_public_url or None,
        "deduped": deduped,
    }


def _check_prepare_rate_limit(user_id: int) -> None:
    now = time.time()
    window = _prepare_rate_limit.setdefault(user_id, [])
    _prepare_rate_limit[user_id] = [t for t in window if now - t < 60]
    window = _prepare_rate_limit[user_id]
    if len(window) >= 10:
        raise HTTPException(status_code=429, detail="上传请求过于频繁，请稍后再试")
    window.append(now)
    # Prune empty entries to prevent unbounded dict growth
    if not window:
        _prepare_rate_limit.pop(user_id, None)


@router.post("/{customer_id}/ai/upload-attachment")
async def ai_upload_attachment(
    customer_id: int,
    file: UploadFile = File(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Server-relay upload (fallback when direct upload is unavailable)."""
    from ..services.ai_attachment import upload_attachment as _upload_attachment

    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)
    try:
        att = await _upload_attachment(file, customer_id, user.id)
        return _attachment_response(att, deduped=False)
    except ValueError as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"detail": str(e)})


@router.post("/{customer_id}/ai/prepare-upload")
async def ai_prepare_upload(
    customer_id: int,
    body: AiPrepareUploadRequest,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Get upload credentials for frontend direct upload to cloud storage."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)

    from ..services.ai_attachment import ALLOWED_MIME_TYPES, find_existing_attachment, _guess_mime_from_filename

    # Validate MIME type (fallback to filename extension if browser sent empty type)
    mime = body.mime_type or _guess_mime_from_filename(body.filename)
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {body.mime_type or body.filename}")
    body.mime_type = mime

    # Validate file size
    max_size = settings.vision_max_pdf_size_mb * 1024 * 1024
    if body.file_size > max_size:
        raise HTTPException(status_code=400, detail=f"文件大小超出限制 ({body.file_size // (1024*1024)}MB)")

    # Per-user rate limit
    _check_prepare_rate_limit(user.id)

    existing = find_existing_attachment(customer_id, body.content_hash)
    if existing:
        return {"mode": "existing", "attachment": _attachment_response(existing, deduped=True)}

    result = storage_facade.prepare_client_upload(body.filename, body.mime_type)
    if result:
        return {"mode": "qiniu", **result}
    return {"mode": "server"}


@router.post("/{customer_id}/ai/confirm-upload")
async def ai_confirm_upload(
    customer_id: int,
    body: AiConfirmUploadRequest,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Confirm a direct upload and create DB record."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    assert_can_view(user, customer_id)

    from ..services.ai_attachment import (
        ALLOWED_MIME_TYPES, find_existing_attachment, normalize_content_hash,
        _create_attachment_record, _start_background_analysis, _guess_mime_from_filename,
    )

    # Validate again on confirm (fallback to filename extension)
    mime = body.mime_type or _guess_mime_from_filename(body.filename)
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="不支持的文件类型")
    body.mime_type = mime
    max_size = settings.vision_max_pdf_size_mb * 1024 * 1024
    if body.file_size > max_size:
        raise HTTPException(status_code=400, detail="文件大小超出限制")

    existing = find_existing_attachment(customer_id, body.content_hash)
    if existing:
        return _attachment_response(existing, deduped=True)

    attachment = _create_attachment_record(
        customer_id=customer_id,
        user_id=user.id,
        filename=body.filename,
        mime_type=body.mime_type,
        file_size=body.file_size,
        storage_provider='qiniu',
        storage_key=body.object_key,
        storage_public_url=body.public_url,
        content_hash=normalize_content_hash(body.content_hash),
    )
    _start_background_analysis(attachment)
    return _attachment_response(attachment, deduped=False)
