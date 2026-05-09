"""话术模板管理 API"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..models import SpeechCategory, SpeechTemplate
from ..route_helper import UnifiedResponseRoute
from ..security import get_current_user, require_role, require_permission
from ..services.crm_speech_templates import (
    SCENE_CATEGORY_MAP,
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


def _template_response(row: SpeechTemplate) -> dict:
    import json as _json
    meta = None
    if row.metadata_json:
        try:
            meta = _json.loads(row.metadata_json)
        except (ValueError, TypeError):
            meta = None
    return {
        'id': row.id,
        'scene_key': row.scene_key,
        'style': row.style,
        'label': row.label,
        'content': row.content,
        'is_builtin': row.is_builtin,
        'category_id': row.category_id,
        'metadata_json': meta,
    }


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

    # Build category lookup: scene_key -> {category_id, l1, l2, l3}
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
            cat_map[scene_key] = {'category_id': cat_id, 'l3': cat_name, 'parent_id': parent_id}
            if parent_id:
                parent_ids.add(parent_id)

    # Auto-backfill: assign L3 category_id to scenes that have a mapping but no DB assignment
    uncategorized_keys = [k for k in scene_keys if k not in cat_map and k in SCENE_CATEGORY_MAP]
    if uncategorized_keys:
        l3_name_to_id: dict[str, int] = dict(
            db.query(SpeechCategory.name, SpeechCategory.id)
            .filter(SpeechCategory.level == 3, SpeechCategory.deleted_at.is_(None))
            .all()
        )
        for key in uncategorized_keys:
            mapping = SCENE_CATEGORY_MAP[key]
            l3_name = mapping[1] if isinstance(mapping, tuple) else mapping
            l3_id = l3_name_to_id.get(l3_name)
            if l3_id:
                db.query(SpeechTemplate).filter_by(scene_key=key, category_id=None).update({'category_id': l3_id})
                cat_row = db.query(SpeechCategory).get(l3_id)
                cat_map[key] = {'category_id': l3_id, 'l3': l3_name, 'parent_id': cat_row.parent_id}
                if cat_row.parent_id:
                    parent_ids.add(cat_row.parent_id)
        db.commit()

    # Resolve L2 and L1 names
    l2_names: dict[int, str] = {}
    l1_names: dict[int, str] = {}
    all_parents = set(parent_ids)
    if all_parents:
        for p in db.query(SpeechCategory.id, SpeechCategory.name, SpeechCategory.parent_id).filter(SpeechCategory.id.in_(all_parents)).all():
            l2_names[p.id] = p.name
            if p.parent_id:
                all_parents.add(p.parent_id)
        l1_ids = {pid for pid in all_parents if pid not in l2_names}
        if l1_ids:
            for p in db.query(SpeechCategory.id, SpeechCategory.name).filter(SpeechCategory.id.in_(l1_ids)).all():
                l1_names[p.id] = p.name

    # Build L2 → L1 mapping
    l2_to_l1: dict[int, int | None] = {}
    if parent_ids:
        for p in db.query(SpeechCategory.id, SpeechCategory.parent_id).filter(SpeechCategory.id.in_(parent_ids)).all():
            l2_to_l1[p.id] = p.parent_id

    return [
        {
            'key': key,
            'label': SCENE_LABELS.get(key, key),
            'styles': list(STYLES),
            'category_id': cat_map.get(key, {}).get('category_id'),
            'category_l1': l1_names.get(l2_to_l1.get(cat_map.get(key, {}).get('parent_id')), ''),
            'category_l2': l2_names.get(cat_map.get(key, {}).get('parent_id'), ''),
            'category_l3': cat_map.get(key, {}).get('l3', ''),
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
    require_permission(user, 'speech_template')
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
    return _template_response(row)


@router.post('')
def create_template(
    req: TemplateCreateReq,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    require_permission(user, 'speech_template')
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
    return _template_response(row)


@router.post('/import-csv')
async def import_templates_csv(
    request: Request,
    file: UploadFile = File(...),
    index_rag: bool = Form(False),
    dry_run: bool = Form(False),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    require_permission(user, 'speech_template')
    filename = file.filename or ''
    if filename and not filename.lower().endswith('.csv'):
        raise HTTPException(400, '仅支持 CSV 文件')

    raw = await file.read()
    if not raw:
        raise HTTPException(400, 'CSV 文件为空')

    stats = import_speech_templates_csv(db, decode_csv_bytes(raw), dry_run=dry_run, owner_id=user.id)
    rag_stats = None
    if index_rag and not dry_run:
        rag_stats = await _index_rag_speech_templates(db)

    return {
        **stats,
        'rag_index': rag_stats,
    }


class SpeechRagMetaReq(BaseModel):
    summary: str | None = None
    customer_goal: list[str] | None = None
    intervention_scene: list[str] | None = None
    question_type: list[str] | None = None
    safety_level: str | None = None
    visibility: str | None = None
    tags: list[str] | None = None
    usage_note: str | None = None


@router.patch('/{template_id}/rag-meta')
async def update_rag_meta(
    template_id: int,
    req: SpeechRagMetaReq,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    require_permission(user, 'speech_template')
    row = db.query(SpeechTemplate).get(template_id)
    if not row:
        raise HTTPException(404, '模板不存在')

    import json as _json
    meta: dict = {}
    if row.metadata_json:
        try:
            meta = _json.loads(row.metadata_json)
        except (ValueError, TypeError):
            meta = {}

    updates = req.model_dump(exclude_none=True)
    meta.update(updates)
    row.metadata_json = _json.dumps(meta, ensure_ascii=False) if meta else ""
    db.commit()
    db.refresh(row)
    invalidate_cache()

    # Incremental RAG index for this single template
    from ..rag.resource_indexer import index_single_speech_template
    await index_single_speech_template(db, row.id)

    return _template_response(row)


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


class CategoryMoveReq(BaseModel):
    new_parent_id: int


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

    # Count templates per category
    from sqlalchemy import func
    counts = dict(
        db.query(SpeechTemplate.category_id, func.count(SpeechTemplate.id))
        .group_by(SpeechTemplate.category_id).all()
    )

    l1_list = [c for c in categories if c.level == 1]
    l2_by_parent: dict[int, list] = {}
    l3_by_parent: dict[int, list] = {}
    for c in categories:
        if c.level == 2 and c.parent_id:
            l2_by_parent.setdefault(c.parent_id, []).append(c)
        elif c.level == 3 and c.parent_id:
            l3_by_parent.setdefault(c.parent_id, []).append(c)

    result = []
    for l1 in l1_list:
        l2_children = []
        for l2 in l2_by_parent.get(l1.id, []):
            l3_children = []
            for l3 in l3_by_parent.get(l2.id, []):
                l3_children.append({
                    'id': l3.id, 'name': l3.name, 'level': 3,
                    'parent_id': l2.id, 'sort_order': l3.sort_order,
                    'template_count': counts.get(l3.id, 0),
                })
            l2_children.append({
                'id': l2.id, 'name': l2.name, 'level': 2,
                'parent_id': l1.id, 'sort_order': l2.sort_order,
                'template_count': counts.get(l2.id, 0),
                'children': l3_children,
            })
        result.append({
            'id': l1.id, 'name': l1.name, 'level': 1,
            'sort_order': l1.sort_order,
            'children': l2_children,
        })
    return result


@router.post('/categories')
def create_category(req: CategoryCreateReq, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_role(user, 'admin')
    if req.parent_id:
        parent = db.query(SpeechCategory).get(req.parent_id)
        if not parent or parent.deleted_at:
            raise HTTPException(400, '父分类不存在')
        level = parent.level + 1
        if level > 3:
            raise HTTPException(400, '最多支持 3 级分类')
    else:
        level = 1
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
    child_count = db.query(SpeechCategory).filter_by(parent_id=row.id, deleted_at=None).count()
    if child_count:
        raise HTTPException(400, '该分类下还有子分类，无法删除')
    tpl_count = db.query(SpeechTemplate).filter_by(category_id=row.id).count()
    if tpl_count:
        raise HTTPException(400, f'该分类下还有 {tpl_count} 个话术模板，无法删除')
    from datetime import datetime
    row.deleted_at = datetime.utcnow()
    db.commit()
    return {'ok': True}


@router.put('/categories/{category_id}/move')
def move_category(
    category_id: int,
    req: CategoryMoveReq,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    require_role(user, 'admin')
    row = db.query(SpeechCategory).get(category_id)
    if not row or row.deleted_at:
        raise HTTPException(404, '分类不存在')
    if row.level < 2:
        raise HTTPException(400, '一级分类不可移动')
    new_parent = db.query(SpeechCategory).get(req.new_parent_id)
    if not new_parent or new_parent.deleted_at:
        raise HTTPException(400, '目标分类不存在')
    expected_parent_level = row.level - 1
    if new_parent.level != expected_parent_level:
        raise HTTPException(400, f'{row.level} 级分类只能移动到 {expected_parent_level} 级分类下')
    row.parent_id = req.new_parent_id
    db.commit()
    invalidate_cache()
    return {'ok': True, 'id': row.id, 'new_parent_id': req.new_parent_id}


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
