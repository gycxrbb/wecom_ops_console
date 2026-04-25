"""Lightweight in-memory TTL cache for CRM profile data.

Not intended for multi-process deployment; for that scenario switch to Redis.
Thread-safe via a simple lock.
"""
from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}

# Default TTLs (seconds)
PROFILE_TTL = 120        # customer profile: 2 min
FILTER_OPTIONS_TTL = 300  # filter dropdowns: 5 min


def get(key: str) -> Any | None:
    """Return cached value if it exists and hasn't expired, else None."""
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
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
