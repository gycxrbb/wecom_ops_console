"""Vision analyzer — Stage 1 of the two-stage pipeline.

Sends images to GPT-4o-mini (aihubmix) for visual understanding,
then returns structured text descriptions for DeepSeek consumption.
"""
from __future__ import annotations

import asyncio
import base64
import logging
from io import BytesIO
from pathlib import Path

from ...clients.ai_chat_client import chat_completion
from ...config import settings
from ...database import SessionLocal
from ..models import CrmAiAttachment
from .document_extractor import DOCUMENT_MIME_TYPES as _DOC_MIME_TYPES
from .document_extractor import extract_document_text as _extract_doc_text

_log = logging.getLogger(__name__)

# Vision API works well at lower resolution — 1024px is enough for text/chart extraction
VISION_MAX_DIMENSION = 1024
VISION_JPEG_QUALITY = 70
# PDF pages get higher quality to preserve text clarity (scanned docs)
VISION_PDF_DPI = 150
VISION_PDF_MAX_DIMENSION = 1800
VISION_PDF_JPEG_QUALITY = 85

VISION_PROMPT = """你是一个专业的医学图表分析助手。请仔细观察这张图片，提取以下信息：

1. 图表类型（血糖曲线、体检报告、饮食照片、其他）
2. 关键数据点和数值
3. 如果是曲线图：波动趋势、峰值/谷值时间、异常区间
4. 如果是报告：所有指标及其正常/异常状态
5. 如果是照片：可见的食物/物品及其特征

请用结构化文本输出，确保信息完整准确。不要做医学诊断，只做客观描述。"""

VISION_PROMPT_PDF_PAGE = """这是一份 PDF 文档的其中一页。请识别并提取该页面中的所有文字、表格、图表信息。
保持原始结构和层级，确保数据准确完整。"""


MAX_ANALYSIS_RETRIES = 3


async def analyze_attachment(attachment: CrmAiAttachment) -> str:
    """Analyze an attachment via Vision API. Returns description text.

    Uses cached result if processing_status == 'analyzed'.
    Retries up to MAX_ANALYSIS_RETRIES times before permanently failing.
    """
    if attachment.processing_status == "analyzed" and attachment.vision_description:
        return attachment.vision_description

    try:
        if attachment.mime_type == "application/pdf":
            description = await _analyze_pdf(attachment)
        elif attachment.mime_type in _DOC_MIME_TYPES:
            description = await _analyze_document(attachment)
        else:
            description = await _analyze_image(attachment)

        _update_attachment(attachment, description=description, status="analyzed")
        return description

    except Exception as e:
        retry_count = (attachment.analysis_retry_count or 0) + 1
        if retry_count < MAX_ANALYSIS_RETRIES:
            _log.warning("Vision analysis failed for %s (attempt %d/%d): %s",
                         attachment.attachment_id, retry_count, MAX_ANALYSIS_RETRIES, e)
            _update_attachment(attachment, retry_count=retry_count)
            return f"[附件解析中，请稍后再试（第{retry_count}次失败）]"
        else:
            _log.error("Vision analysis permanently failed for %s after %d attempts: %s",
                       attachment.attachment_id, MAX_ANALYSIS_RETRIES, e, exc_info=True)
            fallback = f"[附件无法识别：{attachment.original_filename}]"
            _update_attachment(attachment, description=fallback, status="failed")
            return fallback


def _downscale_for_vision(raw: bytes, max_dim: int = VISION_MAX_DIMENSION,
                          quality: int = VISION_JPEG_QUALITY) -> bytes:
    """Downscale image and re-encode as JPEG."""
    from PIL import Image

    img = Image.open(BytesIO(raw))
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    if w > max_dim or h > max_dim:
        ratio = min(max_dim / w, max_dim / h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


async def _analyze_document(attachment: CrmAiAttachment) -> str:
    """Extract text from document files (docx, xlsx, txt, md) — no Vision needed."""
    raw = _read_attachment_file(attachment)
    if not raw:
        raise RuntimeError(f"Cannot read document file: {attachment.attachment_id}")
    description = await asyncio.to_thread(
        _extract_doc_text, raw, attachment.mime_type, attachment.original_filename
    )
    _log.info("Document text extracted: %s, %d chars", attachment.attachment_id, len(description))
    return description


async def _analyze_image(attachment: CrmAiAttachment) -> str:
    image_bytes = _read_attachment_file(attachment)
    if not image_bytes:
        raise RuntimeError(f"Cannot read attachment file: {attachment.attachment_id}")

    # Downscale for Vision API — reduces payload ~4x, speeds up upload + model processing
    image_bytes = await asyncio.to_thread(_downscale_for_vision, image_bytes)
    _log.info("Vision image prepared: %s, %dKB → %dKB",
              attachment.attachment_id, attachment.file_size // 1024, len(image_bytes) // 1024)

    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:image/jpeg;base64,{b64}"

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": VISION_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]

    content, usage = await chat_completion(
        messages, temperature=0.3, max_tokens=2048,
        provider="aihubmix", model=settings.vision_model,
    )

    _log.info("Vision analyzed image %s: %d chars, %d tokens",
              attachment.attachment_id, len(content), usage.get("total_tokens", 0))
    _record_usage(attachment, usage)
    return content


async def _analyze_pdf(attachment: CrmAiAttachment) -> str:
    pdf_bytes = _read_attachment_file(attachment)
    if not pdf_bytes:
        raise RuntimeError(f"Cannot read PDF file: {attachment.attachment_id}")

    try:
        import pymupdf
    except ImportError:
        raise RuntimeError("pymupdf not installed — PDF analysis unavailable")

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        total_pages = len(doc)
        max_pages = min(total_pages, settings.vision_max_pdf_pages)
        attachment.page_count = total_pages

        # Path 1: Native text extraction for text-based PDFs (no Vision needed)
        native_text = await asyncio.to_thread(_extract_pdf_text, doc)
        if native_text:
            header = f"PDF文档共{total_pages}页（文本提取模式）"
            if len(native_text) > 12000:
                native_text = native_text[:12000] + "\n...[内容过长已截断]"
            return f"{header}\n\n{native_text}"

        # Path 2: Rasterize scanned pages with higher quality
        async def _analyze_page(page_idx: int) -> tuple[int, str]:
            page = doc[page_idx]
            page_bytes: bytes | None = None
            images = page.get_images(full=True)
            if len(images) == 1:
                try:
                    xref = images[0][0]
                    base_image = doc.extract_image(xref)
                    if base_image and base_image.get("image") and base_image["width"] >= 800:
                        page_bytes = base_image["image"]
                except Exception:
                    pass

            if not page_bytes:
                pix = page.get_pixmap(dpi=VISION_PDF_DPI)
                page_bytes = pix.tobytes("png")

            jpeg_bytes = await asyncio.to_thread(
                _downscale_for_vision, page_bytes, VISION_PDF_MAX_DIMENSION, VISION_PDF_JPEG_QUALITY
            )
            b64 = base64.b64encode(jpeg_bytes).decode()
            data_url = f"data:image/jpeg;base64,{b64}"
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT_PDF_PAGE},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }]
            try:
                content, usage = await chat_completion(
                    messages, temperature=0.3, max_tokens=2048,
                    provider="aihubmix", model=settings.vision_model,
                )
                _record_usage(attachment, usage)
                return page_idx, content
            except Exception as e:
                _log.warning("Vision failed on PDF page %d: %s", page_idx + 1, e)
                return page_idx, f"[第{page_idx + 1}页 — 识别失败]"

        results = await asyncio.gather(*[_analyze_page(i) for i in range(max_pages)])
        results.sort(key=lambda r: r[0])
        page_descriptions = [f"[第{idx + 1}页]\n{text}" for idx, text in results]
        header = f"PDF文档共{total_pages}页（扫描件模式，已分析{max_pages}页）"
        return f"{header}\n\n" + "\n\n".join(page_descriptions)
    finally:
        doc.close()


def _extract_pdf_text(doc) -> str | None:
    """Try native text extraction. Returns text if pages are text-based, None if scanned."""
    text_parts: list[str] = []
    for page in doc:
        text = page.get_text("text").strip()
        text_parts.append(text)
    full_text = "\n\n".join(text_parts).strip()
    if len(full_text) < 100 * len(doc):
        return None
    return full_text


def _read_attachment_file(attachment: CrmAiAttachment) -> bytes | None:
    if attachment.storage_local_path and Path(attachment.storage_local_path).exists():
        return Path(attachment.storage_local_path).read_bytes()

    # Fallback: download from storage provider
    try:
        from ...services.storage import StorageResult, storage_facade as sf
        handle = StorageResult(
            provider=attachment.storage_provider,
            object_key=attachment.storage_key,
            public_url=attachment.storage_public_url or "",
            original_filename=attachment.original_filename,
            stored_filename=attachment.original_filename,
            mime_type=attachment.mime_type,
            file_size=attachment.file_size,
            local_path=attachment.storage_local_path or "",
        )
        return sf.download_bytes(handle)
    except Exception:
        _log.warning("Cannot download attachment %s", attachment.attachment_id, exc_info=True)
        return None


def _record_usage(attachment: CrmAiAttachment, usage: dict) -> None:
    attachment.vision_model = settings.vision_model
    attachment.vision_tokens = (attachment.vision_tokens or 0) + usage.get("total_tokens", 0)


def _update_attachment(attachment: CrmAiAttachment, description: str | None = None,
                      status: str | None = None, retry_count: int | None = None) -> None:
    if retry_count is not None:
        attachment.analysis_retry_count = retry_count
    try:
        with SessionLocal() as db:
            record = db.query(CrmAiAttachment).filter_by(id=attachment.id).first()
            if record:
                if description is not None:
                    record.vision_description = description
                if status is not None:
                    record.processing_status = status
                if retry_count is not None:
                    record.analysis_retry_count = retry_count
                record.vision_model = attachment.vision_model
                record.vision_tokens = attachment.vision_tokens
                db.commit()
    except Exception:
        _log.warning("Failed to update attachment record", exc_info=True)


def build_user_message_with_attachments(
    original_message: str,
    descriptions: list[tuple[str, str]],
) -> str:
    """Build enhanced user message with attachment descriptions prepended."""
    if not descriptions:
        return original_message

    parts = ["【附件分析结果】"]
    for filename, desc in descriptions:
        parts.append(f"[附件: {filename}]")
        parts.append(desc)
        parts.append("")

    parts.append("【用户提问】")
    parts.append(original_message)
    return "\n".join(parts)
