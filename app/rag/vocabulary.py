"""Controlled vocabulary for RAG — single source of truth for all tag dimensions."""
from __future__ import annotations

from typing import Any

# Each entry: (code, chinese_label, description, sort_order)
VOCABULARY: dict[str, list[tuple[str, str, str | None, int]]] = {
    "source_type": [
        ("speech_template", "话术模板", "CRM 话术库", 1),
        ("material", "素材", "素材库", 2),
        ("manual_card", "人工知识卡片", "未来知识卡片表", 3),
        ("external_doc", "外部文档", "外部文档资源", 4),
    ],
    "content_kind": [
        ("script", "话术", "教练回复话术模板", 1),
        ("text", "文本", "通用文本资料", 2),
        ("knowledge_card", "知识卡片", "结构化知识", 3),
        ("image", "图片", "图片素材", 4),
        ("video", "视频", "视频素材", 5),
        ("meme", "表情包", "表情包素材", 6),
        ("file", "文件", "PDF/表格/文档类附件", 7),
    ],
    "customer_goal": [
        ("weight_loss", "减脂", "减脂减重", 1),
        ("glucose_control", "控糖", "血糖管理", 2),
        ("habit_building", "习惯养成", "饮食/运动习惯建立", 3),
        ("nutrition_education", "饮食营养教育", "营养知识科普", 4),
        ("exercise_adherence", "运动坚持", "运动依从性提升", 5),
        ("emotion_support", "情绪支持", "情绪管理与心理支持", 6),
        ("device_usage", "设备使用", "健康设备使用指导", 7),
        ("maintenance", "长期维护", "长期维护阶段", 8),
    ],
    "intervention_scene": [
        ("meal_checkin", "晒餐/餐盘打卡", None, 1),
        ("meal_review", "餐评", None, 2),
        ("obstacle_breaking", "破阻力", None, 3),
        ("habit_education", "习惯教育", None, 4),
        ("emotional_support", "情绪支持", None, 5),
        ("qa_support", "问题答疑", None, 6),
        ("period_review", "周期复盘", None, 7),
        ("maintenance", "长期维护", None, 8),
        ("abnormal_intervention", "异常干预", None, 9),
        ("data_monitoring", "数据监测", None, 10),
        ("device_guidance", "设备指导", None, 11),
        ("points_operation", "积分/社群运营", None, 12),
    ],
    "question_type": [
        ("dining_out", "外食/外卖", None, 1),
        ("carb_choose", "主食选择", None, 2),
        ("low_calorie", "低卡食材", None, 3),
        ("late_night_snack", "晚间零食", None, 4),
        ("craving", "嘴馋/食欲", None, 5),
        ("hunger", "饥饿感", None, 6),
        ("food_safety", "食材安全", None, 7),
        ("high_glucose", "血糖偏高", None, 8),
        ("blood_fluctuation", "血糖波动", None, 9),
        ("data_monitoring", "数据解读", None, 10),
        ("no_checkin", "不打卡", None, 11),
        ("low_motivation", "动力不足", None, 12),
        ("device_usage", "设备使用", None, 13),
        ("plateau", "平台期", None, 14),
    ],
    "visibility": [
        ("coach_internal", "仅教练可见", "内部参考，不外发", 1),
        ("customer_visible", "客户可见", "可发客户，仍需教练复核", 2),
    ],
    "safety_level": [
        ("general", "通用", "无特殊限制", 1),
        ("nutrition_education", "营养科普", "营养知识，非医疗建议", 2),
        ("medical_sensitive", "医疗敏感", "涉及指标解读，需教练确认", 3),
        ("doctor_review", "需医生审核", "涉及用药/诊疗，必须医生确认", 4),
        ("contraindicated", "禁忌", "绝对禁止发给客户", 5),
    ],
    "status": [
        ("candidate", "候选", None, 1),
        ("approved", "已审核", None, 2),
        ("active", "已上线", None, 3),
        ("disabled", "停用", None, 4),
        ("archived", "归档", None, 5),
    ],
}

# Chinese-to-English alias mappings for CSV import compatibility
VISIBILITY_ALIASES: dict[str, str] = {
    "customer_sendable": "customer_visible",
    "可发客户": "customer_visible",
    "仅教练": "coach_internal",
    "内部": "coach_internal",
    "内部参考": "coach_internal",
    "教练内部": "coach_internal",
}

SAFETY_LEVEL_ALIASES: dict[str, str] = {
    "medical_review": "doctor_review",
    "营养科普": "nutrition_education",
    "医疗敏感": "medical_sensitive",
    "需医生审核": "doctor_review",
    "禁忌": "contraindicated",
}

TAG_ALIASES: dict[str, dict[str, str]] = {
    "customer_goal": {
        "体重管理": "weight_loss",
        "减重": "weight_loss",
        "减脂减重": "weight_loss",
        "血糖管理": "glucose_control",
        "饮食管理": "nutrition_education",
        "营养教育": "nutrition_education",
        "运动管理": "exercise_adherence",
        "情绪管理": "emotion_support",
        "睡眠管理": "habit_building",
    },
    "question_type": {
        "diet_guidance": "carb_choose",
        "exercise_guidance": "device_usage",
        "medication_adherence": "data_monitoring",
        "lifestyle_change": "low_motivation",
    },
}

# Reverse map: dimension -> {chinese_label: code}
_CHINESE_MAP: dict[str, dict[str, str]] = {}
_CODE_MAP: dict[str, dict[str, tuple[str, str, int]]] = {}


def _build_maps() -> None:
    for dim, entries in VOCABULARY.items():
        _CHINESE_MAP[dim] = {}
        _CODE_MAP[dim] = {}
        for code, label, desc, sort in entries:
            _CHINESE_MAP[dim][label] = code
            _CODE_MAP[dim][code] = (label, desc or "", sort)


_build_maps()


def get_valid_codes(dimension: str) -> set[str]:
    return set(_CODE_MAP.get(dimension, {}).keys())


def validate_code(dimension: str, value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower().replace("-", "_").replace(" ", "_")
    if v in _CODE_MAP.get(dimension, {}):
        return v
    return None


def map_chinese_to_code(dimension: str, chinese: str) -> str | None:
    if not chinese:
        return None
    return _CHINESE_MAP.get(dimension, {}).get(chinese.strip())


def resolve_code(dimension: str, raw: str | None) -> str | None:
    """Try validate_code first, then map_chinese_to_code, then alias tables."""
    if not raw:
        return None
    code = validate_code(dimension, raw)
    if code:
        return code
    chinese_code = map_chinese_to_code(dimension, raw)
    if chinese_code:
        return chinese_code
    if dimension == "visibility":
        return VISIBILITY_ALIASES.get(raw.strip().lower().replace("-", "_").replace(" ", "_"))
    if dimension == "safety_level":
        return SAFETY_LEVEL_ALIASES.get(raw.strip().lower().replace("-", "_").replace(" ", "_"))
    alias = TAG_ALIASES.get(dimension, {})
    normalized = raw.strip().lower().replace("-", "_").replace(" ", "_")
    return alias.get(raw.strip()) or alias.get(normalized)
    return None


def get_label(dimension: str, code: str) -> str:
    entry = _CODE_MAP.get(dimension, {}).get(code)
    return entry[0] if entry else code


def resolve_tag_values(dimension: str, raw: str | None) -> list[str]:
    """Split multi-value string and resolve each to canonical code."""
    if not raw or not raw.strip():
        return []
    import re
    values: list[str] = []
    for item in re.split(r"[|、,，;；/]+", raw):
        code = resolve_code(dimension, item.strip())
        if code and code not in values:
            values.append(code)
    return values
