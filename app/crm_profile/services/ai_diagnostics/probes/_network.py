"""Probe: check network connectivity to AI provider."""
from __future__ import annotations

import socket
import time
from urllib.parse import urlparse

from .....config import settings
from .._types import ProbeResult
from .._registry import register_probe


class NetworkProbe:
    name = "network"
    timeout_ms = 5000

    async def run(self) -> ProbeResult:
        url = settings.ai_base_url
        if not url:
            return ProbeResult(self.name, "error", "ai_base_url 未配置")
        t0 = time.time()
        try:
            parsed = urlparse(url)
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            sock = socket.create_connection((host, port), timeout=5)
            sock.close()
            return ProbeResult(self.name, "ok", f"{host}:{port} 连通正常",
                              latency_ms=int((time.time() - t0) * 1000))
        except Exception as e:
            return ProbeResult(self.name, "error", f"{host} 连接失败: {e}",
                              latency_ms=int((time.time() - t0) * 1000))


register_probe(NetworkProbe())
