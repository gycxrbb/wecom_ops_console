"""Lightweight keyword-based intent recognition for RAG retrieval."""
from __future__ import annotations

from ..config import settings

# Nutrition / dining-out keywords
_NUTRITION_KEYWORDS = frozenset({
    "出差", "外卖", "外食", "点餐", "便利店", "酒店早餐",
    "餐食", "吃什么", "主食", "低卡", "控糖", "饮食",
    "减脂", "食材", "热量", "蛋白质", "碳水", "脂肪",
    "早餐", "午餐", "晚餐", "加餐", "零食", "饮料",
    "营养", "食谱", "卡路里", "饱腹", "代餐",
})

# Points / gamification operation keywords
_POINTS_KEYWORDS = frozenset({
    "积分", "排名", "榜单", "打卡", "活跃", "PK",
    "领先", "冲刺", "暴涨", "潜水", "氛围", "提醒",
    "榜单排名", "积分榜", "活跃度",
})


def recognize_intent(message: str, scene_key: str) -> dict:
    """Return {"domain": str, "negative_scenes": list[str]}.

    domain is "nutrition", "points_operation", or "unknown".
    When domain is nutrition, negative_scenes excludes points operation scenes.
    """
    text = message.lower()

    nutrition_hits = sum(1 for kw in _NUTRITION_KEYWORDS if kw in text)
    points_hits = sum(1 for kw in _POINTS_KEYWORDS if kw in text)

    domain = "unknown"
    negative_scenes: list[str] = []

    if nutrition_hits > 0 and nutrition_hits >= points_hits:
        domain = "nutrition"
        negative_scenes = [
            s.strip()
            for s in settings.rag_points_operation_scenes.split(",")
            if s.strip()
        ]
    elif points_hits > 0 and points_hits > nutrition_hits:
        domain = "points_operation"

    return {"domain": domain, "negative_scenes": negative_scenes}
