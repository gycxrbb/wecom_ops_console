from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..security import (
    get_current_user,
    json_dumps,
    json_loads,
    require_role,
    ALL_PERMISSIONS,
    PERMISSION_LABELS,
    PERMISSION_GROUPS,
)
from ..services.crm_admin_auth import (
    CrmAdminAuthUnavailable,
    fetch_all_crm_admins,
    sync_crm_admin_to_local,
)

router = APIRouter(prefix='/api/v1/permissions', tags=['permissions'])


@router.get('/schema')
def get_permission_schema(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_role(user, 'admin')
    groups = []
    for group_name, keys in PERMISSION_GROUPS.items():
        groups.append({
            'name': group_name,
            'permissions': [{'key': k, 'label': PERMISSION_LABELS.get(k, k)} for k in keys],
        })
    return {'groups': groups, 'all_keys': ALL_PERMISSIONS}


@router.get('/members')
def list_members(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_role(user, 'admin')

    # 从 CRM 拉取所有活跃成员并同步到本地
    try:
        crm_admins = fetch_all_crm_admins()
        for admin in crm_admins:
            sync_crm_admin_to_local(db, admin)
    except CrmAdminAuthUnavailable:
        pass  # CRM 不可用时仍返回本地已有数据

    # 查询所有 CRM 来源用户（排除 admin）
    users = (
        db.query(models.User)
        .filter(models.User.auth_source == 'crm', models.User.status == 1)
        .order_by(models.User.id)
        .all()
    )
    return [
        {
            'id': u.id,
            'username': u.username,
            'display_name': u.display_name,
            'avatar_url': u.avatar_url or '',
            'permissions': json_loads(u.permissions_json, {}),
        }
        for u in users
    ]


@router.put('/members/{user_id}')
async def update_member_permissions(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_role(user, 'admin')
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(404, '用户不存在')
    if target.role == 'admin':
        raise HTTPException(400, '不能修改管理员权限')

    body = await request.json()
    perms = body.get('permissions', {})
    # 只保留合法 key
    cleaned = {k: bool(v) for k, v in perms.items() if k in ALL_PERMISSIONS}
    target.permissions_json = json_dumps(cleaned)
    db.commit()
    return {
        'id': target.id,
        'username': target.username,
        'permissions': cleaned,
    }
