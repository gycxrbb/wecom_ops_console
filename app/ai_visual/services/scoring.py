"""Confidence scoring and threshold routing for visual decision.

Combines LLM semantic signals with RAG evidence, scene fit, safety, and
reusable asset factors into a single confidence score with forced downgrade rules.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass
class ScoreFactors:
    """Individual factor contributions to final confidence."""
    visual_value: float = 0.0
    topic_clarity: float = 0.0
    actionability: float = 0.0
    evidence_strength: float = 0.0
    scene_fit: float = 0.0
    novelty: float = 0.1  # default: no duplicate asset penalty
    safety_penalty: float = 0.0
    reusable_asset_penalty: float = 0.0


# Weights matching the document formula
_W_VISUAL = 0.30
_W_TOPIC = 0.20
_W_ACTION = 0.15
_W_EVIDENCE = 0.20
_W_SCENE = 0.10
_W_NOVELTY = 0.05

_SCENE_FIT_MAP: dict[str, float] = {
    "qa_support": 0.5,
    "health_analysis": 0.7,
    "daily_checkin": 0.6,
    "plan_review": 0.6,
}


def calculate_confidence(factors: ScoreFactors) -> float:
    """Calculate weighted confidence from individual factors."""
    raw = (
        _W_VISUAL * factors.visual_value
        + _W_TOPIC * factors.topic_clarity
        + _W_ACTION * factors.actionability
        + _W_EVIDENCE * factors.evidence_strength
        + _W_SCENE * factors.scene_fit
        + _W_NOVELTY * factors.novelty
        - factors.safety_penalty
        - factors.reusable_asset_penalty
    )
    return round(max(0.0, min(1.0, raw)), 4)


def compute_evidence_strength(rag_sources: list[dict] | None) -> float:
    """Derive evidence strength from RAG hit quality."""
    if not rag_sources:
        return 0.0
    top_score = max((s.get("score", 0) for s in rag_sources), default=0)
    count_bonus = min(len(rag_sources) * 0.03, 0.15)
    return min(top_score + count_bonus, 1.0)


def compute_scene_fit(scene_key: str) -> float:
    """Map scene_key to a fit score."""
    return _SCENE_FIT_MAP.get(scene_key, 0.4)


def compute_novelty(recommended_assets: list[dict] | None) -> float:
    """Higher score when no existing assets cover the same topic."""
    if not recommended_assets:
        return 0.1
    best = max((a.get("quality_score", 0) for a in recommended_assets), default=0)
    if best >= 0.8:
        return 0.0  # high-quality duplicate exists
    return 0.1


def route_by_threshold(
    confidence: float,
    *,
    is_sensitive: bool = False,
    evidence_low: bool = False,
    has_reusable_asset: bool = False,
) -> tuple[str, float]:
    """Route confidence to decision_mode, applying forced downgrades.

    Returns (decision_mode, adjusted_confidence).
    """
    auto_threshold = settings.ai_visual_auto_generate_confidence
    manual_threshold = settings.ai_visual_manual_confirm_confidence

    adjusted = confidence

    # Forced downgrade: sensitive → manual at most
    if is_sensitive and adjusted >= auto_threshold:
        adjusted = min(adjusted, auto_threshold - 0.01)

    # Forced downgrade: low evidence → manual at most
    if evidence_low and adjusted >= auto_threshold:
        adjusted = min(adjusted, auto_threshold - 0.01)

    # Reusable asset: skip new generation
    if has_reusable_asset:
        return ("prefer_reuse", adjusted)

    if adjusted >= auto_threshold:
        return ("auto_async_generate", adjusted)
    if adjusted >= manual_threshold:
        return ("manual_confirm", adjusted)
    return ("no_visual", adjusted)
