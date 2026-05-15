"""AI Coach public API — ask, stream answer, stream thinking, regenerate."""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import AsyncIterator

from ._types import _log, _sse, _TXT_FENCE_RE, PreparedAiTurn, AiChatResult, AiStreamEvent
from ._helpers import (
    _classify_ai_error, _emit_text_chunks, _debug_ai_stream_test,
    _bind_attachments_if_any, _profile_cache_unready_payload,
    _normalize_text, _check_safety_gates, _ensure_output_contract,
    _ensure_session_written,
    _build_shortcut_thinking_text, _extract_customer_name,
)
from ._prepare import _prepare_ai_turn_cached, _prepare_ai_turn_async, _resolve_attachment_descriptions
from ....clients.ai_chat_client import chat_completion, chat_completion_stream
from ....config import settings
from ....database import SessionLocal
from ..context_builder import build_context_text
from ..profile_context_cache import normalize_window_days, get_ai_ready_profile_context, ProfileCacheNotReady
from ..prompt_builder import assemble_lightweight_thinking_prompt
from .. import audit


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
    model: str | None = None,
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

    # Pre-generate message IDs for RAG log binding
    user_message_id = str(uuid.uuid4())

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
        rag_session_id=session_id,
        rag_message_id=user_message_id,
    )

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
    _req_params = {
        "scene_key": scene_key, "output_style": output_style,
        "health_window_days": health_window_days, "model": model or settings.ai_model,
        "attachment_ids": attachment_ids, "quoted_message_id": quoted_message_id,
        "selected_expansions": selected_expansions,
    }
    audit.write_message(prepared.session_id, user_message_id, "user", message,
                        quoted_message_id=quoted_message_id, request_params=_req_params)
    if attachment_ids:
        from ..ai_attachment import bind_attachments_to_message
        with SessionLocal() as _adb:
            bind_attachments_to_message(_adb, attachment_ids, prepared.session_id, user_message_id)
    audit.write_context_snapshot(
        prepared.session_id, build_context_text(prepared.ctx.cards, selected_expansions=selected_expansions), prepared.used_modules,
        prompt_version=prepared.assembly.prompt_version,
        prompt_hash=prepared.assembly.prompt_hash,
        scene_key=prepared.assembly.scene_key,
        output_style=output_style,
        selected_expansions=selected_expansions,
        health_window_days=prepared.health_window_days,
        cache_key=prepared.cache_key,
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
    answer, usage = await chat_completion(prepared.ai_messages, temperature=0.7, max_tokens=15000, model=model)
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
        model=model or settings.ai_model,
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
    model: str | None = None,
) -> AsyncIterator[AiStreamEvent]:
    t_start = time.time()
    _sse.info("[SSE-TIMING] === answer-stream request arrived ===")

    # --- Stage 1: Vision analysis for attachments ---
    original_message = message
    effective_message = message
    att_tuple = tuple(attachment_ids) if attachment_ids else None
    user_preview = original_message[:30] + ('...' if len(original_message) > 30 else '')
    yield AiStreamEvent(event="progress", data={"text": f"收到提问：{user_preview}", "step": "received"})
    if attachment_ids:
        yield AiStreamEvent(event="analyzing", data={"status": "analyzing_attachments"})
        yield AiStreamEvent(event="progress", data={"text": "正在分析附件", "step": "analyzing"})
        effective_message = await _resolve_attachment_descriptions(customer_id, attachment_ids, message)

    # Resolve quoted content for follow-up
    quoted_content: str | None = None
    if quoted_message_id:
        qmsg = audit.find_message_by_id(quoted_message_id)
        if qmsg and qmsg.role == "assistant":
            quoted_content = qmsg.content

    yield AiStreamEvent(event="loading", data={"stage": "prepare"})

    # Pre-generate message IDs so RAG logs can bind to them
    pre_user_message_id = str(uuid.uuid4())
    pre_assistant_message_id = str(uuid.uuid4())

    _sse.info("[SSE-TIMING] prepare start at %.3fs", time.time() - t_start)

    # Run prepare in background with progress queue so we can yield events
    progress_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def _on_progress(text: str, step: str):
        await progress_queue.put({"text": text, "step": step})

    prepare_task = asyncio.create_task(
        _prepare_ai_turn_cached(
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
            rag_session_id=session_id,
            rag_message_id=pre_user_message_id,
            original_message=original_message,
            on_progress=_on_progress,
        )
    )

    try:
        while not prepare_task.done():
            try:
                evt = await asyncio.wait_for(progress_queue.get(), timeout=0.15)
                yield AiStreamEvent(event="progress", data=evt)
            except asyncio.TimeoutError:
                continue
        # Drain remaining progress events
        while not progress_queue.empty():
            evt = progress_queue.get_nowait()
            if evt:
                yield AiStreamEvent(event="progress", data=evt)
        prepared = prepare_task.result()
    except ProfileCacheNotReady as exc:
        _sse.info("[SSE-TIMING] answer profile cache unready key=%s", exc.result.cache_key)
        yield AiStreamEvent(event="error", data=_profile_cache_unready_payload(exc))
        return

    _sse.info("[SSE-TIMING] prepare done at %.3fs", time.time() - t_start)
    t_prepare_done = time.time()

    assistant_message_id = pre_assistant_message_id
    user_message_id = pre_user_message_id

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

    yield AiStreamEvent(event="progress", data={"text": "模型整合回复中", "step": "model_call"})
    yield AiStreamEvent(event="loading", data={"stage": "model_call"})

    _req_params = {
        "scene_key": scene_key, "output_style": output_style,
        "health_window_days": health_window_days, "model": model or settings.ai_model,
        "attachment_ids": list(attachment_ids) if attachment_ids else None,
        "quoted_message_id": quoted_message_id,
        "selected_expansions": selected_expansions,
    }

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
                audit.write_message(prepared.session_id, user_message_id, "user", message,
                                    quoted_message_id=quoted_message_id, request_params=_req_params),
                _bind_attachments_if_any(prepared.session_id, user_message_id, attachment_ids),
                audit.write_context_snapshot(
                    prepared.session_id, build_context_text(prepared.ctx.cards, selected_expansions=selected_expansions), prepared.used_modules,
                    prompt_version=prepared.assembly.prompt_version,
                    prompt_hash=prepared.assembly.prompt_hash,
                    scene_key=prepared.assembly.scene_key,
                    output_style=output_style,
                    selected_expansions=selected_expansions,
                    health_window_days=prepared.health_window_days,
                    cache_key=prepared.cache_key,
                ),
            ),
        )

    _audit_task = asyncio.create_task(_background_audit())

    # Fire-and-forget auto-title generation after user message is persisted
    async def _fire_auto_title():
        await _audit_task  # ensure user message is written first
        try:
            from ._auto_title import generate_auto_title
            await generate_auto_title(prepared.session_id)
        except Exception:
            pass  # non-critical background task
    _ = asyncio.create_task(_fire_auto_title())

    if prepared.shortcut_answer:
        await _audit_task
        async for chunk in _emit_text_chunks(prepared.shortcut_answer, size=14, delay=0.035):
            yield AiStreamEvent(event="delta", data={"delta": chunk})
        audit.write_message(
            prepared.session_id, assistant_message_id, "assistant", prepared.shortcut_answer,
            model="profile_fact_shortcut",
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=int((time.time() - t_start) * 1000),
            requires_medical_review=False,
        )
        yield AiStreamEvent(
            event="done",
            data={
                "session_id": prepared.session_id,
                "message_id": assistant_message_id,
                "model": "profile_fact_shortcut",
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "requires_medical_review": False,
                "safety_notes": [],
                "missing_data_notes": [],
                "timing": {
                    "prepare_ms": int((t_prepare_done - t_start) * 1000),
                    "first_chunk_ms": int((time.time() - t_start) * 1000),
                    "total_ms": int((time.time() - t_start) * 1000),
                },
            },
        )
        return

    # RAG sources event (only when not shortcut)
    if prepared.rag_sources or prepared.rag_recommended_assets:
        yield AiStreamEvent(event="rag", data={
            "rag_status": "ok",
            "sources": prepared.rag_sources,
            "recommended_assets": prepared.rag_recommended_assets,
        })

    collected_chunks: list[str] = []
    usage: dict[str, int] = {}
    t0 = time.time()
    t_first_chunk: float | None = None
    try:
        chunk_count = 0
        _sse.info("[SSE-TIMING] AI API stream starts at %.3fs (audit writes running in background)", time.time() - t_start)
        async for chunk in chat_completion_stream(prepared.ai_messages, temperature=0.7, max_tokens=15000, model=model):
            if chunk.delta:
                if t_first_chunk is None:
                    t_first_chunk = time.time()
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
            model=model or settings.ai_model,
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
                "model": model or settings.ai_model,
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
                "timing": {
                    "prepare_ms": int((t_prepare_done - t_start) * 1000),
                    "first_chunk_ms": int((t_first_chunk - t_start) * 1000) if t_first_chunk else None,
                    "total_ms": int((time.time() - t_start) * 1000),
                },
            },
        )
    except asyncio.CancelledError:
        _log.info("Answer stream cancelled by client")
        return
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
    thinking_provider = settings.ai_thinking_provider or settings.ai_provider
    thinking_model = settings.ai_thinking_model or settings.ai_model
    _sse.info("[SSE-TIMING] === thinking-stream request arrived (provider=%s, model=%s) ===",
              thinking_provider, thinking_model)

    # Resolve session
    if not session_id:
        session_id = str(uuid.uuid4())
    reuse_session = audit.session_exists(session_id)

    # Lightweight: get customer name + module labels (non-blocking, L1 cache hit <100ms)
    customer_name = ""
    module_labels: list[str] = []
    window_days = normalize_window_days(health_window_days)
    try:
        result = get_ai_ready_profile_context(customer_id, window_days=window_days)
        if result.ctx and result.ctx.cards:
            customer_name = _extract_customer_name(result.ctx)
            from ..context_builder import MODULE_LABELS
            module_labels = [
                MODULE_LABELS[c.key] for c in result.ctx.cards
                if c.status in ("ok", "partial") and c.key in MODULE_LABELS
            ]
    except Exception:
        pass  # Profile not ready is OK for thinking

    # Resolve attachment descriptions (reuses cached Vision results)
    effective_message = message
    if attachment_ids:
        effective_message = await _resolve_attachment_descriptions(customer_id, attachment_ids, message)

    yield AiStreamEvent(event="loading", data={"stage": "prepare"})

    # Shortcut: for trivial fact-reading questions, skip LLM entirely
    shortcut_text = _build_shortcut_thinking_text(message, None)

    if shortcut_text:
        yield AiStreamEvent(event="meta", data={
            "session_id": session_id,
            "prompt_version": "shortcut",
            "scene_key": scene_key,
        })
        async for chunk in _emit_text_chunks(shortcut_text, size=14, delay=0.035):
            yield AiStreamEvent(event="delta", data={"delta": chunk})
        yield AiStreamEvent(event="done", data={"session_id": session_id})
        return

    _sse.info("[SSE-TIMING] thinking lightweight prepare done at %.3fs", time.time() - t_start)

    assembly = assemble_lightweight_thinking_prompt(
        scene_key=scene_key,
        module_labels=module_labels,
        customer_name=customer_name,
        user_message=effective_message,
    )

    yield AiStreamEvent(event="meta", data={
        "session_id": session_id,
        "prompt_version": assembly.prompt_version,
        "scene_key": assembly.scene_key,
    })

    yield AiStreamEvent(event="loading", data={"stage": "model_call"})

    try:
        _sse.info("[SSE-TIMING] thinking AI stream starts at %.3fs (provider=%s, model=%s)",
                  time.time() - t_start, thinking_provider, thinking_model)
        chunk_count = 0
        async for chunk in chat_completion_stream(
            assembly.messages,
            temperature=0.6,
            max_tokens=2000,
            model=thinking_model,
            provider=thinking_provider or None,
        ):
            if chunk.delta:
                chunk_count += 1
                _sse.info("[SSE-TIMING] thinking chunk #%d at %.3fs", chunk_count, time.time() - t_start)
                yield AiStreamEvent(event="delta", data={"delta": chunk.delta})
                await asyncio.sleep(0.25)
        _sse.info("[SSE-TIMING] thinking AI done, %d chunks, %.3fs", chunk_count, time.time() - t_start)

        yield AiStreamEvent(event="done", data={"session_id": session_id})
    except asyncio.CancelledError:
        _log.info("Thinking stream cancelled by client")
        return
    except Exception as exc:
        _log.error("Thinking stream failed: %s", exc, exc_info=True)
        yield AiStreamEvent(event="error", data={
            "message": str(exc) or "AI 思考流异常",
            "code": _classify_ai_error(exc),
        })


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

    original_model = ai_msg.model or None
    # Inherit health_window_days from original user message request params
    original_window = 7
    if user_msg.request_params_json:
        try:
            import json as _json
            orig_params = _json.loads(user_msg.request_params_json)
            original_window = orig_params.get("health_window_days", 7)
        except Exception:
            pass

    async for event in stream_ai_coach_answer(
        customer_id,
        user_msg.content or "",
        session_id=ai_msg.session_id,
        local_user_id=local_user_id,
        crm_admin_id=crm_admin_id,
        scene_key=session.scene_key or "qa_support",
        entry_scene=session.entry_scene or "customer_profile",
        output_style=session.output_style or "coach_brief",
        health_window_days=original_window,
        regenerated_from_message_id=original_message_id,
        model=original_model,
    ):
        yield event
