from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from .. import models
from .api import get_user_or_401, require_role

router = APIRouter(prefix='/api/v1/asset-folders', tags=['asset-folders'])

SYSTEM_EMOTION_FOLDER_NAME = '表情包'
SYSTEM_VOICE_FOLDER_NAME = '语音'


class FolderCreate(BaseModel):
    name: str
    parent_id: int | None = None

class FolderRename(BaseModel):
    name: str


class FolderMove(BaseModel):
    parent_id: int | None = None


def is_system_folder(folder: models.AssetFolder) -> bool:
    return folder.parent_id is None and folder.name in {SYSTEM_EMOTION_FOLDER_NAME, SYSTEM_VOICE_FOLDER_NAME}


def ensure_system_folders(db: Session) -> None:
    max_order = db.query(func.max(models.AssetFolder.sort_order)).scalar() or 0
    for name in [SYSTEM_EMOTION_FOLDER_NAME, SYSTEM_VOICE_FOLDER_NAME]:
        exists = db.query(models.AssetFolder).filter(
            models.AssetFolder.name == name,
            models.AssetFolder.parent_id == None,
        ).first()
        if exists:
            continue
        max_order += 1
        folder = models.AssetFolder(
            name=name,
            sort_order=max_order,
            parent_id=None,
            owner_id=None,
        )
        db.add(folder)
    db.commit()


def serialize_folder(folder: models.AssetFolder, asset_count: int = 0, child_count: int = 0) -> dict:
    return {
        'id': folder.id,
        'name': folder.name,
        'sort_order': folder.sort_order,
        'parent_id': folder.parent_id,
        'is_system': is_system_folder(folder),
        'asset_count': asset_count,
        'child_count': child_count,
        'created_at': folder.created_at.isoformat(),
    }


@router.get('')
def list_folders(request: Request, db: Session = Depends(get_db)):
    get_user_or_401(request, db)
    ensure_system_folders(db)
    folders = db.query(models.AssetFolder).order_by(models.AssetFolder.sort_order, models.AssetFolder.id).all()
    counts = dict(
        db.query(models.Material.folder_id, func.count(models.Material.id))
        .group_by(models.Material.folder_id)
        .all()
    )
    child_counts = dict(
        db.query(models.AssetFolder.parent_id, func.count(models.AssetFolder.id))
        .group_by(models.AssetFolder.parent_id)
        .all()
    )
    return [
        serialize_folder(f, counts.get(f.id, 0), child_counts.get(f.id, 0))
        for f in folders
    ]


@router.post('')
def create_folder(body: FolderCreate, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    ensure_system_folders(db)
    name = body.name.strip()
    parent_id = body.parent_id
    if not name:
        raise HTTPException(400, '文件夹名称不能为空')
    if parent_id is not None:
        parent = db.query(models.AssetFolder).filter(models.AssetFolder.id == parent_id).first()
        if not parent:
            raise HTTPException(404, '父文件夹不存在')
    exists = db.query(models.AssetFolder).filter(
        models.AssetFolder.name == name,
        models.AssetFolder.parent_id == parent_id
    ).first()
    if exists:
        raise HTTPException(400, '同级目录下已存在同名文件夹')
    max_order = db.query(func.max(models.AssetFolder.sort_order)).scalar() or 0
    folder = models.AssetFolder(name=name, sort_order=max_order + 1, parent_id=parent_id, owner_id=user.id)
    db.add(folder)
    db.commit()
    return serialize_folder(folder, 0, 0)


@router.put('/{folder_id}')
def rename_folder(folder_id: int, body: FolderRename, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    ensure_system_folders(db)
    folder = db.query(models.AssetFolder).filter(models.AssetFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(404, '文件夹不存在')
    if is_system_folder(folder):
        raise HTTPException(400, '系统文件夹不支持重命名')
    name = body.name.strip()
    if not name:
        raise HTTPException(400, '文件夹名称不能为空')
    dup = db.query(models.AssetFolder).filter(
        models.AssetFolder.name == name,
        models.AssetFolder.id != folder_id,
        models.AssetFolder.parent_id == folder.parent_id
    ).first()
    if dup:
        raise HTTPException(400, '同级目录下已存在同名文件夹')
    folder.name = name
    db.commit()
    count = db.query(func.count(models.Material.id)).filter(models.Material.folder_id == folder_id).scalar()
    child_count = db.query(func.count(models.AssetFolder.id)).filter(models.AssetFolder.parent_id == folder_id).scalar()
    return serialize_folder(folder, count, child_count)


@router.delete('/{folder_id}')
def delete_folder(folder_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    ensure_system_folders(db)
    folder = db.query(models.AssetFolder).filter(models.AssetFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(404, '文件夹不存在')
    if is_system_folder(folder):
        raise HTTPException(400, '系统文件夹不支持删除')
    count = db.query(func.count(models.Material.id)).filter(models.Material.folder_id == folder_id).scalar()
    if count > 0:
        raise HTTPException(400, f'该文件夹下还有 {count} 个素材，请先移动或删除')
    child_count = db.query(func.count(models.AssetFolder.id)).filter(models.AssetFolder.parent_id == folder_id).scalar()
    if child_count > 0:
        raise HTTPException(400, f'该文件夹下还有 {child_count} 个子文件夹，请先处理')
    db.delete(folder)
    db.commit()
    return {'ok': True}


@router.patch('/{folder_id}/move')
def move_folder(folder_id: int, body: FolderMove, request: Request, db: Session = Depends(get_db)):
    user = get_user_or_401(request, db)
    require_role(user, 'admin', 'coach')
    ensure_system_folders(db)
    folder = db.query(models.AssetFolder).filter(models.AssetFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(404, '文件夹不存在')
    if is_system_folder(folder):
        raise HTTPException(400, '系统文件夹不支持移动')

    parent_id = body.parent_id
    if parent_id == folder_id:
        raise HTTPException(400, '不能把文件夹移动到自己下面')

    parent = None
    if parent_id is not None:
        parent = db.query(models.AssetFolder).filter(models.AssetFolder.id == parent_id).first()
        if not parent:
            raise HTTPException(404, '目标父文件夹不存在')
        cursor = parent
        while cursor is not None:
            if cursor.id == folder_id:
                raise HTTPException(400, '不能移动到自己的子文件夹下面')
            cursor = db.query(models.AssetFolder).filter(models.AssetFolder.id == cursor.parent_id).first() if cursor.parent_id else None

    dup = db.query(models.AssetFolder).filter(
        models.AssetFolder.name == folder.name,
        models.AssetFolder.id != folder_id,
        models.AssetFolder.parent_id == parent_id
    ).first()
    if dup:
        raise HTTPException(400, '目标目录下已存在同名文件夹')

    folder.parent_id = parent_id
    db.commit()
    count = db.query(func.count(models.Material.id)).filter(models.Material.folder_id == folder_id).scalar()
    child_count = db.query(func.count(models.AssetFolder.id)).filter(models.AssetFolder.parent_id == folder_id).scalar()
    return serialize_folder(folder, count, child_count)
