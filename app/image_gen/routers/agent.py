"""agent 模式辅助端点（playground fetch 调用，返回裸 JSON，不经过 UnifiedResponseRoute）。

- GET  /customer-profile/{cid}  get_customer_profile function tool 的数据源（脱敏摘要）
- POST /history/callback        agent 出图后回调，把生成结果落历史（复用 write_success/write_failure）
"""
from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.database import SessionLocal
from app.security import get_current_user, require_permission

from ..schemas.history import HistoryCallbackRequest
from ..services.customer_profile_tool import ProfileNotReady, build_desensitized_profile
from ..services.history_service import new_record_id, write_failure, write_success

_log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/customer-profile/{cid}")
def get_customer_profile_endpoint(cid: int, request: Request):
    """get_customer_profile agent tool 数据源：返回客户脱敏健康/生活摘要（context_text）。"""
    db = SessionLocal()
    try:
        user = get_current_user(request, db)
        require_permission(user, "crm_profile")
        from app.crm_profile.services.permission import assert_can_view

        assert_can_view(user, cid)
    finally:
        db.close()

    try:
        return build_desensitized_profile(cid, window_days=7)
    except ProfileNotReady as exc:
        return JSONResponse(
            status_code=503,
            content={"error": {"message": str(exc), "type": "profile_not_ready"}},
        )


@router.post("/history/callback")
async def history_callback(body: HistoryCallbackRequest, request: Request):
    """agent 出图后回调：把结果落历史。存储/落库在线程池执行（复用 write_success），不阻塞。"""
    db = SessionLocal()
    try:
        user = get_current_user(request, db)
    finally:
        db.close()

    record_id = new_record_id()
    image_bytes = base64.b64decode(body.image_b64) if body.image_b64 else b""
    params = {
        "size": body.size,
        "quality": body.quality,
        "requested_model": body.model,
        "mode": "agent",
    }

    if body.status == "success" and image_bytes:
        public_url = await write_success(
            record_id=record_id,
            operator_user_id=user.id,
            customer_id=body.customer_id,
            mode="agent",
            prompt=body.prompt,
            params=params,
            model=body.model or "",
            provider_name=body.provider_name or "",
            image_bytes=image_bytes,
            gen_ms=body.latency_ms or 0,
            audit_call_id=record_id,
        )
        return {"record_id": record_id, "public_url": public_url, "status": "success"}

    await write_failure(
        record_id=record_id,
        operator_user_id=user.id,
        customer_id=body.customer_id,
        mode="agent",
        prompt=body.prompt,
        params=params,
        model=body.model or "",
        provider_name=body.provider_name or "",
        error_code=body.error_code or "agent_failed",
        error_message=body.error_message or "",
        gen_ms=body.latency_ms or 0,
        audit_call_id=record_id,
    )
    return {"record_id": record_id, "status": "failed"}
