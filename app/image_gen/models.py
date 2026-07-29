"""图片生成模块 ORM：供应商配置 / 生图历史 / 提示词库。

复用项目统一 ``Base``。api_key 用 Fernet 加密存储（复用 security.encrypt_webhook），
与 app_secret_key 绑定（轮换 secret 会让已存的 provider key 失效，需重新配置）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ImageGenProvider(Base):
    """生图供应商配置（管理员维护）。base_url 存根（不含 /v1），按 provider_kind 拼接。"""

    __tablename__ = "image_gen_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="供应商显示名")
    provider_kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="openai_compatible", comment="openai_compatible | doubao"
    )
    base_url: Mapped[str] = mapped_column(String(255), nullable=False, comment="根地址，不含 /v1")
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="Fernet 密文")
    default_model: Mapped[str] = mapped_column(String(128), nullable=False, default="gpt-image-2")
    agent_model: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="agent /responses 推理模型；空=仅图片，不参与 agent"
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="小优先")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=1500)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    extra_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="扩展参数")
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("idx_image_gen_providers_priority", "priority", "enabled"),)


class ImageGenHistory(Base):
    """生图历史：直出同步落库；agent 模式前端回调落库（P1）。"""

    __tablename__ = "image_gen_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="业务记录 ID")
    operator_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True, comment="CRM 客户 ID")
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="direct", comment="direct | agent")
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="size/n/quality 等")
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success", comment="success | failed | running(任务化在途)")
    storage_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    public_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    error_code: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    audit_call_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="关联 crm_ai_invocations.call_id")
    image_b64: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="任务化成功时的 base64，供刷新后轮询返回；画廊同步不用")
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_image_gen_history_operator_created", "operator_user_id", "created_at"),
        Index("idx_image_gen_history_customer_created", "customer_id", "created_at"),
    )


class ImageGenPrompt(Base):
    """提示词库：系统内置 / 教练私人 / 共享。可见性：system+shared 全员，private 仅 owner。P2 启用。"""

    __tablename__ = "image_gen_prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="", comment="食谱/问候/科普 ...")
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="system", comment="system | private | shared")
    owner_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("idx_image_gen_prompts_scope", "scope", "enabled"),)
