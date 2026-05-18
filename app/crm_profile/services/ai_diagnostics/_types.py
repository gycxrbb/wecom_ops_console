"""Diagnostic probe types and report structures."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProbeResult:
    probe_name: str
    status: str          # "ok" / "warning" / "error" / "timeout"
    message: str = ""
    latency_ms: int = 0
    detail: dict = field(default_factory=dict)


@dataclass
class DiagnosticReport:
    status: str = "ok"   # "ok" / "degraded" / "unhealthy"
    probes: list[ProbeResult] = field(default_factory=list)
    summary: str = ""

    @staticmethod
    def from_results(results: list[ProbeResult]) -> DiagnosticReport:
        worst = "ok"
        for r in results:
            if r.status == "error":
                worst = "unhealthy"
                break
            if r.status == "warning" and worst != "unhealthy":
                worst = "degraded"
        failed = [r for r in results if r.status in ("error", "warning")]
        summary = "; ".join(f"{r.probe_name}: {r.message}" for r in failed) if failed else "All checks passed"
        return DiagnosticReport(status=worst, probes=results, summary=summary)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "summary": self.summary,
            "probes": [
                {"name": r.probe_name, "status": r.status, "message": r.message,
                 "latency_ms": r.latency_ms, "detail": r.detail}
                for r in self.probes
            ],
        }
