"""Hard rule gates for visual decision — deterministic blocking before LLM/scoring.

These rules NEVER call LLM. They provide fast, predictable blocking for:
- Fact/PII queries
- Drug dosage / diagnosis / acute risk
- Individual data lookups
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PreRuleResult:
    """Result of hard rule pre-check."""
    blocked: bool = False
    reason: str = ""
    rule_id: str = ""


# Fact queries — questions about individual data, not suitable for visualization
_FACT_PATTERNS: tuple[str, ...] = (
    "几岁", "多大", "生日", "姓名", "名字", "电话", "地址",
    "几斤", "体重多少", "血压多少", "心率多少", "血糖多少",
    "她血糖", "他血糖", "客户血压", "客户心率",
)

# Individual data lookups — numeric/factual queries about a specific person
_DATA_LOOKUP_PATTERNS: tuple[str, ...] = (
    "查一下", "告诉我她的", "告诉我他的", "她最近", "他最近",
    "数据怎么样", "指标怎么样",
)

# Drug / diagnosis / acute risk — always block
_DRUG_DIAGNOSIS_PATTERNS: tuple[str, ...] = (
    "停药", "换药", "减药", "加药", "调药",
    "诊断", "确诊",
    "胸痛", "心梗", "中风", "昏迷", "急救", "120",
)


def pre_rule_check(message: str) -> PreRuleResult:
    """Run hard rule gates. Returns blocked=True if message must NOT generate visual."""
    text = message.lower()

    # 1. Drug / diagnosis / acute risk
    for p in _DRUG_DIAGNOSIS_PATTERNS:
        if p in text:
            return PreRuleResult(blocked=True, reason=f"医疗安全拦截: {p}", rule_id="hard_medical_block")

    # 2. Fact/PII queries
    for p in _FACT_PATTERNS:
        if p in text:
            return PreRuleResult(blocked=True, reason="事实/数据查询，不适合可视化", rule_id="hard_fact_query")

    # 3. Data lookups (only block if it looks like a pure question)
    for p in _DATA_LOOKUP_PATTERNS:
        if p in text and ("?" in text or "？" in text):
            return PreRuleResult(blocked=True, reason="数据查询，不适合可视化", rule_id="hard_data_lookup")

    return PreRuleResult()


def is_sensitive_topic(message: str) -> bool:
    """Check if message touches supplement / medical boundary topics.

    These are NOT blocked, but should be downgraded to manual_confirm at most.
    """
    text = message.lower()
    sensitive = (
        "补剂", "保健品", "phgg", "益生元", "益生菌",
        "维生素", "钙片", "铁剂", "服用", "怎么服用",
        "服用方法", "服用量",
    )
    return any(s in text for s in sensitive)


def has_reusable_asset_override(
    rag_sources: list[dict] | None,
    recommended_assets: list[dict] | None,
) -> bool:
    """Check if there are high-quality reusable assets that should prevent new generation.

    Returns True if an existing asset should be preferred over generating a new one.
    """
    if not recommended_assets:
        return False
    for asset in recommended_assets:
        quality = asset.get("quality_score", 0)
        if quality >= 0.8:
            return True
    return False
