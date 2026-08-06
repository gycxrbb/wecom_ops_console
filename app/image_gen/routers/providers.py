"""供应商配置 CRUD（仅 admin）。api_key 出参永远脱敏，明文不落盘/不下发。"""
from __future__ import annotations

import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user, require_role

from ..models import ImageGenProvider
from ..schemas.providers import ProviderCreate, ProviderUpdate
from ..services import provider_repo
from ..services.image_client import ImageGenerationError, generate_with_provider
from ..services.provider_chain import _row_to_config

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
        "agent_model": getattr(row, "agent_model", None) or None,
        "purpose": getattr(row, "purpose", None) or "image_only",
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


@router.post("/providers/{provider_id}/test")
async def test_provider(provider_id: int, request: Request, db: Session = Depends(get_db)):
    """测试供应商渠道可用性。

    生图专用/双用 → 生成一张最简低质量图（size=auto、n=1、quality=low，快速探活）；
    对话专用 → 发"你好"验证 chat 接口。
    """
    _require_admin(request, db)
    row = db.query(ImageGenProvider).filter(ImageGenProvider.id == provider_id).first()
    if not row:
        raise HTTPException(404, "供应商不存在")
    cfg = _row_to_config(row)
    kind = "chat" if cfg.purpose == "chat_only" else "image"
    started = time.perf_counter()
    try:
        if kind == "image":
            await generate_with_provider(
                cfg, prompt="(connectivity test)", model=cfg.default_model,
                size="auto", n=1, quality="low",
            )
        else:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect=20, read=60, write=10, pool=10),
                trust_env=False,
            ) as client:
                resp = await client.post(
                    f"{cfg.base_url.rstrip('/')}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": cfg.agent_model or cfg.default_model,
                        "messages": [{"role": "user", "content": "你好"}],
                        "max_tokens": 16,
                    },
                )
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        return {
            "success": True,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "kind": kind,
            "message": "可用",
        }
    except ImageGenerationError as e:
        return _test_failed(started, kind, str(e))
    except Exception as e:
        return _test_failed(started, kind, str(e))


def _test_failed(started: float, kind: str, message: str) -> dict:
    return {
        "success": False,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "kind": kind,
        "message": message[:300],
    }
