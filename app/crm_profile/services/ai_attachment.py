"""Attachment upload service for AI coach — handles file validation, storage, and DB recording."""
from __future__ import annotations

import asyncio
import hashlib
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


def normalize_content_hash(content_hash: str | None) -> str:
    value = (content_hash or "").strip().lower()
    if len(value) != 64:
        return ""
    if any(ch not in "0123456789abcdef" for ch in value):
        return ""
    return value


def find_existing_attachment(customer_id: int, content_hash: str | None) -> CrmAiAttachment | None:
    normalized_hash = normalize_content_hash(content_hash)
    if not normalized_hash:
        return None
    with SessionLocal() as db:
        attachment = (
            db.query(CrmAiAttachment)
            .filter(
                CrmAiAttachment.crm_customer_id == customer_id,
                CrmAiAttachment.content_hash == normalized_hash,
                CrmAiAttachment.storage_key != "",
            )
            .order_by(CrmAiAttachment.id.desc())
            .first()
        )
        if attachment:
            db.expunge(attachment)
        return attachment


async def upload_attachment(
    file: UploadFile,
    customer_id: int,
    user_id: int,
) -> CrmAiAttachment:
    """Server-relay upload: read file, compress, store via storage_facade."""
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

    content_hash = hashlib.sha256(raw).hexdigest()
    existing = find_existing_attachment(customer_id, content_hash)
    if existing:
        _log.info("Attachment upload deduped: id=%s, file=%s", existing.attachment_id, filename)
        return existing

    if content_type.startswith("image/"):
        raw = _maybe_compress_image(raw, content_type)

    payload = UploadPayload(content=raw, filename=filename, mime_type=content_type)
    result = storage_facade.upload(payload)

    attachment = _create_attachment_record(
        customer_id=customer_id,
        user_id=user_id,
        filename=filename,
        mime_type=content_type,
        file_size=len(raw),
        storage_provider=result.provider,
        storage_key=result.object_key,
        storage_public_url=result.public_url,
        storage_local_path=result.local_path,
        content_hash=content_hash,
    )

    _log.info("Attachment uploaded: id=%s, file=%s, size=%d", attachment.attachment_id, filename, len(raw))
    _start_background_analysis(attachment)
    return attachment


def _create_attachment_record(
    *,
    customer_id: int,
    user_id: int,
    filename: str,
    mime_type: str,
    file_size: int,
    storage_provider: str = '',
    storage_key: str = '',
    storage_public_url: str = '',
    storage_local_path: str = '',
    content_hash: str = '',
) -> CrmAiAttachment:
    """Create a CrmAiAttachment DB record."""
    attachment = CrmAiAttachment(
        attachment_id=uuid.uuid4().hex[:32],
        crm_customer_id=customer_id,
        uploaded_by=user_id,
        original_filename=filename,
        mime_type=mime_type,
        file_size=file_size,
        content_hash=normalize_content_hash(content_hash),
        storage_provider=storage_provider,
        storage_key=storage_key,
        storage_public_url=storage_public_url,
        storage_local_path=storage_local_path,
        page_count=1,
        processing_status="pending",
    )
    with SessionLocal() as db:
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
        db.expunge(attachment)
    return attachment


def _start_background_analysis(attachment: CrmAiAttachment) -> None:
    """Trigger Vision analysis in background so it's ready when the user sends a message."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _analyze():
        await asyncio.sleep(1)
        from .vision_analyzer import analyze_attachment
        try:
            desc = await analyze_attachment(attachment)
            _log.info("Background Vision analysis done: id=%s, %d chars", attachment.attachment_id, len(desc))
        except Exception:
            _log.warning("Background Vision analysis failed: id=%s", attachment.attachment_id, exc_info=True)

    loop.create_task(_analyze())


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


def bind_attachments_to_message(db: Session, attachment_ids: list[str],
                                session_id: str, message_id: str) -> int:
    """Back-fill session_id and message_id on attachment records. Returns count updated."""
    if not attachment_ids:
        return 0
    count = (
        db.query(CrmAiAttachment)
        .filter(CrmAiAttachment.attachment_id.in_(attachment_ids))
        .update({CrmAiAttachment.session_id: session_id, CrmAiAttachment.message_id: message_id},
                synchronize_session="fetch")
    )
    db.commit()
    return count
