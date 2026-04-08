from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from .. import models
from ..security import json_dumps
from .storage import LocalStorageProvider, QiniuStorageProvider, StorageResult, UploadPayload, storage_facade


@dataclass(slots=True)
class MaterialMigrationStats:
    scanned: int = 0
    migrated: int = 0
    skipped: int = 0
    failed: int = 0
    migrated_ids: list[int] = field(default_factory=list)
    skipped_ids: list[int] = field(default_factory=list)
    failed_items: list[dict[str, str]] = field(default_factory=list)


def _build_provider(name: str):
    provider = (name or "local").strip().lower()
    if provider == "qiniu":
        return QiniuStorageProvider()
    return LocalStorageProvider()


def _build_storage_result(material: models.Material) -> StorageResult:
    return StorageResult(
        provider=material.storage_provider or "local",
        object_key=material.storage_key or "",
        public_url=material.public_url or material.url or "",
        original_filename=material.source_filename or material.name,
        stored_filename=Path(material.storage_key or material.storage_path or material.name).name,
        mime_type=material.mime_type or "",
        file_size=material.file_size or 0,
        local_path=material.storage_path or "",
        bucket=material.bucket_name or "local",
        extra={"domain": material.domain or "", "provider_etag": material.provider_etag or ""},
    )


def _record_migration_event(
    db: Session,
    material: models.Material,
    *,
    operation_status: str,
    target_provider: str,
    error_message: str = "",
    extra: dict | None = None,
) -> None:
    record = models.MaterialStorageRecord(
        material_id=material.id,
        provider=target_provider,
        bucket_name=material.bucket_name or "",
        storage_key=material.storage_key or "",
        public_url=material.public_url or material.url or "",
        operation_type="migrate",
        operation_status=operation_status,
        operator_user_id=material.owner_id,
        operator_ip="migration-script",
        provider_etag=material.provider_etag or "",
        file_size=material.file_size or 0,
        mime_type=material.mime_type or "",
        error_message=error_message,
        extra_json=json_dumps(extra or {}),
    )
    db.add(record)


def _should_skip_material(
    material: models.Material,
    *,
    target_provider: str,
    force: bool,
) -> bool:
    if material.enabled != 1:
        return True
    if material.storage_status == "deleted":
        return True
    if not force and (material.storage_provider or "local") == target_provider:
        return True
    return False


def _iter_candidates(
    db: Session,
    *,
    material_ids: Iterable[int] | None,
    limit: int | None,
) -> list[models.Material]:
    query = db.query(models.Material).order_by(models.Material.id.asc())
    if material_ids:
        query = query.filter(models.Material.id.in_(list(material_ids)))
    if limit:
        query = query.limit(limit)
    return query.all()


def migrate_materials_to_provider(
    db: Session,
    *,
    target_provider: str = "qiniu",
    material_ids: Iterable[int] | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    force: bool = False,
    keep_local_copy: bool = True,
) -> MaterialMigrationStats:
    target_provider_name = (target_provider or "qiniu").strip().lower()
    provider = _build_provider(target_provider_name)
    stats = MaterialMigrationStats()

    for material in _iter_candidates(db, material_ids=material_ids, limit=limit):
        stats.scanned += 1
        if _should_skip_material(material, target_provider=target_provider_name, force=force):
            stats.skipped += 1
            stats.skipped_ids.append(material.id)
            continue

        source_handle = _build_storage_result(material)

        try:
            payload = storage_facade.download_bytes(source_handle)
            if dry_run:
                stats.migrated += 1
                stats.migrated_ids.append(material.id)
                _record_migration_event(
                    db,
                    material,
                    operation_status="dry_run",
                    target_provider=target_provider_name,
                    extra={
                        "source_provider": source_handle.provider,
                        "source_local_path": source_handle.local_path,
                        "preserve_local_copy": keep_local_copy,
                        "dry_run": True,
                    },
                )
                continue

            upload_result = provider.upload(
                UploadPayload(
                    filename=material.source_filename or material.name,
                    content=payload,
                    mime_type=material.mime_type or "application/octet-stream",
                )
            )

            material.storage_provider = upload_result.provider
            material.storage_key = upload_result.object_key
            material.bucket_name = upload_result.bucket
            material.public_url = upload_result.public_url
            material.url = upload_result.public_url
            material.domain = urlparse(upload_result.public_url).netloc if upload_result.public_url else ""
            material.storage_status = "ready"
            material.provider_etag = upload_result.extra.get("hash", "")
            material.last_migrated_at = datetime.utcnow()

            _record_migration_event(
                db,
                material,
                operation_status="success",
                target_provider=target_provider_name,
                extra={
                    "source_provider": source_handle.provider,
                    "source_key": source_handle.object_key,
                    "source_local_path": source_handle.local_path,
                    "target_key": upload_result.object_key,
                    "preserve_local_copy": keep_local_copy,
                    "dry_run": False,
                },
            )

            if not keep_local_copy and source_handle.provider == "local":
                try:
                    LocalStorageProvider().delete(source_handle)
                except FileNotFoundError:
                    pass

            stats.migrated += 1
            stats.migrated_ids.append(material.id)
        except Exception as exc:
            stats.failed += 1
            stats.failed_items.append({"material_id": str(material.id), "error": str(exc)})
            _record_migration_event(
                db,
                material,
                operation_status="failed",
                target_provider=target_provider_name,
                error_message=str(exc),
                extra={
                    "source_provider": source_handle.provider,
                    "source_key": source_handle.object_key,
                    "source_local_path": source_handle.local_path,
                    "preserve_local_copy": keep_local_copy,
                    "dry_run": dry_run,
                },
            )

    db.commit()
    return stats
