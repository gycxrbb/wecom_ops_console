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
    "rag_meta_json": "TEXT",
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
                    error_message TEXT,
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
        _ensure_material_storage_error_message_text(conn)
        if not _has_named_index(inspector, "material_storage_records", "ix_material_storage_records_material_id"):
            conn.execute(text("CREATE INDEX ix_material_storage_records_material_id ON material_storage_records (material_id)"))
        if not _has_named_index(inspector, "material_storage_records", "ix_material_storage_records_provider"):
            conn.execute(text("CREATE INDEX ix_material_storage_records_provider ON material_storage_records (provider)"))
        if not _has_named_index(inspector, "material_storage_records", "ix_material_storage_records_created_at"):
            conn.execute(text("CREATE INDEX ix_material_storage_records_created_at ON material_storage_records (created_at)"))


def _ensure_material_storage_error_message_text(conn) -> None:
    inspector = inspect(conn)
    columns = {column["name"]: column for column in inspector.get_columns("material_storage_records")}
    column = columns.get("error_message")
    if not column:
        return

    column_type = str(column.get("type", "")).upper()
    if "TEXT" in column_type:
        return

    dialect = conn.dialect.name
    if dialect == "mysql":
        conn.execute(text("ALTER TABLE material_storage_records MODIFY COLUMN error_message TEXT"))
    elif dialect == "sqlite":
        return
    else:
        conn.execute(text("ALTER TABLE material_storage_records ALTER COLUMN error_message TYPE TEXT"))


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

    # CRM AI attachments: ensure indexes (table created by ORM create_all)
    ensure_crm_ai_attachment_indexes(engine)

    # CRM AI message feedback table
    ensure_crm_ai_feedback_schema(engine)


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


def ensure_crm_ai_attachment_indexes(engine: Engine) -> None:
    """Ensure indexes and columns on crm_ai_attachments table."""
    inspector = inspect(engine)
    if "crm_ai_attachments" not in inspector.get_table_names():
        return

    # Add missing columns for evolving schema
    existing_cols = {c["name"] for c in inspector.get_columns("crm_ai_attachments")}
    if "storage_public_url" not in existing_cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE crm_ai_attachments ADD COLUMN storage_public_url TEXT"))
    if "content_hash" not in existing_cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE crm_ai_attachments ADD COLUMN content_hash VARCHAR(64) DEFAULT ''"))
    if "analysis_retry_count" not in existing_cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE crm_ai_attachments ADD COLUMN analysis_retry_count INTEGER DEFAULT 0"))

    idx_checks = [
        ("crm_ai_attachments", "ix_crm_ai_att_att_id", ("attachment_id",), True),
        ("crm_ai_attachments", "ix_crm_ai_att_customer", ("crm_customer_id",), False),
        ("crm_ai_attachments", "ix_crm_ai_att_session", ("session_id",), False),
        ("crm_ai_attachments", "ix_crm_ai_att_status", ("processing_status",), False),
        ("crm_ai_attachments", "ix_crm_ai_att_customer_hash", ("crm_customer_id", "content_hash"), False),
    ]
    with engine.begin() as conn:
        for table_name, idx_name, columns, unique in idx_checks:
            _ensure_named_index(conn, table_name, idx_name, columns, unique=unique)

        # Widen mime_type column for long MIME types (e.g. application/vnd.openxmlformats-...)
        cols = {c["name"]: c for c in inspect(conn).get_columns("crm_ai_attachments")}
        mime_col = cols.get("mime_type")
        if mime_col:
            col_type = str(mime_col.get("type", "")).upper()
            # Extract length from VARCHAR(n) or String(n)
            import re
            m = re.search(r'\((\d+)\)', col_type)
            if m and int(m.group(1)) < 128:
                dialect = conn.dialect.name
                if dialect == "mysql":
                    conn.execute(text("ALTER TABLE crm_ai_attachments MODIFY COLUMN mime_type VARCHAR(128) NOT NULL"))
                elif dialect == "sqlite":
                    pass  # SQLite doesn't enforce VARCHAR length
                else:
                    conn.execute(text("ALTER TABLE crm_ai_attachments ALTER COLUMN mime_type TYPE VARCHAR(128)"))


_CRM_AI_PHASE2_COLUMNS = {
    "crm_ai_sessions": {
        "scene_key": "VARCHAR(32)",
        "output_style": "VARCHAR(32)",
        "prompt_version": "VARCHAR(16)",
        "prompt_hash": "VARCHAR(128)",
    },
    "crm_ai_messages": {
        "safety_result": "TEXT",
        "request_params_json": "TEXT",
    },
    "crm_ai_context_snapshots": {
        "prompt_version": "VARCHAR(16)",
        "prompt_hash": "VARCHAR(128)",
        "scene_key": "VARCHAR(32)",
        "output_style": "VARCHAR(32)",
        "selected_expansions": "TEXT",
        "health_window_days": "INT",
        "cache_key": "VARCHAR(128)",
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
        if "query_intent_json" not in existing_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE rag_retrieval_logs ADD COLUMN query_intent_json TEXT"))
        if "rerank_scores_json" not in existing_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE rag_retrieval_logs ADD COLUMN rerank_scores_json TEXT"))

    if "rag_tags" in existing_tables:
        existing_columns = {c["name"] for c in inspector.get_columns("rag_tags")}
        if "aliases" not in existing_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE rag_tags ADD COLUMN aliases TEXT"))

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

        # 3. Add code column to speech_categories if missing
        cat_columns = [c['name'] for c in inspector.get_columns('speech_categories')]
        if 'code' not in cat_columns:
            conn.execute(text("ALTER TABLE speech_categories ADD COLUMN code VARCHAR(128)"))
            _ensure_named_index(conn, 'speech_categories', 'uq_speech_cat_code', ('code',), unique=True)

    # 3. Seed / migrate categories
    from .models import SpeechCategory, SpeechTemplate
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        if db.query(SpeechCategory).count() == 0:
            _seed_3level_categories(db)
        else:
            _migrate_to_3level_categories(db)

        # Migrate old visibility values in metadata_json
        _migrate_visibility_values(db)
    finally:
        db.close()


def _migrate_visibility_values(db) -> None:
    """Replace legacy visibility values in speech_templates.metadata_json."""
    from .models import SpeechTemplate
    import json as _json

    VISIBILITY_MAP = {
        'customer_sendable': 'customer_visible',
        'internal': 'coach_internal',
        'public': 'customer_visible',
    }
    rows = db.query(SpeechTemplate).filter(
        SpeechTemplate.metadata_json.isnot(None),
        SpeechTemplate.metadata_json != '',
    ).all()
    updated = 0
    for row in rows:
        try:
            meta = _json.loads(row.metadata_json)
        except (ValueError, TypeError):
            continue
        vis = meta.get('visibility')
        if vis and vis in VISIBILITY_MAP:
            meta['visibility'] = VISIBILITY_MAP[vis]
            row.metadata_json = _json.dumps(meta, ensure_ascii=False)
            updated += 1
    if updated:
        db.commit()


def _seed_3level_categories(db) -> None:
    """Fresh install: create L1 > L2 > L3 categories with codes and backfill template category_id."""
    from .models import SpeechCategory, SpeechTemplate
    from .services.crm_speech_templates import CATEGORY_SEED, SCENE_CATEGORY_MAP

    l3_name_to_id: dict[str, int] = {}
    for l1_idx, l1 in enumerate(CATEGORY_SEED, 1):
        cat_l1 = SpeechCategory(name=l1['name'], code=l1.get('code'), level=1, sort_order=l1_idx)
        db.add(cat_l1)
        db.flush()
        for l2_idx, l2_child in enumerate(l1['children'], 1):
            if isinstance(l2_child, str):
                cat_l2 = SpeechCategory(name=l2_child, level=2, parent_id=cat_l1.id, sort_order=l2_idx)
            else:
                cat_l2 = SpeechCategory(name=l2_child['name'], code=l2_child.get('code'), level=2, parent_id=cat_l1.id, sort_order=l2_idx)
            db.add(cat_l2)
            db.flush()
            children = l2_child.get('children', []) if isinstance(l2_child, dict) else []
            for l3_idx, l3_item in enumerate(children, 1):
                if isinstance(l3_item, dict):
                    l3_name = l3_item['name']
                    l3_code = l3_item.get('code')
                else:
                    l3_name = l3_item
                    l3_code = None
                cat_l3 = SpeechCategory(name=l3_name, code=l3_code, level=3, parent_id=cat_l2.id, sort_order=l3_idx)
                db.add(cat_l3)
                db.flush()
                l3_name_to_id[l3_name] = cat_l3.id
    db.commit()

    # Backfill category_id for existing templates → point to L3
    for tpl in db.query(SpeechTemplate).filter(SpeechTemplate.category_id.is_(None)).all():
        mapping = SCENE_CATEGORY_MAP.get(tpl.scene_key)
        if isinstance(mapping, tuple):
            l3_id = l3_name_to_id.get(mapping[1])
            if l3_id:
                tpl.category_id = l3_id
    db.commit()


def _backfill_category_codes(db, name_to_code: dict[str, str]) -> None:
    """Backfill code column on existing categories that have no code set."""
    from .models import SpeechCategory
    rows = db.query(SpeechCategory).filter(
        SpeechCategory.deleted_at.is_(None),
    ).all()
    updated = 0
    for row in rows:
        if not row.code and row.name in name_to_code:
            row.code = name_to_code[row.name]
            updated += 1
    if updated:
        db.commit()


def _migrate_to_3level_categories(db) -> None:
    """Existing DB: create L3 categories under existing L2, migrate template category_id from L2 → L3, backfill codes."""
    from .models import SpeechCategory, SpeechTemplate
    from .services.crm_speech_templates import CATEGORY_SEED, SCENE_CATEGORY_MAP

    # Build name -> code lookup from seed for backfill
    name_to_code: dict[str, str] = {}
    for l1 in CATEGORY_SEED:
        name_to_code[l1['name']] = l1.get('code', '')
        for l2_child in l1['children']:
            if isinstance(l2_child, dict):
                name_to_code[l2_child['name']] = l2_child.get('code', '')
                for l3_item in l2_child.get('children', []):
                    if isinstance(l3_item, dict):
                        name_to_code[l3_item['name']] = l3_item.get('code', '')

    existing_l3 = db.query(SpeechCategory).filter(SpeechCategory.level == 3, SpeechCategory.deleted_at.is_(None)).count()
    if existing_l3 > 0:
        # L3 already exists — just backfill codes if missing
        _backfill_category_codes(db, name_to_code)
        return

    # Build L2 name -> L3 children from seed
    l2_to_l3_children: dict[str, list] = {}
    for l1 in CATEGORY_SEED:
        for l2_child in l1['children']:
            if isinstance(l2_child, dict):
                l2_to_l3_children[l2_child['name']] = l2_child.get('children', [])

    # Create L3 categories under each existing L2
    l3_name_to_id: dict[str, int] = {}
    l2_cats = db.query(SpeechCategory).filter(SpeechCategory.level == 2, SpeechCategory.deleted_at.is_(None)).all()
    for l2 in l2_cats:
        l3_children = l2_to_l3_children.get(l2.name, [])
        for idx, l3_item in enumerate(l3_children, 1):
            if isinstance(l3_item, dict):
                l3_name = l3_item['name']
                l3_code = l3_item.get('code')
            else:
                l3_name = l3_item
                l3_code = None
            cat_l3 = SpeechCategory(name=l3_name, code=l3_code, level=3, parent_id=l2.id, sort_order=idx)
            db.add(cat_l3)
            db.flush()
            l3_name_to_id[l3_name] = cat_l3.id
    db.commit()

    if not l3_name_to_id:
        return

    # Migrate templates: category_id from L2 → L3
    for tpl in db.query(SpeechTemplate).filter(SpeechTemplate.category_id.isnot(None)).all():
        cat = db.query(SpeechCategory).get(tpl.category_id)
        if not cat or cat.level != 2:
            continue
        mapping = SCENE_CATEGORY_MAP.get(tpl.scene_key)
        if isinstance(mapping, tuple):
            l3_id = l3_name_to_id.get(mapping[1])
            if l3_id:
                tpl.category_id = l3_id
        else:
            first_l3 = db.query(SpeechCategory).filter_by(parent_id=cat.id, level=3).order_by(SpeechCategory.sort_order).first()
            if first_l3:
                tpl.category_id = first_l3.id
    db.commit()

    # Backfill codes on existing L1/L2 as well
    _backfill_category_codes(db, name_to_code)


def ensure_crm_ai_feedback_schema(engine: Engine) -> None:
    """Ensure crm_ai_message_feedback table exists."""
    autoincrement_kw = "AUTO_INCREMENT" if engine.dialect.name.lower() == "mysql" else "AUTOINCREMENT"
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS crm_ai_message_feedback (
                id INTEGER PRIMARY KEY {autoincrement_kw},
                feedback_id VARCHAR(64) NOT NULL,
                session_id VARCHAR(64) NOT NULL,
                message_id VARCHAR(64) NOT NULL,
                user_message_id VARCHAR(64),
                crm_customer_id INTEGER NOT NULL,
                coach_user_id INTEGER NOT NULL,
                crm_admin_id INTEGER,
                rating VARCHAR(16) NOT NULL,
                reason_category VARCHAR(64),
                reason_text TEXT,
                expected_answer TEXT,
                user_question_snapshot TEXT,
                ai_answer_snapshot TEXT,
                customer_reply_snapshot TEXT,
                scene_key VARCHAR(32),
                output_style VARCHAR(32),
                prompt_version VARCHAR(16),
                prompt_hash VARCHAR(128),
                model VARCHAR(64),
                status VARCHAR(24) NOT NULL DEFAULT 'new',
                admin_note TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
    inspector = inspect(engine)
    if "crm_ai_message_feedback" in inspector.get_table_names():
        idx_checks = [
            ("ix_crm_feedback_fid", "crm_ai_message_feedback", ("feedback_id",), True),
            ("ix_crm_feedback_sid", "crm_ai_message_feedback", ("session_id",), False),
            ("ix_crm_feedback_mid", "crm_ai_message_feedback", ("message_id",), False),
            ("ix_crm_feedback_cid", "crm_ai_message_feedback", ("crm_customer_id",), False),
            ("ux_crm_feedback_mid_uid", "crm_ai_message_feedback", ("message_id", "coach_user_id"), True),
        ]
        with engine.begin() as conn:
            for idx_name, table, columns, unique in idx_checks:
                _ensure_named_index(conn, table, idx_name, columns, unique=unique)

    # P1: regenerated_from_message_id + quoted_message_id on crm_ai_messages
    ensure_crm_ai_message_p1_columns(engine)


def ensure_crm_ai_message_p1_columns(engine: Engine) -> None:
    """Add P1 columns to crm_ai_messages for regeneration and quote tracking."""
    inspector = inspect(engine)
    if "crm_ai_messages" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("crm_ai_messages")}
    with engine.begin() as conn:
        if "regenerated_from_message_id" not in existing:
            conn.execute(text("ALTER TABLE crm_ai_messages ADD COLUMN regenerated_from_message_id VARCHAR(64)"))
        if "quoted_message_id" not in existing:
            conn.execute(text("ALTER TABLE crm_ai_messages ADD COLUMN quoted_message_id VARCHAR(64)"))


def ensure_prompt_snapshot_is_current(engine: Engine) -> None:
    """Add is_current column to prompt_snapshots for tracking active snapshot."""
    inspector = inspect(engine)
    if "prompt_snapshots" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("prompt_snapshots")}
    with engine.begin() as conn:
        if "is_current" not in existing:
            conn.execute(text("ALTER TABLE prompt_snapshots ADD COLUMN is_current BOOLEAN DEFAULT 0"))

    # Add layer/label to snapshot items for recreating deleted templates
    if "prompt_snapshot_items" in inspector.get_table_names():
        existing = {c["name"] for c in inspector.get_columns("prompt_snapshot_items")}
        with engine.begin() as conn:
            if "layer" not in existing:
                conn.execute(text("ALTER TABLE prompt_snapshot_items ADD COLUMN layer VARCHAR(32)"))
            if "label" not in existing:
                conn.execute(text("ALTER TABLE prompt_snapshot_items ADD COLUMN label VARCHAR(64)"))


def ensure_auto_ranking_config_schema(engine: Engine) -> None:
    """Create auto_ranking_configs table if not exists."""
    dialect = engine.dialect.name.lower()
    with engine.begin() as conn:
        if dialect == "mysql":
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS auto_ranking_configs (
                    id INTEGER NOT NULL AUTO_INCREMENT,
                    name VARCHAR(128) NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    crm_group_ids_json TEXT,
                    target_local_group_id INTEGER NOT NULL,
                    must_scene_keys_json TEXT,
                    extra_scene_pool_json TEXT,
                    scene_count INTEGER DEFAULT 3,
                    speech_style VARCHAR(32) DEFAULT 'professional',
                    include_breakdown_on_monday INTEGER DEFAULT 1,
                    skip_weekends INTEGER DEFAULT 0,
                    skip_dates_json TEXT,
                    push_hour INTEGER DEFAULT 0,
                    push_minute INTEGER DEFAULT 0,
                    last_run_at DATETIME,
                    last_error TEXT,
                    created_at DATETIME,
                    updated_at DATETIME,
                    PRIMARY KEY (id)
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS auto_ranking_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(128) NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    crm_group_ids_json TEXT DEFAULT '[]',
                    target_local_group_id INTEGER NOT NULL,
                    must_scene_keys_json TEXT DEFAULT '["top_leader", "top_six"]',
                    extra_scene_pool_json TEXT DEFAULT '[]',
                    scene_count INTEGER DEFAULT 3,
                    speech_style VARCHAR(32) DEFAULT 'professional',
                    include_breakdown_on_monday INTEGER DEFAULT 1,
                    skip_weekends INTEGER DEFAULT 0,
                    skip_dates_json TEXT DEFAULT '[]',
                    push_hour INTEGER DEFAULT 0,
                    push_minute INTEGER DEFAULT 0,
                    last_run_at DATETIME,
                    last_error TEXT DEFAULT '',
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """))
    # 补列兜底：表已存在但缺少新字段
    inspector = inspect(engine)
    if "auto_ranking_configs" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("auto_ranking_configs")}
        with engine.begin() as conn:
            if "push_hour" not in cols:
                conn.execute(text("ALTER TABLE auto_ranking_configs ADD COLUMN push_hour INTEGER DEFAULT 0"))
            if "push_minute" not in cols:
                conn.execute(text("ALTER TABLE auto_ranking_configs ADD COLUMN push_minute INTEGER DEFAULT 0"))
            if "rank_metric" not in cols:
                conn.execute(text("ALTER TABLE auto_ranking_configs ADD COLUMN rank_metric VARCHAR(32) DEFAULT 'current_points'"))
