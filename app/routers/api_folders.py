from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from .. import models
from .api import get_user_or_401, require_role

router = APIRouter(prefix='/api/v1/asset-folders', tags=['asset-folders'])


class FolderCreate(BaseModel):
    name: str

class FolderRename(BaseModel):
    name: str


def serialize_folder(folder: models.AssetFolder, asset_count: int = 0) -> dict:
    return {
        'id': folder.id,
        'name': folder.name,
        'sort_order': folder.sort_order,
        'asset_count': asset_count,
        'created_at': folder.created_at.isoformat(),
    }


@router.get('')
def list_folders(request: Request, db: Session = Depends(get_db)):
    get_user_or_401(request, db)
    folders = db.query(models.AssetFolder).order_by(models.AssetFolder.sort_order, models.AssetFolder.id).all()
    counts = dict(
        db.query(models.Material.folder_id, func.count(models.Material.id))
        .group_by(models.Material.folder_id)
        .all()
    )
    return [
        serialize_folder(f, counts.get(f.id, 0))
        for f in folders
    ]


@router.post('')
def create_folder(body: FolderCreate, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    name = body.name.strip()
    if not name:
        raise HTTPException(400, '文件夹名称不能为空')
    exists = db.query(models.AssetFolder).filter(models.AssetFolder.name == name).first()
    if exists:
        raise HTTPException(400, '同名文件夹已存在')
    max_order = db.query(func.max(models.AssetFolder.sort_order)).scalar() or 0
    folder = models.AssetFolder(name=name, sort_order=max_order + 1, owner_id=user.id)
    db.add(folder)
    db.commit()
    return serialize_folder(folder, 0)


@router.put('/{folder_id}')
def rename_folder(folder_id: int, body: FolderRename, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    folder = db.query(models.AssetFolder).filter(models.AssetFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(404, '文件夹不存在')
    name = body.name.strip()
    if not name:
        raise HTTPException(400, '文件夹名称不能为空')
    dup = db.query(models.AssetFolder).filter(models.AssetFolder.name == name, models.AssetFolder.id != folder_id).first()
    if dup:
        raise HTTPException(400, '同名文件夹已存在')
    folder.name = name
    db.commit()
    count = db.query(func.count(models.Material.id)).filter(models.Material.folder_id == folder_id).scalar()
    return serialize_folder(folder, count)


@router.delete('/{folder_id}')
def delete_folder(folder_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    folder = db.query(models.AssetFolder).filter(models.AssetFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(404, '文件夹不存在')
    count = db.query(func.count(models.Material.id)).filter(models.Material.folder_id == folder_id).scalar()
    if count > 0:
        raise HTTPException(400, f'该文件夹下还有 {count} 个素材，请先移动或删除')
    db.delete(folder)
    db.commit()
    return {'ok': True}
