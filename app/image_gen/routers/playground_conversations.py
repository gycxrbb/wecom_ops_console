"""playground agent 对话持久化（Bearer 鉴权，强制按本人）。

供 gpt_image_playground 的存储适配层(serverStorage.ts)调用。后端为真值，
playground 本地 IndexedDB 降级为缓存。走裸 JSON（不包装），与 proxy.py 一致——
playground fetch 期望 OpenAI 兼容风格的裸响应。
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user

from ..models import PlaygroundConversation
from ..schemas.playground_storage import ConversationUpsertRequest, ConversationUpdateRequest

router = APIRouter()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def _fmt_dt(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def _get_owned(request: Request, db: Session, conversation_id: str, *, include_deleted: bool = False) -> PlaygroundConversation:
    """取当前用户名下的对话；不存在或他人对话统一 404（不暴露存在性）。"""
    user = get_current_user(request, db)
    conv = (
        db.query(PlaygroundConversation)
        .filter(
            PlaygroundConversation.conversation_id == conversation_id,
            PlaygroundConversation.owner_user_id == user.id,
        )
        .first()
    )
    if not conv or (not include_deleted and conv.deleted_at is not None):
        raise HTTPException(404, "对话不存在")
    return conv


@router.get("/conversations")
def list_conversations(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出当前用户的对话摘要（按 last_active_at 倒序，不含 data_json）。"""
    user = get_current_user(request, db)
    q = db.query(PlaygroundConversation).filter(
        PlaygroundConversation.owner_user_id == user.id,
        PlaygroundConversation.deleted_at.is_(None),
    )
    total = q.count()
    rows = (
        q.order_by(PlaygroundConversation.last_active_at.desc(), PlaygroundConversation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [
            {
                "conversation_id": c.conversation_id,
                "title": c.title,
                "auto_title": c.auto_title,
                "last_active_at": _fmt_dt(c.last_active_at),
                "updated_at": _fmt_dt(c.updated_at),
            }
            for c in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, request: Request, db: Session = Depends(get_db)):
    """取整条对话（含 data_json）——点击进入对话时拉取。"""
    conv = _get_owned(request, db, conversation_id)
    return {
        "conversation_id": conv.conversation_id,
        "title": conv.title,
        "auto_title": conv.auto_title,
        "data_json": conv.data_json,
        "last_active_at": _fmt_dt(conv.last_active_at),
        "created_at": _fmt_dt(conv.created_at),
        "updated_at": _fmt_dt(conv.updated_at),
    }


@router.put("/conversations/{conversation_id}")
def upsert_conversation(
    conversation_id: str,
    body: ConversationUpsertRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """upsert 整条对话（新建/更新；已软删的会被复活）。同步主入口。"""
    user = get_current_user(request, db)
    conv = (
        db.query(PlaygroundConversation)
        .filter(
            PlaygroundConversation.conversation_id == conversation_id,
            PlaygroundConversation.owner_user_id == user.id,
        )
        .first()
    )
    now = datetime.utcnow()
    last_active = _parse_dt(body.last_active_at) or now
    if conv:
        if body.title is not None:
            conv.title = body.title
        if body.auto_title is not None:
            conv.auto_title = body.auto_title
        conv.data_json = body.data_json
        conv.last_active_at = last_active
        conv.deleted_at = None  # 复活
    else:
        conv = PlaygroundConversation(
            conversation_id=conversation_id,
            owner_user_id=user.id,
            title=body.title or "",
            auto_title=body.auto_title,
            data_json=body.data_json,
            last_active_at=last_active,
        )
        db.add(conv)
    db.commit()
    return {"conversation_id": conversation_id, "ok": True}


@router.patch("/conversations/{conversation_id}")
def update_conversation(
    conversation_id: str,
    body: ConversationUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """重命名对话。"""
    conv = _get_owned(request, db, conversation_id)
    if body.title is not None:
        conv.title = body.title
    db.commit()
    return {"conversation_id": conversation_id, "title": conv.title}


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, request: Request, db: Session = Depends(get_db)):
    """软删对话（playground 端删除同步）。"""
    conv = _get_owned(request, db, conversation_id, include_deleted=True)
    conv.deleted_at = datetime.utcnow()
    db.commit()
    return {"conversation_id": conversation_id, "deleted": True}
