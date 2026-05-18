"""Probe registry — each probe is a lightweight async health check."""
from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from ._types import ProbeResult

_log = logging.getLogger(__name__)

_PROBES: list[DiagnosticProbe] = []


@runtime_checkable
class DiagnosticProbe(Protocol):
    name: str
    timeout_ms: int

    async def run(self) -> ProbeResult: ...


def register_probe(probe: DiagnosticProbe) -> None:
    _PROBES.append(probe)


def list_probes() -> list[DiagnosticProbe]:
    return list(_PROBES)
