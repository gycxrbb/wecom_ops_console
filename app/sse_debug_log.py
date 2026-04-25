"""File-only logger for SSE streaming diagnostics. Writes to logs/sse_debug.log."""
from __future__ import annotations

import logging
import os

_logger: logging.Logger | None = None


def get_sse_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("sse_debug")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # don't duplicate to root/uvicorn

    fh = logging.FileHandler(
        os.path.join(log_dir, "sse_debug.log"),
        encoding="utf-8",
        delay=False,
    )
    fh.setFormatter(logging.Formatter(
        "%(asctime)s.%(msecs)03d  %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(fh)
    _logger = logger
    return logger
