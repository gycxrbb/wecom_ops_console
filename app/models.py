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
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    owner = relationship('User')

    @property
    def file_name(self) -> str:
        return self.name

class Schedule(Base, TimestampMixin):
    __tablename__ = 'schedules'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey('groups.id'))
    template_id: Mapped[int | None] = mapped_column(ForeignKey('templates.id'), nullable=True)
    msg_type: Mapped[str] = mapped_column(String(32), default='markdown')
    content_snapshot: Mapped[str] = mapped_column(Text)
    variables: Mapped[str] = mapped_column(Text, default='{}')
    schedule_type: Mapped[str] = mapped_column(String(32), default='once')
    cron_expr: Mapped[str | None] = mapped_column(String(64), nullable=True)
    run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default='Asia/Shanghai')
    skip_weekends: Mapped[int] = mapped_column(Integer, default=0)
    skip_dates: Mapped[str] = mapped_column(Text, default='[]')
    require_approval: Mapped[int] = mapped_column(Integer, default=0)
    approval_status: Mapped[str] = mapped_column(String(32), default='not_required')
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    group = relationship('Group')
    template = relationship('Template')
    owner = relationship('User')

    @property
    def title(self) -> str:
        return self.name

    @title.setter
    def title(self, value: str) -> None:
        self.name = value

    @property
    def content(self) -> str:
        return self.content_snapshot

    @content.setter
    def content(self, value: str) -> None:
        self.content_snapshot = value

    @property
    def group_ids_json(self) -> str:
        return f'[{self.group_id}]' if self.group_id is not None else '[]'

    @group_ids_json.setter
    def group_ids_json(self, value: str) -> None:
        try:
            import json
            parsed = json.loads(value) if isinstance(value, str) else value
        except Exception:
            parsed = value
        if isinstance(parsed, list):
            self.group_id = int(parsed[0]) if parsed else 0
        elif parsed in (None, ''):
            self.group_id = 0
        else:
            self.group_id = int(parsed)

    @property
    def skip_dates_json(self) -> str:
        return self.skip_dates

    @skip_dates_json.setter
    def skip_dates_json(self, value: str) -> None:
        self.skip_dates = value

    @property
    def approval_required(self) -> bool:
        return bool(self.require_approval)

    @approval_required.setter
    def approval_required(self, value: bool) -> None:
        self.require_approval = 1 if value else 0

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
