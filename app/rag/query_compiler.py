"""Query Compiler — structured intent extraction for RAG retrieval."""
from __future__ import annotations

from dataclasses import dataclass, field

from .intent_rules import recognize_intent
from .vocabulary import VOCABULARY, get_label, get_valid_codes

_SAFETY_ORDER = ["general", "nutrition_education", "medical_sensitive", "doctor_review", "contraindicated"]

# Build keyword-to-code reverse index from vocabulary Chinese labels
_GOAL_KEYWORDS: dict[str, str] = {}
_SCENE_KEYWORDS: dict[str, str] = {}
_QTYPE_KEYWORDS: dict[str, str] = {}

for _code, _label, _desc, _sort in VOCABULARY.get("customer_goal", []):
    for _kw in _label.split("/"):
        _kw = _kw.strip()
        if _kw:
            _GOAL_KEYWORDS[_kw] = _code

for _code, _label, _desc, _sort in VOCABULARY.get("intervention_scene", []):
    for _kw in _label.split("/"):
        _kw = _kw.strip()
        if _kw:
            _SCENE_KEYWORDS[_kw] = _code

for _code, _label, _desc, _sort in VOCABULARY.get("question_type", []):
    for _kw in _label.split("/"):
        _kw = _kw.strip()
        if _kw:
            _QTYPE_KEYWORDS[_kw] = _code


@dataclass
class QueryIntent:
    domain: str = "unknown"
    customer_goals: list[str] = field(default_factory=list)
    intervention_scenes: list[str] = field(default_factory=list)
    question_types: list[str] = field(default_factory=list)
    max_safety_level: str = "medical_sensitive"
    negative_scenes: list[str] = field(default_factory=list)
    query_text: str = ""


def compile_query(message: str, scene_key: str) -> QueryIntent:
    """Compile user message + scene into structured query intent."""
    intent = recognize_intent(message, scene_key)

    goals = _extract_keywords(message, _GOAL_KEYWORDS)
    scenes = _extract_keywords(message, _SCENE_KEYWORDS)
    qtypes = _extract_keywords(message, _QTYPE_KEYWORDS)

    if scene_key and scene_key in get_valid_codes("intervention_scene"):
        if scene_key not in scenes:
            scenes.append(scene_key)

    label_parts = []
    for g in goals:
        label_parts.append(get_label("customer_goal", g))
    for s in scenes:
        label_parts.append(get_label("intervention_scene", s))
    for q in qtypes:
        label_parts.append(get_label("question_type", q))

    if label_parts:
        query_text = f"{' '.join(label_parts)} {message}"
    else:
        query_text = f"{scene_key} {message}" if scene_key else message

    max_safety = "nutrition_education"
    text_lower = message.lower()
    if any(kw in text_lower for kw in ("用药", "药物", "胰岛素", "药品", "处方")):
        max_safety = "doctor_review"
    elif any(kw in text_lower for kw in ("血糖", "血压", "指标", "检查", "检验")):
        max_safety = "medical_sensitive"

    return QueryIntent(
        domain=intent["domain"],
        customer_goals=goals,
        intervention_scenes=scenes,
        question_types=qtypes,
        max_safety_level=max_safety,
        negative_scenes=intent.get("negative_scenes", []),
        query_text=query_text,
    )


def _extract_keywords(text: str, mapping: dict[str, str]) -> list[str]:
    found: list[str] = []
    for keyword, code in mapping.items():
        if keyword in text and code not in found:
            found.append(code)
    return found
