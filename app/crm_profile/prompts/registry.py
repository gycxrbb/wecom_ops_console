"""Prompt Template Registry — loads prompts from DB (priority) or .md files (fallback)."""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from pathlib import Path

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

VALID_STYLES = {
    "coach_brief": "教练简报",
    "customer_reply": "客户话术",
    "handoff_note": "交接备注",
    "bullet_list": "要点列表",
    "detailed_report": "详细报告",
}

_PROMPT_VERSION = "v2.1"

# ── TTL Cache ───────────────────────────────────────────────────────────────

_CACHE_TTL = 60  # seconds
_CACHE_MISS = object()  # sentinel: key not in cache or expired
_cache: dict[str, tuple[object, float]] = {}
_cache_lock = threading.Lock()


def _cache_get(key: str):
    """Return cached value, or _CACHE_MISS if absent/expired."""
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return _CACHE_MISS
        val, ts = entry
        if (time.monotonic() - ts) < _CACHE_TTL:
            return val
        return _CACHE_MISS


def _cache_set(key: str, value) -> None:
    with _cache_lock:
        _cache[key] = (value, time.monotonic())


def _cache_invalidate(key: str | None = None) -> None:
    with _cache_lock:
        if key:
            _cache.pop(key, None)
        else:
            _cache.clear()


# ── DB lookup ────────────────────────────────────────────────────────────────

def _db_lookup(key: str) -> tuple[str, bool] | None:
    """Load prompt from DB. Returns (content, is_active) or None if not in DB."""
    try:
        from ...database import SessionLocal
        from ...models_prompt import PromptTemplate

        db = SessionLocal()
        try:
            row = db.query(PromptTemplate).filter_by(key=key).first()
            if row is None:
                return None
            return (row.content, row.is_active)
        finally:
            db.close()
    except Exception:
        return None


# ── Core loader ──────────────────────────────────────────────────────────────

def _read_md(rel_path: str) -> str:
    fp = _PROMPTS_DIR / rel_path
    if not fp.exists():
        _log.warning("Prompt template not found: %s", fp)
        return ""
    return fp.read_text(encoding="utf-8").strip()


def _load_prompt(cache_key: str, fallback_path: str) -> str:
    """Load prompt: cache → DB → .md file.

    Templates marked is_active=False in DB return "" (no .md fallback),
    ensuring snapshot rollback fully deactivates v2-only templates.
    """
    cached = _cache_get(cache_key)
    if cached is not _CACHE_MISS:
        return cached if cached else ""

    db_result = _db_lookup(cache_key)
    if db_result is not None:
        content, is_active = db_result
        if not is_active:
            _cache_set(cache_key, None)
            return ""
        _cache_set(cache_key, content)
        return content

    # Not in DB at all — fallback to .md
    content = _read_md(fallback_path)
    if content:
        _cache_set(cache_key, content)
    return content


# ── Public API ───────────────────────────────────────────────────────────────

def reload_prompt(key: str) -> None:
    """Invalidate cache for a specific prompt key (called after admin save)."""
    _cache_invalidate(key)


def reload_all() -> None:
    """Invalidate all cached prompts."""
    _cache_invalidate()


def get_platform_guardrails() -> str:
    return _load_prompt("platform_guardrails", "base/platform_guardrails.md")


def get_health_coach_core() -> str:
    return _load_prompt("health_coach_core", "base/health_coach_core.md")


def get_visible_thinking_core() -> str:
    return _load_prompt("visible_thinking_core", "base/visible_thinking_core.md")


def get_context_header() -> str:
    return _load_prompt("context_header", "base/context_header.md")


def get_rag_header() -> str:
    return _load_prompt("rag_header", "base/rag_header.md")


def get_scene_hint_header() -> str:
    return _load_prompt("scene_hint_header", "base/scene_hint_header.md")


def get_scene_prompt(scene_key: str) -> str:
    if scene_key not in VALID_SCENES:
        _log.warning("Unknown scene key: %s, falling back to qa_support", scene_key)
        scene_key = "qa_support"
    return _load_prompt(scene_key, f"scenes/{scene_key}.md")


def get_style_prompt(style_key: str) -> str:
    if style_key not in VALID_STYLES:
        _log.warning("Unknown style key: %s, falling back to coach_brief", style_key)
        style_key = "coach_brief"
    return _load_prompt(style_key, f"styles/{style_key}.md")


def get_scene_label(scene_key: str) -> str:
    return VALID_SCENES.get(scene_key, scene_key)


def get_style_label(style_key: str) -> str:
    return VALID_STYLES.get(style_key, style_key)


def get_version() -> str:
    return _PROMPT_VERSION


def get_system_prompt_hash(scene_key: str) -> str:
    combined = get_platform_guardrails() + get_health_coach_core() + get_scene_prompt(scene_key)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def get_visible_thinking_prompt_hash(scene_key: str) -> str:
    combined = get_platform_guardrails() + get_visible_thinking_core() + get_scene_prompt(scene_key)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]
