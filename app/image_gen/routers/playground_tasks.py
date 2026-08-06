"""playground 生图任务持久化（Bearer 鉴权，强制按本人）。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user

from ..models import PlaygroundTask
from ..schemas.playground_storage import TaskUpsertRequest

router = APIRouter()


def _fmt_dt(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def _get_owned_task(request: Request, db: Session, task_id: str) -> PlaygroundTask:
    user = get_current_user(request, db)
    task = (
        db.query(PlaygroundTask)
        .filter(
            PlaygroundTask.task_id == task_id,
            PlaygroundTask.owner_user_id == user.id,
        )
        .first()
    )
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


@router.get("/tasks")
def list_tasks(
    request: Request,
    db: Session = Depends(get_db),
    conversation_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出当前用户的任务（按 created_at 倒序，可选按对话过滤）。"""
    user = get_current_user(request, db)
    q = db.query(PlaygroundTask).filter(PlaygroundTask.owner_user_id == user.id)
    if conversation_id:
        q = q.filter(PlaygroundTask.conversation_id == conversation_id)
    total = q.count()
    rows = (
        q.order_by(PlaygroundTask.created_at.desc(), PlaygroundTask.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [
            {
                "task_id": t.task_id,
                "conversation_id": t.conversation_id,
                "created_at": _fmt_dt(t.created_at),
            }
            for t in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/tasks/{task_id}")
def get_task(task_id: str, request: Request, db: Session = Depends(get_db)):
    """取整条任务（含 data_json）。"""
    task = _get_owned_task(request, db, task_id)
    return {
        "task_id": task.task_id,
        "conversation_id": task.conversation_id,
        "data_json": task.data_json,
        "created_at": _fmt_dt(task.created_at),
    }


@router.put("/tasks/{task_id}")
def upsert_task(
    task_id: str,
    body: TaskUpsertRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """upsert 任务（新建/更新）。"""
    user = get_current_user(request, db)
    task = (
        db.query(PlaygroundTask)
        .filter(
            PlaygroundTask.task_id == task_id,
            PlaygroundTask.owner_user_id == user.id,
        )
        .first()
    )
    created = _parse_dt(body.created_at)
    if task:
        task.conversation_id = body.conversation_id
        task.data_json = body.data_json
        if created:
            task.created_at = created
    else:
        task = PlaygroundTask(
            task_id=task_id,
            owner_user_id=user.id,
            conversation_id=body.conversation_id,
            data_json=body.data_json,
            created_at=created or datetime.utcnow(),
        )
        db.add(task)
    db.commit()
    return {"task_id": task_id, "ok": True}


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str, request: Request, db: Session = Depends(get_db)):
    """硬删任务。"""
    task = _get_owned_task(request, db, task_id)
    db.delete(task)
    db.commit()
    return {"task_id": task_id, "deleted": True}
