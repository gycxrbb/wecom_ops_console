"""生图历史查询（登录用户即可，admin 后台用）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from datetime import timedelta

from app.database import get_db
from app.security import create_access_token, get_current_user

from ..services import history_service

router = APIRouter()


@router.get("/token")
def issue_image_gen_token(request: Request, db: Session = Depends(get_db)):
    """为同源 iframe(playground)签发短期 access token。

    playground 在 iframe 里对 session cookie 的投递不可靠（Bearer PLACEHOLDER 无效 + cookie 未送达 → 401），
    故由父页(AiCoachPanel)调用本接口拿 token 作为 apiKey 传给 playground；playground 以 Bearer 发回，
    get_current_user 解码 JWT 鉴权。真实 inferera key 仍在后端 DB，不下发。
    """
    user = get_current_user(request, db)
    token = create_access_token({"sub": str(user.id)}, expires_delta=timedelta(hours=24))
    return {"token": token}


def _to_out(row) -> dict:
    return {
        "id": row.id,
        "record_id": row.record_id,
        "operator_user_id": row.operator_user_id,
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
def list_history(
    request: Request,
    db: Session = Depends(get_db),
    customer_id: int | None = Query(None),
    mode: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    user = get_current_user(request, db)
    # 用户隔离：非管理员只能看自己的生图历史；管理员（ImageGenAdmin 审计）可看全部
    operator_user_id = None if getattr(user, "role", None) == "admin" else user.id
    rows, total = history_service.list_history(
        db,
        customer_id=customer_id,
        mode=mode,
        status=status,
        operator_user_id=operator_user_id,
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
def get_history(record_id: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    row = history_service.get_history(db, record_id)
    if not row:
        raise HTTPException(404, "记录不存在")
    # 用户隔离：非管理员只能查自己的记录（不暴露他人记录的存在性）
    if getattr(user, "role", None) != "admin" and row.operator_user_id != user.id:
        raise HTTPException(404, "记录不存在")
    return _to_out(row)
