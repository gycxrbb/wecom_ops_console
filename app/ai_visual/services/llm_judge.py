"""LLM-based semantic judgment for visual intent routing.

Calls a small model to assess whether a user message warrants visual generation.
Returns structured JSON — does NOT make the final decision.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from app.config import settings

_log = logging.getLogger(__name__)

_PROMPT_TEMPLATE = (Path(__file__).resolve().parent.parent / "prompts" / "visual_judge.md").read_text(encoding="utf-8")


@dataclass
class LlmVisualJudge:
    """Structured output from the LLM visual judge."""
    has_visual_value: bool
    visual_value: float  # 0-1
    topic_clarity: float  # 0-1
    actionability: float  # 0-1
    text_only_sufficient: bool
    recommended_visual_type: str
    topic: str
    risk_hint: str  # "low" | "medium" | "high"
    reason: str


def _build_user_message(
    *,
    message: str,
    scene_key: str,
    rag_sources: list[dict] | None,
    recommended_assets: list[dict] | None,
    profile_safety_signals: dict | None,
) -> str:
    rag_summary = json.dumps(
        [{"title": s.get("title", ""), "score": s.get("score", 0), "source_type": s.get("source_type", "")}
         for s in (rag_sources or [])[:5]],
        ensure_ascii=False,
    ) if rag_sources else "[]"

    assets_summary = json.dumps(
        [{"title": a.get("title", ""), "quality": a.get("quality_score", 0)}
         for a in (recommended_assets or [])[:3]],
        ensure_ascii=False,
    ) if recommended_assets else "[]"

    safety_summary = json.dumps(profile_safety_signals or {}, ensure_ascii=False)

    return _PROMPT_TEMPLATE.replace("{{message}}", message) \
        .replace("{{scene_key}}", scene_key) \
        .replace("{{rag_sources_summary}}", rag_summary) \
        .replace("{{recommended_assets_summary}}", assets_summary) \
        .replace("{{profile_safety_signals}}", safety_summary)


def _extract_system_prompt() -> str:
    """Split the prompt template — everything before '请根据以下上下文' is system prompt."""
    marker = "请根据以下上下文"
    idx = _PROMPT_TEMPLATE.find(marker)
    if idx > 0:
        return _PROMPT_TEMPLATE[:idx].strip()
    return ""


def _parse_json_response(raw: str) -> LlmVisualJudge | None:
    """Extract JSON from LLM response, tolerant of markdown fences."""
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    # Remove trailing ```
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object in the response
        match = re.search(r"\{[^{}]*\}", cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                _log.warning("LLM judge: failed to parse JSON response")
                return None
        else:
            _log.warning("LLM judge: no JSON object found in response")
            return None

    required = {"has_visual_value", "visual_value", "topic_clarity", "actionability",
                "text_only_sufficient", "recommended_visual_type", "topic", "risk_hint", "reason"}
    if not required.issubset(data.keys()):
        _log.warning("LLM judge: missing fields %s", required - data.keys())
        return None

    return LlmVisualJudge(
        has_visual_value=bool(data["has_visual_value"]),
        visual_value=float(data["visual_value"]),
        topic_clarity=float(data["topic_clarity"]),
        actionability=float(data["actionability"]),
        text_only_sufficient=bool(data["text_only_sufficient"]),
        recommended_visual_type=str(data["recommended_visual_type"]),
        topic=str(data["topic"])[:50],
        risk_hint=str(data.get("risk_hint", "low")),
        reason=str(data["reason"])[:200],
    )


async def call_llm_judge(
    *,
    message: str,
    scene_key: str = "qa_support",
    rag_sources: list[dict] | None = None,
    recommended_assets: list[dict] | None = None,
    profile_safety_signals: dict | None = None,
) -> LlmVisualJudge | None:
    """Call small model for visual intent assessment. Returns None on failure."""
    import asyncio
    from app.clients.ai_chat_client import chat_completion

    if not settings.ai_visual_llm_judge_enabled:
        return None

    system_prompt = _extract_system_prompt()
    user_msg = _build_user_message(
        message=message,
        scene_key=scene_key,
        rag_sources=rag_sources,
        recommended_assets=recommended_assets,
        profile_safety_signals=profile_safety_signals,
    )

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_msg})

    timeout = settings.ai_visual_llm_judge_timeout_seconds

    try:
        content, _usage = await asyncio.wait_for(
            chat_completion(
                messages,
                model=settings.ai_visual_llm_judge_model,
                temperature=0.3,
                max_tokens=512,
            ),
            timeout=timeout,
        )
        return _parse_json_response(content)
    except asyncio.TimeoutError:
        _log.warning("LLM judge timed out (%ds)", timeout)
        return None
    except Exception:
        _log.warning("LLM judge failed", exc_info=True)
        return None
