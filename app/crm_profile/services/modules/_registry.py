"""Metric registry — single source of truth for health summary field metadata.

Every health metric's label, unit, precision, source table, group, and thresholds
are defined here. Sub-modules and context_builder read from this registry instead
of maintaining separate hardcoded dicts.

Adding a new metric: add a MetricDef entry here, then write the calculation in
the appropriate sub-module. No other metadata changes needed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MetricDef:
    key: str
    label: str
    unit: str = ""
    precision: int = 0        # decimal places; -1 = no formatting
    stat_type: str = "avg"    # avg|latest|count|sum|flag|container
    source_table: str = ""
    group: str = "base"       # base|glucose|meal|sleep|exercise|heartrate|nutrition|stress|meta
    thresholds: dict | None = None
    ai_safety_note: str | None = None


# ── Backward-compatible threshold constants ──
GLUCOSE_HIGH: float = 10.0
GLUCOSE_LOW: float = 3.9
WATER_TARGET_ML: int = 2000
HR_HIGH: int = 100
HR_LOW: int = 50
STRESS_HIGH: int = 80

# ── Maps container payload key → metric group ──
NESTED_KEY_MAP: dict[str, str] = {
    "sleep_detail": "sleep",
    "exercise_detail": "exercise",
    "heart_rate": "heartrate",
    "nutrition": "nutrition",
    "stress_detail": "stress",
}

M = MetricDef
HEALTH_METRICS: dict[str, MetricDef] = {
    # ── base (customer_health via _summarize.py) ──
    "days":                    M("days",                    "记录天数",              stat_type="count"),
    "window_days":             M("window_days",             "统计窗口(天)",           stat_type="latest"),
    "weight":                  M("weight",                  "最新体重(kg)",          "kg",  2, "latest", "customer_health"),
    "weight_trend":            M("weight_trend",            "体重变化",              stat_type="flag"),
    "blood_pressure":          M("blood_pressure",          "血压摘要",              stat_type="flag"),
    "blood_pressure_avg_sbp":  M("blood_pressure_avg_sbp",  "收缩压均值(mmHg)",      "mmHg", 0, "avg",  "customer_health"),
    "blood_pressure_avg_dbp":  M("blood_pressure_avg_dbp",  "舒张压均值(mmHg)",      "mmHg", 0, "avg",  "customer_health"),
    "fbs_avg":                 M("fbs_avg",                 "空腹血糖均值(mmol/L)",   "mmol/L", 1, "avg", "customer_health"),
    "pbs_avg":                 M("pbs_avg",                 "餐后血糖均值(mmol/L)",   "mmol/L", 1, "avg", "customer_health"),
    "glucose":                 M("glucose",                 "血糖摘要",              stat_type="flag"),
    "sleep":                   M("sleep",                   "睡眠摘要",              stat_type="flag"),
    "sleep_avg_min":           M("sleep_avg_min",           "日均睡眠(分钟)",         "min",  0, "avg", "customer_health"),
    "activity":                M("activity",                "运动摘要",              stat_type="flag"),
    "step_avg":                M("step_avg",                "日均步数(步)",           "步",   0, "avg", "customer_health"),
    "diet":                    M("diet",                    "饮食摘要",              stat_type="flag"),
    "kcal_avg":                M("kcal_avg",                "日均热量(kcal)",         "kcal", 0, "avg", "customer_health"),
    "symptoms":                M("symptoms",                "症状反馈",              stat_type="flag"),
    "bmi":                     M("bmi",                     "BMI",                  "",     1, "latest", "computed"),
    "hba1c_latest":            M("hba1c_latest",            "最新糖化血红蛋白(%)",    "%",    1, "latest", "customer_health"),
    "hba1c_avg":               M("hba1c_avg",               "糖化血红蛋白均值(%)",    "%",    1, "avg",   "customer_health"),
    # ── glucose (customer_glucose via _glucose.py) ──
    "glucose_avg":             M("glucose_avg",             "血糖均值(mmol/L)",       "mmol/L", 1, "avg",    "customer_glucose", "glucose"),
    "glucose_peak":            M("glucose_peak",            "血糖峰值(mmol/L)",       "mmol/L", 1, "max",    "customer_glucose", "glucose"),
    "glucose_low":             M("glucose_low",             "血糖谷值(mmol/L)",       "mmol/L", 1, "min",    "customer_glucose", "glucose"),
    "glucose_days":            M("glucose_days",            "血糖记录天数",           stat_type="count", source_table="customer_glucose", group="glucose"),
    "glucose_high_days":       M("glucose_high_days",       "血糖偏高天数",           stat_type="count", source_table="customer_glucose", group="glucose",
                                thresholds={"high": GLUCOSE_HIGH}),
    "glucose_low_days":        M("glucose_low_days",        "低血糖天数",             stat_type="count", source_table="customer_glucose", group="glucose",
                                thresholds={"low": GLUCOSE_LOW}),
    "glucose_highlights":      M("glucose_highlights",      "血糖波动",              stat_type="flag", group="glucose"),
    # ── meal (customer_health JSON via _meals.py) ──
    "meal_record_days":        M("meal_record_days",        "饮食记录天数",           stat_type="count", source_table="customer_health", group="meal"),
    "meal_complete_days":      M("meal_complete_days",      "三餐完整天数",           stat_type="count", source_table="customer_health", group="meal"),
    "water_avg_ml":            M("water_avg_ml",            "日均饮水(ml)",           "ml", 0, "avg", "customer_health", "meal"),
    "water_on_target_days":    M("water_on_target_days",    "饮水达标天数",           stat_type="count", source_table="customer_health", group="meal",
                                thresholds={"target": WATER_TARGET_ML}),
    "meal_highlights":         M("meal_highlights",         "近期餐食",              stat_type="flag", group="meal"),
    # ── sleep (customer_sleep via _sleep.py) ──
    "sleep_detail":            M("sleep_detail",            "睡眠结构详情",           stat_type="container", source_table="customer_sleep", group="sleep"),
    "sleep_record_days":       M("sleep_record_days",       "睡眠记录天数",           stat_type="count", source_table="customer_sleep", group="sleep"),
    "sleep_avg_deep_min":      M("sleep_avg_deep_min",      "日均深睡(分钟)",         "min",  0, "avg", "customer_sleep", "sleep"),
    "sleep_avg_rem_min":       M("sleep_avg_rem_min",       "日均REM(分钟)",          "min",  0, "avg", "customer_sleep", "sleep"),
    "sleep_avg_score":         M("sleep_avg_score",         "睡眠评分",              "",     0, "avg", "customer_sleep", "sleep"),
    "sleep_avg_rhr":           M("sleep_avg_rhr",           "睡眠静息心率",           "bpm",  0, "avg", "customer_sleep", "sleep"),
    # ── exercise (customer_sport via _exercise.py) ──
    "exercise_detail":         M("exercise_detail",         "运动详情",              stat_type="container", source_table="customer_sport", group="exercise"),
    "exercise_record_days":    M("exercise_record_days",    "运动记录天数",           stat_type="count", source_table="customer_sport", group="exercise"),
    "exercise_avg_calories":   M("exercise_avg_calories",   "日均运动消耗(kcal)",     "kcal", 0, "avg", "customer_sport", "exercise"),
    "exercise_total_calories": M("exercise_total_calories", "总运动消耗(kcal)",       "kcal", 0, "sum", "customer_sport", "exercise"),
    "exercise_avg_steps":      M("exercise_avg_steps",      "日均步数",              "步",   0, "avg", "customer_sport", "exercise"),
    "exercise_types":          M("exercise_types",          "运动类型",              stat_type="flag", source_table="customer_sport", group="exercise"),
    # ── heartrate (customer_heartrate via _heartrate.py) ──
    "heart_rate":              M("heart_rate",              "心率详情",              stat_type="container", source_table="customer_heartrate", group="heartrate"),
    "hr_avg":                  M("hr_avg",                  "日均心率(bpm)",          "bpm", 0, "avg",  "customer_heartrate", "heartrate"),
    "hr_max":                  M("hr_max",                  "最高心率(bpm)",          "bpm", 0, "max",  "customer_heartrate", "heartrate"),
    "hr_min":                  M("hr_min",                  "最低心率(bpm)",          "bpm", 0, "min",  "customer_heartrate", "heartrate"),
    "hr_days":                 M("hr_days",                 "心率记录天数",           stat_type="count", source_table="customer_heartrate", group="heartrate"),
    "hr_high_days":            M("hr_high_days",            "心率偏高天数",           stat_type="count", source_table="customer_heartrate", group="heartrate",
                                thresholds={"high": HR_HIGH}),
    "hr_low_days":             M("hr_low_days",             "心率偏低天数",           stat_type="count", source_table="customer_heartrate", group="heartrate",
                                thresholds={"low": HR_LOW}),
    # ── nutrition (customer_health via _nutrition.py) ──
    "nutrition":               M("nutrition",               "营养素详情",             stat_type="container", source_table="customer_health", group="nutrition"),
    "cho_avg_g":               M("cho_avg_g",               "日均碳水(g)",            "g",    0, "avg", "customer_health", "nutrition"),
    "fat_avg_g":               M("fat_avg_g",               "日均脂肪(g)",            "g",    0, "avg", "customer_health", "nutrition"),
    "protein_avg_g":           M("protein_avg_g",           "日均蛋白质(g)",           "g",    0, "avg", "customer_health", "nutrition"),
    "fiber_avg_g":             M("fiber_avg_g",             "日均膳食纤维(g)",         "g",    0, "avg", "customer_health", "nutrition"),
    "kcal_out_avg":            M("kcal_out_avg",            "日均消耗(kcal)",         "kcal", 0, "avg", "customer_health", "nutrition"),
    # ── stress (customer_stress + customer_health via _stress.py) ──
    "stress_detail":           M("stress_detail",           "压力与用药详情",          stat_type="container", source_table="customer_stress", group="stress"),
    "stress_avg":              M("stress_avg",              "压力均值",               "",     0, "avg", "customer_stress", "stress"),
    "stress_days":             M("stress_days",             "压力记录天数",            stat_type="count", source_table="customer_stress", group="stress"),
    "stress_high_days":        M("stress_high_days",        "高压天数",               stat_type="count", source_table="customer_stress", group="stress",
                                thresholds={"high": STRESS_HIGH}),
    "stress_text":             M("stress_text",             "压力描述",               stat_type="flag", source_table="customer_health", group="stress"),
    "medication":              M("medication",              "用药记录",               stat_type="flag", source_table="customer_health", group="stress",
                                ai_safety_note="仅做提醒，不生成医疗调整建议"),
    # ── meta (health_summary.py orchestration) ──
    "trend_flags":             M("trend_flags",             "趋势标记",               stat_type="flag",  group="meta"),
    "data_quality":            M("data_quality",            "数据质量",               stat_type="container", group="meta"),
    "stale_hint":              M("stale_hint",              "数据过时提示",            stat_type="flag",  group="meta"),
}
del M

# ── Validation ──
assert HEALTH_METRICS["glucose_high_days"].thresholds and HEALTH_METRICS["glucose_high_days"].thresholds["high"] == GLUCOSE_HIGH
assert HEALTH_METRICS["glucose_low_days"].thresholds and HEALTH_METRICS["glucose_low_days"].thresholds["low"] == GLUCOSE_LOW
assert HEALTH_METRICS["hr_high_days"].thresholds and HEALTH_METRICS["hr_high_days"].thresholds["high"] == HR_HIGH
assert HEALTH_METRICS["hr_low_days"].thresholds and HEALTH_METRICS["hr_low_days"].thresholds["low"] == HR_LOW
assert HEALTH_METRICS["stress_high_days"].thresholds and HEALTH_METRICS["stress_high_days"].thresholds["high"] == STRESS_HIGH


# ── Helper functions ──

def get_label(key: str) -> str:
    return HEALTH_METRICS[key].label if key in HEALTH_METRICS else key


def get_thresholds(key: str) -> dict | None:
    m = HEALTH_METRICS.get(key)
    return m.thresholds if m else None


def apply_precision(key: str, value: Any) -> Any:
    m = HEALTH_METRICS.get(key)
    if not m or m.precision < 0 or value is None or not isinstance(value, (int, float)):
        return value
    return round(float(value), m.precision)


def get_metrics_by_group(group: str) -> dict[str, MetricDef]:
    return {k: v for k, v in HEALTH_METRICS.items() if v.group == group}


def build_field_labels() -> dict[str, str]:
    return {k: v.label for k, v in HEALTH_METRICS.items()}
