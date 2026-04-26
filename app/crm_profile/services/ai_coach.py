"""AI Coach service — prompt assembly, safety gates, AI call, audit, streaming."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal

from ...clients.ai_chat_client import chat_completion, chat_completion_stream
from ...clients.crm_db import get_connection, return_connection
from ...config import settings
from ...database import SessionLocal
from ...sse_debug_log import get_sse_logger
from ..models import CustomerAiProfileNote
from ..schemas.context import ModulePayload
from . import audit
from .cache import get as cache_get, get_stale as cache_get_stale, put as cache_put, PROFILE_TTL
from .context_builder import build_context_text, validate_field_whitelist, get_module_label
from .profile_loader import load_profile
from .prompt_builder import assemble_prompt, assemble_visible_thinking_prompt
from .safety_gate import build_safety_input, evaluate_ai_answer_safety

_log = logging.getLogger(__name__)
_sse = get_sse_logger()


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


def _compose_ai_messages(assembly, session_id: str, reuse_session: bool) -> list[dict[str, Any]]:
    ai_messages: list[dict[str, Any]] = []
    if assembly.messages:
        ai_messages.extend(msg for msg in assembly.messages[:-1] if msg.get("role") == "system")

    if reuse_session:
        history = audit.load_session_messages(session_id, limit=10)
        for h in history:
            ai_messages.append({"role": h["role"], "content": h["content"]})

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
    event: Literal["meta", "delta", "done", "error", "loading"]
    data: dict[str, Any] = field(default_factory=dict)


# --- Prepare cache: avoid duplicate DB queries when answer + thinking run concurrently ---

_PREPARE_CACHE: dict[tuple, tuple[float, PreparedAiTurn]] = {}
_PREPARE_TTL = 15.0


def _prepare_cache_key(customer_id: int, message: str, session_id: str | None,
                       scene_key: str, output_style: str) -> tuple:
    return (customer_id, message, session_id or "", scene_key, output_style)


async def _prepare_ai_turn_cached(
    customer_id: int,
    message: str,
    *,
    session_id: str | None,
    scene_key: str,
    output_style: str,
    prompt_mode: Literal["answer", "thinking"],
    selected_expansions: list[str] | None = None,
) -> PreparedAiTurn:
    """Prepare with turn-level cache. First call writes, second call reads within TTL."""
    key = _prepare_cache_key(customer_id, message, session_id, scene_key, output_style)
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
        ai_messages = _compose_ai_messages(assembly, cached.session_id, cached.reuse_session)
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
        )

    prepared = await _prepare_ai_turn_async(
        customer_id, message,
        session_id=session_id, scene_key=scene_key,
        output_style=output_style, prompt_mode=prompt_mode,
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
    prompt_mode: Literal["answer", "thinking"],
    selected_expansions: list[str] | None = None,
) -> PreparedAiTurn:
    """Async wrapper: runs the synchronous _prepare_ai_turn in a thread to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _prepare_ai_turn(
            customer_id, message,
            session_id=session_id, scene_key=scene_key,
            output_style=output_style, prompt_mode=prompt_mode,
            selected_expansions=selected_expansions,
        ),
    )


def _prepare_ai_turn(
    customer_id: int,
    message: str,
    *,
    session_id: str | None,
    scene_key: str,
    output_style: str,
    prompt_mode: Literal["answer", "thinking"],
    selected_expansions: list[str] | None = None,
) -> PreparedAiTurn:
    reuse_session = bool(session_id) and audit.session_exists(session_id)
    if not session_id:
        session_id = str(uuid.uuid4())

    profile_cache_key = f"profile:{customer_id}"
    ctx = cache_get(profile_cache_key)
    if ctx:
        _sse.info("[SSE-TIMING] profile from cache (hit)")
    else:
        # Stale-while-revalidate: use expired cache if available, refresh in background
        stale_ctx = cache_get_stale(profile_cache_key)
        if stale_ctx:
            ctx = stale_ctx
            _sse.info("[SSE-TIMING] profile from STALE cache (stale-while-revalidate)")
            # Refresh in background so next request gets fresh data
            def _bg_refresh():
                try:
                    conn = get_connection()
                    try:
                        fresh = load_profile(customer_id)
                    finally:
                        return_connection(conn)
                    cache_put(profile_cache_key, fresh, PROFILE_TTL)
                except Exception:
                    pass
            threading.Thread(target=_bg_refresh, daemon=True).start()
        else:
            # True miss — must load synchronously
            conn = get_connection()
            try:
                ctx = load_profile(customer_id)
            finally:
                return_connection(conn)
            cache_put(profile_cache_key, ctx, PROFILE_TTL)
            _sse.info("[SSE-TIMING] profile loaded from DB (cache miss)")

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
    if prompt_mode == "thinking":
        assembly = assemble_visible_thinking_prompt(
            scene_key=scene_key,
            context_text=context_text,
            customer_name=customer_name,
            profile_note=profile_note,
            user_message=message,
        )
    else:
        assembly = assemble_prompt(
            scene_key=scene_key,
            context_text=context_text,
            customer_name=customer_name,
            profile_note=profile_note,
            user_message=message,
            output_style=output_style,
        )

    return PreparedAiTurn(
        session_id=session_id,
        reuse_session=reuse_session,
        ctx=ctx,
        safety_card=safety_card,
        used_modules=used_modules,
        missing_notes=missing_notes,
        assembly=assembly,
        ai_messages=_compose_ai_messages(assembly, session_id, reuse_session),
        shortcut_answer=_try_answer_profile_fact_question(message, ctx),
        shortcut_thinking=_build_shortcut_thinking_text(message, ctx),
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
) -> AiChatResult:
    """Non-streaming fallback entry for AI coach."""
    prepared = _prepare_ai_turn(
        customer_id,
        message,
        session_id=session_id,
        scene_key=scene_key,
        output_style=output_style,
        prompt_mode="answer",
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
    audit.write_message(prepared.session_id, user_message_id, "user", message)
    audit.write_context_snapshot(
        prepared.session_id, build_context_text(prepared.ctx.cards), prepared.used_modules,
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
) -> AsyncIterator[AiStreamEvent]:
    t_start = time.time()
    _sse.info("[SSE-TIMING] === answer-stream request arrived ===")

    yield AiStreamEvent(event="loading", data={"stage": "prepare"})

    _sse.info("[SSE-TIMING] prepare start at %.3fs", time.time() - t_start)
    prepared = await _prepare_ai_turn_cached(
        customer_id,
        message,
        session_id=session_id,
        scene_key=scene_key,
        output_style=output_style,
        prompt_mode="answer",
        selected_expansions=selected_expansions,
    )
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
                audit.write_message(prepared.session_id, user_message_id, "user", message),
                audit.write_context_snapshot(
                    prepared.session_id, build_context_text(prepared.ctx.cards), prepared.used_modules,
                    prompt_version=prepared.assembly.prompt_version,
                    prompt_hash=prepared.assembly.prompt_hash,
                    scene_key=prepared.assembly.scene_key,
                    output_style=output_style,
                    selected_expansions=None,
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
        )
        yield AiStreamEvent(
            event="done",
            data={
                "session_id": prepared.session_id,
                "message_id": assistant_message_id,
                "token_usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                "requires_medical_review": requires_review,
                "safety_notes": safety_notes,
                "missing_data_notes": prepared.missing_notes,
                "safety_result": safety_result,
            },
        )
    except Exception as exc:
        _log.error("Answer stream failed: %s", exc, exc_info=True)
        yield AiStreamEvent(event="error", data={"message": str(exc) or "AI 服务异常"})


async def stream_ai_coach_thinking(
    customer_id: int,
    message: str,
    *,
    session_id: str | None = None,
    scene_key: str = "qa_support",
    output_style: str = "coach_brief",
) -> AsyncIterator[AiStreamEvent]:
    t_start = time.time()
    _sse.info("[SSE-TIMING] === thinking-stream request arrived (provider=%s) ===", settings.ai_provider)

    yield AiStreamEvent(event="loading", data={"stage": "prepare"})

    # DeepSeek: lightweight path — skip _prepare_ai_turn_async (SQLite contention),
    # read profile from cache directly, build prompt inline, then call API normally.
    if settings.ai_provider == 'deepseek':
        _sse.info("[SSE-TIMING] deepseek thinking: lightweight prepare at %.3fs", time.time() - t_start)
        resolved_sid = session_id or str(uuid.uuid4())
        profile_cache_key = f"profile:{customer_id}"
        ctx = cache_get(profile_cache_key)

        if not ctx:
            # Stale-while-revalidate for DeepSeek thinking path too
            stale_ctx = cache_get_stale(profile_cache_key)
            if stale_ctx:
                ctx = stale_ctx
                _sse.info("[SSE-TIMING] deepseek thinking: profile from STALE cache at %.3fs", time.time() - t_start)
                def _bg_refresh_ds():
                    try:
                        conn = get_connection()
                        try:
                            fresh = load_profile(customer_id)
                        finally:
                            return_connection(conn)
                        cache_put(profile_cache_key, fresh, PROFILE_TTL)
                    except Exception:
                        pass
                threading.Thread(target=_bg_refresh_ds, daemon=True).start()
            else:
                _sse.info("[SSE-TIMING] deepseek thinking: profile cache miss, loading from DB at %.3fs", time.time() - t_start)
                loop = asyncio.get_event_loop()
                ctx = await loop.run_in_executor(None, lambda: load_profile(customer_id))
                if ctx:
                    cache_put(profile_cache_key, ctx, PROFILE_TTL)
                else:
                    yield AiStreamEvent(event="meta", data={"session_id": resolved_sid})
                    yield AiStreamEvent(event="delta", data={"delta": "等待客户数据加载…"})
                    yield AiStreamEvent(event="done", data={"session_id": resolved_sid})
                    return

        # Shortcut for simple fact questions — no API call needed
        shortcut_thinking = _build_shortcut_thinking_text(message, ctx)
        if shortcut_thinking:
            yield AiStreamEvent(event="meta", data={"session_id": resolved_sid})
            async for chunk in _emit_text_chunks(shortcut_thinking, size=14, delay=0.035):
                yield AiStreamEvent(event="delta", data={"delta": chunk})
            yield AiStreamEvent(event="done", data={"session_id": resolved_sid})
            return

        context_text = build_context_text(ctx.cards)
        basic_card = next((c for c in ctx.cards if c.key == "basic_profile"), None)
        customer_name = ""
        if basic_card and basic_card.payload:
            customer_name = str(basic_card.payload.get("display_name") or "").strip()

        assembly = assemble_visible_thinking_prompt(
            scene_key=scene_key,
            context_text=context_text,
            customer_name=customer_name,
            user_message=message,
        )

        yield AiStreamEvent(event="meta", data={
            "session_id": resolved_sid,
            "prompt_version": assembly.prompt_version,
            "scene_key": assembly.scene_key,
        })
        yield AiStreamEvent(event="loading", data={"stage": "model_call"})
        _sse.info("[SSE-TIMING] deepseek thinking: prepare done at %.3fs, API call starts",
                  time.time() - t_start)
        try:
            chunk_count = 0
            async for chunk in chat_completion_stream(assembly.messages, temperature=0.4, max_tokens=4096):
                if chunk.delta:
                    chunk_count += 1
                    _sse.info("[SSE-TIMING] deepseek thinking chunk #%d at %.3fs",
                              chunk_count, time.time() - t_start)
                    yield AiStreamEvent(event="delta", data={"delta": chunk.delta})
                    await asyncio.sleep(0)
            _sse.info("[SSE-TIMING] deepseek thinking done, %d chunks, %.3fs",
                      chunk_count, time.time() - t_start)
            yield AiStreamEvent(event="done", data={"session_id": resolved_sid})
        except Exception as exc:
            _log.error("DeepSeek thinking stream failed: %s", exc, exc_info=True)
            yield AiStreamEvent(event="error", data={"message": str(exc) or "AI 思考流异常"})
        return

    # aihubmix: cached prepare path (shares context with answer stream)
    _sse.info("[SSE-TIMING] thinking prepare start at %.3fs", time.time() - t_start)
    prepared = await _prepare_ai_turn_cached(
        customer_id,
        message,
        session_id=session_id,
        scene_key=scene_key,
        output_style=output_style,
        prompt_mode="thinking",
    )
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
        yield AiStreamEvent(event="error", data={"message": str(exc) or "AI 思考流异常"})
