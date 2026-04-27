"""File-only logger for SSE streaming diagnostics. Writes to logs/sse_debug.log."""
from __future__ import annotations

import logging
import os
import threading

_logger: logging.Logger | None = None
_log_path: str = ""


def get_sse_logger() -> logging.Logger:
    global _logger, _log_path
    if _logger is not None:
        return _logger

    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    _log_path = os.path.join(log_dir, "sse_debug.log")

    logger = logging.getLogger("sse_debug")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # don't duplicate to root/uvicorn

    fh = logging.FileHandler(
        _log_path,
        encoding="utf-8",
        delay=False,
    )
    fh.setFormatter(logging.Formatter(
        "%(asctime)s.%(msecs)03d  %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(fh)
    _logger = logger
    return logger


def clear_sse_log() -> None:
    """Truncate the SSE debug log in a background thread (non-blocking)."""
    path = _log_path
    if not path:
        return

    def _truncate():
        try:
            with open(path, "w", encoding="utf-8"):
                pass
        except OSError:
            pass

    threading.Thread(target=_truncate, daemon=True).start()
