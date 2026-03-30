from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class User(Base, TimestampMixin):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default='coach')
    display_name: Mapped[str] = mapped_column(String(100), default='')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Group(Base, TimestampMixin):
    __tablename__ = 'groups'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    alias: Mapped[str] = mapped_column(String(120), default='')
    webhook_encrypted: Mapped[str] = mapped_column(Text, default='')
    description: Mapped[str] = mapped_column(Text, default='')
    tags_json: Mapped[str] = mapped_column(Text, default='[]')
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_test_group: Mapped[bool] = mapped_column(Boolean, default=False)

class Template(Base, TimestampMixin):
    __tablename__ = 'templates'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(80), default='general')
    msg_type: Mapped[str] = mapped_column(String(30), default='markdown')
    description: Mapped[str] = mapped_column(Text, default='')
    content_json: Mapped[str] = mapped_column(Text)
    variables_json: Mapped[str] = mapped_column(Text, default='{}')
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_by = relationship('User')

class Asset(Base, TimestampMixin):
    __tablename__ = 'assets'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    asset_type: Mapped[str] = mapped_column(String(30))
    file_name: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(120), default='application/octet-stream')
    size: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_by = relationship('User')

class MessageJob(Base, TimestampMixin):
    __tablename__ = 'message_jobs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(140), index=True)
    group_ids_json: Mapped[str] = mapped_column(Text, default='[]')
    template_id: Mapped[int | None] = mapped_column(ForeignKey('templates.id'), nullable=True)
    template = relationship('Template')
    msg_type: Mapped[str] = mapped_column(String(30), default='markdown')
    content_json: Mapped[str] = mapped_column(Text)
    variables_json: Mapped[str] = mapped_column(Text, default='{}')
    schedule_type: Mapped[str] = mapped_column(String(20), default='none')
    run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cron_expr: Mapped[str] = mapped_column(String(120), default='')
    timezone: Mapped[str] = mapped_column(String(60), default='Asia/Shanghai')
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    approved_by = relationship('User', foreign_keys=[approved_by_id])
    status: Mapped[str] = mapped_column(String(30), default='draft')
    last_error: Mapped[str] = mapped_column(Text, default='')
    skip_dates_json: Mapped[str] = mapped_column(Text, default='[]')
    skip_weekends: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_by = relationship('User', foreign_keys=[created_by_id])
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class SendLog(Base):
    __tablename__ = 'send_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey('message_jobs.id'), nullable=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey('groups.id'), nullable=True)
    initiated_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    msg_type: Mapped[str] = mapped_column(String(30))
    run_mode: Mapped[str] = mapped_column(String(20), default='immediate')
    request_json: Mapped[str] = mapped_column(Text, default='{}')
    response_json: Mapped[str] = mapped_column(Text, default='{}')
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    job = relationship('MessageJob')
    group = relationship('Group')
    initiated_by = relationship('User')
class ApprovalRequest(Base, TimestampMixin):
    __tablename__ = 'approval_requests'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default='pending')
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
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[int] = mapped_column(Integer)
    detail_json: Mapped[str] = mapped_column(Text, default='{}')
    ip: Mapped[str] = mapped_column(String(64), default='')
    
    user = relationship('User')
