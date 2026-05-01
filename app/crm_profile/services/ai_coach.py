"""AI Coach service — prompt assembly, safety gates, AI call, audit, streaming."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal

from ...clients.ai_chat_client import chat_completion, chat_completion_stream
from ...config import settings
from ...database import SessionLocal
from ...sse_debug_log import get_sse_logger
from ..models import CustomerAiProfileNote
from ..schemas.context import ModulePayload
from . import audit
from .context_builder import build_context_text, validate_field_whitelist, get_module_label
from .profile_context_cache import ProfileCacheNotReady, get_ai_ready_profile_context, normalize_window_days
from .prompt_builder import assemble_prompt, assemble_visible_thinking_prompt
from .safety_gate import build_safety_input, evaluate_ai_answer_safety

_log = logging.getLogger(__name__)
_sse = get_sse_logger()


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


def _normalize_text(text: str) -> str:
    return "".join(str(text or "").strip().lower().split())


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


def _chunk_text(text: str, size: int = 28) -> list[str]:
    cleaned = str(text or "")
    if not cleaned:
        return []
    return [cleaned[i:i + size] for i in range(0, len(cleaned), size)]


_TXT_FENCE_RE = re.compile(r"```txt\b")


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


async def _debug_ai_stream_test() -> AsyncIterator[AiStreamEvent]:
    """Call AI with stream=True and log each chunk's arrival time. For diagnostics only."""
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


def _load_profile_note(customer_id: int) -> CustomerAiProfileNote | None:
    db = SessionLocal()
    try:
        return db.query(CustomerAiProfileNote).filter_by(crm_customer_id=customer_id).first()
    finally:
        db.close()


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


@dataclass
class PreparedAiTurn:
    session_id: str
    reuse_session: bool
    ctx: Any
    safety_card: ModulePayload
    used_modules: list[str]
    missing_notes: list[str]
    assembly: Any
    ai_messages: list[dict[str, Any]]
    shortcut_answer: str | None = None
    shortcut_thinking: str | None = None
    rag_context_text: str = ""
    rag_sources: list[dict] = field(default_factory=list)
    rag_recommended_assets: list[dict] = field(default_factory=list)
    quoted_content: str | None = None


@dataclass
class AiChatResult:
    session_id: str
    message_id: str
    answer: str
    safety_notes: list[str] = field(default_factory=list)
    missing_data_notes: list[str] = field(default_factory=list)
    used_modules: list[str] = field(default_factory=list)
    token_usage: dict = field(default_factory=dict)
    requires_medical_review: bool = False
    prompt_version: str = ""
    scene_key: str = ""


@dataclass
class AiStreamEvent:
    event: Literal["meta", "delta", "done", "error", "loading", "rag", "analyzing"]
    data: dict[str, Any] = field(default_factory=dict)


def _profile_cache_unready_payload(exc: ProfileCacheNotReady) -> dict[str, Any]:
    result = exc.result
    return {
        "message": str(exc), "cache_status": result.status, "cache_key": result.cache_key,
        "health_window_days": result.health_window_days, "source": result.source,
    }


# --- Prepare cache: avoid duplicate DB queries when answer + thinking run concurrently ---

_PREPARE_CACHE: dict[tuple, tuple[float, PreparedAiTurn]] = {}
_PREPARE_TTL = 15.0


def _prepare_cache_key(customer_id: int, message: str, session_id: str | None,
                       scene_key: str, output_style: str, health_window_days: int,
                       attachment_ids: tuple[str, ...] | None = None,
                       quoted_content_hash: str = "") -> tuple:
    return (customer_id, message, session_id or "", scene_key, output_style, health_window_days, attachment_ids or (), quoted_content_hash)


async def _prepare_ai_turn_cached(
    customer_id: int,
    message: str,
    *,
    session_id: str | None,
    scene_key: str,
    output_style: str,
    health_window_days: int = 7,
    prompt_mode: Literal["answer", "thinking"],
    selected_expansions: list[str] | None = None,
    attachment_ids: tuple[str, ...] | None = None,
    quoted_content: str | None = None,
) -> PreparedAiTurn:
    """Prepare with turn-level cache. First call writes, second call reads within TTL."""
    window_days = normalize_window_days(health_window_days)
    qch = hashlib.sha256((quoted_content or "").encode()).hexdigest()[:8] if quoted_content else ""
    key = _prepare_cache_key(customer_id, message, session_id, scene_key, output_style, window_days, attachment_ids, qch)
    now = time.time()
    hit = _PREPARE_CACHE.get(key)
    if hit and now - hit[0] < _PREPARE_TTL:
        cached = hit[1]
        _sse.info("[SSE-TIMING] prepare cache HIT at %.3fs", now)
        # Re-assemble prompt for the specific mode, reuse context
        if prompt_mode == "thinking":
            assembly = assemble_visible_thinking_prompt(
                scene_key=scene_key,
                context_text=build_context_text(cached.ctx.cards, selected_expansions=selected_expansions),
                customer_name=_extract_customer_name(cached.ctx),
                profile_note=cached.assembly,  # not used, pass None equivalent
                user_message=message,
            )
        else:
            assembly = assemble_prompt(
                scene_key=scene_key,
                context_text=build_context_text(cached.ctx.cards, selected_expansions=selected_expansions),
                customer_name=_extract_customer_name(cached.ctx),
                profile_note=None,
                user_message=message,
                output_style=output_style,
            )
        ai_messages = _compose_ai_messages(assembly, cached.session_id, cached.reuse_session, quoted_content=quoted_content)
        return PreparedAiTurn(
            session_id=cached.session_id,
            reuse_session=cached.reuse_session,
            ctx=cached.ctx,
            safety_card=cached.safety_card,
            used_modules=cached.used_modules,
            missing_notes=cached.missing_notes,
            assembly=assembly,
            ai_messages=ai_messages,
            shortcut_answer=cached.shortcut_answer,
            shortcut_thinking=cached.shortcut_thinking,
            quoted_content=quoted_content,
        )

    prepared = await _prepare_ai_turn_async(
        customer_id, message,
        session_id=session_id, scene_key=scene_key,
        output_style=output_style, health_window_days=window_days, prompt_mode=prompt_mode,
        selected_expansions=selected_expansions,
        quoted_content=quoted_content,
    )
    _PREPARE_CACHE[key] = (now, prepared)
    return prepared


def _extract_customer_name(ctx: Any) -> str:
    basic_card = next((c for c in ctx.cards if c.key == "basic_profile"), None)
    if basic_card and basic_card.payload:
        return str(basic_card.payload.get("display_name") or "").strip()
    return ""


async def _prepare_ai_turn_async(
    customer_id: int,
    message: str,
    *,
    session_id: str | None,
    scene_key: str,
    output_style: str,
    health_window_days: int = 7,
    prompt_mode: Literal["answer", "thinking"],
    selected_expansions: list[str] | None = None,
    quoted_content: str | None = None,
) -> PreparedAiTurn:
    """Async wrapper: runs RAG retrieval (async) then _prepare_ai_turn (sync via executor)."""
    rag_context_text = ""
    rag_sources: list[dict] = []
    rag_recommended_assets: list[dict] = []
    if settings.rag_enabled:
        try:
            from ...rag.retriever import retrieve_rag_context as _rag_retrieve
            rag_bundle = await _rag_retrieve(
                customer_id=customer_id, message=message,
                scene_key=scene_key, output_style=output_style,
                profile_context=None,
            )
            if rag_bundle and rag_bundle.rag_status == "ok":
                rag_context_text = rag_bundle.context_text
                rag_sources = [s.model_dump() for s in rag_bundle.sources]
                rag_recommended_assets = [a.model_dump() for a in rag_bundle.recommended_assets]
        except Exception:
            _log.exception("RAG retrieval failed for customer %s", customer_id)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _prepare_ai_turn(
            customer_id, message,
            session_id=session_id, scene_key=scene_key,
            output_style=output_style, health_window_days=health_window_days, prompt_mode=prompt_mode,
            selected_expansions=selected_expansions,
            rag_context_text=rag_context_text,
            rag_sources=rag_sources,
            rag_recommended_assets=rag_recommended_assets,
            quoted_content=quoted_content,
        ),
    )


def _prepare_ai_turn(
    customer_id: int,
    message: str,
    *,
    session_id: str | None,
    scene_key: str,
    output_style: str,
    health_window_days: int = 7,
    prompt_mode: Literal["answer", "thinking"],
    selected_expansions: list[str] | None = None,
    rag_context_text: str = "",
    rag_sources: list[dict] | None = None,
    rag_recommended_assets: list[dict] | None = None,
    quoted_content: str | None = None,
) -> PreparedAiTurn:
    reuse_session = bool(session_id) and audit.session_exists(session_id)
    if not session_id:
        session_id = str(uuid.uuid4())

    window_days = normalize_window_days(health_window_days)
    profile_result = get_ai_ready_profile_context(customer_id, window_days=window_days)
    ctx = profile_result.ctx
    _sse.info(
        "[SSE-TIMING] profile cache ready source=%s key=%s window=%s",
        profile_result.source,
        profile_result.cache_key,
        window_days,
    )

    safety_card = next((c for c in ctx.cards if c.key == "safety_profile"), None)
    if not safety_card or safety_card.status not in ("ok", "partial"):
        audit.write_guardrail_event(session_id, "prompt_safety_missing", "safety_profile not loaded")
        raise RuntimeError("安全档案未加载，无法使用 AI 助手")

    violations = validate_field_whitelist(ctx.cards)
    if violations:
        for violation in violations:
            audit.write_guardrail_event(session_id, "prompt_field_blocked", violation)

    context_text = build_context_text(ctx.cards, selected_expansions=selected_expansions)
    used_modules = [c.key for c in ctx.cards if c.status in ("ok", "partial")]
    basic_card = next((c for c in ctx.cards if c.key == "basic_profile"), None)
    customer_name = ""
    if basic_card and basic_card.payload:
        customer_name = str(basic_card.payload.get("display_name") or "").strip()

    missing_notes: list[str] = []
    for card in ctx.cards:
        if card.status == "empty":
            missing_notes.append(f"{get_module_label(card.key)} 暂无数据")
        elif card.warnings:
            missing_notes.extend(card.warnings)

    profile_note = _load_profile_note(customer_id)

    # RAG context retrieval (optional, degrades gracefully)
    # Note: actual RAG retrieval is done in _prepare_ai_turn_async (async context)
    # and passed here via rag_context_text parameter.

    if prompt_mode == "thinking":
        assembly = assemble_visible_thinking_prompt(
            scene_key=scene_key,
            context_text=context_text,
            customer_name=customer_name,
            profile_note=profile_note,
            user_message=message,
            rag_context_text=rag_context_text,
        )
    else:
        assembly = assemble_prompt(
            scene_key=scene_key,
            context_text=context_text,
            customer_name=customer_name,
            profile_note=profile_note,
            user_message=message,
            output_style=output_style,
            rag_context_text=rag_context_text,
        )

    return PreparedAiTurn(
        session_id=session_id,
        reuse_session=reuse_session,
        ctx=ctx,
        safety_card=safety_card,
        used_modules=used_modules,
        missing_notes=missing_notes,
        assembly=assembly,
        ai_messages=_compose_ai_messages(assembly, session_id, reuse_session, quoted_content=quoted_content),
        shortcut_answer=_try_answer_profile_fact_question(message, ctx),
        shortcut_thinking=_build_shortcut_thinking_text(message, ctx),
        rag_context_text=rag_context_text,
        rag_sources=rag_sources or [],
        rag_recommended_assets=rag_recommended_assets or [],
        quoted_content=quoted_content,
    )


async def ask_ai_coach(
    customer_id: int,
    message: str,
    *,
    session_id: str | None = None,
    local_user_id: int = 0,
    crm_admin_id: int | None = None,
    scene_key: str = "qa_support",
    entry_scene: str = "customer_profile",
    selected_expansions: list[str] | None = None,
    output_style: str = "coach_brief",
    health_window_days: int = 7,
    attachment_ids: list[str] | None = None,
    quoted_message_id: str | None = None,
) -> AiChatResult:
    """Non-streaming fallback entry for AI coach."""
    effective_message = message
    if attachment_ids:
        effective_message = await _resolve_attachment_descriptions(customer_id, attachment_ids, message)

    quoted_content: str | None = None
    if quoted_message_id:
        qmsg = audit.find_message_by_id(quoted_message_id)
        if qmsg and qmsg.role == "assistant":
            quoted_content = qmsg.content

    prepared = await _prepare_ai_turn_async(
        customer_id,
        effective_message,
        session_id=session_id,
        scene_key=scene_key,
        output_style=output_style,
        health_window_days=health_window_days,
        prompt_mode="answer",
        selected_expansions=selected_expansions,
        quoted_content=quoted_content,
    )
    user_message_id = str(uuid.uuid4())

    _ensure_session_written(
        prepared.session_id,
        local_user_id=local_user_id,
        customer_id=customer_id,
        crm_admin_id=crm_admin_id,
        entry_scene=entry_scene,
        scene_key=prepared.assembly.scene_key,
        output_style=output_style,
        prompt_version=prepared.assembly.prompt_version,
        prompt_hash=prepared.assembly.prompt_hash,
    )
    audit.write_message(prepared.session_id, user_message_id, "user", message, quoted_message_id=quoted_message_id)
    audit.write_context_snapshot(
        prepared.session_id, build_context_text(prepared.ctx.cards, selected_expansions=selected_expansions), prepared.used_modules,
        prompt_version=prepared.assembly.prompt_version,
        prompt_hash=prepared.assembly.prompt_hash,
        scene_key=prepared.assembly.scene_key,
        output_style=output_style,
        selected_expansions=selected_expansions,
    )

    if prepared.shortcut_answer:
        assistant_message_id = str(uuid.uuid4())
        audit.write_message(
            prepared.session_id, assistant_message_id, "assistant", prepared.shortcut_answer,
            model="profile_fact_shortcut",
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0,
            requires_medical_review=False,
        )
        return AiChatResult(
            session_id=prepared.session_id,
            message_id=assistant_message_id,
            answer=prepared.shortcut_answer,
            safety_notes=[],
            missing_data_notes=[],
            used_modules=prepared.used_modules,
            token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            requires_medical_review=False,
            prompt_version=prepared.assembly.prompt_version,
            scene_key=prepared.assembly.scene_key,
        )

    t0 = time.time()
    answer, usage = await chat_completion(prepared.ai_messages, temperature=0.7, max_tokens=15000)
    latency_ms = int((time.time() - t0) * 1000)
    requires_review, safety_notes, safety_result = _check_safety_gates(answer, prepared.safety_card.payload or {})

    if requires_review:
        for note in safety_notes:
            audit.write_guardrail_event(
                prepared.session_id,
                "output_allergy_hit" if "过敏" in note else "output_medical_term",
                note,
            )

    assistant_message_id = str(uuid.uuid4())
    answer = _ensure_output_contract(answer)
    audit.write_message(
        prepared.session_id, assistant_message_id, "assistant", answer,
        model=settings.ai_model,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        latency_ms=latency_ms,
        requires_medical_review=requires_review,
        safety_result=safety_result,
    )

    return AiChatResult(
        session_id=prepared.session_id,
        message_id=assistant_message_id,
        answer=answer,
        safety_notes=safety_notes,
        missing_data_notes=prepared.missing_notes,
        used_modules=prepared.used_modules,
        token_usage={
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
        requires_medical_review=requires_review,
        prompt_version=prepared.assembly.prompt_version,
        scene_key=prepared.assembly.scene_key,
    )


async def stream_ai_coach_answer(
    customer_id: int,
    message: str,
    *,
    session_id: str | None = None,
    local_user_id: int = 0,
    crm_admin_id: int | None = None,
    scene_key: str = "qa_support",
    entry_scene: str = "customer_profile",
    output_style: str = "coach_brief",
    selected_expansions: list[str] | None = None,
    health_window_days: int = 7,
    attachment_ids: list[str] | None = None,
    quoted_message_id: str | None = None,
    regenerated_from_message_id: str | None = None,
) -> AsyncIterator[AiStreamEvent]:
    t_start = time.time()
    _sse.info("[SSE-TIMING] === answer-stream request arrived ===")

    # --- Stage 1: Vision analysis for attachments ---
    effective_message = message
    att_tuple = tuple(attachment_ids) if attachment_ids else None
    if attachment_ids:
        yield AiStreamEvent(event="analyzing", data={"status": "analyzing_attachments"})
        effective_message = await _resolve_attachment_descriptions(customer_id, attachment_ids, message)

    # Resolve quoted content for follow-up
    quoted_content: str | None = None
    if quoted_message_id:
        qmsg = audit.find_message_by_id(quoted_message_id)
        if qmsg and qmsg.role == "assistant":
            quoted_content = qmsg.content

    yield AiStreamEvent(event="loading", data={"stage": "prepare"})

    _sse.info("[SSE-TIMING] prepare start at %.3fs", time.time() - t_start)
    try:
        prepared = await _prepare_ai_turn_cached(
            customer_id,
            effective_message,
            session_id=session_id,
            scene_key=scene_key,
            output_style=output_style,
            health_window_days=health_window_days,
            prompt_mode="answer",
            selected_expansions=selected_expansions,
            attachment_ids=att_tuple,
            quoted_content=quoted_content,
        )
    except ProfileCacheNotReady as exc:
        _sse.info("[SSE-TIMING] answer profile cache unready key=%s", exc.result.cache_key)
        yield AiStreamEvent(event="error", data=_profile_cache_unready_payload(exc))
        return
    _sse.info("[SSE-TIMING] prepare done at %.3fs", time.time() - t_start)

    assistant_message_id = str(uuid.uuid4())
    user_message_id = str(uuid.uuid4())

    _sse.info("[SSE-TIMING] yield meta at %.3fs", time.time() - t_start)
    yield AiStreamEvent(
        event="meta",
        data={
            "session_id": prepared.session_id,
            "message_id": assistant_message_id,
            "prompt_version": prepared.assembly.prompt_version,
            "scene_key": prepared.assembly.scene_key,
            "used_modules": prepared.used_modules,
        },
    )
    _sse.info("[SSE-TIMING] meta yielded, firing background audit writes at %.3fs", time.time() - t_start)

    # RAG sources event (optional)
    if prepared.rag_sources or prepared.rag_recommended_assets:
        yield AiStreamEvent(event="rag", data={
            "rag_status": "ok",
            "sources": prepared.rag_sources,
            "recommended_assets": prepared.rag_recommended_assets,
        })

    yield AiStreamEvent(event="loading", data={"stage": "model_call"})

    async def _background_audit():
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: (
                _ensure_session_written(
                    prepared.session_id,
                    local_user_id=local_user_id,
                    customer_id=customer_id,
                    crm_admin_id=crm_admin_id,
                    entry_scene=entry_scene,
                    scene_key=prepared.assembly.scene_key,
                    output_style=output_style,
                    prompt_version=prepared.assembly.prompt_version,
                    prompt_hash=prepared.assembly.prompt_hash,
                ),
                audit.write_message(prepared.session_id, user_message_id, "user", message, quoted_message_id=quoted_message_id),
                audit.write_context_snapshot(
                    prepared.session_id, build_context_text(prepared.ctx.cards, selected_expansions=selected_expansions), prepared.used_modules,
                    prompt_version=prepared.assembly.prompt_version,
                    prompt_hash=prepared.assembly.prompt_hash,
                    scene_key=prepared.assembly.scene_key,
                    output_style=output_style,
                    selected_expansions=selected_expansions,
                ),
            ),
        )

    _audit_task = asyncio.create_task(_background_audit())

    if prepared.shortcut_answer:
        await _audit_task
        async for chunk in _emit_text_chunks(prepared.shortcut_answer, size=14, delay=0.035):
            yield AiStreamEvent(event="delta", data={"delta": chunk})
        audit.write_message(
            prepared.session_id, assistant_message_id, "assistant", prepared.shortcut_answer,
            model="profile_fact_shortcut",
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0,
            requires_medical_review=False,
        )
        yield AiStreamEvent(
            event="done",
            data={
                "session_id": prepared.session_id,
                "message_id": assistant_message_id,
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "requires_medical_review": False,
                "safety_notes": [],
                "missing_data_notes": [],
            },
        )
        return

    collected_chunks: list[str] = []
    usage: dict[str, int] = {}
    t0 = time.time()
    try:
        chunk_count = 0
        _sse.info("[SSE-TIMING] AI API stream starts at %.3fs (audit writes running in background)", time.time() - t_start)
        async for chunk in chat_completion_stream(prepared.ai_messages, temperature=0.7, max_tokens=15000):
            if chunk.delta:
                collected_chunks.append(chunk.delta)
                chunk_count += 1
                _sse.info("[SSE-TIMING] AI chunk #%d arrived at %.3fs, delta=%d chars",
                          chunk_count, time.time() - t_start, len(chunk.delta))
                yield AiStreamEvent(event="delta", data={"delta": chunk.delta})
                await asyncio.sleep(0)
            if chunk.usage:
                usage = chunk.usage
        _sse.info("[SSE-TIMING] AI stream done, %d chunks, total %.3fs", chunk_count, time.time() - t_start)

        answer_text = "".join(collected_chunks).strip()
        answer_text = _ensure_output_contract(answer_text)
        latency_ms = int((time.time() - t0) * 1000)
        requires_review, safety_notes, safety_result = _check_safety_gates(answer_text, prepared.safety_card.payload or {})

        if requires_review:
            for code in safety_result.get("reason_codes", []):
                audit.write_guardrail_event(
                    prepared.session_id,
                    code,
                    "; ".join(safety_result.get("notes", [])),
                )

        await _audit_task
        _sse.info("[SSE-TIMING] background audit writes confirmed done at %.3fs", time.time() - t_start)
        audit.write_message(
            prepared.session_id, assistant_message_id, "assistant", answer_text,
            model=settings.ai_model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
            requires_medical_review=requires_review,
            safety_result=safety_result,
            regenerated_from_message_id=regenerated_from_message_id,
        )
        # Extract cache metrics from provider usage response
        cached_tokens = usage.get("prompt_cache_hit_tokens") or 0
        if not cached_tokens:
            details = usage.get("prompt_tokens_details") or {}
            cached_tokens = details.get("cached_tokens", 0)

        yield AiStreamEvent(
            event="done",
            data={
                "session_id": prepared.session_id,
                "message_id": assistant_message_id,
                "token_usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                    "cached_tokens": cached_tokens,
                },
                "requires_medical_review": requires_review,
                "safety_notes": safety_notes,
                "missing_data_notes": prepared.missing_notes,
                "safety_result": safety_result,
            },
        )
    except Exception as exc:
        _log.error("Answer stream failed: %s", exc, exc_info=True)
        yield AiStreamEvent(event="error", data={
            "message": str(exc) or "AI 服务异常",
            "code": _classify_ai_error(exc),
        })


async def stream_ai_coach_thinking(
    customer_id: int,
    message: str,
    *,
    session_id: str | None = None,
    scene_key: str = "qa_support",
    output_style: str = "coach_brief",
    selected_expansions: list[str] | None = None,
    health_window_days: int = 7,
    attachment_ids: list[str] | None = None,
) -> AsyncIterator[AiStreamEvent]:
    t_start = time.time()
    _sse.info("[SSE-TIMING] === thinking-stream request arrived (provider=%s) ===", settings.ai_provider)

    # Resolve attachment descriptions (reuses cached Vision results)
    effective_message = message
    att_tuple = tuple(attachment_ids) if attachment_ids else None
    if attachment_ids:
        effective_message = await _resolve_attachment_descriptions(customer_id, attachment_ids, message)

    yield AiStreamEvent(event="loading", data={"stage": "prepare"})

    # Cached prepare path shared by all providers.
    _sse.info("[SSE-TIMING] thinking prepare start at %.3fs", time.time() - t_start)
    try:
        prepared = await _prepare_ai_turn_cached(
            customer_id,
            effective_message,
            session_id=session_id,
            scene_key=scene_key,
            output_style=output_style,
            health_window_days=health_window_days,
            prompt_mode="thinking",
            selected_expansions=selected_expansions,
            attachment_ids=att_tuple,
        )
    except ProfileCacheNotReady as exc:
        _sse.info("[SSE-TIMING] thinking profile cache unready key=%s", exc.result.cache_key)
        yield AiStreamEvent(event="error", data=_profile_cache_unready_payload(exc))
        return
    _sse.info("[SSE-TIMING] thinking prepare done at %.3fs", time.time() - t_start)

    yield AiStreamEvent(
        event="meta",
        data={
            "session_id": prepared.session_id,
            "prompt_version": prepared.assembly.prompt_version,
            "scene_key": prepared.assembly.scene_key,
        },
    )

    shortcut_thinking = prepared.shortcut_thinking
    if shortcut_thinking:
        async for chunk in _emit_text_chunks(shortcut_thinking, size=14, delay=0.035):
            yield AiStreamEvent(event="delta", data={"delta": chunk})
        yield AiStreamEvent(event="done", data={"session_id": prepared.session_id})
        return

    yield AiStreamEvent(event="loading", data={"stage": "model_call"})

    try:
        _sse.info("[SSE-TIMING] thinking AI stream starts at %.3fs", time.time() - t_start)
        chunk_count = 0
        async for chunk in chat_completion_stream(prepared.ai_messages, temperature=0.4, max_tokens=4096):
            if chunk.delta:
                chunk_count += 1
                _sse.info("[SSE-TIMING] thinking chunk #%d at %.3fs", chunk_count, time.time() - t_start)
                yield AiStreamEvent(event="delta", data={"delta": chunk.delta})
                await asyncio.sleep(0)
        _sse.info("[SSE-TIMING] thinking AI done, %d chunks, %.3fs", chunk_count, time.time() - t_start)

        yield AiStreamEvent(event="done", data={"session_id": prepared.session_id})
    except Exception as exc:
        _log.error("Thinking stream failed: %s", exc, exc_info=True)
        yield AiStreamEvent(event="error", data={
            "message": str(exc) or "AI 思考流异常",
            "code": _classify_ai_error(exc),
        })


async def _resolve_attachment_descriptions(
    customer_id: int,
    attachment_ids: list[str],
    original_message: str,
) -> str:
    """Load attachments, run Vision analysis if needed, build enhanced user message."""
    from .ai_attachment import load_attachments
    from .vision_analyzer import analyze_attachment, build_user_message_with_attachments

    with SessionLocal() as db:
        attachments = load_attachments(db, attachment_ids, customer_id)

    if not attachments:
        return original_message

    descriptions: list[tuple[str, str]] = []
    for att in attachments:
        desc = await analyze_attachment(att)
        descriptions.append((att.original_filename, desc))

    return build_user_message_with_attachments(original_message, descriptions)


async def regenerate_ai_coach_answer(
    customer_id: int,
    original_message_id: str,
    *,
    local_user_id: int = 0,
    crm_admin_id: int | None = None,
) -> AsyncIterator[AiStreamEvent]:
    """Regenerate an AI answer for the same question, preserving the old answer."""
    ai_msg = audit.find_message_by_id(original_message_id)
    if not ai_msg or ai_msg.role != "assistant":
        yield AiStreamEvent(event="error", data={"message": "消息不存在或不是 AI 回复", "code": "not_found"})
        return

    session = audit.find_session_by_id(ai_msg.session_id)
    if not session or session.crm_customer_id != customer_id:
        yield AiStreamEvent(event="error", data={"message": "消息不属于该客户", "code": "not_found"})
        return

    user_msg = audit.find_preceding_user_message(ai_msg.session_id, original_message_id)
    if not user_msg:
        yield AiStreamEvent(event="error", data={"message": "找不到原始教练问题", "code": "not_found"})
        return

    async for event in stream_ai_coach_answer(
        customer_id,
        user_msg.content or "",
        session_id=ai_msg.session_id,
        local_user_id=local_user_id,
        crm_admin_id=crm_admin_id,
        scene_key=session.scene_key or "qa_support",
        entry_scene=session.entry_scene or "customer_profile",
        output_style=session.output_style or "coach_brief",
        health_window_days=7,
        regenerated_from_message_id=original_message_id,
    ):
        yield event
