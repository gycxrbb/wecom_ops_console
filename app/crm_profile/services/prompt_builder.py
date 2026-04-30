# -*- coding: utf-8 -*-
"""5-layer prompt builder for CRM AI Coach.

Layers:
  1. Platform guardrails (safety, medical boundary)
  2. Health coach core (role, methodology, style)
  3. Scene strategy (meal_review, data_monitoring, etc.)
  4. Customer context (auto-aggregated from CRM)
  5. Customer profile note (coach-maintained supplementary info)

Runtime input (layer 6) is the user message, handled by the caller.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..models import CustomerAiProfileNote
from ..prompts.registry import (
    get_all_base_prompts,
    get_context_header,
    get_rag_header,
    get_scene_hint_header,
    get_scene_prompt,
    get_scene_label,
    get_style_prompt,
    get_version,
    get_system_prompt_hash,
    get_visible_thinking_prompt_hash,
)

_log = logging.getLogger(__name__)

_NOTE_FIELD_LABELS = {
    "communication_style_note": "沟通风格补充",
    "current_focus_note": "当前阶段重点",
    "execution_barrier_note": "执行障碍",
    "lifestyle_background_note": "作息/家庭/工作背景",
    "coach_strategy_note": "教练内部策略备注",
}


@dataclass
class PromptAssembly:
    """Result of prompt assembly - messages list + audit metadata."""
    messages: list[dict] = field(default_factory=list)
    prompt_version: str = ""
    prompt_hash: str = ""
    scene_key: str = ""
    used_layers: list[str] = field(default_factory=list)


def build_profile_note_text(note: CustomerAiProfileNote | None) -> str:
    """Serialize the coach-maintained profile note into prompt text."""
    if not note:
        return ""
    sections: list[str] = []
    for attr, label in _NOTE_FIELD_LABELS.items():
        val = getattr(note, attr, None)
        if val and val.strip():
            sections.append(f"{label}:​{val.strip()}")
    if not sections:
        return ""
    return "### 教练补充的客户专属信息\n" + "\n".join(sections)


def _render_template(template: str, **kwargs: str) -> str:
    """Simple {{ var }} replacement for prompt templates."""
    result = template
    for key, value in kwargs.items():
        result = result.replace("{{ " + key + " }}", value)
    return result


def assemble_prompt(
    *,
    scene_key: str,
    context_text: str,
    customer_name: str,
    profile_note: CustomerAiProfileNote | None = None,
    user_message: str,
    output_style: str = "coach_brief",
    rag_context_text: str = "",
) -> PromptAssembly:
    """Assemble the full 5-layer prompt into a messages list."""
    style_prompt = get_style_prompt(output_style)
    style_hint = (
        "输出模式：" + style_prompt
        if style_prompt
        else "输出模式：简洁教练简报，结论优先。"
    )

    # Layer 1 + 2: base system prompt (all active base-layer templates)
    system_text = get_all_base_prompts()
    used_layers = ["base:all"]

    # Layer 3: scene
    scene_text = get_scene_prompt(scene_key)
    if scene_text:
        system_text += "\n\n" + scene_text
        used_layers.append(f"scene:{scene_key}")

    # Layer 4: customer context (externalized header)
    header_template = get_context_header()
    context_header = _render_template(
        header_template, customer_name=customer_name or "未知客户"
    )
    context_header += "\n\n" + context_text
    used_layers.append("customer_context")

    messages = [
        {"role": "system", "content": system_text},
        {"role": "system", "content": context_header},
    ]

    # Layer 4.5~5.5: dynamic context (RAG, profile note, scene hint)
    # Separated into independent messages for better prompt-cache hit rates.
    dynamic_parts: list[str] = []

    if rag_context_text:
        rag_hdr = get_rag_header()
        dynamic_parts.append(rag_hdr + "\n\n" + rag_context_text)
        used_layers.append("rag_context")

    note_text = build_profile_note_text(profile_note)
    if note_text:
        dynamic_parts.append(note_text)
        used_layers.append("profile_note")

    if profile_note and getattr(profile_note, "preferred_scene_hint", None):
        scene_hint_tpl = get_scene_hint_header()
        if scene_hint_tpl:
            scene_label = get_scene_label(profile_note.preferred_scene_hint)
            scene_hint_text = _render_template(
                scene_hint_tpl, scene_label=scene_label
            )
            dynamic_parts.append(scene_hint_text)
            used_layers.append("scene_hint")

    if dynamic_parts:
        messages.append({"role": "system", "content": "\n\n".join(dynamic_parts)})

    messages.append({"role": "user", "content": f"{user_message}\n\n{style_hint}"})

    return PromptAssembly(
        messages=messages,
        prompt_version=get_version(),
        prompt_hash=get_system_prompt_hash(scene_key),
        scene_key=scene_key,
        used_layers=used_layers,
    )


def assemble_visible_thinking_prompt(
    *,
    scene_key: str,
    context_text: str,
    customer_name: str,
    profile_note: CustomerAiProfileNote | None = None,
    user_message: str,
    rag_context_text: str = "",
) -> PromptAssembly:
    """Assemble a separate, UI-safe reasoning-summary prompt for the thinking box."""
    system_text = get_all_base_prompts()
    used_layers = ["base:all"]

    scene_text = get_scene_prompt(scene_key)
    if scene_text:
        scene_prefix = (
            f"\n\n当前工作场景：{scene_key}。\n"
            "下面是该场景的正式策略参考，请据此组织「思考摘要」，"
            "而不是直接输出最终建议。\n"
        )
        system_text += scene_prefix + scene_text
        used_layers.append(f"scene:{scene_key}")

    header_template = get_context_header()
    context_header = _render_template(
        header_template, customer_name=customer_name or "未知客户"
    )
    thinking_hint = "\n你正在为健康教练生成「可展示的思考摘要」，而不是最终回复。\n\n"
    context_header = context_header + thinking_hint + context_text
    used_layers.append("customer_context")

    messages = [
        {"role": "system", "content": system_text},
        {"role": "system", "content": context_header},
    ]

    # Dynamic context — separated for prompt-cache friendliness.
    dynamic_parts: list[str] = []

    if rag_context_text:
        rag_hdr = get_rag_header()
        dynamic_parts.append(rag_hdr + "\n\n" + rag_context_text)
        used_layers.append("rag_context")

    note_text = build_profile_note_text(profile_note)
    if note_text:
        dynamic_parts.append(note_text)
        used_layers.append("profile_note")

    if profile_note and getattr(profile_note, "preferred_scene_hint", None):
        scene_hint_tpl = get_scene_hint_header()
        if scene_hint_tpl:
            scene_label = get_scene_label(profile_note.preferred_scene_hint)
            scene_hint_text = _render_template(
                scene_hint_tpl, scene_label=scene_label
            )
            dynamic_parts.append(scene_hint_text)
            used_layers.append("scene_hint")

    if dynamic_parts:
        messages.append({"role": "system", "content": "\n\n".join(dynamic_parts)})

    messages.append({
        "role": "user",
        "content": (
            f"{user_message}\n\n"
            "请输出给界面展示的简短思考摘要。"
            "重点写：你正在看什么信息、有哪些风险边界、准备如何组织正式回复。"
        ),
    })

    return PromptAssembly(
        messages=messages,
        prompt_version=get_version(),
        prompt_hash=get_visible_thinking_prompt_hash(scene_key),
        scene_key=scene_key,
        used_layers=used_layers,
    )
