from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from .. import models
from ..security import json_dumps


@dataclass(slots=True)
class MaterialAuditStats:
    scanned: int = 0
    healthy: int = 0
    missing_source: int = 0
    marked_missing: int = 0
    qiniu_ready: int = 0
    local_ready: int = 0
    missing_items: list[dict[str, str]] = field(default_factory=list)


def _record_audit_event(
    db: Session,
    material: models.Material,
    *,
    operation_status: str,
    error_message: str = "",
    extra: dict | None = None,
) -> None:
    db.add(
        models.MaterialStorageRecord(
            material_id=material.id,
            provider=material.storage_provider or "local",
            bucket_name=material.bucket_name or "",
            storage_key=material.storage_key or "",
            public_url=material.public_url or material.url or "",
            operation_type="audit",
            operation_status=operation_status,
            operator_user_id=material.owner_id,
            operator_ip="audit-script",
            provider_etag=material.provider_etag or "",
            file_size=material.file_size or 0,
            mime_type=material.mime_type or "application/octet-stream",
            error_message=error_message,
            extra_json=json_dumps(extra or {}),
        )
    )


def audit_material_sources(
    db: Session,
    *,
    mark_missing: bool = False,
    material_ids: list[int] | None = None,
) -> MaterialAuditStats:
    stats = MaterialAuditStats()

    query = db.query(models.Material).filter(models.Material.enabled == 1).order_by(models.Material.id.asc())
    if material_ids:
        query = query.filter(models.Material.id.in_(material_ids))

    for material in query.all():
        stats.scanned += 1
        provider = (material.storage_provider or "local").strip().lower()
        if provider == "qiniu":
            stats.qiniu_ready += 1
            stats.healthy += 1
            continue

        stats.local_ready += 1
        source_path = (material.storage_path or "").strip()
        if source_path and Path(source_path).exists():
            stats.healthy += 1
            continue

        stats.missing_source += 1
        stats.missing_items.append(
            {
                "material_id": str(material.id),
                "name": material.name,
                "storage_path": source_path,
            }
        )
        if mark_missing:
            material.storage_status = "source_missing"
            stats.marked_missing += 1
            _record_audit_event(
                db,
                material,
                operation_status="missing_source",
                error_message=f"source file missing: {source_path}",
                extra={"storage_path": source_path},
            )

    if mark_missing:
        db.commit()
    return stats
