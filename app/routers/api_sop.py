from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from .. import models
from ..security import get_current_user, require_permission
from ..route_helper import _dt

router = APIRouter(prefix='/api/v1/sop-documents', tags=['sop-documents'])


class SopDocCreate(BaseModel):
    title: str
    category: str = '其他'
    url: str
    description: str = ''

class SopDocUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    url: str | None = None
    description: str | None = None


VALID_CATEGORIES = ['运营流程', '话术库',"经验库", '营养知识', '培训手册', '其他']


def serialize_doc(doc: models.SopDocument) -> dict:
    return {
        'id': doc.id,
        'title': doc.title,
        'category': doc.category,
        'url': doc.url,
        'description': doc.description,
        'sort_order': doc.sort_order,
        'created_by': doc.created_by,
        'created_at': _dt(doc.created_at),
        'updated_at': _dt(doc.updated_at),
    }


@router.get('')
def list_docs(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    docs = db.query(models.SopDocument).order_by(
        models.SopDocument.sort_order, models.SopDocument.id.desc()
    ).all()
    return [serialize_doc(d) for d in docs]


@router.get('/categories')
def list_categories(request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    return VALID_CATEGORIES


@router.post('')
def create_doc(body: SopDocCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_permission(user, 'sop')
    title = body.title.strip()
    if not title:
        raise HTTPException(400, '文档标题不能为空')
    url = body.url.strip()
    if not url:
        raise HTTPException(400, '文档链接不能为空')
    category = body.category if body.category in VALID_CATEGORIES else '其他'
    max_order = db.query(func.max(models.SopDocument.sort_order)).scalar() or 0
    doc = models.SopDocument(
        title=title,
        category=category,
        url=url,
        description=body.description.strip(),
        sort_order=max_order + 1,
        created_by=user.id,
    )
    db.add(doc)
    db.commit()
    return serialize_doc(doc)


@router.put('/{doc_id}')
def update_doc(doc_id: int, body: SopDocUpdate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_permission(user, 'sop')
    doc = db.query(models.SopDocument).filter(models.SopDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(404, '文档不存在')
    if body.title is not None:
        doc.title = body.title.strip()
    if body.category is not None:
        doc.category = body.category if body.category in VALID_CATEGORIES else '其他'
    if body.url is not None:
        doc.url = body.url.strip()
    if body.description is not None:
        doc.description = body.description.strip()
    db.commit()
    return serialize_doc(doc)


@router.delete('/{doc_id}')
def delete_doc(doc_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_permission(user, 'sop')
    doc = db.query(models.SopDocument).filter(models.SopDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(404, '文档不存在')
    db.delete(doc)
    db.commit()
    return {'ok': True}
