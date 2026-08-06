"""playground 图片资产（七牛直传 + 按 image_id 查重，借鉴 ai_attachment）。

供 gpt_image_playground 把图片脱离 base64 上云。Bearer 鉴权，强制按本人。
直传流程：prepare（发凭证/查重）→ 前端 FormData POST 七牛 → confirm（记 image_id↔url）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app.services.storage import storage_facade

from ..models import PlaygroundAsset

router = APIRouter()


class AssetPrepareRequest(BaseModel):
    image_id: str  # playground 的 SHA-256 内容 hash
    mime_type: str = "image/png"


class AssetConfirmRequest(BaseModel):
    image_id: str
    object_key: str
    public_url: str
    thumb_url: str = ""
    width: int = 0
    height: int = 0
    source: str = "upload"  # upload / generated / mask


def _get_owned_asset(request: Request, db: Session, image_id: str) -> PlaygroundAsset:
    user = get_current_user(request, db)
    asset = (
        db.query(PlaygroundAsset)
        .filter(
            PlaygroundAsset.image_id == image_id,
            PlaygroundAsset.owner_user_id == user.id,
        )
        .first()
    )
    if not asset:
        raise HTTPException(404, "图片不存在")
    return asset


@router.get("/assets/{image_id}")
def get_asset(image_id: str, request: Request, db: Session = Depends(get_db)):
    """查图片 url（playground 显示侧按 image_id 换 url）。"""
    asset = _get_owned_asset(request, db, image_id)
    return {"image_id": asset.image_id, "public_url": asset.public_url, "thumb_url": asset.thumb_url}


@router.post("/assets/prepare")
def prepare_asset(body: AssetPrepareRequest, request: Request, db: Session = Depends(get_db)):
    """七牛直传凭证（先按 image_id 查重：已存在直接返回 url，跳过上传）。"""
    user = get_current_user(request, db)
    existing = (
        db.query(PlaygroundAsset)
        .filter(
            PlaygroundAsset.image_id == body.image_id,
            PlaygroundAsset.owner_user_id == user.id,
        )
        .first()
    )
    if existing:
        return {"mode": "existing", "public_url": existing.public_url, "thumb_url": existing.thumb_url}
    cred = storage_facade.prepare_client_upload(f"{body.image_id}.png", body.mime_type)
    if not cred:
        raise HTTPException(503, "对象存储未就绪，请联系管理员")
    return {"mode": "qiniu", **cred}


@router.post("/assets/confirm")
def confirm_asset(body: AssetConfirmRequest, request: Request, db: Session = Depends(get_db)):
    """确认直传，记录 image_id ↔ url（幂等：已存在则补全 url）。"""
    user = get_current_user(request, db)
    asset = (
        db.query(PlaygroundAsset)
        .filter(
            PlaygroundAsset.image_id == body.image_id,
            PlaygroundAsset.owner_user_id == user.id,
        )
        .first()
    )
    if asset:
        if body.public_url and not asset.public_url:
            asset.public_url = body.public_url
            asset.object_key = body.object_key
            asset.thumb_url = asset.thumb_url or body.thumb_url
            asset.width = asset.width or body.width
            asset.height = asset.height or body.height
            db.commit()
        return {"image_id": asset.image_id, "public_url": asset.public_url, "ok": True}
    asset = PlaygroundAsset(
        image_id=body.image_id,
        owner_user_id=user.id,
        source=body.source,
        object_key=body.object_key,
        public_url=body.public_url,
        thumb_url=body.thumb_url,
        width=body.width,
        height=body.height,
    )
    db.add(asset)
    db.commit()
    return {"image_id": body.image_id, "public_url": body.public_url, "ok": True}
