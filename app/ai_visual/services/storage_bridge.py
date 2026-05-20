"""Bridge between generated images and the storage facade."""
from __future__ import annotations

import logging

from app.services.storage import storage_facade, UploadPayload

_log = logging.getLogger(__name__)


class StorageError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


def store_visual_asset(
    *,
    image_bytes: bytes,
    job_id: str,
    mime_type: str = "image/png",
) -> dict:
    """Upload image bytes via storage facade.

    Returns dict with: provider, object_key, public_url, local_path, file_size
    Raises StorageError on failure.
    """
    filename = f"visual_{job_id}.png"

    try:
        result = storage_facade.upload(UploadPayload(
            content=image_bytes,
            filename=filename,
            mime_type=mime_type,
            object_key=f"ai_visual/{job_id}.png",
        ))
    except Exception as e:
        _log.error("Storage upload failed for job %s: %s", job_id, e)
        raise StorageError(f"Storage upload failed: {e}") from e

    return {
        "provider": result.provider,
        "object_key": result.object_key,
        "public_url": result.public_url,
        "local_path": result.local_path,
        "file_size": result.file_size,
    }
