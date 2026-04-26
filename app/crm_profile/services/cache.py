"""Lightweight in-memory TTL cache for CRM profile data.

Not intended for multi-process deployment; for that scenario switch to Redis.
Thread-safe via a simple lock.

Supports stale-while-revalidate: ``get_stale()`` returns expired entries so
callers can use stale data while refreshing in the background.

Note: ``get()`` does NOT delete expired entries — it returns None but leaves
them in the store so ``get_stale()`` can still find them within the grace period.
"""
from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}

# Default TTLs (seconds)
PROFILE_TTL = 600        # customer profile: 10 min (profile data changes infrequently)
FILTER_OPTIONS_TTL = 300  # filter dropdowns: 5 min

# Stale grace period: expired entries are kept this long after TTL for stale-while-revalidate.
STALE_GRACE = 300  # 5 minutes


def get(key: str) -> Any | None:
    """Return cached value if it exists and hasn't expired, else None.

    Does NOT remove expired entries so ``get_stale()`` can still find them.
    """
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            return None
        return value


def get_stale(key: str) -> Any | None:
    """Return value even if expired (within grace period), for stale-while-revalidate.

    Returns None only if the key never existed or has exceeded TTL + grace period.
    Cleans up entries that are past the grace period.
    """
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        now = time.monotonic()
        if now > expires_at + STALE_GRACE:
            del _store[key]
            return None
        return value


def put(key: str, value: Any, ttl: float = PROFILE_TTL) -> None:
    """Store a value with the given TTL."""
    with _lock:
        _store[key] = (time.monotonic() + ttl, value)


def invalidate(key: str) -> None:
    """Remove a specific key."""
    with _lock:
        _store.pop(key, None)


def invalidate_prefix(prefix: str) -> None:
    """Remove all keys with the given prefix."""
    with _lock:
        to_del = [k for k in _store if k.startswith(prefix)]
        for k in to_del:
            del _store[k]


def clear_all() -> None:
    """Clear entire cache."""
    with _lock:
        _store.clear()
