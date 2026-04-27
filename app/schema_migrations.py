from __future__ import annotations

import json

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


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
    "source_tag": "VARCHAR(32)",
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


def _format_index_columns(columns: str | tuple[str, ...] | list[str]) -> str:
    if isinstance(columns, str):
        return columns
    return ", ".join(columns)


def _ensure_named_index(
    conn,
    table_name: str,
    index_name: str,
    columns: str | tuple[str, ...] | list[str],
    *,
    unique: bool = False,
) -> None:
    """Create index if missing using inspector checks.

    MySQL 不支持 `CREATE INDEX IF NOT EXISTS`，因此统一改为先查后建。
    """
    inspector = inspect(conn)
    if _has_named_index(inspector, table_name, index_name):
        return

    unique_sql = "UNIQUE " if unique else ""
    conn.execute(
        text(
            f"CREATE {unique_sql}INDEX {index_name} "
            f"ON {table_name} ({_format_index_columns(columns)})"
        )
    )


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

    # message_logs: add resolved column
    inspector = inspect(engine)
    if "message_logs" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("message_logs")}
        if "resolved" not in existing_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE message_logs ADD COLUMN resolved BOOLEAN DEFAULT 0"))

    # users: add crm_admin_id column
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "crm_admin_id" not in existing_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN crm_admin_id INTEGER NULL"))

    # CRM AI audit tables: ensure indexes exist (tables created by ORM create_all)
    ensure_crm_ai_indexes(engine)

    # CRM AI Phase 2: add audit trail columns
    _ensure_crm_ai_phase2_columns(engine)


def ensure_crm_ai_indexes(engine: Engine) -> None:
    """Ensure indexes exist on CRM AI audit tables (tables created by ORM create_all)."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    table_indexes = [
        ("crm_ai_sessions", "ix_crm_ai_sessions_session_id", ("session_id",), False),
        ("crm_ai_sessions", "ix_crm_ai_sessions_customer_id", ("crm_customer_id",), False),
        ("crm_ai_messages", "ix_crm_ai_messages_session_id", ("session_id",), False),
        ("crm_ai_messages", "ix_crm_ai_messages_message_id", ("message_id",), False),
        ("crm_ai_context_snapshots", "ix_crm_ai_snapshots_session_id", ("session_id",), False),
        ("crm_ai_guardrail_events", "ix_crm_ai_guardrails_session_id", ("session_id",), False),
        ("crm_ai_profile_cache", "ix_crm_ai_profile_cache_key", ("cache_key",), True),
        ("crm_ai_profile_cache", "ix_crm_ai_profile_cache_customer_window", ("crm_customer_id", "health_window_days"), False),
        ("crm_ai_profile_cache", "ix_crm_ai_profile_cache_expires", ("expires_at",), False),
    ]

    with engine.begin() as conn:
        for table_name, idx_name, columns, unique in table_indexes:
            if table_name in existing_tables:
                _ensure_named_index(conn, table_name, idx_name, columns, unique=unique)


_CRM_AI_PHASE2_COLUMNS = {
    "crm_ai_sessions": {
        "scene_key": "VARCHAR(32)",
        "output_style": "VARCHAR(32)",
        "prompt_version": "VARCHAR(16)",
        "prompt_hash": "VARCHAR(128)",
    },
    "crm_ai_messages": {
        "safety_result": "TEXT",
    },
    "crm_ai_context_snapshots": {
        "prompt_version": "VARCHAR(16)",
        "prompt_hash": "VARCHAR(128)",
        "scene_key": "VARCHAR(32)",
        "output_style": "VARCHAR(32)",
        "selected_expansions": "TEXT",
    },
}


def _ensure_crm_ai_phase2_columns(engine: Engine) -> None:
    """Add Phase 2 audit columns to CRM AI tables if missing."""
    inspector = inspect(engine)
    for table_name, column_specs in _CRM_AI_PHASE2_COLUMNS.items():
        if table_name not in inspector.get_table_names():
            continue
        existing = {c["name"] for c in inspector.get_columns(table_name)}
        missing = {col: spec for col, spec in column_specs.items() if col not in existing}
        if not missing:
            continue
        with engine.begin() as conn:
            for col_name, col_spec in missing.items():
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_spec}"))


def ensure_external_docs_schema(engine: Engine) -> None:
    """确保 external_doc_* 系列索引存在。表由 Base.metadata.create_all 创建。"""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    idx_checks = [
        ('uq_external_doc_resource_source', 'external_doc_resources',
         ('source_platform', 'source_doc_token', 'doc_type'), True),
        ('idx_external_doc_resources_status', 'external_doc_resources',
         ('status',), False),
        ('idx_external_doc_resources_owner', 'external_doc_resources',
         ('owner_user_id',), False),
        ('uq_external_doc_terms', 'external_doc_terms',
         ('dimension', 'code', 'scope_type', 'scope_id'), True),
        ('idx_external_doc_bindings_ws_role', 'external_doc_bindings',
         ('workspace_id', 'relation_role'), False),
        ('idx_external_doc_bindings_ws_stage', 'external_doc_bindings',
         ('workspace_id', 'primary_stage_term_id'), False),
        ('idx_external_doc_bindings_resource', 'external_doc_bindings',
         ('resource_id',), False),
        ('uq_external_doc_term_binding', 'external_doc_term_bindings',
         ('resource_id', 'term_id', 'binding_type'), True),
    ]
    with engine.begin() as conn:
        for idx_name, table, columns, unique in idx_checks:
            if table in existing_tables:
                _ensure_named_index(conn, table, idx_name, columns, unique=unique)


def ensure_rag_schema(engine: Engine) -> None:
    """确保 RAG 表补充列和索引存在。表由 Base.metadata.create_all 创建。"""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if "rag_retrieval_logs" in existing_tables:
        existing_columns = {c["name"] for c in inspector.get_columns("rag_retrieval_logs")}
        if "intent_json" not in existing_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE rag_retrieval_logs ADD COLUMN intent_json TEXT"))

    rag_indexes = [
        ("idx_rag_tags_dimension", "rag_tags", ("dimension",), False),
        ("idx_rag_resources_source", "rag_resources", ("source_type", "source_id"), False),
        ("idx_rag_resources_status", "rag_resources", ("status",), False),
        ("idx_rag_chunks_resource", "rag_chunks", ("resource_id",), False),
        ("idx_rag_chunks_status", "rag_chunks", ("status",), False),
        ("idx_rag_retrieval_logs_session", "rag_retrieval_logs", ("session_id",), False),
        ("idx_rag_retrieval_logs_customer", "rag_retrieval_logs", ("customer_id",), False),
    ]
    with engine.begin() as conn:
        for idx_name, table, columns, unique in rag_indexes:
            if table in existing_tables:
                _ensure_named_index(conn, table, idx_name, columns, unique=unique)


def ensure_speech_category_schema(engine: Engine) -> None:
    """确保 speech_categories 表存在，并种子分类数据 + 回填 category_id。"""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    with engine.begin() as conn:
        # 1. Create table if not exists
        if 'speech_categories' not in existing_tables:
            conn.execute(text("""
                CREATE TABLE speech_categories (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(64) NOT NULL,
                    parent_id INTEGER REFERENCES speech_categories(id),
                    level INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME,
                    updated_at DATETIME,
                    deleted_at DATETIME
                )
            """))
            _ensure_named_index(conn, 'speech_categories', 'ix_speech_cat_parent', ('parent_id',), unique=False)

        # 2. Add category_id column to speech_templates if missing
        existing_columns = [c['name'] for c in inspector.get_columns('speech_templates')]
        if 'category_id' not in existing_columns:
            conn.execute(text("ALTER TABLE speech_templates ADD COLUMN category_id INTEGER"))
            _ensure_named_index(conn, 'speech_templates', 'ix_speech_tpl_category', ('category_id',), unique=False)
        if 'metadata_json' not in existing_columns:
            conn.execute(text("ALTER TABLE speech_templates ADD COLUMN metadata_json TEXT"))

    # 3. Seed categories if empty
    from .models import SpeechCategory, SpeechTemplate
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        if db.query(SpeechCategory).count() == 0:
            from .services.crm_speech_templates import CATEGORY_SEED, SCENE_CATEGORY_MAP
            name_to_id: dict[str, int] = {}
            for l1 in CATEGORY_SEED:
                cat_l1 = SpeechCategory(name=l1['name'], level=1, sort_order=CATEGORY_SEED.index(l1) + 1)
                db.add(cat_l1)
                db.flush()
                name_to_id[l1['name']] = cat_l1.id
                for idx, child_name in enumerate(l1['children'], 1):
                    cat_l2 = SpeechCategory(name=child_name, level=2, parent_id=cat_l1.id, sort_order=idx)
                    db.add(cat_l2)
                    db.flush()
                    name_to_id[child_name] = cat_l2.id
            db.commit()

            # 4. Backfill category_id for existing templates
            for tpl in db.query(SpeechTemplate).filter(SpeechTemplate.category_id.is_(None)).all():
                l2_name = SCENE_CATEGORY_MAP.get(tpl.scene_key)
                if l2_name and l2_name in name_to_id:
                    tpl.category_id = name_to_id[l2_name]
            db.commit()
    finally:
        db.close()
