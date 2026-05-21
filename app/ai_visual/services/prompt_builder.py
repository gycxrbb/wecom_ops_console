"""Convert visual brief to gpt-image-2 prompt string.

Template-based construction with safety gate.
LLM-enhanced generation as primary path with template fallback.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from .visual_safety import evaluate_visual_safety

_log = logging.getLogger(__name__)

_TEMPLATE = (Path(__file__).resolve().parent.parent / "prompts" / "image_prompt_template.md").read_text(encoding="utf-8")
_PROMPT_GEN_SYSTEM = (Path(__file__).resolve().parent.parent / "prompts" / "prompt_generator.md").read_text(encoding="utf-8")


def build_image_prompt(brief: dict) -> str | None:
    """Build a gpt-image-2 prompt from visual brief (template-based).

    Returns None if the generated prompt fails safety checks.
    """
    title = brief.get("title", "健康知识卡片")
    key_points = brief.get("key_points", [])
    style_hint = brief.get("style_hint", "clean educational infographic")
    tone = brief.get("tone", "warm_professional")
    avoid = brief.get("avoid_claims", [])
    visual_type = brief.get("visual_type", "health_education_card")

    # Build bullet-point section
    points_text = ""
    if key_points:
        items = "\n".join(f"- {p}" for p in key_points[:5])
        points_text = f"\nKey points to include as text:\n{items}"

    # Build avoid section
    avoid_text = ""
    if avoid:
        avoid_text = f"\nDo NOT include any of these claims: {', '.join(avoid)}"

    prompt = _TEMPLATE
    prompt = prompt.replace("{{title}}", title)
    prompt = prompt.replace("{{style_hint}}", style_hint)
    prompt = prompt.replace("{{tone}}", tone)
    prompt = prompt.replace("{{visual_type}}", visual_type)
    prompt = prompt.replace("{{key_points}}", points_text)
    prompt = prompt.replace("{{avoid_claims}}", avoid_text)

    # Trim whitespace
    prompt = "\n".join(line for line in prompt.split("\n") if line.strip())

    # Safety gate on title + actual content (not the avoid section)
    safety = evaluate_visual_safety(title, prompt.replace(avoid_text, ""))
    if safety.blocked:
        return None

    return prompt


async def build_image_prompt_llm(
    *,
    brief: dict,
    rag_sources: list[dict] | None,
    user_question: str,
) -> str | None:
    """Generate image prompt via LLM using user question + top RAG source.

    Returns None on failure (caller should fallback to template prompt).
    """
    from app.config import settings

    # Pick highest-score RAG source as core reference
    best_source = ""
    if rag_sources:
        sorted_sources = sorted(rag_sources, key=lambda s: s.get("score", 0), reverse=True)
        best_source = sorted_sources[0].get("content") or sorted_sources[0].get("text") or ""

    title = brief.get("title", "健康知识卡片")
    visual_type = brief.get("visual_type", "health_education_card")
    key_points = brief.get("key_points", [])

    user_msg_parts = [
        f"User Question: {user_question}",
        f"Visual Type: {visual_type}",
        f"Title: {title}",
    ]
    if best_source:
        user_msg_parts.append(f"Reference Content:\n{best_source[:1500]}")
    if key_points:
        user_msg_parts.append("Suggested Key Points:\n" + "\n".join(f"- {p}" for p in key_points[:5]))

    messages = [
        {"role": "system", "content": _PROMPT_GEN_SYSTEM},
        {"role": "user", "content": "\n\n".join(user_msg_parts)},
    ]

    try:
        from app.clients.ai_chat_client import chat_completion
        result = await asyncio.wait_for(
            chat_completion(
                messages,
                model=settings.ai_visual_prompt_model,
                temperature=0.7,
                max_tokens=800,
            ),
            timeout=settings.ai_visual_prompt_timeout_seconds,
        )
        prompt_text = result[0].strip() if result else ""
    except Exception as e:
        _log.warning("[Visual] LLM prompt generation failed: %s", e)
        return None

    if not prompt_text or len(prompt_text) < 20:
        _log.warning("[Visual] LLM prompt too short (%d chars), discarding", len(prompt_text))
        return None

    safety = evaluate_visual_safety(title, prompt_text)
    if safety.blocked:
        _log.warning("[Visual] LLM prompt blocked by safety: %s", safety.matched_rules)
        return None

    _log.info("[Visual] LLM prompt generated (%d chars)", len(prompt_text))
    return prompt_text
