"""Context builder — plan resolution, whitelist validation, token estimation."""
from __future__ import annotations

import json
import logging

from ..schemas.context import ModulePayload, ContextBuildPlan

_log = logging.getLogger(__name__)

# Prohibited fields per §5.7
_PROHIBITED_KEYS = {
    "last_login_ip", "user_id", "huami_user_id", "avatar",
    "password", "salt", "wxwork", "settings",
    "openid", "unionid",
    "raw_data",
}

# Max prompt tokens
_DEFAULT_TOKEN_BUDGET = 30000

MODULE_LABELS = {
    "basic_profile": "基础档案",
    "safety_profile": "安全档案",
    "goals_preferences": "目标与偏好",
    "health_summary_7d": "近7天健康摘要",
    "body_comp_latest_30d": "近30天体成分",
    "points_engagement_14d": "近14天积分与活跃",
    "service_scope": "服务关系",
    "habit_adherence_14d": "近14天习惯执行",
    "plan_progress_14d": "近14天计划推进",
    "reminder_adherence_14d": "提醒依从",
    "learning_engagement_30d": "近30天学习",
    "ai_decision_labels": "AI决策标签",
}

FIELD_LABELS = {
    "basic_profile": {
        "display_name": "客户姓名",
        "gender": "性别",
        "age": "年龄",
        "height_cm": "身高(cm)",
        "weight_kg": "体重(kg)",
        "bmi": "BMI",
        "crm_status": "客户状态",
        "tags": "客户标签",
        "has_cgm": "是否佩戴CGM",
        "compliance_level": "配合度",
        "severity": "风险等级",
        "points": "当前积分",
        "total_points": "累计积分",
    },
    "safety_profile": {
        "health_condition_summary": "健康状况",
        "medical_history": "病史",
        "genetic_history": "家族史",
        "allergies": "过敏信息",
        "sport_injuries": "运动损伤",
        "prescription_summary": "处方摘要",
        "contraindications": "禁忌与病史",
        "risk_level": "风险等级",
    },
    "goals_preferences": {
        "primary_goals": "主要目标",
        "target_weight_kg": "目标体重(kg)",
        "target_heart_rate": "目标心率",
        "target_glucose": "目标血糖",
        "target_blood_pressure": "目标血压",
        "diet": "饮食偏好",
        "exercise": "运动偏好",
        "sleep": "睡眠质量",
    },
    "health_summary_7d": {
        "days": "记录天数",
        "weight": "最新体重(kg)",
        "weight_trend": "体重变化",
        "blood_pressure": "血压摘要",
        "glucose": "血糖摘要",
        "sleep": "睡眠摘要",
        "activity": "运动摘要",
        "diet": "饮食摘要",
        "symptoms": "症状反馈",
        "window_days": "统计窗口(天)",
        "glucose_avg": "血糖均值(mmol/L)",
        "glucose_peak": "血糖峰值(mmol/L)",
        "glucose_days": "血糖记录天数",
        "glucose_high_days": "血糖偏高天数",
        "meal_record_days": "饮食记录天数",
        "meal_complete_days": "三餐完整天数",
        "water_avg_ml": "日均饮水(ml)",
        "water_on_target_days": "饮水达标天数",
    },
    "body_comp_latest_30d": {
        "days": "记录天数",
        "latest": "最新体成分",
        "trend": "30天变化",
    },
    "points_engagement_14d": {
        "points_current": "当前积分",
        "points_total": "累计积分",
        "earned_14d": "近14天获得积分",
        "spent_14d": "近14天消费积分",
        "active_days_14d": "近14天活跃天数",
        "summary": "活跃摘要",
    },
    "service_scope": {
        "group_names": "所属群",
        "group_count": "群数量",
        "current_coach_names": "负责教练",
        "staff_count": "服务成员数",
    },
    "habit_adherence_14d": {
        "active_habits_count": "活跃习惯数",
        "avg_checkin_completion_rate_14d": "14天打卡完成率",
        "failed_checkin_days_14d": "14天未打卡天数",
        "current_streak_max": "最大连续打卡",
        "top_obstacles": "主要障碍",
        "if_then_plan_summary": "IF-THEN计划摘要",
    },
    "plan_progress_14d": {
        "current_plan_title": "当前计划",
        "current_plan_status": "计划状态",
        "plan_day_progress": "计划进度",
        "todo_completion_rate_14d": "14天待办完成率",
        "overdue_todo_count": "逾期待办数",
        "pause_resume_events": "暂停恢复记录",
    },
    "reminder_adherence_14d": {
        "active_reminder_count": "活跃提醒数",
        "reminders_by_business_type": "按类型分布",
        "trigger_count_total": "总触发次数",
        "last_triggered_at": "最近触发时间",
        "estimated_follow_through_rate": "估算执行率",
    },
    "learning_engagement_30d": {
        "course_total_assigned": "分配课程数",
        "course_in_progress": "学习中",
        "course_completed": "已完成",
        "completion_rate": "完成率",
        "study_minutes_30d": "30天学习分钟",
        "last_learning_at": "最近学习时间",
    },
    "ai_decision_labels": {
        "label_count": "标签数",
        "label_summary": "标签摘要",
    },
}


def get_module_label(module_key: str) -> str:
    return MODULE_LABELS.get(module_key, module_key)


def get_field_label(module_key: str, field_key: str) -> str:
    return FIELD_LABELS.get(module_key, {}).get(field_key, field_key)


def resolve_context_plan(
    entry_scene: str = "customer_profile",
    selected_expansions: list[str] | None = None,
) -> ContextBuildPlan:
    """Generate a ContextBuildPlan based on scene and user selections."""
    plan = ContextBuildPlan()

    if selected_expansions:
        plan.expansion_modules = selected_expansions

    return plan


def validate_field_whitelist(cards: list[ModulePayload]) -> list[str]:
    """Scan payloads for prohibited fields. Returns list of violations found."""
    violations = []
    for card in cards:
        for key in card.payload:
            if key in _PROHIBITED_KEYS:
                violations.append(f"{card.key}.{key}")
    return violations


def estimate_tokens(cards: list[ModulePayload]) -> int:
    """Rough token estimate: ~4 chars per token for Chinese text."""
    total_chars = 0
    for card in cards:
        if card.status != "ok":
            continue
        for v in card.payload.values():
            if v is not None and not isinstance(v, (list, dict)):
                total_chars += len(str(v))
    return total_chars // 4


def build_context_text(
    cards: list[ModulePayload],
    token_budget: int = _DEFAULT_TOKEN_BUDGET,
    selected_expansions: list[str] | None = None,
) -> str:
    """Serialize cards into context text for AI, respecting token budget.

    When selected_expansions is provided, matching modules get expanded
    detail instead of just summary.
    """
    expansions = set(selected_expansions or [])
    sections = []
    total_est = 0

    for card in cards:
        if card.status not in ("ok", "partial") or not card.payload:
            continue
        lines = []
        is_expanded = card.key in expansions or any(
            e in expansions and e.startswith(card.key.split("_")[0])
            for e in expansions
        )
        for k, v in card.payload.items():
            if v is None:
                continue
            if isinstance(v, (list, dict)):
                # Include expanded details for selected modules
                if is_expanded and isinstance(v, list):
                    for idx, item in enumerate(v[:5]):
                        if isinstance(item, dict):
                            detail_lines = [f"{sk}: {sv}" for sk, sv in item.items()
                                            if sv is not None and not isinstance(sv, (list, dict))]
                            if detail_lines:
                                lines.append(f"  [{idx + 1}] " + " | ".join(detail_lines))
                        else:
                            lines.append(f"  [{idx + 1}] {item}")
                continue
            lines.append(f"{get_field_label(card.key, k)}: {v}")
        if not lines:
            continue
        header_prefix = " [展开详情]" if is_expanded else ""
        header = get_module_label(card.key) + header_prefix
        section = f"### {header}\n" + "\n".join(lines)
        est = len(section) // 4
        if total_est + est > token_budget:
            break
        sections.append(section)
        total_est += est

    return "\n\n".join(sections)
