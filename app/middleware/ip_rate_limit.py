"""全局 IP 限流中间件：防止接口被无限调用 / DDoS

采用纯 ASGI 中间件实现，避免 BaseHTTPMiddleware 的兼容性问题。
"""
from __future__ import annotations

import json
import time
import logging
from collections import defaultdict
from threading import Lock

logger = logging.getLogger(__name__)

# ── 配置 ──
# 通用接口：每个 IP 每分钟最多 120 次请求
GLOBAL_RATE_LIMIT = 120
GLOBAL_WINDOW_SECONDS = 60

# 敏感接口（登录/注册等）：每个 IP 每分钟最多 20 次请求
SENSITIVE_RATE_LIMIT = 20
SENSITIVE_WINDOW_SECONDS = 60

# 敏感路径
SENSITIVE_PATHS = {'/login', '/api/v1/auth/login', '/api/v1/auth/refresh'}

# 白名单路径（不做限流，如健康检查）
WHITELIST_PATHS = {'/health'}

# 跳过前缀
SKIP_PREFIXES = ('/static/', '/uploads/', '/assets/')

_global_buckets: dict[str, list[float]] = defaultdict(list)
_sensitive_buckets: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def _get_client_ip_from_scope(scope: dict) -> str:
    """从 ASGI scope 的 headers 和 client 中提取客户端 IP。"""
    headers = dict(scope.get('headers', []))
    forwarded = headers.get(b'x-forwarded-for', b'').decode('latin-1', errors='ignore')
    if forwarded:
        return forwarded.split(',')[0].strip()
    client = scope.get('client')
    return client[0] if client else ''


def _check_bucket(buckets: dict[str, list[float]], key: str, limit: int, window: int) -> tuple[bool, int]:
    """检查滑动窗口是否允许请求。返回 (allowed, retry_after_seconds)。"""
    now = time.time()
    cutoff = now - window
    buckets[key] = [t for t in buckets[key] if t > cutoff]
    timestamps = buckets[key]

    if len(timestamps) >= limit:
        retry_after = int(timestamps[0] + window - now) + 1
        return False, max(retry_after, 1)

    timestamps.append(now)
    return True, 0


def cleanup_buckets() -> None:
    """定期清理过期记录，防止内存泄漏。由外部定时调用。"""
    now = time.time()
    with _lock:
        for buckets, window in [(_global_buckets, GLOBAL_WINDOW_SECONDS), (_sensitive_buckets, SENSITIVE_WINDOW_SECONDS)]:
            expired = [k for k, ts in buckets.items() if not ts or now - ts[-1] > window * 2]
            for k in expired:
                del buckets[k]


async def _send_429(send, retry_after: int, message: str) -> None:
    """直接通过 ASGI send 返回 429 响应。"""
    body = json.dumps({'code': 42900, 'message': message, 'data': {'retry_after': retry_after}}).encode('utf-8')
    await send({
        'type': 'http.response.start',
        'status': 429,
        'headers': [
            [b'content-type', b'application/json'],
            [b'content-length', str(len(body)).encode()],
            [b'retry-after', str(retry_after).encode()],
        ],
    })
    await send({'type': 'http.response.body', 'body': body})


class IPRateLimitMiddleware:
    """纯 ASGI 中间件：基于 IP 的全局请求频率限制。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        path: str = scope.get('path', '')

        # 白名单 / 静态资源跳过
        if path in WHITELIST_PATHS or path.startswith(SKIP_PREFIXES):
            await self.app(scope, receive, send)
            return

        client_ip = _get_client_ip_from_scope(scope)
        if not client_ip:
            await self.app(scope, receive, send)
            return

        with _lock:
            # 全局限流
            allowed, retry_after = _check_bucket(_global_buckets, client_ip, GLOBAL_RATE_LIMIT, GLOBAL_WINDOW_SECONDS)
            if not allowed:
                logger.warning('IP %s 触发全局限流 (%d/%dmin)，拒绝请求 %s', client_ip, GLOBAL_RATE_LIMIT, GLOBAL_WINDOW_SECONDS // 60, path)
                await _send_429(send, retry_after, f'请求过于频繁，请 {retry_after} 秒后重试')
                return

            # 敏感接口额外限流
            if path in SENSITIVE_PATHS:
                allowed, retry_after = _check_bucket(_sensitive_buckets, client_ip, SENSITIVE_RATE_LIMIT, SENSITIVE_WINDOW_SECONDS)
                if not allowed:
                    logger.warning('IP %s 触发敏感接口限流 (%d/%dmin)，拒绝请求 %s', client_ip, SENSITIVE_RATE_LIMIT, SENSITIVE_WINDOW_SECONDS // 60, path)
                    await _send_429(send, retry_after, f'请求过于频繁，请 {retry_after} 秒后重试')
                    return

        await self.app(scope, receive, send)
