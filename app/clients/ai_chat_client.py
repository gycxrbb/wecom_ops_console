"""Generic OpenAI-compatible chat client with multi-provider support (aihubmix / DeepSeek)."""
from __future__ import annotations

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

_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    """Lazy singleton httpx client with connection pooling and HTTP/2."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            http2=settings.ai_http2_enabled,
            timeout=httpx.Timeout(connect=5, read=90, write=10, pool=5),
            limits=httpx.Limits(
                max_connections=50,
                max_keepalive_connections=20,
                keepalive_expiry=300.0,
            ),
            transport=httpx.AsyncHTTPTransport(retries=1),
        )
    return _client


@dataclass
class ChatStreamChunk:
    delta: str = ""
    usage: dict = field(default_factory=dict)
    finish_reason: str | None = None


def _resolve_config(*, model_override: str | None = None) -> dict:
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


async def chat_completion(
    messages: list[dict],
    *,
    temperature: float = 0.7,
    max_tokens: int = 16384,
    model: str | None = None,
) -> tuple[str, dict]:
    cfg = _resolve_config(model_override=model)
    if not cfg['api_key'] or cfg['api_key'] == 'your-api-key-here':
        raise RuntimeError('AI 服务未配置，请设置 API KEY')

    _log.info("AI chat completion → provider=%s, model=%s", cfg['provider'], cfg['model'])
    url = f"{cfg['base_url']}/chat/completions"
    headers = {
        'Authorization': f"Bearer {cfg['api_key']}",
        'Content-Type': 'application/json',
    }
    payload = _build_payload(cfg, messages, temperature=temperature, max_tokens=max_tokens)

    try:
        client = await _get_client()
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        content = data['choices'][0]['message']['content'].strip()
        usage = data.get('usage', {})
        return content, usage
    except httpx.TimeoutException:
        _log.warning('AI chat completion timed out')
        raise RuntimeError('AI 服务响应超时')
    except httpx.HTTPStatusError as e:
        _log.error('AI API error: %s %s', e.response.status_code, e.response.text[:200])
        raise RuntimeError(f'AI 服务返回错误 ({e.response.status_code})')
    except Exception as e:
        _log.error('AI chat unexpected error: %s', e, exc_info=True)
        raise RuntimeError('AI 服务异常')


async def chat_completion_stream(
    messages: list[dict],
    *,
    temperature: float = 0.7,
    max_tokens: int = 16384,
    model: str | None = None,
) -> AsyncIterator[ChatStreamChunk]:
    cfg = _resolve_config(model_override=model)
    if not cfg['api_key'] or cfg['api_key'] == 'your-api-key-here':
        raise RuntimeError('AI 服务未配置，请设置 API KEY')

    _log.info("AI chat stream → provider=%s, model=%s", cfg['provider'], cfg['model'])
    url = f"{cfg['base_url']}/chat/completions"
    headers = {
        'Authorization': f"Bearer {cfg['api_key']}",
        'Content-Type': 'application/json',
    }
    payload = _build_payload(cfg, messages, temperature=temperature, max_tokens=max_tokens, stream=True)

    usage: dict = {}
    t0 = time.time()
    raw_idx = 0
    emitted_idx = 0
    buffer = ""
    first_chunk_yielded = False
    try:
        client = await _get_client()
        async with client.stream('POST', url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            _sse.info("[SSE-HTTPX] stream connected (provider=%s) at %.3fs", cfg['provider'], time.time() - t0)
            async for raw_line in resp.aiter_lines():
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
                finish_reason = choice.get('finish_reason')
                if not content:
                    continue

                raw_idx += 1
                # First chunk: yield immediately for TTFT
                if not first_chunk_yielded:
                    first_chunk_yielded = True
                    emitted_idx += 1
                    _sse.info("[SSE-HTTPX] first chunk at %.3fs, %d chars", time.time() - t0, len(content))
                    yield ChatStreamChunk(delta=content, usage=usage)
                    continue

                # Buffer subsequent small chunks
                buffer += content
                if len(buffer) >= _CHUNK_BUFFER_SIZE:
                    emitted_idx += 1
                    _sse.info("[SSE-HTTPX] emit buffered chunk #%d at %.3fs, %d chars",
                              emitted_idx, time.time() - t0, len(buffer))
                    yield ChatStreamChunk(delta=buffer, usage=usage)
                    buffer = ""
    except httpx.TimeoutException:
        _log.warning('AI chat stream timed out')
        raise RuntimeError('AI 服务响应超时')
    except httpx.HTTPStatusError as e:
        _log.error('AI API stream error: %s %s', e.response.status_code, e.response.text[:200])
        raise RuntimeError(f'AI 服务返回错误 ({e.response.status_code})')
    except Exception as e:
        _log.error('AI chat stream unexpected error: %s', e, exc_info=True)
        raise RuntimeError('AI 服务异常')
