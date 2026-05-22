"""Build structured visual brief from a VisualDecision and RAG context.

The brief is a JSON dict stored in the job row, consumed by prompt_builder.
Deterministic — no LLM calls, just text extraction from RAG sources.
"""
from __future__ import annotations

import re

from ..schemas.visual import VisualDecision


def build_visual_brief(
    *,
    decision: VisualDecision,
    rag_sources: list[dict] | None = None,
    scene_key: str = "qa_support",
) -> dict:
    """Convert decision + RAG context into a structured visual brief dict."""
    key_points = _extract_key_points(rag_sources)
    source_titles = _extract_source_titles(rag_sources)

    return {
        "title": decision.topic,
        "visual_type": decision.visual_type,
        "audience": "customer",
        "safety_level": decision.safety_level,
        "key_points": key_points[:6],
        "source_titles": source_titles[:4],
        "scene_key": scene_key,
        "style_hint": _style_for_type(decision.visual_type),
        "tone": "warm_professional",
        "avoid_claims": [
            "保证降糖", "替代医生建议", "根治", "包治",
            "一定瘦", "用药指导",
        ],
    }


def _extract_key_points(rag_sources: list[dict] | None) -> list[str]:
    """Extract short key-point strings from RAG source content."""
    if not rag_sources:
        return []
    points: list[str] = []
    for src in rag_sources[:5]:
        content = src.get("content", "") or src.get("text", "")
        # Do NOT fallback to title — RAG document titles are internal labels, not knowledge content
        if not content:
            continue
        # Split on numbered items or bullet markers
        segments = re.split(r"(?:\n|。|；)", content)
        for seg in segments:
            seg = seg.strip().lstrip("0123456789.-) ")
            if 8 <= len(seg) <= 80:
                points.append(seg)
            if len(points) >= 8:
                break
        if len(points) >= 8:
            break
    return points


def _extract_source_titles(rag_sources: list[dict] | None) -> list[str]:
    if not rag_sources:
        return []
    return [s.get("title", "") for s in rag_sources if s.get("title")]


def _style_for_type(visual_type: str) -> str:
    """Map visual type to a style hint for the image prompt."""
    styles = {
        "health_education_card": "clean infographic card, warm pastel colors, clear text hierarchy",
        "nutrition_choice_card": "food choice checklist style, organized sections, warm tones",
        "behavior_step_card": "step-by-step flowchart style, numbered steps, clear arrows",
        "risk_signal_card": "alert-style card, icon-based, clear warnings, not alarming",
        "review_card": "positive reinforcement card, achievement style, warm gradient",
        "checklist_card": "clean checklist layout, checkbox style, organized rows",
    }
    return styles.get(visual_type, "clean educational infographic, warm professional style")
