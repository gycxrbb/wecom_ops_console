import json
import math
from datetime import date
from pathlib import Path

from .config import get_params_dir

# 维度归属映射
DIM_MAP = {
    "glucose": ["hba1c"],
    "vascular": ["sbp", "pp"],
    "metabolic": ["tc", "hscrp"],
    "hepatorenal": ["albumin", "creatinine"],
    "skeletal": ["alp"],
}

# 完整度门控
REQUIRED_CODES = {"hba1c", "albumin", "creatinine", "tc"}
OPTIONAL_CODES = {"alp", "hscrp"}
ALL_CODES = REQUIRED_CODES | OPTIONAL_CODES | {"sbp", "pp"}


def load_params(version: str = "v2.0-draft") -> dict:
    """从 JSON 文件加载指定版本的 KDM 参数。"""
    path = get_params_dir() / f"{version}.json"
    if not path.is_file():
        raise FileNotFoundError(f"参数文件不存在: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def assess_readiness(biomarkers: dict, bp_data: dict | None) -> dict:
    """评估数据完备度，返回是否可计算、置信度、缺失项。"""
    available = set()
    missing = []
    warnings = []

    for code in ["hba1c", "albumin", "creatinine", "alp", "hscrp", "tc"]:
        if biomarkers.get(code) is not None:
            available.add(code)
        else:
            missing.append(code)

    has_bp = bp_data and bp_data.get("sbp_mean") is not None
    if has_bp:
        available.add("sbp")
        available.add("pp")
    else:
        missing.extend(["sbp", "pp"])

    n = len(available)

    if n < 5:
        return {
            "can_calculate": False, "n_available": n, "total": 8,
            "missing": missing, "confidence": "low",
            "warnings": [f"还需补充 {len(missing)} 项数据"],
        }

    if n >= 7:
        confidence = "high"
    else:
        confidence = "medium"

    core_missing = [c for c in missing if c in REQUIRED_CODES]
    if core_missing:
        confidence = "low"
        warnings.append(f"核心指标缺失：{','.join(core_missing)}，结果准确性受限")

    if bp_data and bp_data.get("n_records", 0) < 3:
        warnings.append(f"血压记录不足（n={bp_data.get('n_records', 0)}）")

    return {
        "can_calculate": True, "n_available": n, "total": 8,
        "missing": missing, "confidence": confidence, "warnings": warnings,
    }


def _resolve_qi_si(params: dict, code: str, gender: str) -> tuple[float, float]:
    """解析参数：支持分性别 qi_male/qi_female 或统一 qi。"""
    if code == "creatinine":
        if gender == "male":
            qi = params.get("qi_male", params.get("qi", 0))
            si = params.get("si_male", params.get("si", 0))
        else:
            qi = params.get("qi_female", params.get("qi", 0))
            si = params.get("si_female", params.get("si", 0))
        return qi, si
    return params["qi"], params["si"]


def _aggregate_dimensions(contributions: dict) -> dict:
    """将指标贡献度聚合为 5 个维度分数。"""
    result = {}
    for dim, codes in DIM_MAP.items():
        vals = [contributions[c] for c in codes if c in contributions]
        result[dim] = round(sum(vals) / len(vals), 4) if vals else None
    return result


def calculate_kdm(
    age: float,
    gender: str,
    biomarkers: dict,
    sbp_mean: float | None = None,
    dbp_mean: float | None = None,
    param_version: str = "v2.0-draft",
    checkup_age_days: int | None = None,
    bp_window_days: int | None = None,
    bp_record_count: int | None = None,
) -> dict:
    """
    KDM 核心计算。纯函数，无外部依赖。

    参数:
        age: 日历年龄（精确到小数）
        gender: "male" | "female"
        biomarkers: {code: value | None, ...} 已完成单位标准化
        sbp_mean: 血压收缩压均值（已完成窗口聚合）
        dbp_mean: 血压舒张压均值
        param_version: 参数版本号
        checkup_age_days: 距体检日期天数
        bp_window_days: 血压均值窗口天数
        bp_record_count: 血压有效记录数

    返回:
        计算结果字典，或 raise InsufficientDataError
    """
    params = load_params(param_version)
    s2_ca = params["meta"]["s2_ca"]

    # 补算血压指标
    bm = dict(biomarkers)
    if sbp_mean is not None and dbp_mean is not None:
        bm["sbp"] = sbp_mean
        bm["pp"] = round(sbp_mean - dbp_mean, 1)

    # 时效降权
    age_weight_applied = False
    age_weight = 1.0
    if checkup_age_days is not None and checkup_age_days > 548:
        age_weight = 0.7
        age_weight_applied = True

    # 完备度门控
    bp_data = None
    if sbp_mean is not None:
        bp_data = {"sbp_mean": sbp_mean, "n_records": bp_record_count or 0}
    readiness = assess_readiness(bm, bp_data)
    if not readiness["can_calculate"]:
        raise InsufficientDataError(
            f"有效数据仅 {readiness['n_available']} 项，需至少 5 项。"
            f"缺失：{readiness['missing']}"
        )

    # KDM 公式
    numerator = age / s2_ca
    denominator = 1.0 / s2_ca
    contributions = {}
    used_codes = []
    missing_codes = []

    for code in params["biomarkers"]:
        val = bm.get(code)
        if val is None:
            missing_codes.append(code)
            continue

        p = params["biomarkers"][code]
        qi, si = _resolve_qi_si(p, code, gender)
        ki = p["ki"]

        # hs-CRP 对数变换
        xi = math.log(max(val, 0.01)) if p.get("log_transform") else val

        # 围绝经期 ALP 补丁
        if code == "alp" and gender == "female" and age >= 50:
            ki *= 1.28

        si2 = si ** 2
        contrib = (xi - qi) * ki / si2 * age_weight

        numerator += contrib
        denominator += ki ** 2 / si2
        contributions[code] = round(contrib, 5)
        used_codes.append(code)

    if len(used_codes) < 5:
        raise InsufficientDataError(f"有效数据仅 {len(used_codes)} 项")

    ba = numerator / denominator
    baa = ba - age

    dim_scores = _aggregate_dimensions(contributions)

    return {
        "biological_age": round(ba, 1),
        "chronological_age": round(age, 1),
        "age_acceleration": round(baa, 1),
        "n_biomarkers": len(used_codes),
        "total_biomarkers": 8,
        "used_codes": used_codes,
        "missing_codes": missing_codes,
        "contributions": contributions,
        "dim_scores": dim_scores,
        "confidence": readiness["confidence"],
        "warnings": readiness["warnings"],
        "param_version": param_version,
        "age_weight_applied": age_weight_applied,
        "bp_window_days": bp_window_days,
        "bp_record_count": bp_record_count,
    }


class InsufficientDataError(Exception):
    """数据不足以完成计算。"""
