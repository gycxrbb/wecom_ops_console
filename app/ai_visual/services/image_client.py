"""AI visual image generation client.

设计要点（对齐 aihubmix 官方 sample 与 OpenAI Python SDK 的行为）：

- 默认走 HTTP/1.1，不与全局 ``ai_http2_enabled`` 联动。httpx 的 HTTP/2 在
  长 hang 请求上历史不稳（参考 bug.md #65/#66），而 OpenAI SDK 自身也走
  HTTP/1.1。
- 读超时按 aihubmix 官方说明对齐 ≥10 分钟（``ai_visual_generation_timeout_seconds``
  默认 600s）。gpt-image-2 单次生成可能 >5 分钟。
- 每次 ``generate_image`` 用一次性 client，避免长期复用连接池在出错后
  残留坏连接。
- 连接级错误（``RemoteProtocolError`` / ``ReadError`` / ``ConnectError`` 等）
  做有限重试；只有当一次尝试已经跑到接近读超时（``ai_visual_generation_gateway_timeout_hint_seconds``）
  才判 ``api_timeout`` 并停止重试，避免被 aihubmix 多次计费。
- ``doubao/doubao-seedream-*`` 走 aihubmix predictions endpoint；其他模型继续走
  OpenAI-compatible ``/images/generations``。
"""
from __future__ import annotations

import asyncio
import base64
import logging
import time
from typing import Any

import httpx

from app.config import settings

_log = logging.getLogger(__name__)

# 历史兼容：测试用例会向 _clients 注入，保留同名容器但当前实现不再复用全局连接池。
_clients: dict[bool, httpx.AsyncClient] = {}
_RETRYABLE_STATUS_CODES = {502, 503, 504}
_RETRYABLE_TRANSPORT_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
    httpx.ReadError,
    httpx.RemoteProtocolError,
    httpx.WriteError,
)
_DOUBAO_SEEDREAM_PREFIXES = ("doubao/", "doubao-seedream")


class ImageGenerationError(Exception):
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        super().__init__(message)


def _build_client(*, http2: bool) -> httpx.AsyncClient:
    timeout = httpx.Timeout(
        connect=20,
        read=settings.ai_visual_generation_timeout_seconds,
        write=30,
        pool=10,
    )
    return httpx.AsyncClient(timeout=timeout, http2=http2)


def _image_http2_enabled() -> bool:
    return bool(getattr(settings, "ai_visual_http2_enabled", False))


def _max_retry_rounds() -> int:
    return max(1, settings.ai_visual_generation_max_retries)


def _gateway_timeout_hint_seconds() -> float:
    return max(1.0, float(settings.ai_visual_generation_gateway_timeout_hint_seconds))


async def _sleep_before_retry(round_index: int) -> None:
    delay = max(0.0, settings.ai_visual_generation_retry_delay_seconds) * round_index
    if delay > 0:
        await asyncio.sleep(delay)


async def generate_image(
    *,
    prompt: str,
    model: str | None = None,
    size: str = "auto",
    n: int = 1,
) -> tuple[bytes, dict]:
    """Call the configured image generation API. Returns (image_bytes, metadata_dict).

    Raises ImageGenerationError on failure.
    """
    model_name = model or settings.ai_visual_model
    base_url = settings.ai_base_url.rstrip("/")
    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
    }
    endpoint = _endpoint_for_model(model_name)
    url, payload = _build_generation_request(
        base_url=base_url,
        model_name=model_name,
        prompt=prompt,
        size=size,
        n=n,
    )

    _log.info(
        "Image generation: model=%s, endpoint=%s, size=%s, prompt_len=%d, read_timeout=%ds",
        model_name, endpoint, _metadata_size(model_name, size), len(prompt), settings.ai_visual_generation_timeout_seconds,
    )

    try:
        resp = await _post_generation(url, headers, payload)
        data = resp.json()
    except ImageGenerationError:
        raise
    except httpx.TimeoutException:
        raise ImageGenerationError(
            "api_timeout",
            f"Image generation timed out (read={settings.ai_visual_generation_timeout_seconds}s)",
        )
    except httpx.HTTPStatusError as e:
        body = ""
        try:
            body = e.response.text[:300]
        except Exception:
            pass
        raise ImageGenerationError("api_error", f"API error {e.response.status_code}: {body}")
    except Exception as e:
        raise ImageGenerationError("api_error", f"Connection error: {e}")

    image_source = _extract_image_source(data)
    if image_source["kind"] == "b64":
        image_bytes = base64.b64decode(image_source["value"])
    elif image_source["kind"] == "url":
        image_url = image_source["value"]
        try:
            dl_resp = await _download_image(image_url)
            image_bytes = dl_resp.content
        except Exception as e:
            raise ImageGenerationError("api_error", f"Failed to download image: {e}")
    else:
        raise ImageGenerationError("api_error", "No b64_json or url in response")

    metadata = {
        "model": model_name,
        "endpoint": endpoint,
        "size": _metadata_size(model_name, size),
        "prompt_chars": len(prompt),
    }

    _log.info("Image generation success: %d bytes", len(image_bytes))
    return image_bytes, metadata


def _endpoint_for_model(model_name: str) -> str:
    return "doubao_predictions" if _is_doubao_seedream_model(model_name) else "openai_images"


def _is_doubao_seedream_model(model_name: str) -> bool:
    normalized = (model_name or "").strip().lower()
    return normalized.startswith(_DOUBAO_SEEDREAM_PREFIXES) or "doubao-seedream" in normalized


def _normalize_doubao_model_path(model_name: str) -> str:
    normalized = (model_name or "").strip().strip("/")
    if normalized.startswith("doubao/"):
        return normalized
    return f"doubao/{normalized}"


def _metadata_size(model_name: str, requested_size: str) -> str:
    if _is_doubao_seedream_model(model_name):
        return settings.ai_visual_seedream_size or "2K"
    return requested_size


def _build_generation_request(
    *,
    base_url: str,
    model_name: str,
    prompt: str,
    size: str,
    n: int,
) -> tuple[str, dict]:
    if _is_doubao_seedream_model(model_name):
        model_path = _normalize_doubao_model_path(model_name)
        return (
            f"{base_url}/models/{model_path}/predictions",
            {
                "input": {
                    "prompt": prompt,
                    "size": settings.ai_visual_seedream_size or "2K",
                    "sequential_image_generation": "disabled",
                    "stream": False,
                    "response_format": "url",
                    "watermark": bool(settings.ai_visual_seedream_watermark),
                }
            },
        )

    return (
        f"{base_url}/images/generations",
        {
            "model": model_name,
            "prompt": prompt,
            "n": n,
            "size": size,
            "quality": "auto",
        },
    )


def _extract_image_source(data: dict[str, Any]) -> dict[str, str]:
    """Return the first image source from OpenAI or predictions-style responses."""
    openai_images = data.get("data")
    source = _source_from_candidate(openai_images)
    if source:
        return source

    for key in ("output", "result", "images", "image", "urls", "url"):
        source = _source_from_candidate(data.get(key))
        if source:
            return source

    prediction = data.get("prediction")
    source = _source_from_candidate(prediction)
    if source:
        return source

    status = data.get("status")
    if status and status not in {"succeeded", "success", "completed"}:
        raise ImageGenerationError("api_error", f"Image prediction not completed: status={status}")

    raise ImageGenerationError("api_error", "No image data in response")


def _source_from_candidate(candidate: Any) -> dict[str, str] | None:
    if candidate is None:
        return None
    if isinstance(candidate, str):
        if candidate.startswith(("http://", "https://")):
            return {"kind": "url", "value": candidate}
        if candidate.startswith("data:image/") and ";base64," in candidate:
            return {"kind": "b64", "value": candidate.split(";base64,", 1)[1]}
        return None
    if isinstance(candidate, list):
        for item in candidate:
            source = _source_from_candidate(item)
            if source:
                return source
        return None
    if isinstance(candidate, dict):
        for key in ("b64_json", "base64", "image_base64"):
            value = candidate.get(key)
            if isinstance(value, str) and value:
                return {"kind": "b64", "value": value}
        for key in ("url", "image_url", "image", "file_url"):
            source = _source_from_candidate(candidate.get(key))
            if source:
                return source
        for key in ("output", "result", "images", "data"):
            source = _source_from_candidate(candidate.get(key))
            if source:
                return source
    return None


async def _post_generation(url: str, headers: dict, payload: dict) -> httpx.Response:
    last_error: Exception | None = None
    max_rounds = _max_retry_rounds()
    use_http2 = _image_http2_enabled()

    for round_index in range(1, max_rounds + 1):
        client = _build_client(http2=use_http2)
        request_started_at = time.perf_counter()
        try:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code in _RETRYABLE_STATUS_CODES:
                last_error = httpx.HTTPStatusError(
                    f"retryable upstream status {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
                _log.warning(
                    "Image generation upstream HTTP %d (round=%d/%d, http2=%s)",
                    resp.status_code, round_index, max_rounds, use_http2,
                )
            else:
                resp.raise_for_status()
                return resp
        except _RETRYABLE_TRANSPORT_ERRORS as exc:
            last_error = exc
            elapsed_seconds = time.perf_counter() - request_started_at
            if elapsed_seconds >= _gateway_timeout_hint_seconds():
                # 已经长 hang 到接近读超时，几乎可以确定上游真的在生成但网关/上游 timeout 了；
                # 继续重试只会被多次计费。归类为 api_timeout 并停止。
                raise ImageGenerationError(
                    "api_timeout",
                    "Image generation upstream disconnected after "
                    f"{elapsed_seconds:.1f}s before sending a response; "
                    "likely provider gateway timeout or upstream generation timeout",
                ) from exc
            _log.warning(
                "Image generation connection error (round=%d/%d, http2=%s, elapsed=%.1fs): %s",
                round_index, max_rounds, use_http2, elapsed_seconds, exc,
            )
        finally:
            try:
                await client.aclose()
            except Exception:
                pass

        if round_index < max_rounds:
            await _sleep_before_retry(round_index)

    if last_error:
        raise last_error
    raise RuntimeError("Image generation failed before receiving a response")


async def _download_image(image_url: str) -> httpx.Response:
    last_error: Exception | None = None
    max_rounds = _max_retry_rounds()
    use_http2 = _image_http2_enabled()

    for round_index in range(1, max_rounds + 1):
        client = _build_client(http2=use_http2)
        try:
            resp = await client.get(image_url)
            if resp.status_code in _RETRYABLE_STATUS_CODES:
                last_error = httpx.HTTPStatusError(
                    f"retryable image download status {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
            else:
                resp.raise_for_status()
                return resp
        except _RETRYABLE_TRANSPORT_ERRORS as exc:
            last_error = exc
        finally:
            try:
                await client.aclose()
            except Exception:
                pass

        if round_index < max_rounds:
            _log.warning(
                "Image download retry %d/%d for generated image: %s",
                round_index + 1, max_rounds, last_error,
            )
            await _sleep_before_retry(round_index)

    if last_error:
        raise last_error
    raise RuntimeError("Generated image download failed")
