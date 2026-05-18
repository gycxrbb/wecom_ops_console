"""Probe: check JWT secret key is configured."""
from __future__ import annotations

from .....config import settings
from .._types import ProbeResult
from .._registry import register_probe


class AuthProbe:
    name = "auth"
    timeout_ms = 300

    async def run(self) -> ProbeResult:
        if settings.jwt_secret_key == "your-256-bit-secret-key-change-me":
            return ProbeResult(self.name, "warning", "JWT 密钥使用默认值，生产环境需更换")
        return ProbeResult(self.name, "ok", "鉴权配置正常")


register_probe(AuthProbe())
