"""CRM 外部群发送映射 — 本地发送群绑定管理

职责：管理 CRM 外部群 → 本地发送群的映射关系。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from ..models import CrmGroupSendBinding, Group

_log = logging.getLogger(__name__)


def list_bindings(db: Session) -> list[dict[str, Any]]:
    """返回所有绑定记录，附带本地群名称"""
    rows = (
        db.query(CrmGroupSendBinding, Group.name)
        .join(Group, Group.id == CrmGroupSendBinding.local_group_id)
        .order_by(CrmGroupSendBinding.id)
        .all()
    )
    return [
        {
            'id': b.id,
            'crm_group_id': b.crm_group_id,
            'crm_group_name_snapshot': b.crm_group_name_snapshot,
            'local_group_id': b.local_group_id,
            'local_group_name': gname,
            'enabled': b.enabled,
            'remark': b.remark,
            'created_at': b.created_at.isoformat() if b.created_at else None,
            'updated_at': b.updated_at.isoformat() if b.updated_at else None,
        }
        for b, gname in rows
    ]


def get_binding_by_crm_group(db: Session, crm_group_id: int) -> CrmGroupSendBinding | None:
    return (
        db.query(CrmGroupSendBinding)
        .filter(CrmGroupSendBinding.crm_group_id == crm_group_id)
        .first()
    )


def get_bindings_map_by_crm_group_ids(db: Session, crm_group_ids: list[int]) -> dict[int, dict[str, Any]]:
    """批量返回 CRM 群绑定信息，避免逐群查本地库。"""
    normalized_group_ids = sorted({int(group_id) for group_id in crm_group_ids if group_id})
    if not normalized_group_ids:
        return {}

    rows = (
        db.query(CrmGroupSendBinding, Group.name)
        .join(Group, Group.id == CrmGroupSendBinding.local_group_id)
        .filter(CrmGroupSendBinding.crm_group_id.in_(normalized_group_ids))
        .all()
    )
    return {
        binding.crm_group_id: {
            'id': binding.id,
            'crm_group_id': binding.crm_group_id,
            'local_group_id': binding.local_group_id,
            'local_group_name': local_group_name,
            'enabled': bool(binding.enabled),
            'remark': binding.remark,
        }
        for binding, local_group_name in rows
    }


def upsert_binding(
    db: Session,
    crm_group_id: int,
    crm_group_name: str,
    local_group_id: int,
    remark: str = '',
) -> dict[str, Any]:
    """创建或更新绑定。如果 crm_group_id 已存在则更新。"""
    existing = get_binding_by_crm_group(db, crm_group_id)
    if existing:
        existing.crm_group_name_snapshot = crm_group_name
        existing.local_group_id = local_group_id
        existing.remark = remark
        existing.enabled = 1
        db.commit()
        db.refresh(existing)
        _log.info('更新 CRM 群绑定: crm_group_id=%s -> local_group_id=%s', crm_group_id, local_group_id)
        return {'id': existing.id, 'updated': True}

    binding = CrmGroupSendBinding(
        crm_group_id=crm_group_id,
        crm_group_name_snapshot=crm_group_name,
        local_group_id=local_group_id,
        remark=remark,
    )
    db.add(binding)
    db.commit()
    db.refresh(binding)
    _log.info('创建 CRM 群绑定: crm_group_id=%s -> local_group_id=%s', crm_group_id, local_group_id)
    return {'id': binding.id, 'created': True}


def delete_binding(db: Session, binding_id: int) -> bool:
    binding = db.query(CrmGroupSendBinding).filter(CrmGroupSendBinding.id == binding_id).first()
    if not binding:
        return False
    db.delete(binding)
    db.commit()
    _log.info('删除 CRM 群绑定: id=%s', binding_id)
    return True


def toggle_binding(db: Session, binding_id: int, enabled: bool) -> bool:
    binding = db.query(CrmGroupSendBinding).filter(CrmGroupSendBinding.id == binding_id).first()
    if not binding:
        return False
    binding.enabled = 1 if enabled else 0
    db.commit()
    return True


def get_all_local_groups(db: Session) -> list[dict[str, Any]]:
    """返回所有可用的本地发送群（供绑定选择）"""
    rows = db.query(Group).filter(Group.enabled == 1).order_by(Group.name).all()
    return [{'id': g.id, 'name': g.name} for g in rows]


def batch_bind(
    db: Session,
    crm_group_ids: list[int],
    crm_group_names: dict[int, str],
    local_group_id: int,
) -> dict[str, Any]:
    """一键绑定：将多个 CRM 群统一绑定到一个本地发送群。"""
    # 校验本地群存在
    local_group = db.query(Group).filter(Group.id == local_group_id, Group.enabled == 1).first()
    if not local_group:
        raise ValueError(f'本地群 {local_group_id} 不存在或已禁用')

    bound = 0
    updated = 0
    for gid in crm_group_ids:
        gname = crm_group_names.get(gid, f'CRM群#{gid}')
        existing = get_binding_by_crm_group(db, gid)
        if existing:
            existing.crm_group_name_snapshot = gname
            existing.local_group_id = local_group_id
            existing.enabled = 1
            db.commit()
            updated += 1
        else:
            binding = CrmGroupSendBinding(
                crm_group_id=gid,
                crm_group_name_snapshot=gname,
                local_group_id=local_group_id,
            )
            db.add(binding)
            db.commit()
            bound += 1

    _log.info('一键绑定完成: 新建 %d, 更新 %d → 本地群 %s', bound, updated, local_group.name)
    return {'bound': bound, 'updated': updated, 'total': bound + updated, 'local_group_name': local_group.name}
