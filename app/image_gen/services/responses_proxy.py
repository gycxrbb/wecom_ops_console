"""agent 模式 Responses API 透传。

把 playground 的 /responses 请求体原样转发到上游 /v1/responses，SSE 字节流原样回传。
- 透明：不改 body（里面的 tools/instructions/input 由 playground 决定，含 get_customer_profile
  等 function tool），只把 Authorization 换成 provider key、拼上游 URL。
- 首字节前(拿到 200 状态码、尚未吐任何 SSE 字节)按 provider 优先级 failover；
  一旦提交流给客户端，中途断流只结束(不切换，避免重复计费/乱序)。
- 4xx(非 429)= 客户端错误(提示词/策略)，不 failover，原样回给客户端；
  5xx/429/连接级错误 = 基础设施问题，切下一个 provider。
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Tuple

import httpx
from fastapi.responses import JSONResponse

from .provider_chain import ProviderConfig

_log = logging.getLogger(__name__)

# 可 failover 的连接级异常
_FAILABILITY_TRANSPORT = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.RemoteProtocolError,
    httpx.ReadError,
    httpx.ReadTimeout,
    httpx.WriteError,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
)


def _openai_error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"message": message, "type": "image_gen_error", "code": code}},
    )


def _is_image_generation_only_turn_body(body_obj) -> bool:
    """识别 playground hybrid 的生图轮：tools 只含 image_generation 且 tool_choice=required。

    生图轮不覆盖 model（用请求体里的图像模型）；仅对话轮覆盖为 agent_model。
    （与 proxy._is_image_generation_only_turn 同逻辑，独立一份避免 service→router 循环 import）
    """
    if not isinstance(body_obj, dict):
        return False
    tools = body_obj.get("tools")
    if not isinstance(tools, list) or not tools:
        return False
    if body_obj.get("tool_choice") != "required":
        return False
    return all(isinstance(t, dict) and t.get("type") == "image_generation" for t in tools)


async def stream_responses(
    providers: list[ProviderConfig],
    body_bytes: bytes,
) -> Tuple[AsyncIterator[bytes] | None, JSONResponse | None]:
    """遍历 providers，返回 (SSE 字节生成器, None) 或 (None, 错误响应)。

    若 provider 配了 agent_model，把请求体的 model 覆盖为该推理模型（agent /responses 需要
    推理模型，而图片供应商的 default_model 可能是 image 模型）。
    """
    body_obj = None
    try:
        body_obj = json.loads(body_bytes)
    except Exception:
        body_obj = None

    last_error: Exception | Tuple[int, bytes] | None = None

    is_image_only_turn = _is_image_generation_only_turn_body(body_obj)
    for provider in providers:
        # 对话轮 + 配了 agent_model 的 provider：覆盖 model 为推理模型
        # 生图轮（image_generation tool）：不覆盖，用请求体里的图像模型
        if body_obj is not None and getattr(provider, "agent_model", None) and not is_image_only_turn:
            send_bytes = json.dumps({**body_obj, "model": provider.agent_model}, ensure_ascii=False).encode("utf-8")
        else:
            send_bytes = body_bytes
        url = f"{provider.base_url.rstrip('/')}/v1/responses"
        headers = {"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json"}
        timeout = httpx.Timeout(connect=20, read=provider.timeout_seconds, write=30, pool=10)
        # trust_env=False：不走系统代理（见 memory #142/#145）
        client = httpx.AsyncClient(timeout=timeout, trust_env=False)
        try:
            req = client.build_request("POST", url, headers=headers, content=send_bytes)
            resp = await client.send(req, stream=True)
        except _FAILABILITY_TRANSPORT as exc:
            await client.aclose()
            last_error = exc
            _log.warning("image_gen /responses provider %s connect failed: %s", provider.name, exc)
            continue

        try:
            if resp.status_code == 200:
                _log.info("image_gen /responses streaming provider=%s", provider.name)
                return _relay(resp, client), None

            # 非 200：读错误体，决定是否 failover
            err_body = await resp.aread()
            await resp.aclose()
            await client.aclose()
            if resp.status_code == 429 or resp.status_code >= 500:
                last_error = (resp.status_code, err_body)
                _log.warning(
                    "image_gen /responses provider %s HTTP %d, failover", provider.name, resp.status_code
                )
                continue
            # 4xx(非 429)：客户端错误，不 failover，回给客户端
            return None, _openai_error(
                "api_error",
                f"上游 HTTP {resp.status_code}: {err_body[:300].decode('utf-8', 'ignore')}",
                resp.status_code,
            )
        except _FAILABILITY_TRANSPORT as exc:
            try:
                await resp.aclose()
            except Exception:
                pass
            await client.aclose()
            last_error = exc
            _log.warning("image_gen /responses provider %s stream open failed: %s", provider.name, exc)
            continue

    # 所有 provider 都没成
    if isinstance(last_error, tuple):
        code, body = last_error
        return None, _openai_error(
            "api_error",
            f"所有供应商失败（last HTTP {code}）: {body[:300].decode('utf-8', 'ignore')}",
            502,
        )
    return None, _openai_error("api_error", f"所有供应商不可用: {last_error}", 502)


async def _relay(resp: httpx.Response, client: httpx.AsyncClient) -> AsyncIterator[bytes]:
    """把上游 SSE 字节原样吐给客户端，结束/异常时关闭 resp 与 client。"""
    try:
        async for chunk in resp.aiter_bytes():
            yield chunk
    finally:
        try:
            await resp.aclose()
        except Exception:
            pass
        try:
            await client.aclose()
        except Exception:
            pass
