"""Audit logging for CRM AI coach interactions."""
from __future__ import annotations

import hashlib
import logging
from collections import defaultdict

from ...database import SessionLocal
from ..models import CrmAiSession, CrmAiMessage, CrmAiContextSnapshot, CrmAiGuardrailEvent

_log = logging.getLogger(__name__)


def write_session(session_id: str, local_user_id: int, crm_customer_id: int,
                  crm_admin_id: int | None = None, entry_scene: str = "customer_profile"):
    db = SessionLocal()
    try:
        db.add(CrmAiSession(
            session_id=session_id,
            local_user_id=local_user_id,
            crm_admin_id=crm_admin_id,
            crm_customer_id=crm_customer_id,
            entry_scene=entry_scene,
        ))
        db.commit()
    except Exception:
        _log.exception("Failed to write audit session")
        db.rollback()
    finally:
        db.close()


def write_message(session_id: str, message_id: str, role: str,
                  content: str, model: str = "",
                  prompt_tokens: int = 0, completion_tokens: int = 0,
                  latency_ms: int = 0, requires_medical_review: bool = False):
    db = SessionLocal()
    try:
        db.add(CrmAiMessage(
            session_id=session_id,
            message_id=message_id,
            role=role,
            content=content,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            requires_medical_review=requires_medical_review,
        ))
        db.commit()
    except Exception:
        _log.exception("Failed to write audit message")
        db.rollback()
    finally:
        db.close()


def write_context_snapshot(session_id: str, context_json: str,
                           used_modules: list[str]):
    context_hash = hashlib.sha256(context_json.encode()).hexdigest()
    db = SessionLocal()
    try:
        db.add(CrmAiContextSnapshot(
            session_id=session_id,
            context_hash=context_hash,
            compact_json=context_json,
            used_modules=",".join(used_modules),
        ))
        db.commit()
    except Exception:
        _log.exception("Failed to write context snapshot")
        db.rollback()
    finally:
        db.close()


def write_guardrail_event(session_id: str, event_type: str, detail: str = ""):
    db = SessionLocal()
    try:
        db.add(CrmAiGuardrailEvent(
            session_id=session_id,
            event_type=event_type,
            detail=detail,
        ))
        db.commit()
    except Exception:
        _log.exception("Failed to write guardrail event")
        db.rollback()
    finally:
        db.close()


def load_session_messages(session_id: str, limit: int = 10) -> list[dict]:
    """Return recent messages for a session, ordered by creation time ascending."""
    db = SessionLocal()
    try:
        rows = (
            db.query(CrmAiMessage)
            .filter(CrmAiMessage.session_id == session_id)
            .order_by(CrmAiMessage.created_at.desc())
            .limit(limit)
            .all()
        )
        # Return in chronological order (oldest first)
        rows.reverse()
        return [{"role": r.role, "content": r.content} for r in rows]
    except Exception:
        _log.exception("Failed to load session messages")
        return []
    finally:
        db.close()


def _preview_text(content: str | None, limit: int = 36) -> str:
    text = (content or "").replace("\r", " ").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _serialize_token_usage(row: CrmAiMessage) -> dict[str, int]:
    return {
        "prompt_tokens": row.prompt_tokens or 0,
        "completion_tokens": row.completion_tokens or 0,
        "total_tokens": (row.prompt_tokens or 0) + (row.completion_tokens or 0),
    }


def load_customer_sessions(customer_id: int, limit: int = 20) -> list[dict]:
    """Return recent AI sessions for a customer with lightweight summary info."""
    db = SessionLocal()
    try:
        sessions = (
            db.query(CrmAiSession)
            .filter(CrmAiSession.crm_customer_id == customer_id)
            .order_by(CrmAiSession.created_at.desc(), CrmAiSession.id.desc())
            .limit(limit)
            .all()
        )
        if not sessions:
            return []

        session_ids = [row.session_id for row in sessions]
        message_rows = (
            db.query(CrmAiMessage)
            .filter(CrmAiMessage.session_id.in_(session_ids))
            .order_by(CrmAiMessage.created_at.desc(), CrmAiMessage.id.desc())
            .all()
        )

        counts: dict[str, int] = defaultdict(int)
        latest_by_session: dict[str, CrmAiMessage] = {}
        for row in message_rows:
            counts[row.session_id] += 1
            if row.session_id not in latest_by_session:
                latest_by_session[row.session_id] = row

        items: list[dict] = []
        for session in sessions:
            latest = latest_by_session.get(session.session_id)
            items.append({
                "session_id": session.session_id,
                "entry_scene": session.entry_scene,
                "started_at": str(session.created_at) if session.created_at else None,
                "last_message_at": str(latest.created_at) if latest and latest.created_at else (str(session.created_at) if session.created_at else None),
                "message_count": counts.get(session.session_id, 0),
                "last_message_preview": _preview_text(latest.content if latest else ""),
            })
        return items
    except Exception:
        _log.exception("Failed to load customer sessions")
        return []
    finally:
        db.close()


def load_session_detail(customer_id: int, session_id: str) -> dict | None:
    """Return one customer's full AI session detail with chronological messages."""
    db = SessionLocal()
    try:
        session = (
            db.query(CrmAiSession)
            .filter(
                CrmAiSession.crm_customer_id == customer_id,
                CrmAiSession.session_id == session_id,
            )
            .first()
        )
        if not session:
            return None

        rows = (
            db.query(CrmAiMessage)
            .filter(CrmAiMessage.session_id == session_id)
            .order_by(CrmAiMessage.created_at.asc(), CrmAiMessage.id.asc())
            .all()
        )

        messages = [{
            "message_id": row.message_id,
            "role": row.role,
            "content": row.content or "",
            "created_at": str(row.created_at) if row.created_at else None,
            "requires_medical_review": bool(row.requires_medical_review),
            "token_usage": _serialize_token_usage(row),
        } for row in rows]

        latest = rows[-1] if rows else None
        return {
            "session": {
                "session_id": session.session_id,
                "entry_scene": session.entry_scene,
                "started_at": str(session.created_at) if session.created_at else None,
                "last_message_at": str(latest.created_at) if latest and latest.created_at else (str(session.created_at) if session.created_at else None),
                "message_count": len(rows),
                "last_message_preview": _preview_text(latest.content if latest else ""),
            },
            "messages": messages,
        }
    except Exception:
        _log.exception("Failed to load session detail")
        return None
    finally:
        db.close()


def session_exists(session_id: str) -> bool:
    """Check whether a session exists in the DB."""
    db = SessionLocal()
    try:
        return db.query(CrmAiSession).filter(CrmAiSession.session_id == session_id).first() is not None
    except Exception:
        _log.exception("Failed to check session existence")
        return False
    finally:
        db.close()


def mark_medical_review(message_id: str) -> bool:
    """Set requires_medical_review = True for the given message. Returns True if found."""
    db = SessionLocal()
    try:
        msg = db.query(CrmAiMessage).filter(CrmAiMessage.message_id == message_id).first()
        if not msg:
            return False
        msg.requires_medical_review = True
        db.commit()
        return True
    except Exception:
        _log.exception("Failed to mark medical review")
        db.rollback()
        return False
    finally:
        db.close()
