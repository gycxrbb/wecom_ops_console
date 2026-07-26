"""OpenAI 兼容代理端点：供 React gpt_image_playground 调用。

P0：直出 /images/generations（后端编排：生图→存七牛→记历史→审计）。
返回 OpenAI 兼容结构；错误也按 OpenAI {error:{...}} 返回，不经过 UnifiedResponseRoute。
"""
from __future__ import annotations

import base64
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.database import SessionLocal
from app.security import get_current_user

from ..schemas.proxy import ImageGenerationRequest
from ..services.direct_orchestrator import orchestrate_direct
from ..services.image_client import ImageGenerationError
from ..services.provider_chain import NoProviderConfigured, load_providers
from ..services.responses_proxy import stream_responses

router = APIRouter()


@router.post("/images/generations")
async def generate_images(
    body: ImageGenerationRequest,
    request: Request,
):
    """直出生图代理。OpenAI 兼容入参/出参。

    鉴权 + 加载供应商用短生命周期 Session，**在生图前就关闭**——不在数分钟的生成期间
    占用连接池连接。生成(await httpx async)与存储(线程池 asyncio.to_thread)都不阻塞
    事件循环，其他请求不受影响。
    """
    db = SessionLocal()
    try:
        user = get_current_user(request, db)
        providers = load_providers(db)
    finally:
        db.close()

    customer_id = _extract_customer_id(request)

    try:
        result = await orchestrate_direct(
            operator_user_id=user.id,
            customer_id=customer_id,
            prompt=body.prompt,
            providers=providers,
            model=body.model,
            size=body.size or "auto",
            n=body.n or 1,
            quality=body.quality or "auto",
        )
    except NoProviderConfigured:
        return _openai_error("no_provider", "未配置可用的生图供应商，请联系管理员", status=503)
    except ImageGenerationError as exc:
        return _openai_error(exc.error_code, str(exc), status=_status_for_code(exc.error_code))

    b64 = base64.b64encode(result.image_bytes).decode("ascii")
    return {
        "created": int(time.time()),
        "data": [
            {
                "b64_json": b64,
                "url": result.public_url,
                "record_id": result.record_id,
            }
        ],
        "record_id": result.record_id,
    }


@router.post("/responses")
async def responses_proxy(request: Request):
    """agent 模式 Responses API 透传。请求体原样转发到上游 /v1/responses，SSE 流原样回传；
    首字节前按 provider 优先级 failover。历史由前端调 /history/callback 回调写（透传代理本身不落历史）。"""
    db = SessionLocal()
    try:
        get_current_user(request, db)
        providers = load_providers(db)
    finally:
        db.close()
    if not providers:
        return _openai_error("no_provider", "未配置可用的生图供应商，请联系管理员", status=503)

    body_bytes = await request.body()
    gen, err = await stream_responses(providers, body_bytes)
    if err is not None:
        return err
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={"X-Image-Gen-Mode": "agent", "Cache-Control": "no-cache"},
    )


def _extract_customer_id(request: Request) -> int | None:
    # iframe 带 ?cid=，前端可同时塞 x-customer-id header 透传客户上下文（agent 模式 / 审计归属）
    raw = request.headers.get("x-customer-id") or request.query_params.get("cid")
    try:
        return int(raw) if raw else None
    except (TypeError, ValueError):
        return None


def _openai_error(code: str, message: str, *, status: int = 500) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"message": message, "type": "image_gen_error", "code": code}},
    )


def _status_for_code(code: str) -> int:
    if code == "api_timeout":
        return 504
    if code == "api_error":
        return 502
    return 500
