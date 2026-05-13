"""Shared dataclasses, constants and module-level loggers for the ai package."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from ....sse_debug_log import get_sse_logger

_log = logging.getLogger(__name__)
_sse = get_sse_logger()

# --- Prepare cache: avoid duplicate DB queries when answer + thinking run concurrently ---

_PREPARE_CACHE: dict[tuple, tuple[float, Any]] = {}
_PREPARE_TTL = 15.0

_TXT_FENCE_RE = re.compile(r"```txt\b")


@dataclass
class PreparedAiTurn:
    session_id: str
    reuse_session: bool
    ctx: Any
    safety_card: Any  # ModulePayload — avoided import to prevent circular ref
    used_modules: list[str]
    missing_notes: list[str]
    assembly: Any
    ai_messages: list[dict[str, Any]]
    shortcut_answer: str | None = None
    shortcut_thinking: str | None = None
    rag_context_text: str = ""
    rag_sources: list[dict] = field(default_factory=list)
    rag_recommended_assets: list[dict] = field(default_factory=list)
    quoted_content: str | None = None
    health_window_days: int = 7
    cache_key: str | None = None


@dataclass
class AiChatResult:
    session_id: str
    message_id: str
    answer: str
    safety_notes: list[str] = field(default_factory=list)
    missing_data_notes: list[str] = field(default_factory=list)
    used_modules: list[str] = field(default_factory=list)
    token_usage: dict = field(default_factory=dict)
    requires_medical_review: bool = False
    prompt_version: str = ""
    scene_key: str = ""


@dataclass
class AiStreamEvent:
    event: Literal["meta", "delta", "done", "error", "loading", "rag", "analyzing"]
    data: dict[str, Any] = field(default_factory=dict)
