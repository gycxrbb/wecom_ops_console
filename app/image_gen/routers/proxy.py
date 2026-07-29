"""OpenAI 兼容代理端点：供 React gpt_image_playground 调用。

P0：直出 /images/generations（后端编排：生图→存七牛→记历史→审计）。
返回 OpenAI 兼容结构；错误也按 OpenAI {error:{...}} 返回，不经过 UnifiedResponseRoute。
"""
from __future__ import annotations

import base64
import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.database import SessionLocal
from app.security import get_current_user

from ..schemas.proxy import ImageGenerationRequest
from ..services.direct_orchestrator import orchestrate_direct, orchestrate_edit
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


@router.post("/images/edits")
async def images_edit(request: Request):
    """参考图编辑代理（OpenAI 兼容 /images/edits）。multipart：image[] + prompt + model + size + n + 可选 mask。
    后端编排：解析 multipart → /images/edits → 存七牛 → 记历史(mode=edit) → 审计，不阻塞事件循环。"""
    db = SessionLocal()
    try:
        user = get_current_user(request, db)
        providers = load_providers(db)
    finally:
        db.close()
    if not providers:
        return _openai_error("no_provider", "未配置可用的生图供应商，请联系管理员", status=503)

    customer_id = _extract_customer_id(request)
    form = await request.form()
    prompt = (form.get("prompt") or "").strip() or "(image edit)"
    model = form.get("model") or None
    size = form.get("size") or "1024x1024"
    n_raw = form.get("n")
    n = int(n_raw) if (n_raw and str(n_raw).isdigit()) else 1

    images: list[tuple[str, bytes, str]] = []
    for key in ("image", "image[]"):
        for v in form.getlist(key):
            if hasattr(v, "read"):  # UploadFile
                images.append((v.filename or "ref.png", await v.read(), v.content_type or "image/png"))
    mask_field = form.get("mask")
    mask: tuple[str, bytes, str] | None = None
    if mask_field and hasattr(mask_field, "read"):
        mask = (mask_field.filename or "mask.png", await mask_field.read(), mask_field.content_type or "image/png")

    if not images:
        return _openai_error("no_image", "参考图生图需要至少上传一张图片", status=400)

    try:
        result = await orchestrate_edit(
            operator_user_id=user.id,
            customer_id=customer_id,
            prompt=prompt,
            providers=providers,
            images=images,
            model=model,
            size=size,
            n=n,
            mask=mask,
        )
    except NoProviderConfigured:
        return _openai_error("no_provider", "未配置可用的生图供应商，请联系管理员", status=503)
    except ImageGenerationError as exc:
        return _openai_error(exc.error_code, str(exc), status=_status_for_code(exc.error_code))

    b64 = base64.b64encode(result.image_bytes).decode("ascii")
    return {
        "created": int(time.time()),
        "data": [{"b64_json": b64, "url": result.public_url, "record_id": result.record_id}],
        "record_id": result.record_id,
    }


@router.post("/responses")
async def responses_proxy(request: Request):
    """agent 模式 Responses API 透传，统一入口按请求类型路由到不同 key：

    - 对话轮(含 function tool 的 agent 主循环)→ 走配了 agent_model 的「对话专用」供应商，
      请求体 model 被覆盖为 agent_model(推理模型)。
    - 生图轮(playground hybrid 的 callBatchImageSingle：tools 只含 image_generation 且
      tool_choice=required)→ 走未配 agent_model 的「生图专用」供应商，不覆盖 model(用请求体
      里的图像模型)，由生图 key 真正出图。

    对话 key 与生图 key 各司其职，agent 仍是统一 /responses 入口。历史由前端 /history/callback 回调写。
    """
    db = SessionLocal()
    try:
        get_current_user(request, db)
        providers = load_providers(db)
    finally:
        db.close()

    body_bytes = await request.body()
    candidates, missing_error = _select_responses_providers(providers, body_bytes)
    if missing_error is not None:
        return missing_error

    gen, err = await stream_responses(candidates, body_bytes)
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


def _is_image_generation_only_turn(body_bytes: bytes) -> bool:
    """识别 playground hybrid 的生图轮：tools 只含 image_generation 内置工具且 tool_choice=required。

    对应 callBatchImageSingle 构造的请求（单图/批量生图都走 image_generation tool，无 function tool）。
    对话轮 tools 含 function（generate_image_batch/get_customer_profile/...）或 tool_choice 非 required，不命中。
    """
    try:
        body = json.loads(body_bytes)
    except Exception:
        return False
    if not isinstance(body, dict):
        return False
    tools = body.get("tools")
    if not isinstance(tools, list) or not tools:
        return False
    if body.get("tool_choice") != "required":
        return False
    return all(isinstance(t, dict) and t.get("type") == "image_generation" for t in tools)


def _select_responses_providers(providers, body_bytes: bytes):
    """按 /responses 请求类型挑选供应商：生图轮走生图专用 key(无 agent_model)，对话轮走对话 key(有 agent_model)。

    返回 (candidates, None) 或 (None, error_response)。stream_responses 仅对配了 agent_model 的
    供应商覆盖 model——所以生图 key(无 agent_model)天然用请求体里的图像模型，不会被改成对话模型。
    """
    if _is_image_generation_only_turn(body_bytes):
        image_providers = [p for p in providers if not p.agent_model]
        if image_providers:
            return image_providers, None
        # 未单独配置生图 key：退回全部供应商（stream_responses 只对配了 agent_model 的覆盖 model）
        return providers, None

    agents = [p for p in providers if p.agent_model]
    if not agents:
        return None, _openai_error(
            "no_agent_provider",
            "没有配置 agent 推理模型——请在「图片生成管理」给某个供应商填写 agent 推理模型（如 gpt-4o-mini）",
            status=503,
        )
    return agents, None
