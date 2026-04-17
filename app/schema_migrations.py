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

MATERIAL_COLUMN_SPECS = {
    "storage_provider": "VARCHAR(32) DEFAULT 'local'",
    "storage_key": "VARCHAR(255) DEFAULT ''",
    "bucket_name": "VARCHAR(128) DEFAULT ''",
    "domain": "VARCHAR(255) DEFAULT ''",
    "public_url": "VARCHAR(255) DEFAULT ''",
    "source_filename": "VARCHAR(255) DEFAULT ''",
    "storage_status": "VARCHAR(32) DEFAULT 'ready'",
    "provider_etag": "VARCHAR(128) DEFAULT ''",
    "last_migrated_at": "DATETIME",
    "deleted_from_storage_at": "DATETIME",
}


def _has_named_index(inspector, table_name: str, index_name: str) -> bool:
    indexes = inspector.get_indexes(table_name)
    if any(index.get("name") == index_name for index in indexes):
        return True
    unique_constraints = inspector.get_unique_constraints(table_name)
    return any(constraint.get("name") == index_name for constraint in unique_constraints)


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

    if "asset_folders" in inspector.get_table_names():
        existing_columns = {column["name"] for column in inspector.get_columns("asset_folders")}
        if "parent_id" not in existing_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE asset_folders ADD COLUMN parent_id INTEGER NULL"))

    _ensure_material_storage_schema(engine)


def _ensure_material_storage_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if "materials" in inspector.get_table_names():
        existing_columns = {column["name"] for column in inspector.get_columns("materials")}
        missing_columns = [name for name in MATERIAL_COLUMN_SPECS if name not in existing_columns]
        if missing_columns:
            with engine.begin() as conn:
                for column_name in missing_columns:
                    conn.execute(text(f"ALTER TABLE materials ADD COLUMN {column_name} {MATERIAL_COLUMN_SPECS[column_name]}"))

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS material_storage_records (
                    id INTEGER PRIMARY KEY,
                    material_id INTEGER NOT NULL,
                    provider VARCHAR(32) DEFAULT 'local',
                    bucket_name VARCHAR(128) DEFAULT '',
                    storage_key VARCHAR(255) DEFAULT '',
                    public_url VARCHAR(255) DEFAULT '',
                    operation_type VARCHAR(32) DEFAULT 'upload',
                    operation_status VARCHAR(32) DEFAULT 'success',
                    operator_user_id INTEGER NULL,
                    operator_ip VARCHAR(64) DEFAULT '',
                    provider_request_id VARCHAR(128) DEFAULT '',
                    provider_etag VARCHAR(128) DEFAULT '',
                    file_size INTEGER DEFAULT 0,
                    mime_type VARCHAR(128) DEFAULT 'application/octet-stream',
                    error_message VARCHAR(255) DEFAULT '',
                    extra_json TEXT,
                    created_at DATETIME,
                    updated_at DATETIME,
                    deleted_at DATETIME,
                    FOREIGN KEY(material_id) REFERENCES materials (id),
                    FOREIGN KEY(operator_user_id) REFERENCES users (id)
                )
                """
            )
        )
        inspector = inspect(conn)
        if not _has_named_index(inspector, "material_storage_records", "ix_material_storage_records_material_id"):
            conn.execute(text("CREATE INDEX ix_material_storage_records_material_id ON material_storage_records (material_id)"))
        if not _has_named_index(inspector, "material_storage_records", "ix_material_storage_records_provider"):
            conn.execute(text("CREATE INDEX ix_material_storage_records_provider ON material_storage_records (provider)"))
        if not _has_named_index(inspector, "material_storage_records", "ix_material_storage_records_created_at"):
            conn.execute(text("CREATE INDEX ix_material_storage_records_created_at ON material_storage_records (created_at)"))


def ensure_user_profile_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    with engine.begin() as conn:
        if "avatar_url" not in existing_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(255) DEFAULT ''"))
        if "auth_source" not in existing_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN auth_source VARCHAR(32) DEFAULT 'local'"))
        inspector = inspect(conn)
        if not _has_named_index(inspector, "users", "ix_users_status_role_auth_source"):
            conn.execute(text("CREATE INDEX ix_users_status_role_auth_source ON users (status, role, auth_source)"))
        if not _has_named_index(inspector, "users", "ix_users_status_auth_source"):
            conn.execute(text("CREATE INDEX ix_users_status_auth_source ON users (status, auth_source)"))


def ensure_plan_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS plans (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(128) NOT NULL,
                    topic VARCHAR(128) DEFAULT '',
                    stage VARCHAR(64) DEFAULT '',
                    description TEXT,
                    status VARCHAR(32) DEFAULT 'draft',
                    owner_id INTEGER NULL,
                    created_at DATETIME,
                    updated_at DATETIME,
                    deleted_at DATETIME,
                    FOREIGN KEY(owner_id) REFERENCES users (id)
                )
                """
            )
        )
        inspector = inspect(conn)
        if not _has_named_index(inspector, "plans", "ix_plans_name"):
            conn.execute(text("CREATE INDEX ix_plans_name ON plans (name)"))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS plan_days (
                    id INTEGER PRIMARY KEY,
                    plan_id INTEGER NOT NULL,
                    day_number INTEGER DEFAULT 1,
                    title VARCHAR(128) DEFAULT '',
                    focus TEXT,
                    status VARCHAR(32) DEFAULT 'draft',
                    owner_id INTEGER NULL,
                    created_at DATETIME,
                    updated_at DATETIME,
                    deleted_at DATETIME,
                    FOREIGN KEY(plan_id) REFERENCES plans (id),
                    FOREIGN KEY(owner_id) REFERENCES users (id)
                )
                """
            )
        )
        if not _has_named_index(inspector, "plan_days", "ix_plan_days_plan_id"):
            conn.execute(text("CREATE INDEX ix_plan_days_plan_id ON plan_days (plan_id)"))
        if not _has_named_index(inspector, "plan_days", "ux_plan_days_plan_day"):
            conn.execute(text("CREATE UNIQUE INDEX ux_plan_days_plan_day ON plan_days (plan_id, day_number)"))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS plan_nodes (
                    id INTEGER PRIMARY KEY,
                    plan_day_id INTEGER NOT NULL,
                    node_type VARCHAR(32) DEFAULT 'custom',
                    title VARCHAR(128) DEFAULT '',
                    description VARCHAR(255) DEFAULT '',
                    sort_order INTEGER DEFAULT 0,
                    template_id INTEGER NULL,
                    msg_type VARCHAR(32) DEFAULT 'markdown',
                    content_json TEXT,
                    variables_json TEXT,
                    status VARCHAR(32) DEFAULT 'draft',
                    enabled INTEGER DEFAULT 1,
                    owner_id INTEGER NULL,
                    created_at DATETIME,
                    updated_at DATETIME,
                    deleted_at DATETIME,
                    FOREIGN KEY(plan_day_id) REFERENCES plan_days (id),
                    FOREIGN KEY(template_id) REFERENCES templates (id),
                    FOREIGN KEY(owner_id) REFERENCES users (id)
                )
                """
            )
        )
        if not _has_named_index(inspector, "plan_nodes", "ix_plan_nodes_plan_day_id"):
            conn.execute(text("CREATE INDEX ix_plan_nodes_plan_day_id ON plan_nodes (plan_day_id)"))

    # plans / plan_days: add plan_mode and trigger_rule_json
    inspector = inspect(engine)
    if "plans" in inspector.get_table_names():
        existing_plan_cols = {c["name"] for c in inspector.get_columns("plans")}
        if "plan_mode" not in existing_plan_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE plans ADD COLUMN plan_mode VARCHAR(32) DEFAULT 'day_flow'"))
    if "plan_days" in inspector.get_table_names():
        existing_day_cols = {c["name"] for c in inspector.get_columns("plan_days")}
        if "trigger_rule_json" not in existing_day_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE plan_days ADD COLUMN trigger_rule_json TEXT"))
                conn.execute(text("UPDATE plan_days SET trigger_rule_json = '{}' WHERE trigger_rule_json IS NULL"))

    # users: add permissions_json column
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        existing_columns = {column["name"] for column in inspector.get_columns("users")}
        if "permissions_json" not in existing_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN permissions_json TEXT"))

    # schedules: add batch_items_json for queue scheduling
    inspector = inspect(engine)
    if "schedules" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("schedules")}
        if "batch_items_json" not in existing_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE schedules ADD COLUMN batch_items_json TEXT"))
