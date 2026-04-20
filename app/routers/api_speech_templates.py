"""话术模板管理 API"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..route_helper import UnifiedResponseRoute
from ..security import get_current_user, require_role
from ..services.crm_speech_templates import (
    SCENE_LABELS,
    STYLES,
    get_all_templates,
    invalidate_cache,
    seed_speech_templates,
)

router = APIRouter(
    prefix='/api/v1/speech-templates',
    tags=['speech-templates'],
    route_class=UnifiedResponseRoute,
)


class TemplateUpdateReq(BaseModel):
    content: str
    label: str = ''


class TemplateCreateReq(BaseModel):
    scene_key: str
    style: str
    label: str = ''
    content: str


@router.get('/scenes')
def list_scenes(request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    return [
        {'key': key, 'label': label, 'styles': list(STYLES)}
        for key, label in SCENE_LABELS.items()
    ]


@router.get('')
def list_templates(request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    seed_speech_templates(db)
    return get_all_templates(db)


@router.put('/{template_id}')
def update_template(
    template_id: int,
    req: TemplateUpdateReq,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    require_role(user, 'admin', 'coach')
    row = db.query(models.SpeechTemplate).get(template_id)
    if not row:
        raise HTTPException(404, '模板不存在')
    row.content = req.content
    if req.label:
        row.label = req.label
    db.commit()
    db.refresh(row)
    invalidate_cache()
    return {
        'id': row.id,
        'scene_key': row.scene_key,
        'style': row.style,
        'label': row.label,
        'content': row.content,
        'is_builtin': row.is_builtin,
    }


@router.post('')
def create_template(
    req: TemplateCreateReq,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    require_role(user, 'admin', 'coach')
    if req.style not in STYLES:
        raise HTTPException(400, f'不支持的 style: {req.style}')
    existing = (
        db.query(models.SpeechTemplate)
        .filter_by(scene_key=req.scene_key, style=req.style)
        .first()
    )
    if existing:
        raise HTTPException(400, f'{req.scene_key}/{req.style} 已存在')
    row = models.SpeechTemplate(
        scene_key=req.scene_key,
        style=req.style,
        label=req.label or SCENE_LABELS.get(req.scene_key, req.scene_key),
        content=req.content,
        is_builtin=0,
        owner_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    invalidate_cache()
    return {
        'id': row.id,
        'scene_key': row.scene_key,
        'style': row.style,
        'label': row.label,
        'content': row.content,
        'is_builtin': row.is_builtin,
    }


@router.delete('/{template_id}')
def delete_template(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    require_role(user, 'admin')
    row = db.query(models.SpeechTemplate).get(template_id)
    if not row:
        raise HTTPException(404, '模板不存在')
    if row.is_builtin:
        raise HTTPException(400, '内置模板不可删除')
    db.delete(row)
    db.commit()
    invalidate_cache()
    return {'ok': True}
