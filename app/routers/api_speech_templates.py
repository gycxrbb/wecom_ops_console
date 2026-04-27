"""话术模板管理 API"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..models import SpeechCategory, SpeechTemplate
from ..route_helper import UnifiedResponseRoute
from ..security import get_current_user, require_role
from ..services.crm_speech_templates import (
    SCENE_LABELS,
    STYLES,
    get_all_templates,
    invalidate_cache,
    seed_speech_templates,
)
from ..services.speech_template_import import decode_csv_bytes, import_speech_templates_csv

router = APIRouter(
    prefix='/api/v1/speech-templates',
    tags=['speech-templates'],
    route_class=UnifiedResponseRoute,
)


class TemplateUpdateReq(BaseModel):
    content: str
    label: str = ''
    category_id: int | None = None


class TemplateCreateReq(BaseModel):
    scene_key: str
    style: str
    label: str = ''
    content: str
    category_id: int | None = None


async def _index_rag_speech_templates(db: Session) -> dict:
    from ..rag.resource_indexer import index_speech_templates

    return await index_speech_templates(db)


@router.get('/scenes')
def list_scenes(request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    seed_speech_templates(db)
    scene_keys = list(SCENE_LABELS.keys())
    db_scene_keys = (
        db.query(SpeechTemplate.scene_key)
        .distinct()
        .order_by(SpeechTemplate.scene_key)
        .all()
    )
    for (scene_key,) in db_scene_keys:
        if scene_key not in scene_keys:
            scene_keys.append(scene_key)

    # Build category lookup: scene_key -> {category_id, l1, l2}
    cat_map: dict[str, dict] = {}
    rows = (
        db.query(SpeechTemplate.scene_key, SpeechCategory.id, SpeechCategory.name, SpeechCategory.parent_id)
        .outerjoin(SpeechCategory, SpeechTemplate.category_id == SpeechCategory.id)
        .distinct(SpeechTemplate.scene_key)
        .all()
    )
    parent_ids = set()
    for scene_key, cat_id, cat_name, parent_id in rows:
        if cat_id:
            cat_map[scene_key] = {'category_id': cat_id, 'l2': cat_name, 'parent_id': parent_id}
            if parent_id:
                parent_ids.add(parent_id)

    # Resolve L1 names
    l1_names: dict[int, str] = {}
    if parent_ids:
        for p in db.query(SpeechCategory.id, SpeechCategory.name).filter(SpeechCategory.id.in_(parent_ids)).all():
            l1_names[p.id] = p.name

    return [
        {
            'key': key,
            'label': SCENE_LABELS.get(key, key),
            'styles': list(STYLES),
            'category_id': cat_map.get(key, {}).get('category_id'),
            'category_l1': l1_names.get(cat_map.get(key, {}).get('parent_id'), ''),
            'category_l2': cat_map.get(key, {}).get('l2', ''),
        }
        for key in scene_keys
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
    row = db.query(SpeechTemplate).get(template_id)
    if not row:
        raise HTTPException(404, '模板不存在')
    row.content = req.content
    if req.label:
        row.label = req.label
    if req.category_id is not None:
        row.category_id = req.category_id
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
    row = SpeechTemplate(
        scene_key=req.scene_key,
        style=req.style,
        label=req.label or SCENE_LABELS.get(req.scene_key, req.scene_key),
        content=req.content,
        is_builtin=0,
        owner_id=user.id,
        category_id=req.category_id,
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


@router.post('/import-csv')
async def import_templates_csv(
    request: Request,
    file: UploadFile = File(...),
    index_rag: bool = Form(False),
    dry_run: bool = Form(False),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    require_role(user, 'admin', 'coach')
    filename = file.filename or ''
    if filename and not filename.lower().endswith('.csv'):
        raise HTTPException(400, '仅支持 CSV 文件')

    raw = await file.read()
    if not raw:
        raise HTTPException(400, 'CSV 文件为空')

    stats = import_speech_templates_csv(db, decode_csv_bytes(raw), dry_run=dry_run)
    rag_stats = None
    if index_rag and not dry_run:
        rag_stats = await _index_rag_speech_templates(db)

    return {
        **stats,
        'rag_index': rag_stats,
    }


@router.delete('/{template_id}')
def delete_template(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    require_role(user, 'admin')
    row = db.query(SpeechTemplate).get(template_id)
    if not row:
        raise HTTPException(404, '模板不存在')
    if row.is_builtin:
        raise HTTPException(400, '内置模板不可删除')
    db.delete(row)
    db.commit()
    invalidate_cache()
    return {'ok': True}


# ── Category CRUD ──


class CategoryCreateReq(BaseModel):
    name: str
    parent_id: int | None = None
    sort_order: int = 0


class CategoryUpdateReq(BaseModel):
    name: str
    sort_order: int = 0


class AssignCategoryReq(BaseModel):
    assignments: list[dict[str, str | int | None]]  # [{scene_key, category_id}]


@router.get('/categories')
def list_categories(request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    categories = (
        db.query(SpeechCategory)
        .filter(SpeechCategory.deleted_at.is_(None))
        .order_by(SpeechCategory.level, SpeechCategory.sort_order)
        .all()
    )

    # Count templates per L2 category
    from sqlalchemy import func
    counts = dict(
        db.query(SpeechTemplate.category_id, func.count(SpeechTemplate.id))
        .group_by(SpeechTemplate.category_id).all()
    )

    l1_list = [c for c in categories if c.level == 1]
    l2_by_parent: dict[int, list] = {}
    for c in categories:
        if c.level == 2 and c.parent_id:
            l2_by_parent.setdefault(c.parent_id, []).append(c)

    result = []
    for l1 in l1_list:
        children = []
        for l2 in l2_by_parent.get(l1.id, []):
            children.append({
                'id': l2.id, 'name': l2.name, 'level': 2,
                'parent_id': l1.id, 'sort_order': l2.sort_order,
                'template_count': counts.get(l2.id, 0),
            })
        result.append({
            'id': l1.id, 'name': l1.name, 'level': 1,
            'sort_order': l1.sort_order,
            'children': children,
        })
    return result


@router.post('/categories')
def create_category(req: CategoryCreateReq, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_role(user, 'admin')
    level = 2 if req.parent_id else 1
    row = SpeechCategory(name=req.name, parent_id=req.parent_id, level=level, sort_order=req.sort_order)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'id': row.id, 'name': row.name, 'level': row.level, 'parent_id': row.parent_id}


@router.put('/categories/{category_id}')
def update_category(category_id: int, req: CategoryUpdateReq, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_role(user, 'admin')
    row = db.query(SpeechCategory).get(category_id)
    if not row or row.deleted_at:
        raise HTTPException(404, '分类不存在')
    row.name = req.name
    row.sort_order = req.sort_order
    db.commit()
    return {'id': row.id, 'name': row.name}


@router.delete('/categories/{category_id}')
def delete_category(category_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_role(user, 'admin')
    row = db.query(SpeechCategory).get(category_id)
    if not row or row.deleted_at:
        raise HTTPException(404, '分类不存在')
    if row.level == 1:
        child_count = db.query(SpeechCategory).filter_by(parent_id=row.id, deleted_at=None).count()
        if child_count:
            raise HTTPException(400, '该大类下还有子类，无法删除')
    if row.level == 2:
        tpl_count = db.query(SpeechTemplate).filter_by(category_id=row.id).count()
        if tpl_count:
            raise HTTPException(400, f'该子类下还有 {tpl_count} 个话术模板，无法删除')
    from datetime import datetime
    row.deleted_at = datetime.utcnow()
    db.commit()
    return {'ok': True}


@router.post('/assign-category')
def assign_category(req: AssignCategoryReq, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_role(user, 'admin')
    updated = 0
    for item in req.assignments:
        scene_key = item.get('scene_key')
        category_id = item.get('category_id')
        if not scene_key:
            continue
        count = (
            db.query(SpeechTemplate)
            .filter_by(scene_key=scene_key)
            .update({'category_id': category_id})
        )
        updated += count
    db.commit()
    invalidate_cache()
    return {'updated': updated}
