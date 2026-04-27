"""AI context preload — fire-and-forget background warming.

Preloads profile cache so AI first-ask hits warm cache.
Does NOT write audit tables — only warms the profile cache layer.
"""
from __future__ import annotations

from .profile_context_cache import ensure_profile_context, schedule_profile_preload


def preload_ai_context(customer_id: int, window_days: int = 7, wait_ms: int = 0) -> dict:
    """Background-warm profile cache with single-flight dedup.

    Returns a status dict: {"status": "hit"|"scheduled"|"already_running", "cache_key": ...}
    """
    if wait_ms > 0:
        result = ensure_profile_context(customer_id, window_days=window_days, allow_stale=True)
    else:
        result = schedule_profile_preload(customer_id, window_days=window_days)

    return {
        "status": result.status,
        "cache_key": result.cache_key,
        "health_window_days": result.health_window_days,
        "ready": result.ready,
        "source": result.source,
        "generated_at": result.generated_at,
        "expires_at": result.expires_at,
        "stale_expires_at": result.stale_expires_at,
        "message": result.message,
    }
