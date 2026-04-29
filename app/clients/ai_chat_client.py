"""Generic OpenAI-compatible chat client with multi-provider support (aihubmix / DeepSeek).

Includes automatic provider failover: if the primary provider fails,
requests are retried with the fallback provider (transparent to callers).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncIterator

import httpx

from ..config import settings
from ..sse_debug_log import get_sse_logger

_log = logging.getLogger(__name__)
_sse = get_sse_logger()

_CHUNK_BUFFER_SIZE = 12
_STREAM_CONNECT_RETRIES = 2  # total attempts per provider (retry once on connection error)

_clients: dict[bool, httpx.AsyncClient] = {}


def _build_client(*, http2: bool) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        http2=http2,
        timeout=httpx.Timeout(connect=20, read=90, write=10, pool=5),
        limits=httpx.Limits(
            max_connections=50,
            max_keepalive_connections=20,
            keepalive_expiry=300.0,
        ),
        transport=httpx.AsyncHTTPTransport(retries=1),
    )


async def _get_client(*, http2: bool | None = None) -> httpx.AsyncClient:
    """Lazy singleton httpx client with connection pooling."""
    use_http2 = settings.ai_http2_enabled if http2 is None else http2
    client = _clients.get(use_http2)
    if client is None or client.is_closed:
        client = _build_client(http2=use_http2)
        _clients[use_http2] = client
    return client


async def _close_client(*, http2: bool | None = None) -> None:
    """Close one cached client after a protocol-level connection failure."""
    if http2 is None:
        clients = list(_clients.items())
    else:
        client = _clients.get(http2)
        clients = [(http2, client)] if client is not None else []

    for key, client in clients:
        if client is None:
            continue
        try:
            await client.aclose()
        except Exception:
            pass
        _clients.pop(key, None)


def _http2_attempts() -> list[bool]:
    attempts = [settings.ai_http2_enabled]
    if settings.ai_http2_enabled:
        attempts.append(False)
    return attempts


async def _post_chat_completion(url: str, headers: dict, payload: dict) -> httpx.Response:
    last_remote_error: httpx.RemoteProtocolError | None = None
    for idx, use_http2 in enumerate(_http2_attempts(), start=1):
        try:
            client = await _get_client(http2=use_http2)
            return await client.post(url, headers=headers, json=payload)
        except (httpx.RemoteProtocolError, httpx.ReadError) as exc:
            last_remote_error = exc
            await _close_client(http2=use_http2)
            if idx == 1 and settings.ai_http2_enabled:
                _log.warning(
                    "AI chat remote protocol error before response, retrying with HTTP/1.1: %s",
                    exc,
                )
                continue
            raise

    if last_remote_error:
        raise last_remote_error
    raise RuntimeError("AI 服务异常")


async def _stream_chat_completion(
    url: str,
    headers: dict,
    payload: dict,
    *,
    provider: str,
) -> AsyncIterator[tuple[httpx.Response, str]]:
    last_remote_error: httpx.RemoteProtocolError | None = None
    for idx, use_http2 in enumerate(_http2_attempts(), start=1):
        yielded_any_line = False
        try:
            client = await _get_client(http2=use_http2)
            async with client.stream('POST', url, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                async for raw_line in resp.aiter_lines():
                    yielded_any_line = True
                    yield resp, raw_line
                return
        except (httpx.RemoteProtocolError, httpx.ReadError) as exc:
            last_remote_error = exc
            await _close_client(http2=use_http2)
            if not yielded_any_line and idx == 1 and settings.ai_http2_enabled:
                _log.warning(
                    "AI chat stream disconnected before response/chunk "
                    "(provider=%s), retrying with HTTP/1.1: %s",
                    provider,
                    exc,
                )
                continue
            raise

    if last_remote_error:
        raise last_remote_error
    raise RuntimeError("AI 服务异常")


# ── Provider config resolution ──────────────────────────────────────────


@dataclass
class ChatStreamChunk:
    delta: str = ""
    usage: dict = field(default_factory=dict)
    finish_reason: str | None = None


def _resolve_config(*, model_override: str | None = None, provider: str | None = None) -> dict:
    if provider == 'aihubmix':
        return {
            'base_url': settings.ai_base_url.rstrip('/'),
            'api_key': settings.ai_api_key,
            'model': model_override or settings.ai_model,
            'provider': 'aihubmix',
        }
    if provider == 'deepseek':
        return {
            'base_url': settings.deepseek_base_url.rstrip('/'),
            'api_key': settings.deepseek_api_key,
            'model': model_override or settings.deepseek_model,
            'provider': 'deepseek',
        }
    if settings.ai_provider == 'deepseek' and settings.deepseek_api_key:
        return {
            'base_url': settings.deepseek_base_url.rstrip('/'),
            'api_key': settings.deepseek_api_key,
            'model': model_override or settings.deepseek_model,
            'provider': 'deepseek',
        }
    return {
        'base_url': settings.ai_base_url.rstrip('/'),
        'api_key': settings.ai_api_key,
        'model': model_override or settings.ai_model,
        'provider': 'aihubmix',
    }


def _fallback_config(*, model_override: str | None = None) -> dict | None:
    """Return the opposite provider config for failover, or None if unavailable."""
    primary = settings.ai_provider
    if primary == 'deepseek':
        if not settings.ai_api_key:
            return None
        return {
            'base_url': settings.ai_base_url.rstrip('/'),
            'api_key': settings.ai_api_key,
            'model': model_override or settings.ai_model,
            'provider': 'aihubmix',
        }
    if settings.deepseek_api_key:
        return {
            'base_url': settings.deepseek_base_url.rstrip('/'),
            'api_key': settings.deepseek_api_key,
            'model': model_override or settings.deepseek_model,
            'provider': 'deepseek',
        }
    return None


def _is_failover_eligible(exc: Exception) -> bool:
    """Whether an error should trigger provider-level failover."""
    if isinstance(exc, (httpx.TimeoutException, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500 or exc.response.status_code == 429
    if isinstance(exc, RuntimeError):
        msg = str(exc)
        return any(kw in msg for kw in ('超时', '异常', '错误'))
    return True  # Unexpected errors are also eligible


def _build_payload(cfg: dict, messages: list[dict], *,
                   temperature: float, max_tokens: int, stream: bool = False) -> dict:
    payload: dict = {
        'model': cfg['model'],
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens,
    }
    if stream:
        payload['stream'] = True
        payload['stream_options'] = {'include_usage': True}
    return payload


# ── Public API ──────────────────────────────────────────────────────────


async def chat_completion(
    messages: list[dict],
    *,
    temperature: float = 0.7,
    max_tokens: int = 16384,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[str, dict]:
    """Non-streaming chat completion with automatic provider failover."""
    cfg = _resolve_config(model_override=model, provider=provider)
    if not cfg['api_key'] or cfg['api_key'] == 'your-api-key-here':
        raise RuntimeError('AI 服务未配置，请设置 API KEY')

    try:
        return await _do_chat_completion(cfg, messages, temperature, max_tokens)
    except Exception as exc:
        # Explicit provider (e.g. Vision) — no failover
        if provider is not None:
            raise
        if not _is_failover_eligible(exc):
            raise
        fb = _fallback_config(model_override=model)
        if not fb:
            raise
        _log.warning(
            "chat_completion: primary %s failed (%s), failing over to %s",
            cfg['provider'], exc, fb['provider'],
        )
        return await _do_chat_completion(fb, messages, temperature, max_tokens)


async def _do_chat_completion(
    cfg: dict, messages: list[dict], temperature: float, max_tokens: int,
) -> tuple[str, dict]:
    _log.info("AI chat completion → provider=%s, model=%s", cfg['provider'], cfg['model'])
    url = f"{cfg['base_url']}/chat/completions"
    headers = {
        'Authorization': f"Bearer {cfg['api_key']}",
        'Content-Type': 'application/json',
    }
    payload = _build_payload(cfg, messages, temperature=temperature, max_tokens=max_tokens)

    try:
        resp = await _post_chat_completion(url, headers, payload)
        resp.raise_for_status()
        data = resp.json()
        content = data['choices'][0]['message']['content'].strip()
        usage = data.get('usage', {})
        return content, usage
    except httpx.TimeoutException:
        _log.warning('AI chat completion timed out (provider=%s)', cfg['provider'])
        raise RuntimeError('AI 服务响应超时')
    except httpx.HTTPStatusError as e:
        _log.error('AI API error: %s %s (provider=%s)', e.response.status_code, e.response.text[:200], cfg['provider'])
        raise RuntimeError(f'AI 服务返回错误 ({e.response.status_code})')
    except RuntimeError:
        raise
    except Exception as e:
        _log.error('AI chat unexpected error (provider=%s): %s', cfg['provider'], e, exc_info=True)
        raise RuntimeError(f'AI 服务连接失败 ({cfg["provider"]})')


async def chat_completion_stream(
    messages: list[dict],
    *,
    temperature: float = 0.7,
    max_tokens: int = 16384,
    model: str | None = None,
    provider: str | None = None,
) -> AsyncIterator[ChatStreamChunk]:
    """Streaming chat completion with automatic provider failover (pre-first-chunk only)."""
    cfg = _resolve_config(model_override=model, provider=provider)
    if not cfg['api_key'] or cfg['api_key'] == 'your-api-key-here':
        raise RuntimeError('AI 服务未配置，请设置 API KEY')

    yielded_any = False
    try:
        async for chunk in _do_stream(cfg, messages, temperature, max_tokens):
            yielded_any = True
            yield chunk
        return
    except Exception as exc:
        # Already streamed partial content — can't retry
        if yielded_any:
            raise
        # Explicit provider — no failover
        if provider is not None:
            raise
        if not _is_failover_eligible(exc):
            raise
        fb = _fallback_config(model_override=model)
        if not fb:
            raise
        _log.warning(
            "chat_completion_stream: primary %s failed before first chunk (%s), "
            "failing over to %s",
            cfg['provider'], exc, fb['provider'],
        )
        async for chunk in _do_stream(fb, messages, temperature, max_tokens):
            yield chunk


async def _do_stream(
    cfg: dict, messages: list[dict], temperature: float, max_tokens: int,
) -> AsyncIterator[ChatStreamChunk]:
    """Core streaming logic for a single provider config with connection-level retry."""
    _log.info("AI chat stream → provider=%s, model=%s", cfg['provider'], cfg['model'])
    url = f"{cfg['base_url']}/chat/completions"
    headers = {
        'Authorization': f"Bearer {cfg['api_key']}",
        'Content-Type': 'application/json',
    }
    payload = _build_payload(cfg, messages, temperature=temperature, max_tokens=max_tokens, stream=True)

    last_conn_error: Exception | None = None
    for attempt in range(1, _STREAM_CONNECT_RETRIES + 1):
        usage: dict = {}
        t0 = time.time()
        raw_idx = 0
        emitted_idx = 0
        buffer = ""
        first_chunk_yielded = False
        try:
            stream_connected = False
            async for resp, raw_line in _stream_chat_completion(url, headers, payload, provider=cfg['provider']):
                if not stream_connected:
                    stream_connected = True
                    protocol = "HTTP/2" if resp.http_version == "HTTP/2" else "HTTP/1.1"
                    _sse.info(
                        "[SSE-HTTPX] stream connected (provider=%s, protocol=%s) at %.3fs",
                        cfg['provider'],
                        protocol,
                        time.time() - t0,
                    )
                line = (raw_line or '').strip()
                if not line or not line.startswith('data:'):
                    continue

                data_str = line[5:].strip()
                if data_str == '[DONE]':
                    if buffer:
                        emitted_idx += 1
                        _sse.info("[SSE-HTTPX] flush buffer at [DONE], %d chars", len(buffer))
                        yield ChatStreamChunk(delta=buffer, usage=usage)
                        buffer = ""
                    _sse.info("[SSE-HTTPX] [DONE] at %.3fs, raw=%d emitted=%d",
                              time.time() - t0, raw_idx, emitted_idx)
                    yield ChatStreamChunk(usage=usage, finish_reason='stop')
                    break

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    _log.warning('Invalid streaming chunk: %s', data_str[:200])
                    continue

                if data.get('usage'):
                    usage = data.get('usage') or usage

                choices = data.get('choices') or []
                if not choices:
                    continue
                choice = choices[0] or {}
                delta_obj = choice.get('delta') or {}
                content = delta_obj.get('content') or ''
                if not content:
                    continue

                raw_idx += 1
                if not first_chunk_yielded:
                    first_chunk_yielded = True
                    emitted_idx += 1
                    _sse.info("[SSE-HTTPX] first chunk at %.3fs, %d chars", time.time() - t0, len(content))
                    yield ChatStreamChunk(delta=content, usage=usage)
                    continue

                buffer += content
                if len(buffer) >= _CHUNK_BUFFER_SIZE:
                    emitted_idx += 1
                    _sse.info("[SSE-HTTPX] emit buffered chunk #%d at %.3fs, %d chars",
                              emitted_idx, time.time() - t0, len(buffer))
                    yield ChatStreamChunk(delta=buffer, usage=usage)
                    buffer = ""
            return  # stream completed successfully
        except httpx.TimeoutException:
            _log.warning('AI chat stream timed out (provider=%s)', cfg['provider'])
            raise RuntimeError('AI 服务响应超时')
        except httpx.HTTPStatusError as e:
            _log.error('AI API stream error: %s %s (provider=%s)', e.response.status_code, e.response.text[:200], cfg['provider'])
            raise RuntimeError(f'AI 服务返回错误 ({e.response.status_code})')
        except RuntimeError:
            raise
        except Exception as e:
            last_conn_error = e
            if first_chunk_yielded:
                _log.error('AI chat stream broken after partial content (provider=%s): %s', cfg['provider'], e, exc_info=True)
                raise RuntimeError(f'AI 响应中途断开 ({cfg["provider"]})')
            if attempt < _STREAM_CONNECT_RETRIES:
                delay = 1.5 * attempt
                _log.warning(
                    'AI chat stream connection error (provider=%s, attempt=%d/%d), '
                    'retrying in %.1fs: %s',
                    cfg['provider'], attempt, _STREAM_CONNECT_RETRIES, delay, e,
                )
                await _close_client()
                await asyncio.sleep(delay)
                continue
            _log.error('AI chat stream unexpected error (provider=%s): %s', cfg['provider'], e, exc_info=True)
            raise RuntimeError(f'AI 服务连接失败 ({cfg["provider"]})')

    _log.error('AI chat stream exhausted retries (provider=%s): %s', cfg['provider'], last_conn_error)
    raise RuntimeError(f'AI 服务连接失败 ({cfg["provider"]})')
