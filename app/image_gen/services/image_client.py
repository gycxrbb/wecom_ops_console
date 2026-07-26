"""参数化的生图客户端：按 provider 配置调用 OpenAI 兼容 /images/generations。

刻意自包含、不 import ai_visual（避免拖入整个 ai_visual 路由链，保持模块解耦）。
仅面向 openai_compatible 供应商（inferera + gpt-image-2）；doubao 分支 P1 再加。
失败抛 ImageGenerationError(error_code, message)，由 direct_orchestrator 决定是否切换供应商。
"""
from __future__ import annotations

import asyncio
import base64
import logging
import time

import httpx

from .provider_chain import ProviderConfig

_log = logging.getLogger(__name__)

_RETRYABLE_STATUS = {502, 503, 504}
_RETRYABLE_TRANSPORT = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
    httpx.ReadError,
    httpx.RemoteProtocolError,
    httpx.WriteError,
)


class ImageGenerationError(Exception):
    """生图失败。error_code: api_timeout | api_error。"""

    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        super().__init__(message)


def _extract_image_source(data: dict) -> dict:
    """从 OpenAI 兼容响应提取首个图片源。返回 {kind: 'b64'|'url', value}。"""
    items = data.get("data") if isinstance(data, dict) else None
    if isinstance(items, list) and items and isinstance(items[0], dict):
        item = items[0]
        b64 = item.get("b64_json")
        if isinstance(b64, str) and b64:
            return {"kind": "b64", "value": b64}
        url = item.get("url")
        if isinstance(url, str) and url:
            return {"kind": "url", "value": url}
    if isinstance(data, dict):
        url = data.get("url")
        if isinstance(url, str) and url:
            return {"kind": "url", "value": url}
    raise ImageGenerationError("api_error", "上游响应中未找到图片数据")


async def generate_with_provider(
    provider: ProviderConfig,
    *,
    prompt: str,
    model: str | None = None,
    size: str = "auto",
    n: int = 1,
    quality: str = "auto",
) -> tuple[bytes, dict]:
    """调用单个供应商生图。返回 (image_bytes, metadata)。"""
    model_name = model or provider.default_model
    base_url = provider.base_url.rstrip("/")
    url = f"{base_url}/v1/images/generations"
    headers = {"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json"}
    payload = {"model": model_name, "prompt": prompt, "n": n, "size": size, "quality": quality}

    started = time.perf_counter()
    try:
        resp = await _post(provider, url, headers, payload)
    except httpx.TimeoutException:
        raise ImageGenerationError("api_timeout", f"生图超时（>{provider.timeout_seconds}s）")
    except httpx.HTTPStatusError as exc:
        body = ""
        try:
            body = exc.response.text[:300]
        except Exception:
            pass
        raise ImageGenerationError("api_error", f"上游 HTTP {exc.response.status_code}: {body}")
    except Exception as exc:
        raise ImageGenerationError("api_error", f"连接错误: {exc}")

    source = _extract_image_source(resp.json())
    if source["kind"] == "b64":
        image_bytes = base64.b64decode(source["value"])
    else:
        try:
            image_bytes = (await _download(provider, source["value"])).content
        except Exception as exc:
            raise ImageGenerationError("api_error", f"生成图片下载失败: {exc}")

    elapsed = round(time.perf_counter() - started, 2)
    _log.info(
        "image_gen success provider=%s model=%s %d bytes %.1fs",
        provider.name, model_name, len(image_bytes), elapsed,
    )
    return image_bytes, {
        "model": model_name,
        "size": size,
        "n": n,
        "quality": quality,
        "prompt_chars": len(prompt),
        "elapsed_seconds": elapsed,
    }


async def _new_client(provider: ProviderConfig) -> httpx.AsyncClient:
    # trust_env=False：忽略系统代理环境变量（对齐项目 AI 链路修复，见 bug.md SSL 证书问题）
    timeout = httpx.Timeout(connect=20, read=provider.timeout_seconds, write=30, pool=10)
    return httpx.AsyncClient(timeout=timeout, trust_env=False)


async def _post(provider: ProviderConfig, url, headers, payload) -> httpx.Response:
    rounds = max(1, provider.max_retries)
    last_error: Exception | None = None
    for rnd in range(1, rounds + 1):
        client = await _new_client(provider)
        try:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code in _RETRYABLE_STATUS:
                last_error = httpx.HTTPStatusError(
                    f"retryable {resp.status_code}", request=resp.request, response=resp
                )
                _log.warning(
                    "image_gen upstream %d provider=%s round=%d/%d",
                    resp.status_code, provider.name, rnd, rounds,
                )
            else:
                resp.raise_for_status()
                return resp
        except _RETRYABLE_TRANSPORT as exc:
            last_error = exc
            _log.warning(
                "image_gen transport error provider=%s round=%d/%d: %s",
                provider.name, rnd, rounds, exc,
            )
        finally:
            await client.aclose()
        if rnd < rounds:
            await asyncio.sleep(1.0 * rnd)
    raise last_error or RuntimeError("image_gen post failed without response")


async def _download(provider: ProviderConfig, image_url: str) -> httpx.Response:
    rounds = max(1, provider.max_retries)
    last_error: Exception | None = None
    for rnd in range(1, rounds + 1):
        client = await _new_client(provider)
        try:
            resp = await client.get(image_url)
            if resp.status_code in _RETRYABLE_STATUS:
                last_error = httpx.HTTPStatusError(
                    f"retryable {resp.status_code}", request=resp.request, response=resp
                )
            else:
                resp.raise_for_status()
                return resp
        except _RETRYABLE_TRANSPORT as exc:
            last_error = exc
        finally:
            await client.aclose()
        if rnd < rounds:
            await asyncio.sleep(1.0 * rnd)
    raise last_error or RuntimeError("image_gen download failed")
