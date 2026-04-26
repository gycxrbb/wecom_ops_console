"""Structured safety gate for AI coach answers.

Replaces keyword-only checks with rule-based risk evaluation using
structured safety profile data.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class SafetyDecisionInput:
    risk_level: str = ""
    allergies: str = ""
    contraindications: str = ""
    medical_history: str = ""
    sport_injuries: str = ""
    prescription_summary: str = ""


@dataclass
class SafetyDecision:
    level: str = "pass"  # "pass" | "coach_warning" | "medical_review_required"
    reason_codes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


_MEDICAL_KEYWORDS = ["停药", "减药", "加药", "换药", "开药", "诊断", "处方", "建议停"]

_HIGH_INTENSITY_PATTERNS = [
    "高强度运动", "剧烈运动", "高强度训练", "极限运动",
    "快速跑", "冲刺", "HIIT", "高强度间歇",
]

_CONTRAINDICATION_KEYWORDS = [
    "关节", "膝盖", "腰椎", "颈椎", "骨折", "韧带",
    "半月板", "椎间盘", "损伤", "术后", "禁忌",
]

_SEVERE_ALLERGY_PATTERN = re.compile(r"(严重|过敏性休克|anaphylax)", re.IGNORECASE)


def build_safety_input(safety_payload: dict) -> SafetyDecisionInput:
    return SafetyDecisionInput(
        risk_level=str(safety_payload.get("risk_level") or "").strip(),
        allergies=str(safety_payload.get("allergies") or "").strip(),
        contraindications=str(safety_payload.get("contraindications") or "").strip(),
        medical_history=str(safety_payload.get("medical_history") or "").strip(),
        sport_injuries=str(safety_payload.get("sport_injuries") or "").strip(),
        prescription_summary=str(safety_payload.get("prescription_summary") or "").strip(),
    )


def evaluate_ai_answer_safety(answer: str, safety_input: SafetyDecisionInput) -> SafetyDecision:
    """Run structured + text safety rules against an AI answer."""
    decision = SafetyDecision()
    answer_lower = answer.lower()
    has_contraindications = bool(safety_input.contraindications or safety_input.sport_injuries)
    is_high_risk = safety_input.risk_level in ("high", "高", "高风险", "3", "4", "5")

    # Rule 1: High-intensity exercise + contraindication conflict
    if has_contraindications:
        for pattern in _HIGH_INTENSITY_PATTERNS:
            if pattern in answer_lower:
                decision.level = "medical_review_required"
                decision.reason_codes.append("exercise_contraindication_conflict")
                decision.notes.append("AI 建议的运动与当前运动禁忌/损伤冲突，需要复核")
                break

    # Rule 2: Medical expression in answer
    for kw in _MEDICAL_KEYWORDS:
        if kw in answer:
            if decision.level != "medical_review_required":
                decision.level = "medical_review_required"
            decision.reason_codes.append("medical_term")
            decision.notes.append(f"AI 回复中包含医疗相关表述「{kw}」，需要医疗审核")
            break

    # Rule 3: Allergen conflict
    if safety_input.allergies:
        allergens = [a.strip() for a in safety_input.allergies.replace("，", ",").replace("、", ",").split(",") if a.strip()]
        severe_allergy = bool(_SEVERE_ALLERGY_PATTERN.search(safety_input.allergies))
        for allergen in allergens:
            if allergen and allergen in answer:
                if is_high_risk or severe_allergy:
                    if decision.level != "medical_review_required":
                        decision.level = "medical_review_required"
                    decision.reason_codes.append("allergen_conflict_severe")
                    decision.notes.append(f"AI 回复中提到了过敏原「{allergen}」，客户风险等级较高，需要复核")
                else:
                    if decision.level == "pass":
                        decision.level = "coach_warning"
                    decision.reason_codes.append("allergen_conflict")
                    decision.notes.append(f"AI 回复中提到了过敏原「{allergen}」，请教练重点复核")
                break

    # Rule 4: High-risk customer conservative output
    if is_high_risk and decision.level == "pass":
        for pattern in _HIGH_INTENSITY_PATTERNS:
            if pattern in answer_lower:
                decision.level = "coach_warning"
                decision.reason_codes.append("high_risk_exercise_hint")
                decision.notes.append("高风险客户，AI 建议了高强度运动方向，请教练注意")
                break

    return decision
