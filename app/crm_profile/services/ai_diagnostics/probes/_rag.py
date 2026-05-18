"""Probe: check RAG service (Qdrant) connectivity."""
from __future__ import annotations

import time

from .....config import settings
from .._types import ProbeResult
from .._registry import register_probe


class RagProbe:
    name = "rag"
    timeout_ms = 3000

    async def run(self) -> ProbeResult:
        if not settings.rag_enabled:
            return ProbeResult(self.name, "ok", "RAG 未启用，跳过")
        t0 = time.time()
        try:
            from .....rag.client import get_qdrant_client
            client = get_qdrant_client()
            collections = client.get_collections().collections
            names = [c.name for c in collections]
            target = settings.qdrant_collection
            if target in names:
                info = client.get_collection(target)
                return ProbeResult(self.name, "ok",
                                  f"集合 {target} 存在 ({info.points_count} 条向量)",
                                  latency_ms=int((time.time() - t0) * 1000),
                                  detail={"points": info.points_count})
            return ProbeResult(self.name, "warning",
                              f"集合 {target} 不存在 (可用: {', '.join(names[:5])})",
                              latency_ms=int((time.time() - t0) * 1000))
        except Exception as e:
            return ProbeResult(self.name, "error", f"RAG 连接失败: {e}",
                              latency_ms=int((time.time() - t0) * 1000))


register_probe(RagProbe())
