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

from ..schemas.agent_task import AgentImageTaskSubmit
from ..schemas.history import HistoryCallbackRequest
from ..services.agent_task_service import get_agent_image_task, submit_agent_image_task
from ..services.customer_profile_tool import ProfileNotReady, build_desensitized_profile
from ..services.history_service import new_record_id, write_failure, write_success
from ..services.provider_chain import load_providers

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


def _openai_error(code: str, message: str, *, status: int = 500) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"message": message, "type": "image_gen_error", "code": code}},
    )


def _resolve_customer_id(request: Request, explicit: int | None) -> int | None:
    if explicit is not None:
        return explicit
    raw = request.headers.get("x-customer-id") or request.query_params.get("cid")
    try:
        return int(raw) if raw else None
    except (TypeError, ValueError):
        return None


@router.post("/agent/image-tasks")
async def submit_image_task(body: AgentImageTaskSubmit, request: Request):
    """agent 生图任务化提交：INSERT running 行 + 派后台生图，立即返回 task_id。前端轮询 GET 拿结果。

    鉴权 + 加载供应商用短生命周期 Session，**在派后台 task 前就关闭**——不在数分钟的生成期间占用连接池。
    """
    db = SessionLocal()
    try:
        user = get_current_user(request, db)
        providers = load_providers(db)
    finally:
        db.close()
    if not providers:
        return _openai_error("no_provider", "未配置可用的生图供应商，请联系管理员", status=503)

    customer_id = _resolve_customer_id(request, body.customer_id)
    task_id = await submit_agent_image_task(
        operator_user_id=user.id,
        customer_id=customer_id,
        prompt=body.prompt,
        providers=providers,
        model=body.model,
        size=body.size or "auto",
        n=body.n or 1,
        quality=body.quality or "auto",
    )
    return JSONResponse(status_code=202, content={"task_id": task_id, "status": "running"})


@router.get("/agent/image-tasks/{task_id}")
async def get_image_task(task_id: str, request: Request):
    """agent 生图任务轮询：返回 {task_id, status, data?, error?}。"""
    db = SessionLocal()
    try:
        get_current_user(request, db)
    finally:
        db.close()
    task = await get_agent_image_task(task_id)
    if task is None:
        return _openai_error("task_not_found", "任务不存在", status=404)
    return task
