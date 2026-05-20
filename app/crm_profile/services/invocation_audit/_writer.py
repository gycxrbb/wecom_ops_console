"""Fire-and-forget writer for invocation trace + step records."""
from __future__ import annotations

import logging
from datetime import datetime

from ....database import SessionLocal
from ...models import CrmAiInvocation, CrmAiTraceStep
from ._stage_registry import validate_stage, validate_step_kind

_log = logging.getLogger(__name__)


def start_invocation(
    call_id: str,
    *,
    session_id: str | None = None,
    execution_mode: str = "single_turn",
    local_user_id: int | None = None,
    crm_admin_id: int | None = None,
    crm_customer_id: int | None = None,
    entry_scene: str | None = None,
    scene_key: str | None = None,
    output_style: str | None = None,
    health_window_days: int | None = None,
) -> None:
    db = SessionLocal()
    try:
        db.add(CrmAiInvocation(
            call_id=call_id,
            session_id=session_id,
            execution_mode=execution_mode,
            local_user_id=local_user_id,
            crm_admin_id=crm_admin_id,
            crm_customer_id=crm_customer_id,
            entry_scene=entry_scene or None,
            scene_key=scene_key or None,
            output_style=output_style or None,
            health_window_days=health_window_days,
            status="pending",
            started_at=datetime.utcnow(),
        ))
        db.commit()
    except Exception:
        _log.exception("Failed to start invocation %s", call_id)
        db.rollback()
    finally:
        db.close()


def write_step(
    call_id: str,
    step_index: int,
    kind: str,
    *,
    parent_step_index: int | None = None,
    name: str | None = None,
    status: str = "success",
    error_code: str | None = None,
    error_message: str | None = None,
    input_json: str | None = None,
    output_json: str | None = None,
    latency_ms: int = 0,
    model: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cached_tokens: int = 0,
    tool_name: str | None = None,
    tool_input_hash: str | None = None,
) -> None:
    validate_step_kind(kind)
    db = SessionLocal()
    try:
        db.add(CrmAiTraceStep(
            call_id=call_id,
            step_index=step_index,
            parent_step_index=parent_step_index,
            kind=kind,
            name=name,
            status=status,
            error_code=error_code,
            error_message=error_message,
            input_json=input_json,
            output_json=output_json,
            latency_ms=latency_ms,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            tool_name=tool_name,
            tool_input_hash=tool_input_hash,
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
        ))
        db.commit()
    except Exception:
        _log.exception("Failed to write step %d for %s", step_index, call_id)
        db.rollback()
    finally:
        db.close()


def update_step(
    call_id: str,
    step_index: int,
    kind: str,
    *,
    name: str | None = None,
    status: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    output_json: str | None = None,
    latency_ms: int | None = None,
    model: str | None = None,
) -> None:
    validate_step_kind(kind)
    db = SessionLocal()
    try:
        step = (
            db.query(CrmAiTraceStep)
            .filter_by(call_id=call_id, step_index=step_index, kind=kind)
            .order_by(CrmAiTraceStep.id.desc())
            .first()
        )
        if not step:
            write_step(
                call_id, step_index, kind,
                name=name,
                status=status or "success",
                error_code=error_code,
                error_message=error_message,
                output_json=output_json,
                latency_ms=latency_ms or 0,
                model=model,
            )
            return
        if name is not None:
            step.name = name
        if status is not None:
            step.status = status
        step.error_code = error_code
        step.error_message = error_message[:512] if error_message else None
        if output_json is not None:
            step.output_json = output_json
        if latency_ms is not None:
            step.latency_ms = latency_ms
        if model is not None:
            step.model = model
        step.finished_at = datetime.utcnow()
        db.commit()
    except Exception:
        _log.exception("Failed to update step %d for %s", step_index, call_id)
        db.rollback()
    finally:
        db.close()


def update_stage(
    call_id: str,
    stage: str,
    *,
    context_snapshot_id: int | None = None,
    rag_status: str | None = None,
    rag_hit_count: int | None = None,
    user_message_id: str | None = None,
    assistant_message_id: str | None = None,
    prompt_version: str | None = None,
    prompt_hash: str | None = None,
    cache_key: str | None = None,
    prepare_ms: int | None = None,
) -> None:
    validate_stage(stage)
    db = SessionLocal()
    try:
        inv = db.query(CrmAiInvocation).filter_by(call_id=call_id).first()
        if not inv:
            return
        if context_snapshot_id is not None:
            inv.context_snapshot_id = context_snapshot_id
        if rag_status is not None:
            inv.rag_status = rag_status
        if rag_hit_count is not None:
            inv.rag_hit_count = rag_hit_count
        if user_message_id is not None:
            inv.user_message_id = user_message_id
        if assistant_message_id is not None:
            inv.assistant_message_id = assistant_message_id
        if prompt_version is not None:
            inv.prompt_version = prompt_version
        if prompt_hash is not None:
            inv.prompt_hash = prompt_hash
        if cache_key is not None:
            inv.cache_key = cache_key
        if prepare_ms is not None:
            inv.prepare_ms = prepare_ms
        inv.error_stage = stage
        db.commit()
    except Exception:
        _log.exception("Failed to update stage %s for %s", stage, call_id)
        db.rollback()
    finally:
        db.close()


def finish_invocation(
    call_id: str,
    *,
    assistant_message_id: str | None = None,
    total_prompt_tokens: int = 0,
    total_completion_tokens: int = 0,
    total_tokens: int = 0,
    cached_tokens: int = 0,
    primary_model: str | None = None,
    primary_provider: str | None = None,
    step_count: int = 1,
    latency_ms: int = 0,
    first_token_ms: int = 0,
    prepare_ms: int = 0,
    diagnostics_json: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        inv = db.query(CrmAiInvocation).filter_by(call_id=call_id).first()
        if not inv:
            return
        inv.status = "success"
        inv.error_stage = "done"
        inv.finished_at = datetime.utcnow()
        if assistant_message_id is not None:
            inv.assistant_message_id = assistant_message_id
        inv.total_prompt_tokens = total_prompt_tokens
        inv.total_completion_tokens = total_completion_tokens
        inv.total_tokens = total_tokens
        inv.cached_tokens = cached_tokens
        inv.primary_model = primary_model
        inv.primary_provider = primary_provider
        inv.step_count = step_count
        inv.latency_ms = latency_ms
        inv.first_token_ms = first_token_ms
        inv.prepare_ms = prepare_ms
        if diagnostics_json:
            inv.diagnostics_json = diagnostics_json
        db.commit()
    except Exception:
        _log.exception("Failed to finish invocation %s", call_id)
        db.rollback()
    finally:
        db.close()


def _update_diagnostics_json(call_id: str, report: dict) -> None:
    """Write diagnostics report to an existing invocation record."""
    import json
    db = SessionLocal()
    try:
        inv = db.query(CrmAiInvocation).filter_by(call_id=call_id).first()
        if inv:
            inv.diagnostics_json = json.dumps(report, ensure_ascii=False)
            db.commit()
    except Exception:
        _log.exception("Failed to write diagnostics for %s", call_id)
        db.rollback()
    finally:
        db.close()


def fail_invocation(
    call_id: str,
    stage: str,
    error_code: str,
    error_message: str = "",
    error_detail: str | None = None,
    latency_ms: int = 0,
) -> None:
    validate_stage(stage)
    db = SessionLocal()
    try:
        inv = db.query(CrmAiInvocation).filter_by(call_id=call_id).first()
        if not inv:
            return
        inv.status = "error"
        inv.error_stage = stage
        inv.error_code = error_code
        inv.error_message = error_message[:512] if error_message else None
        if error_detail:
            inv.error_detail = error_detail[:4000]
        inv.finished_at = datetime.utcnow()
        inv.latency_ms = latency_ms
        db.commit()
    except Exception:
        _log.exception("Failed to fail invocation %s", call_id)
        db.rollback()
    finally:
        db.close()
