"""Prompt Template Registry — loads and caches prompt layers from .md files."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from functools import lru_cache

_log = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent

VALID_SCENES = {
    "meal_review": "餐评",
    "data_monitoring": "数据监测",
    "abnormal_intervention": "异常干预",
    "qa_support": "问题答疑",
    "period_review": "周月复盘",
    "long_term_maintenance": "长期维护",
}

_PROMPT_VERSION = "v1.0"


def _read_md(rel_path: str) -> str:
    """Read a .md template file relative to prompts/ directory."""
    fp = _PROMPTS_DIR / rel_path
    if not fp.exists():
        _log.warning("Prompt template not found: %s", fp)
        return ""
    return fp.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def get_platform_guardrails() -> str:
    return _read_md("base/platform_guardrails.md")


@lru_cache(maxsize=1)
def get_health_coach_core() -> str:
    return _read_md("base/health_coach_core.md")


@lru_cache(maxsize=1)
def get_visible_thinking_core() -> str:
    return _read_md("base/visible_thinking_core.md")


@lru_cache(maxsize=8)
def get_scene_prompt(scene_key: str) -> str:
    if scene_key not in VALID_SCENES:
        _log.warning("Unknown scene key: %s, falling back to qa_support", scene_key)
        scene_key = "qa_support"
    return _read_md(f"scenes/{scene_key}.md")


def get_scene_label(scene_key: str) -> str:
    return VALID_SCENES.get(scene_key, scene_key)


def get_version() -> str:
    return _PROMPT_VERSION


def get_system_prompt_hash(scene_key: str) -> str:
    """Return a short hash for audit — identifies which prompt combination was used."""
    combined = get_platform_guardrails() + get_health_coach_core() + get_scene_prompt(scene_key)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def get_visible_thinking_prompt_hash(scene_key: str) -> str:
    combined = get_platform_guardrails() + get_visible_thinking_core() + get_scene_prompt(scene_key)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]
