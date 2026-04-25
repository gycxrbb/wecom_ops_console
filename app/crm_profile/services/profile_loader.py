"""Orchestrate loading of all profile modules for a customer."""
from __future__ import annotations

import logging
from datetime import datetime

from ...clients.crm_db import get_connection, return_connection
from ...config import settings
from ..schemas.context import ModulePayload, CustomerProfileContextV1, SourceStatusEntry
from .context_builder import estimate_tokens, resolve_context_plan, validate_field_whitelist
from .modules import basic_profile, safety_profile, goals_preferences
from .modules import health_summary, body_comp, points_engagement, service_scope

_log = logging.getLogger(__name__)

_LOADERS = [
    basic_profile,
    safety_profile,
    goals_preferences,
    health_summary,
    body_comp,
    points_engagement,
    service_scope,
]


def load_profile(customer_id: int) -> CustomerProfileContextV1:
    """Load all P0 modules and build the profile context."""
    conn = get_connection()
    try:
        cards: list[ModulePayload] = []
        source_status: list[SourceStatusEntry] = []
        for mod in _LOADERS:
            try:
                card = mod.load(conn, customer_id)
                cards.append(card)
                if card.warnings:
                    for w in card.warnings:
                        source_status.append(SourceStatusEntry(
                            module=card.key,
                            status="fallback_latest_archived_or_unknown" if "归档" in w else "ok",
                            warning=w,
                        ))
            except Exception:
                _log.exception("Module %s failed for customer %s", mod.__name__, customer_id)
                cards.append(ModulePayload(
                    key=getattr(mod, "MODULE_KEY", mod.__name__),
                    status="error",
                    payload={},
                    warnings=["模块加载异常"],
                ))
                source_status.append(SourceStatusEntry(
                    module=getattr(mod, "MODULE_KEY", mod.__name__),
                    status="unavailable",
                    warning="模块加载异常",
                ))

        # Build available_actions conditionally
        actions = ["view_profile"]
        ai_enabled = settings.ai_coach_enabled or (bool(settings.ai_api_key) and settings.crm_profile_enabled)
        safety_card = next((c for c in cards if c.key == "safety_profile"), None)
        ai_chat_enabled = False
        ai_chat_reason: str | None = None

        if not ai_enabled:
            ai_chat_reason = "系统尚未启用 AI 教练助手"
        elif not safety_card or safety_card.status not in ("ok", "partial"):
            ai_chat_reason = "当前客户缺少安全档案，暂时无法发起 AI 对话"
        else:
            ai_chat_enabled = True
            actions.append("ai_chat")

        # Fill estimated_tokens per module and compute build plan
        total_tokens = 0
        for card in cards:
            if card.status == "ok":
                card_chars = sum(len(str(v)) for v in card.payload.values() if v is not None and not isinstance(v, (list, dict)))
                card.estimated_tokens = card_chars // 4
                total_tokens += card.estimated_tokens

        build_plan = resolve_context_plan()
        violations = validate_field_whitelist(cards)
        if violations:
            _log.warning("Field whitelist violations for customer %s: %s", customer_id, violations)

        return CustomerProfileContextV1(
            customer_id=customer_id,
            generated_at=datetime.now(),
            cards=cards,
            source_status=source_status,
            available_actions=actions,
            ai_chat_enabled=ai_chat_enabled,
            ai_chat_reason=ai_chat_reason,
            build_plan=build_plan,
        )
    finally:
        return_connection(conn)
