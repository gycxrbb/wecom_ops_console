"""Shared profile context cache for CRM AI.

Redis is intentionally not required yet. This service keeps the existing
in-process cache as L1 and adds an application-DB snapshot as L2 so multiple
uvicorn workers can read the same preloaded profile context.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta

from ...config import settings
from ...database import SessionLocal
from ...sse_debug_log import get_sse_logger
from ..models import CrmAiProfileCache
from ..schemas.context import CustomerProfileContextV1
from .cache import get as l1_get, put as l1_put, invalidate as l1_invalidate, profile_cache_key, PROFILE_TTL
from .profile_loader import load_profile, load_profile_p0

_log = logging.getLogger(__name__)
_sse = get_sse_logger()

VALID_HEALTH_WINDOWS = {7, 14, 30}
PROFILE_CONTEXT_SCHEMA_VERSION = "customer_profile_context.v2"
_singleflight_guard = threading.Lock()
_singleflight_locks: dict[str, threading.Lock] = {}


@dataclass
class ProfileCacheResult:
    status: str
    cache_key: str
    health_window_days: int
    ready: bool = False
    source: str = ""
    ctx: CustomerProfileContextV1 | None = None
    generated_at: str | None = None
    expires_at: str | None = None
    stale_expires_at: str | None = None
    message: str = ""


class ProfileCacheNotReady(RuntimeError):
    """Raised when AI needs a prebuilt profile snapshot but no cache is ready."""

    def __init__(self, result: ProfileCacheResult):
        self.result = result
        super().__init__("客户档案缓存正在准备，请稍后再试")


def normalize_window_days(window_days: int | None) -> int:
    try:
        value = int(window_days or 7)
    except (TypeError, ValueError):
        value = 7
    return value if value in VALID_HEALTH_WINDOWS else 7


def _get_lock(cache_key: str) -> threading.Lock:
    with _singleflight_guard:
        lock = _singleflight_locks.get(cache_key)
        if lock is None:
            lock = threading.Lock()
            _singleflight_locks[cache_key] = lock
        return lock


def _format_dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _serialize_context(ctx: CustomerProfileContextV1) -> str:
    return ctx.model_dump_json()


def _deserialize_context(raw: str) -> CustomerProfileContextV1:
    return CustomerProfileContextV1.model_validate_json(raw)


def _has_required_context_fields(ctx: CustomerProfileContextV1) -> bool:
    service_card = next((card for card in ctx.cards if card.key == "service_issues"), None)
    if not service_card or service_card.status not in ("ok", "partial"):
        return True
    payload = service_card.payload or {}
    issues = payload.get("issues") or []
    if not issues:
        return True
    return bool(str(payload.get("issue_detail_summary") or "").strip())


def _read_l2(cache_key: str, *, allow_stale: bool = True) -> ProfileCacheResult | None:
    db = SessionLocal()
    try:
        row = db.query(CrmAiProfileCache).filter_by(cache_key=cache_key).first()
        if not row:
            return None

        now = datetime.utcnow()
        expires_at = row.expires_at or now
        stale_expires_at = row.stale_expires_at or expires_at
        if now > stale_expires_at:
            return None
        if now > expires_at and not allow_stale:
            return None

        try:
            ctx = _deserialize_context(row.context_json)
        except Exception:
            _log.exception("Invalid cached profile context: %s", cache_key)
            return None
        if not _has_required_context_fields(ctx):
            _sse.info("[PROFILE-CACHE] stale schema key=%s missing=service_issues.issue_detail_summary", cache_key)
            return None
        if getattr(ctx, 'schema_version', None) != PROFILE_CONTEXT_SCHEMA_VERSION:
            _sse.info("[PROFILE-CACHE] schema version mismatch key=%s expected=%s got=%s",
                      cache_key, PROFILE_CONTEXT_SCHEMA_VERSION, getattr(ctx, 'schema_version', None))
            return None

        row.last_hit_at = now
        db.commit()
        l1_put(cache_key, ctx, min(PROFILE_TTL, settings.crm_profile_cache_fresh_ttl_seconds))
        status = "l2_stale" if now > expires_at else "l2_fresh"
        return ProfileCacheResult(
            status=status,
            cache_key=cache_key,
            health_window_days=row.health_window_days,
            ready=True,
            source=status,
            ctx=ctx,
            generated_at=_format_dt(row.generated_at),
            expires_at=_format_dt(row.expires_at),
            stale_expires_at=_format_dt(row.stale_expires_at),
        )
    finally:
        db.close()


def _write_l2(cache_key: str, customer_id: int, window_days: int, ctx: CustomerProfileContextV1) -> None:
    now = datetime.utcnow()
    fresh_ttl = max(60, int(settings.crm_profile_cache_fresh_ttl_seconds))
    stale_ttl = max(fresh_ttl, int(settings.crm_profile_cache_stale_ttl_seconds))
    db = SessionLocal()
    try:
        row = db.query(CrmAiProfileCache).filter_by(cache_key=cache_key).first()
        if not row:
            row = CrmAiProfileCache(
                cache_key=cache_key,
                crm_customer_id=customer_id,
                health_window_days=window_days,
                context_json=_serialize_context(ctx),
            )
            db.add(row)
        row.crm_customer_id = customer_id
        row.health_window_days = window_days
        row.context_json = _serialize_context(ctx)
        row.generated_at = ctx.generated_at or now
        row.expires_at = now + timedelta(seconds=fresh_ttl)
        row.stale_expires_at = now + timedelta(seconds=stale_ttl)
        row.last_hit_at = now
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_cached_profile_context(
    customer_id: int,
    *,
    window_days: int,
    allow_stale: bool = True,
) -> ProfileCacheResult:
    w = normalize_window_days(window_days)
    cache_key = profile_cache_key(customer_id, w)
    ctx = l1_get(cache_key)
    if ctx:
        if not _has_required_context_fields(ctx):
            l1_invalidate(cache_key)
        else:
            _sse.info("[PROFILE-CACHE] hit source=l1 key=%s", cache_key)
            return ProfileCacheResult(
                status="l1_fresh",
                cache_key=cache_key,
                health_window_days=w,
                ready=True,
                source="l1_fresh",
                ctx=ctx,
            )

    l2 = _read_l2(cache_key, allow_stale=allow_stale)
    if l2 and l2.ctx:
        _sse.info("[PROFILE-CACHE] hit source=%s key=%s", l2.source, cache_key)
        return l2

    _sse.info("[PROFILE-CACHE] miss key=%s", cache_key)
    return ProfileCacheResult(
        status="missing",
        cache_key=cache_key,
        health_window_days=w,
        ready=False,
        source="missing",
    )


def ensure_profile_context(
    customer_id: int,
    *,
    window_days: int,
    force_refresh: bool = False,
    allow_stale: bool = True,
) -> ProfileCacheResult:
    w = normalize_window_days(window_days)
    cache_key = profile_cache_key(customer_id, w)

    if not force_refresh:
        cached = get_cached_profile_context(customer_id, window_days=w, allow_stale=allow_stale)
        if cached.ready and cached.ctx:
            return cached

    lock = _get_lock(cache_key)
    with lock:
        if not force_refresh:
            cached = get_cached_profile_context(customer_id, window_days=w, allow_stale=allow_stale)
            if cached.ready and cached.ctx:
                return cached

        _sse.info("[PROFILE-CACHE] build start key=%s", cache_key)
        ctx = load_profile(customer_id, health_window_days=w)
        l1_put(cache_key, ctx, min(PROFILE_TTL, settings.crm_profile_cache_fresh_ttl_seconds))
        _write_l2(cache_key, customer_id, w, ctx)
        _sse.info("[PROFILE-CACHE] build done key=%s cards=%d", cache_key, len(ctx.cards))
        return ProfileCacheResult(
            status="rebuilt",
            cache_key=cache_key,
            health_window_days=w,
            ready=True,
            source="crm_db_rebuild",
            ctx=ctx,
            generated_at=_format_dt(ctx.generated_at),
        )


def get_ai_ready_profile_context(
    customer_id: int,
    *,
    window_days: int,
) -> ProfileCacheResult:
    """Read AI profile context from L1/L2 only; schedule build on true miss."""
    w = normalize_window_days(window_days)
    cached = get_cached_profile_context(customer_id, window_days=w, allow_stale=True)
    if cached.ready and cached.ctx:
        return cached

    preload = schedule_profile_preload(customer_id, window_days=w)
    if preload.ready and preload.ctx:
        return preload
    raise ProfileCacheNotReady(preload)


def get_profile_cache_status(
    customer_id: int,
    *,
    window_days: int,
) -> ProfileCacheResult:
    """Return cache state without building or scheduling a preload."""
    w = normalize_window_days(window_days)
    cache_key = profile_cache_key(customer_id, w)
    cached = get_cached_profile_context(customer_id, window_days=w, allow_stale=True)
    if cached.ready:
        return cached

    lock = _get_lock(cache_key)
    if lock.locked():
        return ProfileCacheResult(
            status="building",
            cache_key=cache_key,
            health_window_days=w,
            ready=False,
            source="singleflight",
            message="profile preload already running",
        )
    return cached


def cleanup_expired_profile_cache() -> int:
    """Delete L2 snapshots that are beyond stale TTL."""
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        deleted = (
            db.query(CrmAiProfileCache)
            .filter(CrmAiProfileCache.stale_expires_at.isnot(None))
            .filter(CrmAiProfileCache.stale_expires_at < now)
            .delete(synchronize_session=False)
        )
        db.commit()
        if deleted:
            _sse.info("[PROFILE-CACHE] cleanup deleted=%s", deleted)
        return int(deleted or 0)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def refresh_expiring_cache_entries() -> int:
    """Rebuild L2 entries that have been hit recently but are past fresh TTL."""
    now = datetime.utcnow()
    fresh_ttl = max(60, int(settings.crm_profile_cache_fresh_ttl_seconds))
    hit_cutoff = now - timedelta(hours=2)
    db = SessionLocal()
    try:
        rows = (
            db.query(CrmAiProfileCache)
            .filter(CrmAiProfileCache.expires_at < now)
            .filter(CrmAiProfileCache.stale_expires_at > now)
            .filter(CrmAiProfileCache.last_hit_at.isnot(None))
            .filter(CrmAiProfileCache.last_hit_at > hit_cutoff)
            .all()
        )
    finally:
        db.close()

    refreshed = 0
    for row in rows:
        try:
            ctx = load_profile(row.crm_customer_id, health_window_days=row.health_window_days)
            l1_put(row.cache_key, ctx, min(PROFILE_TTL, settings.crm_profile_cache_fresh_ttl_seconds))
            _write_l2(row.cache_key, row.crm_customer_id, row.health_window_days, ctx)
            refreshed += 1
        except Exception:
            _log.warning("Background refresh failed for key=%s", row.cache_key)
    if refreshed:
        _sse.info("[PROFILE-CACHE] auto-refresh count=%s", refreshed)
    return refreshed


def schedule_profile_preload(customer_id: int, *, window_days: int) -> ProfileCacheResult:
    w = normalize_window_days(window_days)
    cache_key = profile_cache_key(customer_id, w)
    cached = get_cached_profile_context(customer_id, window_days=w, allow_stale=True)
    if cached.ready:
        return cached

    lock = _get_lock(cache_key)
    if not lock.acquire(blocking=False):
        return ProfileCacheResult(
            status="already_running",
            cache_key=cache_key,
            health_window_days=w,
            ready=False,
            source="singleflight",
            message="profile preload already running",
        )

    def _work():
        try:
            _sse.info("[PROFILE-CACHE] preload thread start key=%s (P0 fast)", cache_key)
            ctx = load_profile_p0(customer_id, health_window_days=w)
            l1_put(cache_key, ctx, min(PROFILE_TTL, settings.crm_profile_cache_fresh_ttl_seconds))
            _write_l2(cache_key, customer_id, w, ctx)
            _sse.info("[PROFILE-CACHE] preload P0 done key=%s cards=%d, starting P1 full load", cache_key, len(ctx.cards))
            # Full load to replace P1 stubs with real data
            try:
                ctx_full = load_profile(customer_id, health_window_days=w)
                l1_put(cache_key, ctx_full, min(PROFILE_TTL, settings.crm_profile_cache_fresh_ttl_seconds))
                _write_l2(cache_key, customer_id, w, ctx_full)
                _sse.info("[PROFILE-CACHE] preload P1 done key=%s cards=%d", cache_key, len(ctx_full.cards))
            except Exception as exc2:
                _log.warning("Profile preload P1 failed key=%s: %s (P0 still cached)", cache_key, exc2)
        except Exception as exc:
            _log.warning("Profile preload failed key=%s: %s", cache_key, exc)
            _sse.info("[PROFILE-CACHE] preload thread failed key=%s err=%s", cache_key, exc)
        finally:
            lock.release()

    threading.Thread(target=_work, daemon=True).start()
    return ProfileCacheResult(
        status="scheduled",
        cache_key=cache_key,
        health_window_days=w,
        ready=False,
        source="background",
    )
