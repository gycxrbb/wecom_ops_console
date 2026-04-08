from __future__ import annotations

import mimetypes
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .base import StorageProvider, StorageResult, UploadPayload
from ...config import UPLOAD_DIR


class LocalStorageProvider(StorageProvider):
    provider_name = 'local'

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or UPLOAD_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _build_object_key(self, filename: str) -> tuple[str, str]:
        suffix = Path(filename).suffix.lower()
        stored_name = f"{datetime.now():%Y/%m/%d}/{uuid4().hex}{suffix}"
        return stored_name, f"/uploads/{stored_name.replace('\\', '/')}"

    def upload(self, payload: UploadPayload) -> StorageResult:
        stored_name, public_url = self._build_object_key(payload.filename)
        target_path = self.base_dir / stored_name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(payload.content)
        return StorageResult(
            provider=self.provider_name,
            object_key=stored_name.replace('\\', '/'),
            public_url=public_url,
            original_filename=Path(payload.filename).name,
            stored_filename=target_path.name,
            mime_type=payload.mime_type,
            file_size=len(payload.content),
            local_path=str(target_path),
            bucket='local',
            extra={'storage_mode': 'filesystem'},
        )

    def delete(self, handle: StorageResult) -> None:
        path = Path(handle.local_path) if handle.local_path else self.base_dir / handle.object_key
        if path.exists():
            path.unlink()

    def download_bytes(self, handle: StorageResult) -> bytes:
        path = Path(handle.local_path) if handle.local_path else self.base_dir / handle.object_key
        return path.read_bytes()

    def build_public_url(self, handle: StorageResult) -> str:
        return handle.public_url or f"/uploads/{handle.object_key}"
