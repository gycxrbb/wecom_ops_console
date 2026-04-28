"""Attachment upload service for AI coach — handles file validation, storage, and DB recording."""
from __future__ import annotations

import logging
import uuid
from io import BytesIO

from fastapi import UploadFile
from PIL import Image
from sqlalchemy.orm import Session

from ...config import settings
from ...database import SessionLocal
from ...services.storage import UploadPayload, storage_facade
from ..models import CrmAiAttachment

_log = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp", "application/pdf",
}

MAX_IMAGE_DIMENSION = 2048


def _validate_upload(file: UploadFile) -> None:
    if not file.content_type or file.content_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"不支持的文件类型: {file.content_type}，仅支持 jpg/png/webp/pdf")

    content_type = file.content_type
    filename = file.filename or ""
    if content_type == "application/pdf":
        max_size = settings.vision_max_pdf_size_mb * 1024 * 1024
    else:
        max_size = settings.vision_max_image_size_mb * 1024 * 1024

    # Size check is done after read, but we validate type here


async def upload_attachment(
    file: UploadFile,
    customer_id: int,
    user_id: int,
) -> CrmAiAttachment:
    _validate_upload(file)

    raw = await file.read()
    if not raw:
        raise ValueError("上传文件为空")

    content_type = file.content_type
    filename = file.filename or "unknown"

    if content_type == "application/pdf":
        max_size = settings.vision_max_pdf_size_mb * 1024 * 1024
    else:
        max_size = settings.vision_max_image_size_mb * 1024 * 1024

    if len(raw) > max_size:
        raise ValueError(f"文件大小超出限制 ({len(raw) // (1024*1024)}MB)")

    # Compress large images
    if content_type.startswith("image/"):
        raw = _maybe_compress_image(raw, content_type)

    # Store file
    payload = UploadPayload(content=raw, filename=filename, mime_type=content_type)
    result = storage_facade.upload(payload)

    # Create DB record
    attachment = CrmAiAttachment(
        attachment_id=uuid.uuid4().hex[:32],
        crm_customer_id=customer_id,
        uploaded_by=user_id,
        original_filename=filename,
        mime_type=content_type,
        file_size=len(raw),
        storage_provider=result.provider,
        storage_key=result.object_key,
        storage_local_path=result.local_path,
        page_count=1,
        processing_status="pending",
    )

    with SessionLocal() as db:
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
        # Detach from session
        db.expunge(attachment)

    _log.info("Attachment uploaded: id=%s, file=%s, size=%d", attachment.attachment_id, filename, len(raw))
    return attachment


def _maybe_compress_image(raw: bytes, content_type: str) -> bytes:
    try:
        img = Image.open(BytesIO(raw))
        w, h = img.size
        if w <= MAX_IMAGE_DIMENSION and h <= MAX_IMAGE_DIMENSION:
            return raw

        ratio = min(MAX_IMAGE_DIMENSION / w, MAX_IMAGE_DIMENSION / h)
        new_w, new_h = int(w * ratio), int(h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        fmt = _pillow_format(content_type)
        buf = BytesIO()
        img.save(buf, format=fmt, quality=85)
        _log.info("Image compressed: %dx%d -> %dx%d", w, h, new_w, new_h)
        return buf.getvalue()
    except Exception:
        _log.warning("Image compression failed, using original", exc_info=True)
        return raw


def _pillow_format(content_type: str) -> str:
    return {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}.get(content_type, "PNG")


def load_attachments(db: Session, attachment_ids: list[str], customer_id: int) -> list[CrmAiAttachment]:
    return (
        db.query(CrmAiAttachment)
        .filter(
            CrmAiAttachment.attachment_id.in_(attachment_ids),
            CrmAiAttachment.crm_customer_id == customer_id,
        )
        .all()
    )
