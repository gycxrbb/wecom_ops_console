"""Probe: check profile cache service health."""
from __future__ import annotations

import time

from .....database import SessionLocal
from ....models import CrmAiProfileCache
from .._types import ProbeResult
from .._registry import register_probe


class ProfileCacheProbe:
    name = "profile_cache"
    timeout_ms = 2000

    async def run(self) -> ProbeResult:
        t0 = time.time()
        try:
            with SessionLocal() as db:
                count = db.query(CrmAiProfileCache).count()
            return ProbeResult(self.name, "ok", f"缓存表正常 ({count} 条记录)",
                              latency_ms=int((time.time() - t0) * 1000))
        except Exception as e:
            return ProbeResult(self.name, "error", f"缓存查询失败: {e}",
                              latency_ms=int((time.time() - t0) * 1000))


register_probe(ProfileCacheProbe())
