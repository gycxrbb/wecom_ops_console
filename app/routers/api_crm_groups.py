"""外部群（CRM 群组）只读 API — 群列表、成员、统计、积分榜单"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..route_helper import UnifiedResponseRoute
from ..security import get_current_user
from ..services import crm_group_directory

router = APIRouter(prefix='/api/v1/crm-groups', tags=['crm-groups'], route_class=UnifiedResponseRoute)


# ---------- 榜单端点（必须在 /{group_id} 通配路由之前注册） ----------


@router.get('/leaderboard/individual')
def individual_leaderboard(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    get_current_user(request, db)
    return crm_group_directory.fetch_crm_individual_leaderboard(page, page_size)


@router.get('/leaderboard/group')
def group_leaderboard(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    get_current_user(request, db)
    return crm_group_directory.fetch_crm_group_leaderboard(page, page_size)


# ---------- 基础端点 ----------


@router.get('')
def list_crm_groups(request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    return crm_group_directory.fetch_crm_groups()


@router.get('/stats')
def get_crm_group_stats(request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    return crm_group_directory.fetch_crm_group_stats()


@router.get('/{group_id}/members')
def get_crm_group_members(group_id: int, request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    return crm_group_directory.fetch_crm_group_members(group_id)


@router.post('/refresh-cache')
def refresh_crm_cache(request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    crm_group_directory.clear_cache()
    return {'ok': True}
