"""AI diagnostics pipeline — run probes and produce DiagnosticReport."""
from __future__ import annotations

import asyncio
import logging

from ._types import DiagnosticReport, ProbeResult
from ._registry import list_probes

_log = logging.getLogger(__name__)

# Auto-register built-in probes on import
from . import probes as _probes  # noqa: F401


async def diagnose() -> DiagnosticReport:
    """Run all registered probes concurrently and return a report."""
    registered = list_probes()
    if not registered:
        return DiagnosticReport(status="ok", summary="No probes registered")

    async def _safe_run(probe) -> ProbeResult:
        try:
            return await asyncio.wait_for(probe.run(), timeout=probe.timeout_ms / 1000.0)
        except asyncio.TimeoutError:
            return ProbeResult(probe.name, "timeout", f"超时 ({probe.timeout_ms}ms)")
        except Exception as e:
            return ProbeResult(probe.name, "error", f"执行异常: {e}")

    results = await asyncio.gather(*[_safe_run(p) for p in registered])
    return DiagnosticReport.from_results(list(results))
