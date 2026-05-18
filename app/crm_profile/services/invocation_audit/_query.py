"""Admin query functions for invocation audit."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import threading

from sqlalchemy import func, cast, Date, Integer, case

from ....database import SessionLocal
from ...models import CrmAiInvocation, CrmAiTraceStep, CrmAiMessage, CrmAiContextSnapshot
from ....models import User as LocalUser
from ....models_rag import RagRetrievalLog

_log = logging.getLogger(__name__)

# In-memory LRU cache for customer names (refreshed every 5 minutes)
_customer_name_cache: dict[int, str] = {}
_customer_name_cache_state = {"ts": 0.0}
_customer_name_cache_lock = threading.Lock()
_CUSTOMER_NAME_CACHE_TTL = 300  # seconds


def _batch_resolve_customer_names(customer_ids: list[int]) -> dict[int, str]:
    """Batch resolve customer IDs to names, with in-memory cache."""
    if not customer_ids:
        return {}
    import time
    now = time.time()
    result: dict[int, str] = {}
    missing: list[int] = []

    with _customer_name_cache_lock:
        expired = (now - _customer_name_cache_state["ts"]) > _CUSTOMER_NAME_CACHE_TTL
        if expired:
            _customer_name_cache.clear()
            _customer_name_cache_state["ts"] = now
        for cid in customer_ids:
            if cid in _customer_name_cache:
                result[cid] = _customer_name_cache[cid]
            else:
                missing.append(cid)

    if not missing:
        return result

    try:
        from ....clients.crm_db import get_connection, return_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                placeholders = ",".join(["%s"] * len(missing))
                cur.execute(
                    f"SELECT id, name FROM customers WHERE id IN ({placeholders})",
                    tuple(missing),
                )
                with _customer_name_cache_lock:
                    for row in cur.fetchall():
                        name = row["name"] or ""
                        result[row["id"]] = name
                        _customer_name_cache[row["id"]] = name
        finally:
            return_connection(conn)
    except Exception:
        _log.debug("Failed to resolve customer names from CRM", exc_info=True)
    return result


def _batch_resolve_user_names(user_ids: list[int]) -> dict[int, str]:
    """Batch resolve local user IDs to display names."""
    if not user_ids:
        return {}
    db = SessionLocal()
    try:
        rows = db.query(LocalUser.id, LocalUser.display_name).filter(LocalUser.id.in_(user_ids)).all()
        return {r.id: r.display_name or r.username if hasattr(r, 'username') else r.display_name or "" for r in rows}
    except Exception:
        _log.debug("Failed to resolve user names", exc_info=True)
        return {}
    finally:
        db.close()


def _batch_fetch_user_message_previews(
    db, message_ids: list[str], max_len: int = 80
) -> dict[str, str]:
    """Batch fetch user message content previews by message_id."""
    if not message_ids:
        return {}
    try:
        rows = (
            db.query(CrmAiMessage.message_id, CrmAiMessage.content)
            .filter(CrmAiMessage.message_id.in_(message_ids))
            .all()
        )
        result = {}
        for r in rows:
            if r.content:
                preview = r.content.replace("\n", " ").strip()
                result[r.message_id] = preview[:max_len] + ("..." if len(preview) > max_len else "")
        return result
    except Exception:
        _log.debug("Failed to fetch user message previews", exc_info=True)
        return {}


def query_invocations(
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    error_code: str | None = None,
    crm_customer_id: int | None = None,
    local_user_id: int | None = None,
    primary_model: str | None = None,
    scene_key: str | None = None,
    session_id: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
) -> tuple[list[dict], int]:
    db = SessionLocal()
    try:
        q = db.query(CrmAiInvocation)
        if status:
            q = q.filter(CrmAiInvocation.status == status)
        if error_code:
            q = q.filter(CrmAiInvocation.error_code == error_code)
        if crm_customer_id:
            q = q.filter(CrmAiInvocation.crm_customer_id == crm_customer_id)
        if local_user_id:
            q = q.filter(CrmAiInvocation.local_user_id == local_user_id)
        if primary_model:
            q = q.filter(CrmAiInvocation.primary_model == primary_model)
        if scene_key:
            q = q.filter(CrmAiInvocation.scene_key == scene_key)
        if session_id:
            q = q.filter(CrmAiInvocation.session_id == session_id)
        if date_start:
            q = q.filter(CrmAiInvocation.started_at >= date_start)
        if date_end:
            q = q.filter(CrmAiInvocation.started_at <= date_end)

        total = q.count()
        rows = (
            q.order_by(CrmAiInvocation.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = [_invocation_to_dict(r) for r in rows]
        # Batch resolve customer names
        cids = list({r.crm_customer_id for r in rows if r.crm_customer_id})
        name_map = _batch_resolve_customer_names(cids)
        # Batch resolve user names
        uids = list({r.local_user_id for r in rows if r.local_user_id})
        user_map = _batch_resolve_user_names(uids)
        # Batch fetch user message previews
        msg_map = _batch_fetch_user_message_previews(
            db, [r.user_message_id for r in rows if r.user_message_id]
        )
        for item in items:
            item["crm_customer_name"] = name_map.get(item.get("crm_customer_id"), "")
            item["local_user_name"] = user_map.get(item.get("local_user_id"), "")
            item["user_message_preview"] = msg_map.get(item.get("user_message_id"))
        return items, total
    except Exception:
        _log.exception("Failed to query invocations")
        return [], 0
    finally:
        db.close()


def find_invocation_by_message_id(message_id: str) -> str | None:
    """Find call_id by assistant_message_id. Returns call_id or None."""
    db = SessionLocal()
    try:
        inv = db.query(CrmAiInvocation).filter_by(assistant_message_id=message_id).first()
        return inv.call_id if inv else None
    except Exception:
        _log.exception("Failed to find invocation by message_id %s", message_id)
        return None
    finally:
        db.close()


def get_invocation_detail(call_id: str) -> dict | None:
    db = SessionLocal()
    try:
        inv = db.query(CrmAiInvocation).filter_by(call_id=call_id).first()
        if not inv:
            return None
        steps = (
            db.query(CrmAiTraceStep)
            .filter_by(call_id=call_id)
            .order_by(CrmAiTraceStep.step_index)
            .all()
        )
        result = _invocation_to_dict(inv)
        result["steps"] = [_step_to_dict(s) for s in steps]
        # Resolve customer name
        if inv.crm_customer_id:
            name_map = _batch_resolve_customer_names([inv.crm_customer_id])
            result["crm_customer_name"] = name_map.get(inv.crm_customer_id, "")
        # Resolve user name
        if inv.local_user_id:
            user_map = _batch_resolve_user_names([inv.local_user_id])
            result["local_user_name"] = user_map.get(inv.local_user_id, "")

        # Fetch user message
        result["user_message"] = None
        if inv.user_message_id:
            umsg = db.query(CrmAiMessage).filter_by(message_id=inv.user_message_id).first()
            if umsg:
                result["user_message"] = {
                    "message_id": umsg.message_id,
                    "content": umsg.content,
                    "request_params": _safe_json(umsg.request_params_json),
                    "created_at": _to_beijing_time(umsg.created_at),
                }

        # Fetch assistant message
        result["assistant_message"] = None
        if inv.assistant_message_id:
            amsg = db.query(CrmAiMessage).filter_by(message_id=inv.assistant_message_id).first()
            if amsg:
                result["assistant_message"] = {
                    "message_id": amsg.message_id,
                    "content": amsg.content,
                    "model": amsg.model,
                    "token_usage": {
                        "prompt_tokens": amsg.prompt_tokens,
                        "completion_tokens": amsg.completion_tokens,
                    },
                    "safety_result": _safe_json(amsg.safety_result),
                    "requires_medical_review": amsg.requires_medical_review,
                    "created_at": _to_beijing_time(amsg.created_at),
                }

        # Fetch RAG retrieval logs
        result["rag_logs"] = []
        if inv.call_id:
            rag_rows = db.query(RagRetrievalLog).filter_by(call_id=inv.call_id).all()
            for r in rag_rows:
                result["rag_logs"].append({
                    "query_text": r.query_text,
                    "hit_json": _safe_json(r.hit_json),
                    "latency_ms": r.latency_ms,
                    "created_at": _to_beijing_time(r.created_at),
                })

        return result
    except Exception:
        _log.exception("Failed to get invocation detail for %s", call_id)
        return None
    finally:
        db.close()


def get_invocation_stats(
    *,
    date_start: str | None = None,
    date_end: str | None = None,
) -> dict:
    db = SessionLocal()
    try:
        # Single query: conditional aggregation in one pass
        base_filters = []
        if date_start:
            base_filters.append(CrmAiInvocation.started_at >= date_start)
        if date_end:
            base_filters.append(CrmAiInvocation.started_at <= date_end)

        agg_row = (
            db.query(
                func.count(CrmAiInvocation.id).label("total"),
                func.sum(func.cast(CrmAiInvocation.status == "success", type_=Integer)).label("success_count"),
                func.sum(func.cast(CrmAiInvocation.status == "error", type_=Integer)).label("error_count"),
                func.avg(
                    case(
                        (CrmAiInvocation.status != "pending", CrmAiInvocation.latency_ms),
                        else_=None,
                    )
                ).label("avg_latency_ms"),
                func.sum(
                    case(
                        (CrmAiInvocation.status != "pending", CrmAiInvocation.total_tokens),
                        else_=0,
                    )
                ).label("total_tokens"),
            )
            .filter(*base_filters)
            .one()
        )

        total = agg_row.total or 0
        success = agg_row.success_count or 0
        error = agg_row.error_count or 0

        errors_by_code = (
            db.query(CrmAiInvocation.error_code, func.count(CrmAiInvocation.id))
            .filter(CrmAiInvocation.error_code.isnot(None))
            .filter(*base_filters)
            .group_by(CrmAiInvocation.error_code)
            .order_by(func.count(CrmAiInvocation.id).desc())
            .limit(10)
            .all()
        )

        return {
            "total": total,
            "success_count": success,
            "error_count": error,
            "error_rate": round(error / total, 4) if total else 0,
            "avg_latency_ms": round(agg_row.avg_latency_ms or 0, 1),
            "total_tokens": agg_row.total_tokens or 0,
            "errors_by_code": [{"code": code, "count": cnt} for code, cnt in errors_by_code],
        }
    except Exception:
        _log.exception("Failed to get invocation stats")
        return {"total": 0, "success_count": 0, "error_count": 0,
                "error_rate": 0, "avg_latency_ms": 0, "total_tokens": 0,
                "errors_by_code": []}
    finally:
        db.close()


def get_invocation_trends(
    *,
    days: int = 14,
    date_start: str | None = None,
    date_end: str | None = None,
) -> list[dict]:
    """Return daily aggregated stats for the given date range."""
    db = SessionLocal()
    try:
        if not date_start:
            date_start = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        if not date_end:
            date_end = datetime.utcnow().strftime("%Y-%m-%d")

        rows = (
            db.query(
                cast(CrmAiInvocation.started_at, Date).label("day"),
                func.count(CrmAiInvocation.id).label("total"),
                func.sum(func.cast(CrmAiInvocation.status == "success", type_=Integer)).label("success_count"),
                func.sum(func.cast(CrmAiInvocation.status == "error", type_=Integer)).label("error_count"),
                func.avg(CrmAiInvocation.latency_ms).label("avg_latency_ms"),
                func.sum(CrmAiInvocation.total_tokens).label("total_tokens"),
            )
            .filter(CrmAiInvocation.started_at >= date_start)
            .filter(CrmAiInvocation.started_at <= date_end + " 23:59:59")
            .group_by(cast(CrmAiInvocation.started_at, Date))
            .order_by(cast(CrmAiInvocation.started_at, Date))
            .all()
        )

        return [
            {
                "date": str(r.day) if r.day else "",
                "total": r.total,
                "success_count": r.success_count or 0,
                "error_count": r.error_count or 0,
                "avg_latency_ms": round(r.avg_latency_ms or 0, 1),
                "total_tokens": r.total_tokens or 0,
            }
            for r in rows
        ]
    except Exception:
        _log.exception("Failed to get invocation trends")
        return []
    finally:
        db.close()


def get_invocation_breakdown(
    *,
    dimension: str = "model",
    date_start: str | None = None,
    date_end: str | None = None,
) -> list[dict]:
    """Return breakdown by model, error_code, scene, or provider."""
    col_map = {
        "model": CrmAiInvocation.primary_model,
        "error_code": CrmAiInvocation.error_code,
        "scene": CrmAiInvocation.scene_key,
        "provider": CrmAiInvocation.primary_provider,
    }
    col = col_map.get(dimension, CrmAiInvocation.primary_model)

    db = SessionLocal()
    try:
        q = db.query(
            col.label("key"),
            func.count(CrmAiInvocation.id).label("total"),
            func.sum(func.cast(CrmAiInvocation.status == "success", type_=Integer)).label("success_count"),
            func.sum(func.cast(CrmAiInvocation.status == "error", type_=Integer)).label("error_count"),
            func.avg(CrmAiInvocation.latency_ms).label("avg_latency_ms"),
            func.sum(CrmAiInvocation.total_tokens).label("total_tokens"),
        )
        if date_start:
            q = q.filter(CrmAiInvocation.started_at >= date_start)
        if date_end:
            q = q.filter(CrmAiInvocation.started_at <= date_end)
        rows = q.group_by(col).order_by(func.count(CrmAiInvocation.id).desc()).limit(20).all()

        return [
            {
                "key": r.key or "(空)",
                "total": r.total,
                "success_count": r.success_count or 0,
                "error_count": r.error_count or 0,
                "avg_latency_ms": round(r.avg_latency_ms or 0, 1),
                "total_tokens": r.total_tokens or 0,
            }
            for r in rows
        ]
    except Exception:
        _log.exception("Failed to get invocation breakdown")
        return []
    finally:
        db.close()


def _to_beijing_time(dt) -> str | None:
    """Convert UTC datetime to Beijing time ISO string."""
    if not dt:
        return None
    from datetime import timezone, timedelta
    bj = timezone(timedelta(hours=8))
    return dt.replace(tzinfo=timezone.utc).astimezone(bj).strftime("%Y-%m-%d %H:%M:%S")


def _safe_json(raw: str | None) -> any:
    """Parse JSON string safely."""
    if not raw:
        return None
    import json
    try:
        return json.loads(raw)
    except Exception:
        return raw


def _invocation_to_dict(inv: CrmAiInvocation) -> dict:
    return {
        "call_id": inv.call_id,
        "session_id": inv.session_id,
        "user_message_id": inv.user_message_id,
        "assistant_message_id": inv.assistant_message_id,
        "execution_mode": inv.execution_mode,
        "local_user_id": inv.local_user_id,
        "crm_admin_id": inv.crm_admin_id,
        "crm_customer_id": inv.crm_customer_id,
        "entry_scene": inv.entry_scene,
        "scene_key": inv.scene_key,
        "output_style": inv.output_style,
        "prompt_version": inv.prompt_version,
        "status": inv.status,
        "error_stage": inv.error_stage,
        "error_code": inv.error_code,
        "error_message": inv.error_message,
        "error_detail": inv.error_detail,
        "rag_status": inv.rag_status,
        "rag_hit_count": inv.rag_hit_count,
        "total_tokens": inv.total_tokens,
        "primary_model": inv.primary_model,
        "primary_provider": inv.primary_provider,
        "step_count": inv.step_count,
        "latency_ms": inv.latency_ms,
        "first_token_ms": inv.first_token_ms,
        "prepare_ms": inv.prepare_ms,
        "diagnostics_json": inv.diagnostics_json,
        "started_at": _to_beijing_time(inv.started_at),
        "finished_at": _to_beijing_time(inv.finished_at),
    }


def _step_to_dict(step: CrmAiTraceStep) -> dict:
    return {
        "step_index": step.step_index,
        "parent_step_index": step.parent_step_index,
        "kind": step.kind,
        "name": step.name,
        "status": step.status,
        "error_code": step.error_code,
        "error_message": step.error_message,
        "latency_ms": step.latency_ms,
        "model": step.model,
        "prompt_tokens": step.prompt_tokens,
        "completion_tokens": step.completion_tokens,
        "cached_tokens": step.cached_tokens,
        "tool_name": step.tool_name,
        "started_at": _to_beijing_time(step.started_at),
        "finished_at": _to_beijing_time(step.finished_at),
    }
