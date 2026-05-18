"""Probe: check AI provider config (API key, base URL, model)."""
from __future__ import annotations

from .....config import settings
from .._types import ProbeResult
from .._registry import register_probe


class ConfigProbe:
    name = "config"
    timeout_ms = 500

    async def run(self) -> ProbeResult:
        issues: list[str] = []
        if not settings.ai_api_key:
            issues.append("ai_api_key 未配置")
        if not settings.ai_base_url:
            issues.append("ai_base_url 未配置")
        if not settings.ai_model:
            issues.append("ai_model 未配置")
        if not settings.ai_coach_enabled:
            issues.append("ai_coach_enabled=False")

        if issues:
            return ProbeResult(self.name, "error", "; ".join(issues))
        return ProbeResult(self.name, "ok", "配置正常")


register_probe(ConfigProbe())
