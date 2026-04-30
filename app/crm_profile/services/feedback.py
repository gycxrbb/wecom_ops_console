"""AI message feedback service — submit / query like/dislike feedback."""
from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import CrmAiMessage, CrmAiMessageFeedback, CrmAiSession

_log = logging.getLogger(__name__)

_TXT_CODE_BLOCK_RE = re.compile(r"```txt\s*\n(.*?)```", re.DOTALL)


def _extract_customer_reply(ai_answer: str) -> str | None:
    """Extract the content of the first ```txt ... ``` code block."""
    m = _TXT_CODE_BLOCK_RE.search(ai_answer)
    if m:
        return m.group(1).strip()
    return None


def submit_feedback(
    db: Session,
    *,
    customer_id: int,
    message_id: str,
    coach_user_id: int,
    crm_admin_id: int | None,
    rating: str,
    reason_category: str | None = None,
    reason_text: str | None = None,
    expected_answer: str | None = None,
) -> CrmAiMessageFeedback:
    """Create or update feedback for an AI assistant message."""
    ai_msg = (
        db.query(CrmAiMessage)
        .filter(CrmAiMessage.message_id == message_id)
        .first()
    )
    if not ai_msg:
        raise ValueError("消息不存在")
    if ai_msg.role != "assistant":
        raise ValueError("只能对 AI 回复进行反馈")

    session_id = ai_msg.session_id

    # Find previous user message for snapshot
    prev_messages = (
        db.query(CrmAiMessage)
        .filter(CrmAiMessage.session_id == session_id)
        .order_by(CrmAiMessage.created_at.asc(), CrmAiMessage.id.asc())
        .all()
    )
    user_question = ""
    user_message_id = None
    for i, m in enumerate(prev_messages):
        if m.message_id == message_id and i > 0:
            for j in range(i - 1, -1, -1):
                if prev_messages[j].role == "user":
                    user_question = prev_messages[j].content or ""
                    user_message_id = prev_messages[j].message_id
                    break
            break

    # Session context
    session = db.query(CrmAiSession).filter(CrmAiSession.session_id == session_id).first()

    # Upsert: same message_id + coach_user_id
    existing = (
        db.query(CrmAiMessageFeedback)
        .filter(
            CrmAiMessageFeedback.message_id == message_id,
            CrmAiMessageFeedback.coach_user_id == coach_user_id,
        )
        .first()
    )

    customer_reply = _extract_customer_reply(ai_msg.content or "")

    if existing:
        existing.rating = rating
        existing.reason_category = reason_category
        existing.reason_text = reason_text
        existing.expected_answer = expected_answer
        existing.customer_reply_snapshot = customer_reply
        existing.ai_answer_snapshot = ai_msg.content
        existing.user_question_snapshot = user_question
        existing.user_message_id = user_message_id
        db.commit()
        db.refresh(existing)
        return existing

    fb = CrmAiMessageFeedback(
        feedback_id=str(uuid.uuid4()),
        session_id=session_id,
        message_id=message_id,
        user_message_id=user_message_id,
        crm_customer_id=customer_id,
        coach_user_id=coach_user_id,
        crm_admin_id=crm_admin_id,
        rating=rating,
        reason_category=reason_category,
        reason_text=reason_text,
        expected_answer=expected_answer,
        user_question_snapshot=user_question,
        ai_answer_snapshot=ai_msg.content,
        customer_reply_snapshot=customer_reply,
        scene_key=session.scene_key if session else None,
        output_style=session.output_style if session else None,
        prompt_version=session.prompt_version if session else None,
        prompt_hash=session.prompt_hash if session else None,
        model=ai_msg.model,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


def get_message_feedback(
    db: Session,
    message_id: str,
    coach_user_id: int,
) -> CrmAiMessageFeedback | None:
    return (
        db.query(CrmAiMessageFeedback)
        .filter(
            CrmAiMessageFeedback.message_id == message_id,
            CrmAiMessageFeedback.coach_user_id == coach_user_id,
        )
        .first()
    )


def load_feedbacks_for_messages(
    db: Session,
    message_ids: list[str],
    coach_user_id: int,
) -> dict[str, CrmAiMessageFeedback]:
    """Bulk-load feedback for a list of message IDs. Returns {message_id: feedback}."""
    if not message_ids:
        return {}
    rows = (
        db.query(CrmAiMessageFeedback)
        .filter(
            CrmAiMessageFeedback.message_id.in_(message_ids),
            CrmAiMessageFeedback.coach_user_id == coach_user_id,
        )
        .all()
    )
    return {r.message_id: r for r in rows}


# ---------------------------------------------------------------------------
# Admin helpers
# ---------------------------------------------------------------------------

_VALID_STATUSES = {"new", "reviewed", "used_for_prompt", "ignored"}


def list_feedbacks_admin(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    rating: str | None = None,
    reason_category: str | None = None,
    status: str | None = None,
    scene_key: str | None = None,
    coach_user_id: int | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
) -> tuple[list[CrmAiMessageFeedback], int]:
    q = db.query(CrmAiMessageFeedback)
    if rating:
        q = q.filter(CrmAiMessageFeedback.rating == rating)
    if reason_category:
        q = q.filter(CrmAiMessageFeedback.reason_category == reason_category)
    if status:
        q = q.filter(CrmAiMessageFeedback.status == status)
    if scene_key:
        q = q.filter(CrmAiMessageFeedback.scene_key == scene_key)
    if coach_user_id is not None:
        q = q.filter(CrmAiMessageFeedback.coach_user_id == coach_user_id)
    if date_start:
        q = q.filter(CrmAiMessageFeedback.created_at >= date_start)
    if date_end:
        q = q.filter(CrmAiMessageFeedback.created_at < date_end)
    total = q.count()
    items = (
        q.order_by(CrmAiMessageFeedback.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_feedback_detail(db: Session, feedback_id: str) -> CrmAiMessageFeedback | None:
    return db.query(CrmAiMessageFeedback).filter(CrmAiMessageFeedback.feedback_id == feedback_id).first()


def update_feedback_status(
    db: Session,
    feedback_id: str,
    *,
    status: str,
    admin_note: str | None = None,
) -> CrmAiMessageFeedback:
    fb = get_feedback_detail(db, feedback_id)
    if not fb:
        raise ValueError("反馈不存在")
    if status not in _VALID_STATUSES:
        raise ValueError(f"无效状态: {status}")
    fb.status = status
    if admin_note is not None:
        fb.admin_note = admin_note
    db.commit()
    db.refresh(fb)
    return fb


def get_feedback_stats(db: Session, *, date_start: str | None = None, date_end: str | None = None) -> dict:
    base = db.query(CrmAiMessageFeedback)
    if date_start:
        base = base.filter(CrmAiMessageFeedback.created_at >= date_start)
    if date_end:
        base = base.filter(CrmAiMessageFeedback.created_at < date_end)

    total = base.count()
    like_count = base.filter(CrmAiMessageFeedback.rating == "like").count()
    dislike_count = base.filter(CrmAiMessageFeedback.rating == "dislike").count()

    def _group(field):
        rows = base.with_entities(field, func.count(CrmAiMessageFeedback.id)).group_by(field).all()
        return [{"key": r[0] or "(空)", "count": r[1]} for r in rows]

    return {
        "total": total,
        "like_count": like_count,
        "dislike_count": dislike_count,
        "dislike_rate": round(dislike_count / total, 4) if total else 0.0,
        "by_reason": _group(CrmAiMessageFeedback.reason_category),
        "by_scene": _group(CrmAiMessageFeedback.scene_key),
        "by_prompt_version": _group(CrmAiMessageFeedback.prompt_version),
    }
