"""playground 生图历史查询（Bearer token 鉴权，强制按当前用户）。

供 gpt_image_playground 的「生图历史」面板调用。区别于管理后台 /api/v1/image-gen/history
（admin 放行全部）：这里始终只返回当前 token 用户自己的记录——playground 是个人视角，
含 admin 也只看自己。返回不含 image_b64（体积大，看图用 public_url）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user

from ..services import history_service

router = APIRouter()


def _to_out(row) -> dict:
    # 不含 operator_user_id（本人已知）、不含 image_b64（体积大，看图用 public_url）
    return {
        "id": row.id,
        "record_id": row.record_id,
        "customer_id": row.customer_id,
        "mode": row.mode,
        "prompt": row.prompt,
        "params_json": row.params_json,
        "model": row.model,
        "provider_name": row.provider_name,
        "latency_ms": row.latency_ms,
        "status": row.status,
        "public_url": row.public_url,
        "error_code": row.error_code,
        "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else None,
    }


@router.get("/history")
def list_my_history(
    request: Request,
    db: Session = Depends(get_db),
    customer_id: int | None = Query(None),
    mode: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """当前 token 用户的生图历史（强制按本人过滤，不看角色）。"""
    user = get_current_user(request, db)
    rows, total = history_service.list_history(
        db,
        customer_id=customer_id,
        mode=mode,
        status=status,
        operator_user_id=user.id,  # 强制本人，不看 role
        page=page,
        page_size=page_size,
    )
    return {
        "items": [_to_out(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/history/{record_id}")
def get_my_history(record_id: str, request: Request, db: Session = Depends(get_db)):
    """单条详情（仅本人；他人记录返回 404，不暴露存在性）。"""
    user = get_current_user(request, db)
    row = history_service.get_history(db, record_id)
    if not row or row.operator_user_id != user.id:
        raise HTTPException(404, "记录不存在")
    return _to_out(row)
