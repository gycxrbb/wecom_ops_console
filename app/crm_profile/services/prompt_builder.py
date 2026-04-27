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
    get_platform_guardrails,
    get_health_coach_core,
    get_visible_thinking_core,
    get_scene_prompt,
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
    """Result of prompt assembly — messages list + audit metadata."""
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
            sections.append(f"{label}：{val.strip()}")
    if not sections:
        return ""
    return "### 教练补充的客户专属信息\n" + "\n".join(sections)


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
    style_hints = {
        "coach_brief": "输出格式：简洁教练简报，结论优先。",
        "customer_reply": "输出格式：直接发给客户的话术草稿，语气亲切自然。",
        "handoff_note": "输出格式：交接备注，结构化分点。",
        "bullet_list": "输出格式：要点列表。",
        "detailed_report": "输出格式：详细分析报告，结构化分节，充分展开所有分析和建议。",
    }
    style_hint = style_hints.get(output_style, style_hints["coach_brief"])

    # Layer 1 + 2: system prompt
    system_text = get_platform_guardrails() + "\n\n" + get_health_coach_core()
    used_layers = ["platform_guardrails", "health_coach_core"]

    # Layer 3: scene
    scene_text = get_scene_prompt(scene_key)
    if scene_text:
        system_text += "\n\n" + scene_text
        used_layers.append(f"scene:{scene_key}")

    # Layer 4: customer context
    context_header = (
        "当前客户的真实姓名是：" + (customer_name or "未知客户") + "。\n"
        "若用户使用'你'来提问，除非明确说明是在问 AI，"
        "自然语言里的'你'默认指当前客户「" + (customer_name or "未知客户") + "」。\n"
        "如果上下文中已经给出了真实姓名、年龄、性别、客户状态、负责教练或所属群，回答时必须直接使用这些真实信息，"
        "不要输出“客户姓名”“姓名字段”“[客户姓名]”之类的字段名、占位词或抽象标签。\n"
        "以下是系统生成的客户上下文，schema_version=customer_profile_context.v1。\n"
        "该上下文已排除手机号、openid、unionid、登录 IP 等敏感身份字段。\n\n"
        + context_text
    )
    used_layers.append("customer_context")

    # Layer 4.5: RAG knowledge context (optional)
    if rag_context_text:
        context_header += (
            "\n\n【公司话术与知识库参考】\n"
            "- 以下内容来自内部话术库/知识库，是辅助参考，不等于客户档案事实。\n"
            "- 回答时优先结合客户档案和安全档案。\n"
            "- 可借鉴话术风格，但不要机械照抄。\n"
            "- 医疗敏感内容只做风险提醒，不做诊断。\n\n"
            + rag_context_text
        )
        used_layers.append("rag_context")

    # Layer 5: coach profile note
    note_text = build_profile_note_text(profile_note)
    if note_text:
        context_header += "\n\n" + note_text
        used_layers.append("profile_note")

    messages = [
        {"role": "system", "content": system_text},
        {"role": "system", "content": context_header},
        {"role": "user", "content": f"{user_message}\n\n{style_hint}"},
    ]

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
    system_text = get_platform_guardrails() + "\n\n" + get_visible_thinking_core()
    used_layers = ["platform_guardrails", "visible_thinking_core"]

    scene_text = get_scene_prompt(scene_key)
    if scene_text:
        system_text += (
            "\n\n当前工作场景："
            + scene_key
            + "。\n下面是该场景的正式策略参考，请据此组织“思考摘要”，而不是直接输出最终建议。\n"
            + scene_text
        )
        used_layers.append(f"scene:{scene_key}")

    context_header = (
        "当前客户的真实姓名是：" + (customer_name or "未知客户") + "。\n"
        "你正在为健康教练生成“可展示的思考摘要”，而不是最终回复。\n"
        "若用户使用'你'来提问，除非明确说明是在问 AI，自然语言里的'你'默认指当前客户「"
        + (customer_name or "未知客户")
        + "」。\n"
        "以下是系统生成的客户上下文，schema_version=customer_profile_context.v1。\n\n"
        + context_text
    )
    used_layers.append("customer_context")

    if rag_context_text:
        context_header += (
            "\n\n【公司话术与知识库参考】\n"
            "- 以下内容来自内部话术库/知识库，是辅助参考。\n\n"
            + rag_context_text
        )
        used_layers.append("rag_context")

    note_text = build_profile_note_text(profile_note)
    if note_text:
        context_header += "\n\n" + note_text
        used_layers.append("profile_note")

    messages = [
        {"role": "system", "content": system_text},
        {"role": "system", "content": context_header},
        {
            "role": "user",
            "content": (
                f"{user_message}\n\n"
                "请输出给界面展示的简短思考摘要。"
                "重点写：你正在看什么信息、有哪些风险边界、准备如何组织正式回复。"
            ),
        },
    ]

    return PromptAssembly(
        messages=messages,
        prompt_version=get_version(),
        prompt_hash=get_visible_thinking_prompt_hash(scene_key),
        scene_key=scene_key,
        used_layers=used_layers,
    )
