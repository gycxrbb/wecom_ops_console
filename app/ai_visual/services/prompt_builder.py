"""Convert visual brief to gpt-image-2 prompt string.

Template-based construction with safety gate.
"""
from __future__ import annotations

from pathlib import Path

from .visual_safety import evaluate_visual_safety

_TEMPLATE = (Path(__file__).resolve().parent.parent / "prompts" / "image_prompt_template.md").read_text(encoding="utf-8")


def build_image_prompt(brief: dict) -> str | None:
    """Build a gpt-image-2 prompt from visual brief.

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
