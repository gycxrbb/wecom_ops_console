"""gpt-image-2 API client — calls /images/generations endpoint.

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
"""
from __future__ import annotations

import asyncio
import base64
import logging
import time

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
    """Call gpt-image-2 API. Returns (image_bytes, metadata_dict).

    Raises ImageGenerationError on failure.
    """
    model_name = model or settings.ai_visual_model
    base_url = settings.ai_base_url.rstrip("/")
    url = f"{base_url}/images/generations"
    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "prompt": prompt,
        "n": n,
        "size": size,
        "quality": "auto",
    }

    _log.info(
        "Image generation: model=%s, size=%s, prompt_len=%d, read_timeout=%ds",
        model_name, size, len(prompt), settings.ai_visual_generation_timeout_seconds,
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

    images = data.get("data", [])
    if not images:
        raise ImageGenerationError("api_error", "No image data in response")

    img_data = images[0]

    # Prefer b64_json (gpt-image-2 default)
    if "b64_json" in img_data:
        image_bytes = base64.b64decode(img_data["b64_json"])
    elif "url" in img_data:
        image_url = img_data["url"]
        try:
            dl_resp = await _download_image(image_url)
            image_bytes = dl_resp.content
        except Exception as e:
            raise ImageGenerationError("api_error", f"Failed to download image: {e}")
    else:
        raise ImageGenerationError("api_error", "No b64_json or url in response")

    metadata = {
        "model": model_name,
        "size": size,
        "prompt_chars": len(prompt),
    }

    _log.info("Image generation success: %d bytes", len(image_bytes))
    return image_bytes, metadata


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
