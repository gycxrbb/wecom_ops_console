"""Visual Intent Router — assess whether a question warrants visual generation.

Orchestrates: hard rule gates → LLM semantic judge (when enabled) → scoring.
Falls back to keyword-based rules when LLM judge is disabled or fails.
"""
from __future__ import annotations

import logging

from ..schemas.visual import VisualDecision
from .decision_rules import pre_rule_check, is_sensitive_topic, has_reusable_asset_override
from .scoring import ScoreFactors, calculate_confidence, compute_evidence_strength, compute_scene_fit, compute_novelty, route_by_threshold
from .visual_safety import evaluate_visual_safety
from app.config import settings

_log = logging.getLogger(__name__)


def assess_visual_need(
    *,
    message: str,
    scene_key: str = "qa_support",
    rag_sources: list[dict] | None = None,
    safety_card: object | None = None,
    recommended_assets: list[dict] | None = None,
    profile_safety_signals: dict | None = None,
) -> VisualDecision:
    """Assess whether a user message warrants visual knowledge card generation."""
    topic = _extract_topic(message)

    # 1. Hard rule gates (deterministic, no LLM)
    rule_result = pre_rule_check(message)
    if rule_result.blocked:
        return VisualDecision(
            need_visual=False, confidence=0.0, decision_mode="no_visual",
            topic=topic, reason=rule_result.reason,
        )

    # 2. Safety check
    safety = evaluate_visual_safety(topic, message)
    if safety.blocked:
        return VisualDecision(
            need_visual=False, confidence=0.0, decision_mode="no_visual",
            topic=topic, reason=f"安全规则拦截: {', '.join(safety.matched_rules)}",
            safety_level="blocked",
        )

    # 3. Route to LLM judge or keyword fallback
    if settings.ai_visual_llm_judge_enabled:
        return _assess_with_llm(
            message=message, topic=topic, scene_key=scene_key,
            rag_sources=rag_sources, recommended_assets=recommended_assets,
            profile_safety_signals=profile_safety_signals, safety=safety,
        )

    return _assess_with_keywords(
        message=message, topic=topic, scene_key=scene_key,
        rag_sources=rag_sources, safety=safety,
    )


def _assess_with_llm(
    *,
    message: str,
    topic: str,
    scene_key: str,
    rag_sources: list[dict] | None,
    recommended_assets: list[dict] | None,
    profile_safety_signals: dict | None,
    safety: object,
) -> VisualDecision:
    """LLM-based assessment. Falls back to keywords on failure."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an async context — can't await directly.
        # Schedule the LLM call and get the result synchronously is not safe.
        # Use keyword fallback for now; the async caller should use assess_visual_need_async.
        _log.info("LLM judge: running inside async loop, falling back to keywords")
        return _assess_with_keywords(
            message=message, topic=topic, scene_key=scene_key,
            rag_sources=rag_sources, safety=safety,
        )

    # Synchronous context — safe to run async LLM call
    from .llm_judge import call_llm_judge
    judge_result = asyncio.get_event_loop().run_until_complete(
        call_llm_judge(
            message=message, scene_key=scene_key,
            rag_sources=rag_sources, recommended_assets=recommended_assets,
            profile_safety_signals=profile_safety_signals,
        )
    )

    if judge_result is None:
        _log.info("LLM judge returned None, falling back to keywords")
        return _assess_with_keywords(
            message=message, topic=topic, scene_key=scene_key,
            rag_sources=rag_sources, safety=safety,
        )

    return _build_decision_from_judge(
        judge=judge_result, message=message, topic=topic,
        scene_key=scene_key, rag_sources=rag_sources,
        recommended_assets=recommended_assets,
    )


async def assess_visual_need_async(
    *,
    message: str,
    scene_key: str = "qa_support",
    rag_sources: list[dict] | None = None,
    safety_card: object | None = None,
    recommended_assets: list[dict] | None = None,
    profile_safety_signals: dict | None = None,
) -> VisualDecision:
    """Async variant — safe to call from async stream handlers."""
    topic = _extract_topic(message)

    # 1. Hard rule gates
    rule_result = pre_rule_check(message)
    if rule_result.blocked:
        return VisualDecision(
            need_visual=False, confidence=0.0, decision_mode="no_visual",
            topic=topic, reason=rule_result.reason,
        )

    # 2. Safety check
    safety = evaluate_visual_safety(topic, message)
    if safety.blocked:
        return VisualDecision(
            need_visual=False, confidence=0.0, decision_mode="no_visual",
            topic=topic, reason=f"安全规则拦截: {', '.join(safety.matched_rules)}",
            safety_level="blocked",
        )

    # 3. LLM judge or fallback
    if settings.ai_visual_llm_judge_enabled:
        from .llm_judge import call_llm_judge
        judge_result = await call_llm_judge(
            message=message, scene_key=scene_key,
            rag_sources=rag_sources, recommended_assets=recommended_assets,
            profile_safety_signals=profile_safety_signals,
        )
        if judge_result is not None:
            return _build_decision_from_judge(
                judge=judge_result, message=message, topic=topic,
                scene_key=scene_key, rag_sources=rag_sources,
                recommended_assets=recommended_assets,
            )
        _log.info("LLM judge failed, falling back to keywords")

    return _assess_with_keywords(
        message=message, topic=topic, scene_key=scene_key,
        rag_sources=rag_sources, safety=safety,
    )


def _build_decision_from_judge(
    *,
    judge: object,
    message: str,
    topic: str,
    scene_key: str,
    rag_sources: list[dict] | None,
    recommended_assets: list[dict] | None,
) -> VisualDecision:
    """Build VisualDecision from LLM judge output + scoring factors."""
    sensitive = is_sensitive_topic(message)
    reusable = has_reusable_asset_override(rag_sources, recommended_assets)
    evidence = compute_evidence_strength(rag_sources)

    factors = ScoreFactors(
        visual_value=judge.visual_value,
        topic_clarity=judge.topic_clarity,
        actionability=judge.actionability,
        evidence_strength=evidence,
        scene_fit=compute_scene_fit(scene_key),
        novelty=compute_novelty(recommended_assets),
        safety_penalty=0.15 if sensitive else 0.0,
        reusable_asset_penalty=0.3 if reusable else 0.0,
    )

    confidence = calculate_confidence(factors)
    decision_mode, adjusted_conf = route_by_threshold(
        confidence,
        is_sensitive=sensitive,
        evidence_low=evidence < 0.3,
        has_reusable_asset=reusable,
    )

    if decision_mode == "no_visual":
        return VisualDecision(
            need_visual=False, confidence=adjusted_conf,
            decision_mode="no_visual", topic=topic,
            reason="可视化价值不足", score_factors=_factors_to_dict(factors),
        )

    if judge.text_only_sufficient and not sensitive:
        return VisualDecision(
            need_visual=False, confidence=adjusted_conf,
            decision_mode="no_visual", topic=topic,
            reason="纯文本已足够", score_factors=_factors_to_dict(factors),
        )

    safety_level = "medical_sensitive" if sensitive else "nutrition_education"
    reason = judge.reason if judge.reason else "适合生成可视化知识卡"
    confirm_question = None
    if decision_mode == "manual_confirm":
        confirm_question = f"可以为「{judge.topic or topic}」生成一张科普知识卡片，是否需要绘制图片？"
        if sensitive:
            confirm_question += "（内容涉及健康补剂，请确认是否适合对外展示）"

    return VisualDecision(
        need_visual=True,
        confidence=adjusted_conf,
        decision_mode=decision_mode,
        visual_type=judge.recommended_visual_type or "health_education_card",
        topic=judge.topic or topic,
        reason=reason,
        safety_level=safety_level,
        confirm_question=confirm_question,
        score_factors=_factors_to_dict(factors),
    )


# ── Keyword-based fallback ──────────────────────────────────────────────

_CANDIDATE_PATTERNS: list[tuple[list[str], float]] = [
    (["出差", "外食", "外卖", "餐食", "点餐", "选餐", "饮食选择"], 0.45),
    (["控糖", "稳糖", "血糖波动", "升糖", "降糖"], 0.35),
    (["运动", "锻炼", "健身", "步数"], 0.25),
    (["膳食纤维", "益生元", "蔬菜", "蛋白质", "碳水", "脂肪", "PHGG", "服用", "补剂", "保健品"], 0.40),
    (["怎么吃", "怎么选", "怎么做", "食谱", "搭配", "推荐", "服用方法", "怎么服用"], 0.35),
    (["清单", "步骤", "方法", "指南", "总结", "复盘"], 0.25),
    (["注意", "避免", "风险", "信号", "表现", "症状"], 0.20),
]

_SCENE_BONUS: dict[str, float] = {
    "qa_support": 0.0,
    "health_analysis": 0.15,
    "daily_checkin": 0.10,
    "plan_review": 0.10,
}


def _assess_with_keywords(
    *,
    message: str,
    topic: str,
    scene_key: str,
    rag_sources: list[dict] | None,
    safety: object,
) -> VisualDecision:
    """Keyword-based assessment — the original rule MVP, now a fallback."""
    text = message.lower()
    confidence = 0.0

    for keywords, base_score in _CANDIDATE_PATTERNS:
        for kw in keywords:
            if kw in text:
                confidence += base_score
                break

    confidence += _SCENE_BONUS.get(scene_key, 0.0)

    if rag_sources and len(rag_sources) > 0:
        top_score = max((s.get("score", 0) for s in rag_sources), default=0)
        if top_score > 0.6:
            confidence += 0.10
        confidence += min(len(rag_sources) * 0.02, 0.10)

    confidence = min(confidence, 1.0)

    is_sensitive = is_sensitive_topic(message)
    safety_level = "nutrition_education"
    if is_sensitive:
        safety_level = "medical_sensitive"
        confidence *= 0.85

    auto_threshold = settings.ai_visual_auto_generate_confidence
    manual_threshold = settings.ai_visual_manual_confirm_confidence

    if confidence >= auto_threshold:
        decision_mode = "auto_async_generate"
        reason = "问题适合可视化，证据充分，安全等级低"
    elif confidence >= manual_threshold:
        decision_mode = "manual_confirm"
        reason = "问题具备可视化价值，但需教练确认"
    else:
        return VisualDecision(
            need_visual=False, confidence=round(confidence, 2),
            decision_mode="no_visual", topic=topic, reason="可视化价值不足",
        )

    confirm_question = None
    if decision_mode == "manual_confirm":
        confirm_question = f"可以为「{topic}」生成一张科普知识卡片，是否需要绘制图片？"
        if is_sensitive:
            confirm_question += "（内容涉及健康补剂，请确认是否适合对外展示）"

    return VisualDecision(
        need_visual=True,
        confidence=round(confidence, 2),
        decision_mode=decision_mode,
        topic=topic,
        reason=reason,
        safety_level=safety_level,
        confirm_question=confirm_question,
    )


def _extract_topic(message: str) -> str:
    msg = message.strip()
    if len(msg) <= 20:
        return msg
    for sep in ["？", "?", "，", ",", "。", "；", "\n"]:
        idx = msg.find(sep)
        if 4 < idx <= 20:
            return msg[:idx]
    return msg[:16] + "..."


def _factors_to_dict(factors: ScoreFactors) -> dict[str, float]:
    return {
        "visual_value": factors.visual_value,
        "topic_clarity": factors.topic_clarity,
        "actionability": factors.actionability,
        "evidence_strength": factors.evidence_strength,
        "scene_fit": factors.scene_fit,
        "novelty": factors.novelty,
        "safety_penalty": factors.safety_penalty,
        "reusable_asset_penalty": factors.reusable_asset_penalty,
    }
