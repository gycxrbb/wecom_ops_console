"""AI Coach prepare chain — profile loading, RAG retrieval, prompt assembly, turn cache."""
from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from typing import Any, Awaitable, Callable, Literal

from ._types import _log, _sse, _PREPARE_CACHE, _PREPARE_TTL, PreparedAiTurn
from ._helpers import (
    _extract_customer_name, _extract_rag_profile_signals, _load_profile_note,
    _compose_ai_messages, _ensure_session_written,
    _try_answer_profile_fact_question, _build_shortcut_thinking_text,
)
from ....config import settings
from ....database import SessionLocal
from ...schemas.context import ModulePayload
from ..context_builder import build_context_text, validate_field_whitelist, get_module_label
from ..profile_context_cache import ProfileCacheNotReady, get_ai_ready_profile_context, normalize_window_days
from ..prompt_builder import assemble_prompt, assemble_visible_thinking_prompt
from .. import audit


def _prepare_cache_key(customer_id: int, message: str, session_id: str | None,
                       scene_key: str, output_style: str, health_window_days: int,
                       attachment_ids: tuple[str, ...] | None = None,
                       quoted_content_hash: str = "") -> tuple:
    return (customer_id, message, session_id or "", scene_key, output_style, health_window_days, attachment_ids or (), quoted_content_hash)


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
    original_message: str | None = None,
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
        shortcut_answer=_try_answer_profile_fact_question(original_message or message, ctx),
        shortcut_thinking=_build_shortcut_thinking_text(original_message or message, ctx),
        rag_context_text=rag_context_text,
        rag_sources=rag_sources or [],
        rag_recommended_assets=rag_recommended_assets or [],
        quoted_content=quoted_content,
        health_window_days=window_days,
        cache_key=profile_result.cache_key,
    )


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
    rag_session_id: str | None = None,
    rag_message_id: str | None = None,
    original_message: str | None = None,
    on_progress: Callable[[str, str], Awaitable] | None = None,
) -> PreparedAiTurn:
    """Async wrapper: runs RAG retrieval (async) then _prepare_ai_turn (sync via executor)."""
    rag_context_text = ""
    rag_sources: list[dict] = []
    rag_recommended_assets: list[dict] = []
    if settings.rag_enabled:
        try:
            if on_progress:
                await on_progress("正在查询知识库...", "rag_search")
            from ....rag.retriever import retrieve_rag_context as _rag_retrieve
            window_days = normalize_window_days(health_window_days)
            profile_signals = _extract_rag_profile_signals(customer_id, window_days)
            # RAG 用原始用户问题检索，不用拼接了附件的 effective_message
            rag_query = original_message or message
            rag_bundle = await _rag_retrieve(
                customer_id=customer_id, message=rag_query,
                scene_key=scene_key, output_style=output_style,
                profile_context=profile_signals if profile_signals else None,
                session_id=rag_session_id,
                message_id=rag_message_id,
            )
            if rag_bundle and rag_bundle.rag_status == "ok":
                rag_context_text = rag_bundle.context_text
                rag_sources = [s.model_dump() for s in rag_bundle.sources]
                rag_recommended_assets = [a.model_dump() for a in rag_bundle.recommended_assets]
            if on_progress:
                if rag_sources:
                    await on_progress(f"召回 {len(rag_sources)} 条相关知识", "rag_done")
                else:
                    await on_progress("知识库未找到相关内容，直接回复", "rag_done")
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
            original_message=original_message,
        ),
    )


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
    rag_session_id: str | None = None,
    rag_message_id: str | None = None,
    original_message: str | None = None,
    on_progress: Callable[[str, str], Awaitable] | None = None,
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
        _shortcut_msg = original_message or message
        return PreparedAiTurn(
            session_id=cached.session_id,
            reuse_session=cached.reuse_session,
            ctx=cached.ctx,
            safety_card=cached.safety_card,
            used_modules=cached.used_modules,
            missing_notes=cached.missing_notes,
            assembly=assembly,
            ai_messages=ai_messages,
            shortcut_answer=_try_answer_profile_fact_question(_shortcut_msg, cached.ctx),
            shortcut_thinking=_build_shortcut_thinking_text(_shortcut_msg, cached.ctx),
            quoted_content=quoted_content,
        )

    prepared = await _prepare_ai_turn_async(
        customer_id, message,
        session_id=session_id, scene_key=scene_key,
        output_style=output_style, health_window_days=window_days, prompt_mode=prompt_mode,
        selected_expansions=selected_expansions,
        quoted_content=quoted_content,
        rag_session_id=rag_session_id,
        rag_message_id=rag_message_id,
        original_message=original_message,
        on_progress=on_progress,
    )
    _PREPARE_CACHE[key] = (now, prepared)
    return prepared


async def _resolve_attachment_descriptions(
    customer_id: int,
    attachment_ids: list[str],
    original_message: str,
) -> str:
    """Load attachments, wait briefly for background analysis, fall back to sync if needed."""
    from ..ai_attachment import load_attachments, _get_analysis_lock
    from ..vision_analyzer import analyze_attachment, build_user_message_with_attachments
    from ...models import CrmAiAttachment

    with SessionLocal() as db:
        attachments = load_attachments(db, attachment_ids, customer_id)

    if not attachments:
        return original_message

    async def _resolve_one(att: CrmAiAttachment) -> str:
        if att.processing_status == "analyzed" and att.vision_description:
            return att.vision_description

        lock = _get_analysis_lock(att.attachment_id)
        try:
            await asyncio.wait_for(lock.acquire(), timeout=8.0)
        except asyncio.TimeoutError:
            return await analyze_attachment(att)

        try:
            with SessionLocal() as db:
                fresh = db.query(CrmAiAttachment).filter_by(
                    attachment_id=att.attachment_id).first()
                if fresh and fresh.processing_status == "analyzed" and fresh.vision_description:
                    return fresh.vision_description
            return await analyze_attachment(att)
        finally:
            lock.release()

    results = await asyncio.gather(*[_resolve_one(att) for att in attachments])
    descriptions = [(att.original_filename, desc) for att, desc in zip(attachments, results)]
    return build_user_message_with_attachments(original_message, descriptions)
