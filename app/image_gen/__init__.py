"""图片生成模块：gpt_image_playground 集成 + 多供应商 failover + 生图历史 + 审计。

模块刻意与 ai_visual 解耦（独立三张表、独立供应商配置、独立历史链路），
仅复用项目级基础设施：Fernet 加密、七牛 storage_facade、invocation_audit。
"""
from . import models  # noqa: F401  — 在 Base.metadata 上注册 ORM 表

from .router import router

__all__ = ["router"]
