from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from .. import models
from ..security import json_dumps
from .storage import StorageResult, UploadPayload, storage_facade


def resolve_material_storage_path(*, local_path: str = '', object_key: str = '', public_url: str = '') -> str:
    normalized_local_path = (local_path or '').strip()
    if normalized_local_path:
        return normalized_local_path
    normalized_object_key = (object_key or '').strip()
    if normalized_object_key:
        return normalized_object_key
    return (public_url or '').strip()


def resolve_material_local_fallback_path(material: models.Material) -> str:
    if (material.storage_provider or 'local').strip().lower() != 'local':
        return ''
    return (material.storage_path or '').strip()


def build_storage_result_from_material(material: models.Material) -> StorageResult:
    return StorageResult(
        provider=material.storage_provider or 'local',
        object_key=material.storage_key or '',
        public_url=material.public_url or material.url or '',
        original_filename=material.source_filename or material.name,
        stored_filename=Path(material.storage_key or material.storage_path or material.name).name,
        mime_type=material.mime_type or 'application/octet-stream',
        file_size=material.file_size or 0,
        bucket=material.bucket_name or '',
        local_path=resolve_material_local_fallback_path(material),
        extra={'etag': material.provider_etag or ''},
    )


def log_material_storage_event(
    db: Session,
    material: models.Material,
    *,
    operation_type: str,
    operation_status: str,
    user_id: int | None,
    operator_ip: str = '',
    error_message: str = '',
    extra: dict | None = None,
) -> models.MaterialStorageRecord:
    record = models.MaterialStorageRecord(
        material_id=material.id,
        provider=material.storage_provider or 'local',
        bucket_name=material.bucket_name or '',
        storage_key=material.storage_key or '',
        public_url=material.public_url or material.url or '',
        operation_type=operation_type,
        operation_status=operation_status,
        operator_user_id=user_id,
        operator_ip=operator_ip,
        provider_etag=material.provider_etag or '',
        file_size=material.file_size or 0,
        mime_type=material.mime_type or 'application/octet-stream',
        error_message=error_message,
        extra_json=json_dumps(extra or {}),
    )
    db.add(record)
    return record


def migrate_material_to_provider(
    db: Session,
    material: models.Material,
    *,
    target_provider: str,
    user_id: int | None = None,
    operator_ip: str = '',
    keep_local_copy: bool = True,
) -> bool:
    target_provider = (target_provider or '').strip().lower()
    if not target_provider:
        raise ValueError('target_provider is required')

    current_handle = build_storage_result_from_material(material)
    previous_provider = material.storage_provider or 'local'
    previous_public_url = material.public_url or material.url or ''
    previous_storage_key = material.storage_key or ''
    previous_storage_path = material.storage_path or ''

    if previous_provider == target_provider and previous_storage_key and previous_public_url:
        return False

    try:
        payload = UploadPayload(
            content=storage_facade.download_bytes(current_handle),
            filename=material.source_filename or material.name,
            mime_type=material.mime_type or 'application/octet-stream',
        )
        storage_result = storage_facade.upload_with_provider(target_provider, payload)
    except Exception as exc:
        log_material_storage_event(
            db,
            material,
            operation_type='migrate',
            operation_status='failed',
            user_id=user_id,
            operator_ip=operator_ip,
            error_message=str(exc),
            extra={'target_provider': target_provider},
        )
        raise

    material.storage_provider = storage_result.provider
    material.storage_key = storage_result.object_key
    material.bucket_name = storage_result.bucket
    material.public_url = storage_result.public_url
    material.url = storage_result.public_url
    material.domain = urlparse(storage_result.public_url).netloc if storage_result.public_url else ''
    material.storage_status = 'ready'
    material.provider_etag = storage_result.extra.get('hash', '') or storage_result.extra.get('etag', '')
    material.last_migrated_at = datetime.utcnow()
    if storage_result.local_path:
        material.storage_path = storage_result.local_path
    elif keep_local_copy and previous_storage_path:
        material.storage_path = previous_storage_path

    log_material_storage_event(
        db,
        material,
        operation_type='migrate',
        operation_status='success',
        user_id=user_id,
        operator_ip=operator_ip,
        extra={
            'target_provider': target_provider,
            'previous_provider': previous_provider,
            'previous_public_url': previous_public_url,
            'previous_storage_key': previous_storage_key,
            'kept_local_copy': bool(keep_local_copy and previous_storage_path),
        },
    )
    return True
