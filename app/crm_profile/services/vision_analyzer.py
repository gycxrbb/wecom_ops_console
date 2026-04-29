"""Vision analyzer — Stage 1 of the two-stage pipeline.

Sends images to GPT-4o-mini (aihubmix) for visual understanding,
then returns structured text descriptions for DeepSeek consumption.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path

from ...clients.ai_chat_client import chat_completion
from ...config import settings
from ...database import SessionLocal
from ..models import CrmAiAttachment

_log = logging.getLogger(__name__)

VISION_PROMPT = """你是一个专业的医学图表分析助手。请仔细观察这张图片，提取以下信息：

1. 图表类型（血糖曲线、体检报告、饮食照片、其他）
2. 关键数据点和数值
3. 如果是曲线图：波动趋势、峰值/谷值时间、异常区间
4. 如果是报告：所有指标及其正常/异常状态
5. 如果是照片：可见的食物/物品及其特征

请用结构化文本输出，确保信息完整准确。不要做医学诊断，只做客观描述。"""

VISION_PROMPT_PDF_PAGE = """这是一份 PDF 文档的其中一页。请识别并提取该页面中的所有文字、表格、图表信息。
保持原始结构和层级，确保数据准确完整。"""


async def analyze_attachment(attachment: CrmAiAttachment) -> str:
    """Analyze an attachment via Vision API. Returns description text.

    Uses cached result if processing_status == 'analyzed'.
    Updates DB record with result or failure status.
    """
    if attachment.processing_status == "analyzed" and attachment.vision_description:
        return attachment.vision_description

    try:
        if attachment.mime_type == "application/pdf":
            description = await _analyze_pdf(attachment)
        else:
            description = await _analyze_image(attachment)

        _update_attachment(attachment, description, "analyzed")
        return description

    except Exception as e:
        _log.error("Vision analysis failed for %s: %s", attachment.attachment_id, e, exc_info=True)
        fallback = f"[附件无法识别：{attachment.original_filename}]"
        _update_attachment(attachment, fallback, "failed")
        return fallback


async def _analyze_image(attachment: CrmAiAttachment) -> str:
    image_bytes = _read_attachment_file(attachment)
    if not image_bytes:
        raise RuntimeError(f"Cannot read attachment file: {attachment.attachment_id}")

    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:{attachment.mime_type};base64,{b64}"

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
    max_pages = min(len(doc), settings.vision_max_pdf_pages)
    page_descriptions: list[str] = []

    for page_idx in range(max_pages):
        page = doc[page_idx]
        # Render page to PNG at 150 DPI
        pix = page.get_pixmap(dpi=150)
        png_bytes = pix.tobytes("png")
        b64 = base64.b64encode(png_bytes).decode()
        data_url = f"data:image/png;base64,{b64}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT_PDF_PAGE},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ]

        try:
            content, usage = await chat_completion(
                messages, temperature=0.3, max_tokens=2048,
                provider="aihubmix", model=settings.vision_model,
            )
            page_descriptions.append(f"[第{page_idx + 1}页]\n{content}")
            _record_usage(attachment, usage)
        except Exception as e:
            _log.warning("Vision failed on PDF page %d: %s", page_idx + 1, e)
            page_descriptions.append(f"[第{page_idx + 1}页 — 识别失败]")

    total_pages = len(doc)
    attachment.page_count = total_pages
    doc.close()

    header = f"PDF文档共{total_pages}页，已分析{max_pages}页"
    return f"{header}\n\n" + "\n\n".join(page_descriptions)


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


def _update_attachment(attachment: CrmAiAttachment, description: str, status: str) -> None:
    try:
        with SessionLocal() as db:
            record = db.query(CrmAiAttachment).filter_by(id=attachment.id).first()
            if record:
                record.vision_description = description
                record.vision_model = attachment.vision_model
                record.vision_tokens = attachment.vision_tokens
                record.processing_status = status
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
