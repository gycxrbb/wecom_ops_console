from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class User(Base, TimestampMixin):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(64), default='')
    role: Mapped[str] = mapped_column(String(32), default='coach')
    status: Mapped[int] = mapped_column(Integer, default=1)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class Group(Base, TimestampMixin):
    __tablename__ = 'groups'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    alias: Mapped[str] = mapped_column(String(128), default='')
    group_type: Mapped[str] = mapped_column(String(32), default='formal')
    tags: Mapped[str] = mapped_column(Text, default='[]')
    webhook_cipher: Mapped[str] = mapped_column(Text, default='')
    webhook_mask: Mapped[str] = mapped_column(String(128), default='')
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    default_template_set_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

class Template(Base, TimestampMixin):
    __tablename__ = 'templates'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    category: Mapped[str] = mapped_column(String(64), default='general')
    msg_type: Mapped[str] = mapped_column(String(32), default='markdown')
    content: Mapped[str] = mapped_column(Text)
    variable_schema: Mapped[str] = mapped_column(Text, default='{}')
    default_variables: Mapped[str] = mapped_column(Text, default='{}')
    is_system: Mapped[int] = mapped_column(Integer, default=0)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    owner = relationship('User')

class AssetFolder(Base, TimestampMixin):
    __tablename__ = 'asset_folders'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey('asset_folders.id'), nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    parent = relationship('AssetFolder', remote_side=[id], backref='children')
    owner = relationship('User')

class Material(Base, TimestampMixin):
    __tablename__ = 'materials'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    material_type: Mapped[str] = mapped_column(String(32))
    storage_path: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(255), default='')
    mime_type: Mapped[str] = mapped_column(String(128), default='application/octet-stream')
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    file_hash: Mapped[str] = mapped_column(String(64), default='')
    tags: Mapped[str] = mapped_column(Text, default='[]')
    folder_id: Mapped[int | None] = mapped_column(ForeignKey('asset_folders.id'), nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    folder = relationship('AssetFolder')
    owner = relationship('User')

    @property
    def file_name(self) -> str:
        return self.name


class Plan(Base, TimestampMixin):
    __tablename__ = 'plans'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    topic: Mapped[str] = mapped_column(String(128), default='')
    stage: Mapped[str] = mapped_column(String(64), default='')
    description: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(String(32), default='draft')
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    owner = relationship('User')
    days: Mapped[list['PlanDay']] = relationship(
        'PlanDay',
        back_populates='plan',
        cascade='all, delete-orphan',
        order_by='PlanDay.day_number',
    )


class PlanDay(Base, TimestampMixin):
    __tablename__ = 'plan_days'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey('plans.id'), index=True)
    day_number: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(128), default='')
    focus: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(String(32), default='draft')
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    plan: Mapped['Plan'] = relationship('Plan', back_populates='days')
    owner = relationship('User')
    nodes: Mapped[list['PlanNode']] = relationship(
        'PlanNode',
        back_populates='plan_day',
        cascade='all, delete-orphan',
        order_by='PlanNode.sort_order',
    )


class PlanNode(Base, TimestampMixin):
    __tablename__ = 'plan_nodes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_day_id: Mapped[int] = mapped_column(ForeignKey('plan_days.id'), index=True)
    node_type: Mapped[str] = mapped_column(String(32), default='custom')
    title: Mapped[str] = mapped_column(String(128), default='')
    description: Mapped[str] = mapped_column(String(255), default='')
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    template_id: Mapped[int | None] = mapped_column(ForeignKey('templates.id'), nullable=True)
    msg_type: Mapped[str] = mapped_column(String(32), default='markdown')
    content_json: Mapped[str] = mapped_column(Text, default='{}')
    variables_json: Mapped[str] = mapped_column(Text, default='{}')
    status: Mapped[str] = mapped_column(String(32), default='draft')
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    plan_day: Mapped['PlanDay'] = relationship('PlanDay', back_populates='nodes')
    template = relationship('Template')
    owner = relationship('User')

class Schedule(Base, TimestampMixin):
    __tablename__ = 'schedules'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    group_id: Mapped[int] = mapped_column(ForeignKey('groups.id'))
    group_ids_json: Mapped[str] = mapped_column(Text, default='[]')
    template_id: Mapped[int | None] = mapped_column(ForeignKey('templates.id'), nullable=True)
    msg_type: Mapped[str] = mapped_column(String(32), default='markdown')
    content_snapshot: Mapped[str] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    variables: Mapped[str] = mapped_column(Text, default='{}')
    schedule_type: Mapped[str] = mapped_column(String(32), default='once')
    cron_expr: Mapped[str | None] = mapped_column(String(64), nullable=True)
    run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default='Asia/Shanghai')
    skip_weekends: Mapped[int] = mapped_column(Integer, default=0)
    skip_dates: Mapped[str] = mapped_column(Text, default='[]')
    skip_dates_json: Mapped[str] = mapped_column(Text, default='[]')
    require_approval: Mapped[int] = mapped_column(Integer, default=0)
    approval_required: Mapped[int] = mapped_column(Integer, default=0)
    approval_status: Mapped[str] = mapped_column(String(32), default='not_required')
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default='draft')
    last_error: Mapped[str] = mapped_column(Text, default='')
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    group = relationship('Group')
    template = relationship('Template')
    owner = relationship('User')

class Message(Base, TimestampMixin):
    __tablename__ = 'messages'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32), default='manual')
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    group_id: Mapped[int] = mapped_column(ForeignKey('groups.id'))
    template_id: Mapped[int | None] = mapped_column(ForeignKey('templates.id'), nullable=True)
    msg_type: Mapped[str] = mapped_column(String(32), default='markdown')
    rendered_content: Mapped[str] = mapped_column(Text)
    request_payload: Mapped[str] = mapped_column(Text, default='{}')
    status: Mapped[str] = mapped_column(String(32), default='pending')
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    group = relationship('Group')
    template = relationship('Template')
    creator = relationship('User')

class MessageLog(Base, TimestampMixin):
    __tablename__ = 'message_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey('messages.id'))
    request_payload: Mapped[str] = mapped_column(Text, default='{}')
    response_payload: Mapped[str] = mapped_column(Text, default='{}')
    http_status: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    message = relationship('Message')

    @property
    def request_json(self) -> str:
        return self.request_payload

    @request_json.setter
    def request_json(self, value: str) -> None:
        self.request_payload = value

    @property
    def response_json(self) -> str:
        return self.response_payload

    @response_json.setter
    def response_json(self, value: str) -> None:
        self.response_payload = value

class ApprovalRequest(Base, TimestampMixin):
    __tablename__ = 'approval_requests'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default='pending')
    applicant_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    approver_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    applicant = relationship('User', foreign_keys=[applicant_id])
    approver = relationship('User', foreign_keys=[approver_id])

class AuditLog(Base, TimestampMixin):
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[int] = mapped_column(Integer)
    detail: Mapped[str] = mapped_column(Text, default='{}')
    ip: Mapped[str] = mapped_column(String(64), default='')
    user = relationship('User')
