"""客户资料脱敏摘要 —— agent 的 get_customer_profile tool 的数据源。

复用 crm_profile 的 profile_context_cache + context_builder。该链路从 SQL 白名单
(basic_profile.py 只 SELECT 非敏感列)到 context_builder._PROHIBITED_KEYS 双重过滤，
已排除手机号/身份证/地址/openid/unionid 等 PII，输出可直接拼进生图 prompt。
"""
from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


class ProfileNotReady(Exception):
    """客户档案缓存尚未预热（打开客户页时会自动预热，稍后重试即可）。"""


def build_desensitized_profile(customer_id: int, window_days: int = 7) -> dict[str, Any]:
    """返回 {customer_id, context_text}。context_text 是中文脱敏摘要，适合直接喂生图 prompt。"""
    from app.crm_profile.services.context_builder import build_context_text
    from app.crm_profile.services.profile_context_cache import (
        ProfileCacheNotReady,
        get_ai_ready_profile_context,
    )

    try:
        result = get_ai_ready_profile_context(customer_id, window_days=window_days)
    except ProfileCacheNotReady as exc:
        raise ProfileNotReady(str(exc) or "客户档案缓存预热中，请稍后重试") from exc

    ctx = result.ctx
    return {
        "customer_id": customer_id,
        "context_text": build_context_text(ctx.cards),
    }
