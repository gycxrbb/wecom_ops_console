"""Data structures for visual decision and safety evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VisualSafetyRule:
    rule_id: str
    category: str  # "content_restriction" | "medical_imagery" | "pii_block" | "brand_guard"
    description: str
    severity: str  # "block" | "warn" | "log"
    keywords: tuple[str, ...] = ()
    applies_to: str = "both"  # "prompt" | "generated_image" | "both"


@dataclass
class VisualSafetyDecision:
    passed: bool
    blocked: bool = False
    warnings: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)


@dataclass
class VisualDecision:
    need_visual: bool
    confidence: float
    decision_mode: str  # "auto_async_generate" | "manual_confirm" | "no_visual"
    visual_type: str = "health_education_card"
    topic: str = ""
    audience: str = "customer"
    reason: str = ""
    safety_level: str = "nutrition_education"
    confirm_question: str | None = None
    score_factors: dict[str, float] | None = None
