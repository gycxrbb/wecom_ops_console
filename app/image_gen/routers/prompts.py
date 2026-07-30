"""内部提示词库 CRUD（playground 同源 fetch，裸 JSON，get_current_user 鉴权）。

挂 raw_api（前缀 /api/v1/image-gen），与 agent.py 同族。封面图走七牛（storage_facade）。
贡献者=当前登录用户；写操作限 owner 或 admin。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app.services.storage.base import UploadPayload
from app.services.storage.facade import storage_facade

from ..schemas.prompts import PromptCreate, PromptUpdate
from ..services import prompt_repo

router = APIRouter()
_MAX_COVER_BYTES = 5 * 1024 * 1024


def _check_owner_or_admin(user, row) -> None:
    if row.owner_user_id != user.id and getattr(user, "role", None) != "admin":
        raise HTTPException(403, "只能编辑/删除自己上传的提示词")


@router.get("/prompts")
def list_prompts(request: Request, category: str | None = None, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    rows = prompt_repo.list_prompts(db, category=category, operator_id=user.id)
    return {"items": [prompt_repo.serialize_with_contributor(db, r) for r in rows]}


@router.post("/prompts")
def create_prompt(body: PromptCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    row = prompt_repo.create_prompt(db, body, owner_id=user.id)
    return prompt_repo.serialize_with_contributor(db, row)


@router.put("/prompts/{prompt_id}")
def update_prompt(
    prompt_id: int, body: PromptUpdate, request: Request, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    row = prompt_repo.get_prompt(db, prompt_id)
    if not row:
        raise HTTPException(404, "提示词不存在")
    _check_owner_or_admin(user, row)
    row = prompt_repo.update_prompt(db, prompt_id, body)
    return prompt_repo.serialize_with_contributor(db, row)


@router.delete("/prompts/{prompt_id}")
def delete_prompt(prompt_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    row = prompt_repo.get_prompt(db, prompt_id)
    if not row:
        raise HTTPException(404, "提示词不存在")
    _check_owner_or_admin(user, row)
    prompt_repo.delete_prompt(db, prompt_id)
    return {"status": "ok"}


@router.post("/prompts/covers")
async def upload_cover(
    request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """封面图上传：multipart → 七牛 → 返回 cover_url。前端拿到 url 再随提示词 body 提交。"""
    get_current_user(request, db)
    raw = await file.read()
    if len(raw) > _MAX_COVER_BYTES:
        raise HTTPException(400, "封面图不能超过 5MB")
    ext = (file.filename or "cover.png").rsplit(".", 1)[-1].lower() or "png"
    object_key = f"image_gen/prompts/{uuid.uuid4().hex}.{ext}"
    result = storage_facade.upload(
        UploadPayload(
            content=raw,
            filename=file.filename or "cover.png",
            mime_type=file.content_type or "image/png",
            object_key=object_key,
        )
    )
    return {"cover_url": result.public_url}
