"""Tool definition and registry."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    category: str = "utility"  # "rag" | "profile" | "visual" | "llm" | "utility"


TOOL_REGISTRY: dict[str, ToolDef] = {}


def register_tool(tool: ToolDef) -> None:
    TOOL_REGISTRY[tool.name] = tool


def get_tool(name: str) -> ToolDef | None:
    return TOOL_REGISTRY.get(name)
