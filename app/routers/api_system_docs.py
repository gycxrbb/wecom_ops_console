from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..route_helper import UnifiedResponseRoute
from ..security import get_current_user
from ..services import system_docs_service

router = APIRouter(prefix='/api/v1/system-docs', tags=['system-docs'], route_class=UnifiedResponseRoute)


class SystemDocUpsert(BaseModel):
    title: str
    slug: str = ''
    category: str = '基础上手'
    author: str = ''
    summary: str = ''
    cover_image: str = ''
    difficulty: str = 'beginner'
    recommended_slugs: list[str] = []
    content: str = ''
    order: int | None = None
    save_mode: str = 'publish'


def _require_admin(request: Request, db: Session):
    user = get_current_user(request, db)
    if user.role != 'admin':
        raise HTTPException(403, '仅管理员可维护系统教学文档')
    return user


@router.get('/tree')
def get_tree(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return system_docs_service.list_system_docs(include_unpublished=user.role == 'admin')


@router.get('/search')
def search_docs(request: Request, q: str = '', db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return system_docs_service.search_system_docs(q, include_unpublished=user.role == 'admin')


@router.get('/entries/{slug}')
def get_entry(slug: str, request: Request, mode: str = 'published', db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    try:
        return system_docs_service.get_system_doc(
            slug,
            mode='draft' if user.role == 'admin' and mode == 'draft' else 'published',
            include_unpublished=user.role == 'admin',
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post('/entries')
def create_entry(body: SystemDocUpsert, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    try:
        return system_docs_service.create_system_doc(
            title=body.title,
            slug=body.slug,
            category=body.category,
            author=body.author,
            summary=body.summary,
            cover_image=body.cover_image,
            difficulty=body.difficulty,
            recommended_slugs=body.recommended_slugs,
            content=body.content,
            order=body.order,
            save_mode=body.save_mode,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put('/entries/{slug}')
def update_entry(slug: str, body: SystemDocUpsert, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    try:
        return system_docs_service.update_system_doc(
            slug,
            title=body.title,
            slug=body.slug,
            category=body.category,
            author=body.author,
            summary=body.summary,
            cover_image=body.cover_image,
            difficulty=body.difficulty,
            recommended_slugs=body.recommended_slugs,
            content=body.content,
            order=body.order,
            save_mode=body.save_mode,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete('/entries/{slug}')
def delete_entry(slug: str, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    try:
        system_docs_service.delete_system_doc(slug)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {'ok': True}


@router.post('/upload-image')
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    article_slug: str = Form(''),
    db: Session = Depends(get_db),
):
    _require_admin(request, db)
    if not file.filename:
        raise HTTPException(400, '缺少文件名')
    payload = await file.read()
    if not payload:
        raise HTTPException(400, '上传文件为空')
    return system_docs_service.upload_system_doc_image(
        content=payload,
        filename=file.filename,
        mime_type=file.content_type,
        article_slug=article_slug,
    )
