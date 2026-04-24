from __future__ import annotations
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import UPLOAD_DIR
from ..security import get_current_user, hash_password, verify_password
from ..route_helper import _dt
from .. import models

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])

AVATAR_DIR = UPLOAD_DIR / "avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_AVATAR_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024


class ProfileUpdateBody(BaseModel):
    display_name: str = Field(default="", max_length=64)


class PasswordUpdateBody(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)


def _serialize_profile(user: models.User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "avatar_url": user.avatar_url or "",
        "role": user.role,
        "status": bool(user.status),
        "auth_source": user.auth_source or "local",
        "last_login_at": _dt(user.last_login_at),
        "created_at": _dt(user.created_at),
        "password_change_available": (user.auth_source or "local") == "local",
    }


@router.get("")
def get_profile(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return _serialize_profile(user)


@router.put("")
async def update_profile(body: ProfileUpdateBody, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    display_name = body.display_name.strip() or user.username
    user.display_name = display_name
    db.commit()
    db.refresh(user)
    return _serialize_profile(user)


@router.post("/avatar")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if file.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(400, "仅支持 JPG、PNG、WEBP、GIF 图片")

    content = await file.read()
    if not content:
        raise HTTPException(400, "上传文件为空")
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(400, "头像大小不能超过 2 MB")

    ext = ALLOWED_AVATAR_TYPES[file.content_type]
    filename = f"user-{user.id}-{uuid4().hex}{ext}"
    target_path = AVATAR_DIR / filename
    target_path.write_bytes(content)

    old_avatar_url = user.avatar_url or ""
    user.avatar_url = f"/uploads/avatars/{filename}"
    db.commit()
    db.refresh(user)

    if old_avatar_url.startswith("/uploads/avatars/"):
        old_path = UPLOAD_DIR / old_avatar_url.replace("/uploads/", "")
        if old_path.exists() and old_path.is_file():
            old_path.unlink(missing_ok=True)

    return {"avatar_url": user.avatar_url, "profile": _serialize_profile(user)}


@router.post("/password")
async def update_password(body: PasswordUpdateBody, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if (user.auth_source or "local") != "local":
        raise HTTPException(400, "当前账号密码由 CRM 统一管理，请前往 CRM 后台修改")
    if body.new_password != body.confirm_password:
        raise HTTPException(400, "两次输入的新密码不一致")
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "当前密码不正确")
    if body.current_password == body.new_password:
        raise HTTPException(400, "新密码不能与当前密码相同")

    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}
