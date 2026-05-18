"""Probe: lightweight model health check via minimal completion request."""
from __future__ import annotations

import time

from .....config import settings
from .._types import ProbeResult
from .._registry import register_probe

_last_probe_time: float = 0
_last_result: ProbeResult | None = None


class ProviderHealthProbe:
    name = "provider_health"
    timeout_ms = 15000

    async def run(self) -> ProbeResult:
        global _last_probe_time, _last_result
        if not settings.ai_api_key:
            return ProbeResult(self.name, "error", "API key 未配置")

        now = time.time()
        if _last_result and now - _last_probe_time < 30:
            return _last_result

        t0 = time.time()
        try:
            from .....clients.ai_chat_client import chat_completion
            content, usage = await chat_completion(
                [{"role": "user", "content": "hi"}],
                temperature=0, max_tokens=5,
                provider=settings.ai_provider,
                model=settings.ai_model,
            )
            latency = int((time.time() - t0) * 1000)
            result = ProbeResult(self.name, "ok", f"模型响应正常 ({latency}ms)",
                                latency_ms=latency, detail={"model": settings.ai_model})
        except Exception as e:
            latency = int((time.time() - t0) * 1000)
            result = ProbeResult(self.name, "error", f"模型调用失败: {e}", latency_ms=latency)

        _last_probe_time = now
        _last_result = result
        return result


register_probe(ProviderHealthProbe())
