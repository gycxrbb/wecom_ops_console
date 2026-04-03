from __future__ import annotations

import json

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


SCHEDULE_COLUMN_SPECS = {
    "title": "VARCHAR(128)",
    "group_ids_json": "TEXT",
    "content": "TEXT",
    "approval_required": "INTEGER DEFAULT 0",
    "approved_at": "DATETIME",
    "approved_by_id": "INTEGER",
    "status": "VARCHAR(32) DEFAULT 'draft'",
    "skip_dates_json": "TEXT",
    "last_error": "TEXT",
    "last_sent_at": "DATETIME",
}


def _compute_schedule_status(row: dict) -> str:
    schedule_type = row.get("schedule_type") or "once"
    enabled = bool(row.get("enabled"))
    require_approval = bool(row.get("require_approval"))
    approval_status = row.get("approval_status") or "not_required"

    if schedule_type == "none":
        return "draft"
    if not enabled:
        return "draft"
    if require_approval:
        if approval_status == "approved":
            return "approved"
        if approval_status == "rejected":
            return "rejected"
        return "pending_approval"
    return "scheduled"


def ensure_schedule_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if "schedules" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("schedules")}
    missing_columns = [name for name in SCHEDULE_COLUMN_SPECS if name not in existing_columns]

    with engine.begin() as conn:
        for column_name in missing_columns:
            conn.execute(text(f"ALTER TABLE schedules ADD COLUMN {column_name} {SCHEDULE_COLUMN_SPECS[column_name]}"))

        rows = conn.execute(
            text(
                """
                SELECT
                    id,
                    name,
                    group_id,
                    content_snapshot,
                    skip_dates,
                    require_approval,
                    approval_status,
                    enabled,
                    schedule_type,
                    title,
                    group_ids_json,
                    content,
                    approval_required,
                    status,
                    skip_dates_json
                FROM schedules
                """
            )
        ).mappings()

        for row in rows:
            group_ids = [row["group_id"]] if row["group_id"] is not None else []
            conn.execute(
                text(
                    """
                    UPDATE schedules
                    SET title = :title,
                        group_ids_json = :group_ids_json,
                        content = :content,
                        approval_required = :approval_required,
                        status = :status,
                        skip_dates_json = :skip_dates_json
                    WHERE id = :id
                    """
                ),
                {
                    "id": row["id"],
                    "title": row["title"] or row["name"],
                    "group_ids_json": row["group_ids_json"] or json.dumps(group_ids, ensure_ascii=False),
                    "content": row["content"] or row["content_snapshot"],
                    "approval_required": row["approval_required"] if row["approval_required"] is not None else row["require_approval"],
                    "status": row["status"] or _compute_schedule_status(dict(row)),
                    "skip_dates_json": row["skip_dates_json"] or row["skip_dates"] or "[]",
                },
            )


def ensure_asset_folders_schema(engine: Engine) -> None:
    inspector = inspect(engine)

    # Add folder_id column to materials if missing
    if "materials" in inspector.get_table_names():
        existing_columns = {column["name"] for column in inspector.get_columns("materials")}
        if "folder_id" not in existing_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE materials ADD COLUMN folder_id INTEGER NULL"))
