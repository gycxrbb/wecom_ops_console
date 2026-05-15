"""Session admin operations — rename, pin, delete, last_active_at, auto_title."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ....database import SessionLocal
from ...models import CrmAiSession

_log = logging.getLogger(__name__)


def _find_session(session_id: str) -> CrmAiSession | None:
    with SessionLocal() as db:
        return db.query(CrmAiSession).filter(CrmAiSession.session_id == session_id).first()


def rename_session(session_id: str, title: str) -> bool:
    with SessionLocal() as db:
        session = db.query(CrmAiSession).filter(CrmAiSession.session_id == session_id).first()
        if not session:
            return False
        session.title = title[:128] if title else None
        db.commit()
        return True


def toggle_pin(session_id: str, pinned: bool) -> bool:
    with SessionLocal() as db:
        session = db.query(CrmAiSession).filter(CrmAiSession.session_id == session_id).first()
        if not session:
            return False
        session.is_pinned = pinned
        session.pinned_at = datetime.now(timezone.utc) if pinned else None
        db.commit()
        return True


def soft_delete_session(session_id: str) -> bool:
    with SessionLocal() as db:
        session = db.query(CrmAiSession).filter(CrmAiSession.session_id == session_id).first()
        if not session:
            return False
        session.is_deleted = True
        session.deleted_at = datetime.now(timezone.utc)
        db.commit()
        return True


def touch_last_active(session_id: str) -> None:
    try:
        with SessionLocal() as db:
            session = db.query(CrmAiSession).filter(CrmAiSession.session_id == session_id).first()
            if session:
                session.last_active_at = datetime.now(timezone.utc)
                db.commit()
    except Exception:
        _log.debug("Failed to update last_active_at for %s", session_id, exc_info=True)


def set_auto_title(session_id: str, content: str) -> None:
    """Set auto_title from first user message content (truncated to 36 chars)."""
    if not content:
        return
    auto_title = content.strip().replace("\n", " ")[:36]
    if len(content.strip()) > 36:
        auto_title += "..."
    try:
        with SessionLocal() as db:
            session = db.query(CrmAiSession).filter(CrmAiSession.session_id == session_id).first()
            if session and not session.auto_title:
                session.auto_title = auto_title
                db.commit()
    except Exception:
        _log.debug("Failed to set auto_title for %s", session_id, exc_info=True)


def update_auto_title(session_id: str, auto_title: str) -> bool:
    """Overwrite auto_title (used by AI title generation)."""
    with SessionLocal() as db:
        session = db.query(CrmAiSession).filter(CrmAiSession.session_id == session_id).first()
        if not session:
            return False
        session.auto_title = auto_title[:128]
        db.commit()
        return True
