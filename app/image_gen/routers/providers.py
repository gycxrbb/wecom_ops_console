"""供应商配置 CRUD（仅 admin）。api_key 出参永远脱敏，明文不落盘/不下发。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user, require_role

from ..schemas.providers import ProviderCreate, ProviderUpdate
from ..services import provider_repo

router = APIRouter()


def _require_admin(request: Request, db: Session) -> None:
    user = get_current_user(request, db)
    require_role(user, "admin")


def _mask_key(encrypted: str) -> str:
    if not encrypted:
        return ""
    if len(encrypted) <= 12:
        return "****"
    return encrypted[:4] + "****" + encrypted[-4:]


def _to_out(row) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "provider_kind": row.provider_kind,
        "base_url": row.base_url,
        "default_model": row.default_model,
        "priority": row.priority,
        "enabled": row.enabled,
        "timeout_seconds": row.timeout_seconds,
        "max_retries": row.max_retries,
        "api_key_masked": _mask_key(row.api_key_encrypted),
    }


@router.get("/providers")
def list_providers(request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    rows = provider_repo.list_providers(db)
    return {"items": [_to_out(r) for r in rows]}


@router.post("/providers")
def create_provider(body: ProviderCreate, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    row = provider_repo.create_provider(db, body)
    return _to_out(row)


@router.put("/providers/{provider_id}")
def update_provider(
    provider_id: int,
    body: ProviderUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_admin(request, db)
    row = provider_repo.update_provider(db, provider_id, body)
    if not row:
        raise HTTPException(404, "供应商不存在")
    return _to_out(row)


@router.delete("/providers/{provider_id}")
def delete_provider(provider_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    ok = provider_repo.delete_provider(db, provider_id)
    if not ok:
        raise HTTPException(404, "供应商不存在")
    return {"status": "ok"}
