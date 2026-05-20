"""Visual safety evaluation — rule-based check for visual generation requests."""
from __future__ import annotations

from ..schemas.visual import VisualSafetyDecision
from ._safety_rules import SAFETY_RULES


def evaluate_visual_safety(topic: str, prompt: str = "") -> VisualSafetyDecision:
    """Evaluate whether a visual generation request passes safety rules."""
    text = f"{topic} {prompt}".lower()
    blocked = False
    warnings: list[str] = []
    matched: list[str] = []

    for rule in SAFETY_RULES:
        hit = any(kw in text for kw in rule.keywords)
        if not hit:
            continue
        matched.append(rule.rule_id)
        if rule.severity == "block":
            blocked = True
        elif rule.severity == "warn":
            warnings.append(rule.description)

    return VisualSafetyDecision(
        passed=not blocked,
        blocked=blocked,
        warnings=warnings,
        matched_rules=matched,
    )
