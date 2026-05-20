"""Minimal Agent Tool Registry."""
from ._registry import TOOL_REGISTRY, get_tool, register_tool
from ._builtin import _register_all  # noqa: F401 — registers tools at import time

__all__ = ["TOOL_REGISTRY", "get_tool", "register_tool"]
