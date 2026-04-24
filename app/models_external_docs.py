from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class ExternalDocResource(Base):
    __tablename__ = 'external_doc_resources'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    open_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_platform: Mapped[str] = mapped_column(String(32), nullable=False, default='feishu')
    source_doc_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False, default='unknown')
    summary: Mapped[str] = mapped_column(String(255), nullable=False, default='')
    access_scope: Mapped[str] = mapped_column(String(32), nullable=False, default='unknown')
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    maintainer_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active')
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default='unverified')
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    extra_meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint('source_platform', 'source_doc_token', 'doc_type',
                         name='uq_external_doc_resource_source'),
        Index('idx_external_doc_resources_status', 'status'),
        Index('idx_external_doc_resources_owner', 'owner_user_id'),
        Index('idx_external_doc_resources_maintainer', 'maintainer_user_id'),
    )


class ExternalDocWorkspace(Base):
    __tablename__ = 'external_doc_workspaces'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    workspace_type: Mapped[str] = mapped_column(String(32), nullable=False, default='project')
    biz_line: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='planning')
    current_stage_term_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False, default='')
    start_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ExternalDocTerm(Base):
    __tablename__ = 'external_doc_terms'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, default='global')
    scope_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint('dimension', 'code', 'scope_type', 'scope_id',
                         name='uq_external_doc_terms'),
    )


class ExternalDocBinding(Base):
    __tablename__ = 'external_doc_bindings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey('external_doc_resources.id'), nullable=False)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey('external_doc_workspaces.id'), nullable=True)
    primary_stage_term_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deliverable_term_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relation_role: Mapped[str] = mapped_column(String(32), nullable=False, default='support')
    is_primary: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remark: Mapped[str] = mapped_column(String(255), nullable=False, default='')
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active')
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index('idx_external_doc_bindings_ws_role', 'workspace_id', 'relation_role'),
        Index('idx_external_doc_bindings_ws_stage', 'workspace_id', 'primary_stage_term_id'),
        Index('idx_external_doc_bindings_resource', 'resource_id'),
    )


class ExternalDocTermBinding(Base):
    __tablename__ = 'external_doc_term_bindings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey('external_doc_resources.id'), nullable=False)
    term_id: Mapped[int] = mapped_column(ForeignKey('external_doc_terms.id'), nullable=False)
    binding_type: Mapped[str] = mapped_column(String(32), nullable=False, default='secondary')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('resource_id', 'term_id', 'binding_type',
                         name='uq_external_doc_term_binding'),
    )


class ExternalDocOpenLog(Base):
    __tablename__ = 'external_doc_open_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey('external_doc_resources.id'), nullable=False)
    workspace_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opened_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    client_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
