"""Initial visual safety rules — block medical/PII/nudity, warn brand."""
from ..schemas.visual import VisualSafetyRule

SAFETY_RULES: list[VisualSafetyRule] = [
    # --- Block: medical imagery ---
    VisualSafetyRule(
        rule_id="block_drug_dosage",
        category="medical_imagery",
        description="禁止生成药物剂量/用药指导图",
        severity="block",
        keywords=("用药", "剂量", "停药", "换药", "减药", "二甲双胍", "胰岛素", "处方"),
        applies_to="prompt",
    ),
    VisualSafetyRule(
        rule_id="block_diagnosis",
        category="medical_imagery",
        description="禁止生成诊断结论图",
        severity="block",
        keywords=("诊断", "确诊", "检查结果", "病理"),
        applies_to="prompt",
    ),
    VisualSafetyRule(
        rule_id="block_acute_risk",
        category="medical_imagery",
        description="禁止生成急性风险相关图",
        severity="block",
        keywords=("胸痛", "心梗", "中风", "昏迷", "急救", "120"),
        applies_to="prompt",
    ),
    # --- Block: PII ---
    VisualSafetyRule(
        rule_id="block_pii",
        category="pii_block",
        description="禁止使用客户隐私信息",
        severity="block",
        keywords=("身份证", "手机号", "姓名", "电话", "地址", "病历"),
        applies_to="prompt",
    ),
    # --- Block: nudity/violence ---
    VisualSafetyRule(
        rule_id="block_nudity_violence",
        category="content_restriction",
        description="禁止裸露/暴力/色情内容",
        severity="block",
        keywords=("裸", "色情", "暴力", "血腥"),
        applies_to="both",
    ),
    # --- Block: false promises ---
    VisualSafetyRule(
        rule_id="block_false_promise",
        category="content_restriction",
        description="禁止生成保证疗效的图片",
        severity="block",
        keywords=("保证降糖", "一定瘦", "包治", "根治"),
        applies_to="prompt",
    ),
    # --- Warn: brand ---
    VisualSafetyRule(
        rule_id="warn_brand",
        category="brand_guard",
        description="提醒品牌一致性",
        severity="warn",
        keywords=("品牌", "logo", "商标"),
        applies_to="both",
    ),
]
