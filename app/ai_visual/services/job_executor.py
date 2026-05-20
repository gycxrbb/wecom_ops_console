"""Background execution for visual jobs."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from ..models import AiVisualAsset, AiVisualJob
from .image_client import ImageGenerationError, generate_image
from .storage_bridge import StorageError, store_visual_asset

_log = logging.getLogger(__name__)


async def execute_job_background(
    job_id: str,
    *,
    audit_call_id: str | None = None,
    audit_step_index: int = 2,
) -> None:
    """Background task: queued -> generating -> ready/failed."""
    started_at = datetime.utcnow()
    _log.info("[Visual] execute_job_background start: job_id=%s", job_id)
    db = SessionLocal()
    try:
        job = _get_job(job_id, db)
        if not job or job.status != "queued":
            _log.warning("[Visual] job %s not found or not queued (status=%s)", job_id, job.status if job else "None")
            return

        job.status = "generating"
        db.commit()
        _log.info("[Visual] job %s: generating image (model=%s, prompt_len=%d)", job_id, job.model, len(job.prompt_text or ""))

        image_bytes, _metadata = await generate_image(prompt=job.prompt_text, model=job.model)
        _log.info("[Visual] job %s: image generated (%d bytes), storing...", job_id, len(image_bytes))

        storage_meta = store_visual_asset(image_bytes=image_bytes, job_id=job.job_id)
        _log.info("[Visual] job %s: stored at %s", job_id, storage_meta.get("public_url") or storage_meta.get("object_key"))

        asset_id = uuid.uuid4().hex[:16]
        asset = AiVisualAsset(
            asset_id=asset_id,
            job_id=job.job_id,
            storage_provider=storage_meta["provider"],
            storage_key=storage_meta.get("object_key"),
            storage_public_url=storage_meta.get("public_url"),
            storage_local_path=storage_meta.get("local_path"),
            mime_type="image/png",
            file_size=storage_meta.get("file_size"),
        )
        db.add(asset)

        job.status = "ready"
        job.generated_at = datetime.utcnow()
        db.commit()

        _log.info("[Visual] job %s COMPLETED: asset_id=%s, url=%s", job_id, asset_id, asset.storage_public_url)
        _update_visual_audit_step(
            call_id=audit_call_id,
            step_index=audit_step_index,
            status="success",
            output={
                "job_id": job.job_id,
                "status": job.status,
                "asset_id": asset_id,
                "preview_url": asset.storage_public_url,
            },
            latency_ms=_elapsed_ms(started_at),
            model=job.model,
        )

    except ImageGenerationError as e:
        _log.warning("[Visual] job %s FAILED (ImageGenerationError): %s — %s", job_id, e.error_code, e)
        _mark_failed(db, job_id, e.error_code, str(e))
        _update_visual_audit_step(
            call_id=audit_call_id,
            step_index=audit_step_index,
            status="failed",
            error_code="visual_generation_failed",
            error_message=f"{e.error_code}: {e}",
            output={"job_id": job_id, "status": "failed", "provider_error_code": e.error_code},
            latency_ms=_elapsed_ms(started_at),
        )
    except StorageError as e:
        _log.warning("[Visual] job %s FAILED (StorageError): %s", job_id, e)
        _mark_failed(db, job_id, "storage_error", str(e))
        _update_visual_audit_step(
            call_id=audit_call_id,
            step_index=audit_step_index,
            status="failed",
            error_code="visual_generation_failed",
            error_message=f"storage_error: {e}",
            output={"job_id": job_id, "status": "failed", "provider_error_code": "storage_error"},
            latency_ms=_elapsed_ms(started_at),
        )
    except Exception as e:
        _log.error("[Visual] job %s FAILED (unexpected): %s", job_id, e, exc_info=True)
        _mark_failed(db, job_id, "internal_error", str(e)[:200])
        _update_visual_audit_step(
            call_id=audit_call_id,
            step_index=audit_step_index,
            status="failed",
            error_code="visual_generation_failed",
            error_message=f"internal_error: {e}",
            output={"job_id": job_id, "status": "failed", "provider_error_code": "internal_error"},
            latency_ms=_elapsed_ms(started_at),
        )
    finally:
        db.close()


def _get_job(job_id: str, db: Session) -> AiVisualJob | None:
    return db.query(AiVisualJob).filter(AiVisualJob.job_id == job_id).first()


def _mark_failed(db: Session, job_id: str, error_code: str, error_message: str) -> None:
    try:
        job = _get_job(job_id, db)
        if job:
            job.status = "failed"
            job.error_code = error_code
            job.error_message = error_message[:512]
            db.commit()
    except Exception:
        _log.error("Failed to mark job %s as failed", job_id, exc_info=True)


def _elapsed_ms(started_at: datetime) -> int:
    return int((datetime.utcnow() - started_at).total_seconds() * 1000)


def _update_visual_audit_step(
    *,
    call_id: str | None,
    step_index: int,
    status: str,
    output: dict,
    latency_ms: int,
    model: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    if not call_id:
        return
    try:
        from app.crm_profile.services.invocation_audit import update_step

        update_step(
            call_id,
            step_index,
            "visual_generation",
            name="auto_image_generate",
            status=status,
            error_code=error_code,
            error_message=error_message,
            output_json=json.dumps(output, ensure_ascii=False),
            latency_ms=latency_ms,
            model=model,
        )
    except Exception:
        _log.exception("Failed to update visual audit step for job %s", output.get("job_id"))
