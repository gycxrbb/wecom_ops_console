"""登录暴力破解防护：基于 IP + 用户名的滑动窗口限流"""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

# ── 配置 ──
MAX_ATTEMPTS = 5          # 窗口内最大失败次数
WINDOW_SECONDS = 900      # 滑动窗口 15 分钟
LOCKOUT_SECONDS = 900     # 锁定时长 15 分钟

_attempts: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def _key(ip: str, username: str) -> str:
    return f'{ip}:{username}'


def check(ip: str, username: str) -> tuple[bool, int]:
    """检查是否允许登录。

    Returns:
        (allowed, retry_after_seconds)
    """
    now = time.time()
    k = _key(ip, username)
    with _lock:
        # 清理过期记录
        _attempts[k] = [t for t in _attempts[k] if now - t < WINDOW_SECONDS]
        if len(_attempts[k]) >= MAX_ATTEMPTS:
            retry_after = int(_attempts[k][0] + LOCKOUT_SECONDS - now)
            return False, max(retry_after, 1)
        return True, 0


def record_failure(ip: str, username: str) -> int:
    """记录一次失败，返回当前窗口内的累计失败次数。"""
    now = time.time()
    k = _key(ip, username)
    with _lock:
        _attempts[k] = [t for t in _attempts[k] if now - t < WINDOW_SECONDS]
        _attempts[k].append(now)
        return len(_attempts[k])


def reset(ip: str, username: str) -> None:
    k = _key(ip, username)
    with _lock:
        _attempts.pop(k, None)


def cleanup() -> None:
    """清理所有过期记录，防止内存泄漏。"""
    now = time.time()
    with _lock:
        expired_keys = [k for k, ts in _attempts.items() if not ts or now - ts[-1] > WINDOW_SECONDS]
        for k in expired_keys:
            del _attempts[k]
