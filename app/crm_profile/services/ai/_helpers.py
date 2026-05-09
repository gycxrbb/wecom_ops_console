"""Private helper functions for the AI coach pipeline.

Contains classification, normalisation, shortcut logic, safety gates,
text chunking, profile loading, message composition and audit utilities.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, AsyncIterator

from ._types import _log, _sse, _TXT_FENCE_RE, AiStreamEvent, PreparedAiTurn
from ....config import settings
from ....database import SessionLocal
from ...models import CustomerAiProfileNote
from ...schemas.context import ModulePayload
from ..context_builder import validate_field_whitelist, get_module_label
from ..profile_context_cache import get_ai_ready_profile_context, normalize_window_days
from ..prompt_builder import assemble_prompt, assemble_visible_thinking_prompt
from ..safety_gate import build_safety_input, evaluate_ai_answer_safety
from .. import audit


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

def _classify_ai_error(exc: Exception) -> str:
    """Map AI exception to a frontend-friendly error code."""
    msg = str(exc)
    if "超时" in msg:
        return "timeout"
    if "连接失败" in msg or "连接中断" in msg or "断开" in msg:
        return "connection"
    if "服务返回错误" in msg:
        return "upstream"
    if "未配置" in msg or "API KEY" in msg:
        return "not_configured"
    return "unknown"


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    return "".join(str(text or "").strip().lower().split())


# ---------------------------------------------------------------------------
# Shortcut / deterministic answers
# ---------------------------------------------------------------------------

def _try_answer_profile_fact_question(message: str, ctx) -> str | None:
    """Deterministically answer simple fact questions from already loaded profile context."""
    q = _normalize_text(message)
    if not q:
        return None

    basic_card = next((c for c in ctx.cards if c.key == "basic_profile"), None)
    service_card = next((c for c in ctx.cards if c.key == "service_scope"), None)
    basic = basic_card.payload if basic_card and basic_card.payload else {}
    service = service_card.payload if service_card and service_card.payload else {}

    customer_name = str(basic.get("display_name") or "").strip()
    age = basic.get("age")
    gender = str(basic.get("gender") or "").strip()
    crm_status = str(basic.get("crm_status") or "").strip()
    coach_names = str(service.get("current_coach_names") or "").strip()
    group_names = str(service.get("group_names") or "").strip()

    if any(k in q for k in ("叫什么", "名字", "姓名")) and customer_name:
        return f"当前客户叫{customer_name}。"

    if any(k in q for k in ("几岁", "年龄")) and age not in (None, ""):
        return f"当前客户{age}岁。"

    if "性别" in q and gender:
        return f"当前客户是{gender}。"

    if any(k in q for k in ("什么状态", "当前状态", "客户状态")) and crm_status:
        return f"当前客户状态是{crm_status}。"

    if any(k in q for k in ("负责教练", "谁负责", "谁在跟")) and coach_names:
        return f"当前负责教练是{coach_names}。"

    if any(k in q for k in ("所属群", "在哪个群", "什么群")) and group_names:
        return f"当前客户所在群是{group_names}。"

    return None


def _build_shortcut_thinking_text(message: str, ctx) -> str | None:
    q = _normalize_text(message)
    if not q:
        return None

    if any(k in q for k in ("叫什么", "名字", "姓名")):
        return "这是姓名直读题，我会直接查看基础档案里的客户姓名并给出简短回答，不做额外推断。"
    if any(k in q for k in ("几岁", "年龄")):
        return "这是年龄直读题，我会直接依据基础档案中的年龄信息回答，不展开额外分析。"
    if "性别" in q:
        return "这是性别直读题，我会直接依据基础档案里的性别信息回答。"
    if any(k in q for k in ("当前状态", "客户状态", "什么状态")):
        return "这是客户状态直读题，我会直接读取当前档案状态后回答。"
    if any(k in q for k in ("负责教练", "谁负责", "谁在跟")):
        return "这是服务关系直读题，我会直接查看当前负责教练信息后回答。"
    if any(k in q for k in ("所属群", "在哪个群", "什么群")):
        return "这是群组直读题，我会直接查看当前所属群信息后回答。"
    return None


# ---------------------------------------------------------------------------
# Safety gates
# ---------------------------------------------------------------------------

def _check_safety_gates(answer: str, safety_payload: dict) -> tuple[bool, list[str], dict]:
    """Post-prompt structured safety check. Returns (requires_review, notes, safety_result)."""
    safety_input = build_safety_input(safety_payload)
    decision = evaluate_ai_answer_safety(answer, safety_input)
    requires_review = decision.level == "medical_review_required"
    safety_result = {
        "level": decision.level,
        "reason_codes": decision.reason_codes,
        "notes": decision.notes,
    }
    return requires_review, decision.notes, safety_result


# ---------------------------------------------------------------------------
# Text chunking helpers
# ---------------------------------------------------------------------------

def _chunk_text(text: str, size: int = 28) -> list[str]:
    cleaned = str(text or "")
    if not cleaned:
        return []
    return [cleaned[i:i + size] for i in range(0, len(cleaned), size)]


def _ensure_output_contract(answer: str) -> str:
    """Guarantee the answer contains a ```txt code block for customer reply."""
    if not answer or _TXT_FENCE_RE.search(answer):
        return answer
    # Fallback: wrap the last substantial paragraph into a txt code block
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", answer) if p.strip()]
    # Find the best candidate: last paragraph that looks like natural language (not list/code)
    candidate = ""
    for p in reversed(paragraphs):
        # Skip lines that look like headers, lists, or short fragments
        if len(p) > 20 and not p.startswith("#") and not p.startswith("- ") * 3:
            candidate = p
            break
    if not candidate:
        candidate = paragraphs[-1] if paragraphs else answer
    return answer.rstrip() + "\n\n```txt\n" + candidate + "\n```"


async def _emit_text_chunks(text: str, *, size: int = 28, delay: float = 0.03) -> AsyncIterator[str]:
    for chunk in _chunk_text(text, size=size):
        yield chunk
        await asyncio.sleep(delay)


# ---------------------------------------------------------------------------
# Debug / diagnostics
# ---------------------------------------------------------------------------

async def _debug_ai_stream_test() -> AsyncIterator[AiStreamEvent]:
    """Call AI with stream=True and log each chunk's arrival time. For diagnostics only."""
    from ....clients.ai_chat_client import chat_completion_stream
    import time

    messages = [{"role": "user", "content": "从1数到20，每个数字占一行。"}]
    t0 = time.time()
    yield AiStreamEvent(event="meta", data={"test": "stream-debug-start"})
    chunk_idx = 0
    async for chunk in chat_completion_stream(messages, temperature=0.3, max_tokens=256):
        if chunk.delta:
            chunk_idx += 1
            elapsed = round(time.time() - t0, 3)
            _sse.info("[SSE-DEBUG] chunk #%d at %.3fs: %r", chunk_idx, elapsed, chunk.delta[:40])
            yield AiStreamEvent(event="delta", data={"delta": chunk.delta, "_elapsed": elapsed, "_idx": chunk_idx})
        if chunk.usage:
            yield AiStreamEvent(event="done", data={
                "total_chunks": chunk_idx,
                "total_seconds": round(time.time() - t0, 2),
                "usage": chunk.usage,
            })


# ---------------------------------------------------------------------------
# Attachment binding
# ---------------------------------------------------------------------------

def _bind_attachments_if_any(session_id: str, user_message_id: str,
                             attachment_ids: list[str] | None):
    """Back-fill session_id/message_id on attachment records (called from executor)."""
    if not attachment_ids:
        return
    try:
        from ..ai_attachment import bind_attachments_to_message
        with SessionLocal() as db:
            bind_attachments_to_message(db, list(attachment_ids), session_id, user_message_id)
    except Exception:
        _log.exception("Failed to bind attachments to message %s", user_message_id)


# ---------------------------------------------------------------------------
# Profile helpers
# ---------------------------------------------------------------------------

def _extract_customer_name(ctx: Any) -> str:
    basic_card = next((c for c in ctx.cards if c.key == "basic_profile"), None)
    if basic_card and basic_card.payload:
        return str(basic_card.payload.get("display_name") or "").strip()
    return ""


def _extract_rag_profile_signals(customer_id: int, window_days: int) -> dict:
    """Extract lightweight RAG boost/filter signals from profile cache (no heavy DB queries)."""
    try:
        result = get_ai_ready_profile_context(customer_id, window_days=window_days)
        if not result.ctx or not result.ctx.cards:
            return {}
        signals: dict = {"customer_goals": [], "safety_risks": [], "service_stage": "", "has_contraindications": False}
        for card in result.ctx.cards:
            if not card.payload:
                continue
            if card.key == "goals_preferences":
                goals = card.payload.get("primary_goals") or card.payload.get("goals") or []
                if isinstance(goals, list):
                    signals["customer_goals"] = [str(g) for g in goals[:5]]
            elif card.key == "safety_profile":
                allergies = card.payload.get("allergies") or ""
                conditions = card.payload.get("health_condition_summary") or ""
                if allergies or conditions:
                    signals["safety_risks"] = ["medical_sensitive"]
                prescriptions = card.payload.get("prescription_summary") or ""
                if prescriptions:
                    signals["has_contraindications"] = True
            elif card.key == "ai_decision_labels":
                stage = card.payload.get("service_stage") or card.payload.get("phase") or ""
                if stage:
                    signals["service_stage"] = str(stage)
            elif card.key == "service_issues":
                issues = card.payload.get("active_issues") or card.payload.get("issues") or []
                if isinstance(issues, list) and issues:
                    signals["service_stage"] = "intervention"
        return signals
    except Exception:
        _log.debug("Failed to extract RAG profile signals for customer %s", customer_id, exc_info=True)
        return {}


def _load_profile_note(customer_id: int) -> CustomerAiProfileNote | None:
    db = SessionLocal()
    try:
        return db.query(CustomerAiProfileNote).filter_by(crm_customer_id=customer_id).first()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Message composition
# ---------------------------------------------------------------------------

def _compose_ai_messages(assembly, session_id: str, reuse_session: bool,
                        quoted_content: str | None = None) -> list[dict[str, Any]]:
    ai_messages: list[dict[str, Any]] = []
    if assembly.messages:
        ai_messages.extend(msg for msg in assembly.messages[:-1] if msg.get("role") == "system")

    if reuse_session:
        history = audit.load_session_messages(session_id, limit=10)
        for h in history:
            ai_messages.append({"role": h["role"], "content": h["content"]})

    # Inject quoted context for follow-up questions
    if quoted_content:
        ai_messages.append({
            "role": "user",
            "content": f"[追问引用]\n以下是之前AI教练的回复：\n{quoted_content}\n\n基于以上内容，我的追问是：",
        })

    user_msg = assembly.messages[-1] if assembly.messages else {"role": "user", "content": ""}
    ai_messages.append(user_msg)
    return ai_messages


# ---------------------------------------------------------------------------
# Session audit helpers
# ---------------------------------------------------------------------------

def _ensure_session_written(
    session_id: str,
    *,
    local_user_id: int,
    customer_id: int,
    crm_admin_id: int | None,
    entry_scene: str,
    scene_key: str = "",
    output_style: str = "",
    prompt_version: str = "",
    prompt_hash: str = "",
) -> None:
    if not audit.session_exists(session_id):
        audit.write_session(
            session_id, local_user_id, customer_id, crm_admin_id, entry_scene,
            scene_key=scene_key, output_style=output_style,
            prompt_version=prompt_version, prompt_hash=prompt_hash,
        )


def _profile_cache_unready_payload(exc) -> dict[str, Any]:
    result = exc.result
    return {
        "message": str(exc), "cache_status": result.status, "cache_key": result.cache_key,
        "health_window_days": result.health_window_days, "source": result.source,
    }
