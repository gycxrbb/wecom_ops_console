"""数据采集适配层。通过 BioageDataProvider 抽象接口获取数据，CRMDataProvider 为 CRM 只读实现。"""

import math
from datetime import date, datetime
from typing import Protocol, runtime_checkable

# 指标 code 映射：标准 code → CRM customer_report_items 中可能的 code 变体
BIOMARKER_CODE_MAP = {
    "hba1c": ["hba1c", "glycated_hemoglobin", "HbA1c"],
    "albumin": ["albumin", "alb", "ALB"],
    "creatinine": ["creatinine", "Cr", "CREA", "cr"],
    "alp": ["alp", "ALP", "alkaline_phosphatase"],
    "hscrp": ["hscrp", "hs_crp", "hs-CRP", "crp_hs", "hsCRP"],
    "tc": ["tc", "total_cholesterol", "chol", "CHOL", "TC"],
}

# 反向映射：CRM code 变体 → 标准 code
_CODE_REVERSE_MAP: dict[str, str] = {}
for std_code, variants in BIOMARKER_CODE_MAP.items():
    for v in variants:
        _CODE_REVERSE_MAP[v.lower()] = std_code


@runtime_checkable
class BioageDataProvider(Protocol):
    """生物年龄数据源抽象接口。迁移到新平台时，只需实现此接口。"""

    def get_customer_basic(self, customer_id: int) -> dict | None:
        """返回 {"birthday": date, "gender": int, "name": str} 或 None"""
        ...

    def get_latest_biomarkers(self, customer_id: int) -> dict:
        """返回 {std_code: {"value": float, "unit": str, "date": date}, ...}"""
        ...

    def get_bp_records(self, customer_id: int, days: int = 7) -> list[dict]:
        """返回 [{"sbp": int, "dbp": int, "ts": str}, ...]"""
        ...

    def get_latest_checkup_date(self, customer_id: int) -> date | None:
        """返回最新体检日期"""
        ...


class CRMDataProvider:
    """CRM 数据源实现。只读 CRM 数据库，通过 PyMySQL 连接池查询。"""

    def __init__(self, get_conn, return_conn):
        self._get_conn = get_conn
        self._return_conn = return_conn

    def get_customer_basic(self, customer_id: int) -> dict | None:
        sql = """
            SELECT birthday, gender, name
            FROM customers
            WHERE id = %s
        """
        row = self._query_one(sql, (customer_id,))
        if not row or not row.get("birthday"):
            return None
        birthday = row["birthday"]
        if isinstance(birthday, str):
            birthday = date.fromisoformat(birthday[:10])
        return {"birthday": birthday, "gender": row["gender"], "name": row.get("name", "")}

    def get_latest_biomarkers(self, customer_id: int) -> dict:
        """获取最新血生化指标，按标准 code 映射。"""
        all_variants = []
        for std_code, variants in BIOMARKER_CODE_MAP.items():
            for v in variants:
                all_variants.append("%s")

        placeholders = ",".join(all_variants)
        sql = f"""
            SELECT cri.code, cri.value, cri.unit, cri.check_date
            FROM customer_report_items cri
            INNER JOIN (
                SELECT code, MAX(check_date) AS latest_date
                FROM customer_report_items
                WHERE customer_id = %s
                  AND code IN ({placeholders})
                  AND value IS NOT NULL
                GROUP BY code
            ) latest ON cri.code = latest.code AND cri.check_date = latest.latest_date
            WHERE cri.customer_id = %s
              AND cri.value IS NOT NULL
        """

        # Build params: subquery customer_id, then code variants, then outer customer_id
        params = [customer_id]
        for std_code, variants in BIOMARKER_CODE_MAP.items():
            for v in variants:
                params.append(v)
        params.append(customer_id)

        rows = self._query_all(sql, tuple(params))
        result = {}
        for row in rows:
            std_code = _CODE_REVERSE_MAP.get(row["code"].lower())
            if not std_code:
                continue
            check_date = row.get("check_date")
            if isinstance(check_date, str):
                check_date = date.fromisoformat(check_date[:10])
            result[std_code] = {
                "value": float(row["value"]),
                "unit": row.get("unit", ""),
                "date": check_date,
            }
        return result

    def get_bp_records(self, customer_id: int, days: int = 7) -> list[dict]:
        """获取血压记录。"""
        sql = """
            SELECT systolic_pressure AS sbp, diastolic_pressure AS dbp, time AS ts
            FROM device_bp_data
            WHERE customer_id = %s
              AND time >= DATE_SUB(NOW(), INTERVAL %s DAY)
              AND systolic_pressure BETWEEN 70 AND 220
              AND diastolic_pressure BETWEEN 40 AND 130
              AND (systolic_pressure - diastolic_pressure) >= 15
            ORDER BY time DESC
        """
        return self._query_all(sql, (customer_id, days))

    def get_latest_checkup_date(self, customer_id: int) -> date | None:
        sql = """
            SELECT MAX(check_date) AS latest_date
            FROM customer_reports
            WHERE customer_id = %s
        """
        row = self._query_one(sql, (customer_id,))
        if not row or not row.get("latest_date"):
            return None
        val = row["latest_date"]
        if isinstance(val, str):
            val = date.fromisoformat(val[:10])
        return val

    def _query_one(self, sql: str, params: tuple) -> dict | None:
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()
        finally:
            self._return_conn(conn)

    def _query_all(self, sql: str, params: tuple) -> list[dict]:
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            self._return_conn(conn)


def standardize_units(biomarkers: dict) -> dict:
    """单位标准化，返回标准单位下的 value。"""
    result = {}
    for code, info in biomarkers.items():
        val = info["value"]
        unit = info.get("unit", "").lower()

        if code == "albumin" and "dl" in unit:
            val = val * 10
        elif code == "creatinine" and "mg" in unit:
            val = val * 88.4
        elif code == "tc" and "mg" in unit:
            val = val / 38.67

        result[code] = val
    return result


def get_checkup_staleness(checkup_date: date) -> dict:
    """评估体检时效性。"""
    days = (date.today() - checkup_date).days
    if days <= 365:
        return {"level": "fresh", "weight": 1.0, "label": None}
    elif days <= 548:
        return {"level": "aging", "weight": 1.0, "label": f"体检数据已有 {days // 30} 个月"}
    elif days <= 730:
        return {"level": "stale", "weight": 0.7, "label": "体检数据较旧，结果置信度较低"}
    else:
        return {"level": "expired", "weight": 0.0, "label": "体检数据超过2年，无法计算"}


def collect_calculation_inputs(
    provider: BioageDataProvider,
    customer_id: int,
    param_version: str = "v2.0-draft",
) -> dict:
    """
    编排数据采集流程，返回 engine 所需的完整输入。

    返回:
        {"status": "ready", "inputs": {...}} 或 {"status": "missing", "readiness": {...}}
    """
    basic = provider.get_customer_basic(customer_id)
    if not basic or not basic.get("birthday"):
        return {"status": "missing", "reason": "缺少客户生日信息"}

    gender_int = basic["gender"]
    if gender_int not in (1, 2):
        return {"status": "missing", "reason": "性别信息不支持（需为男/女）"}
    gender = "male" if gender_int == 1 else "female"

    today = date.today()
    age = (today - basic["birthday"]).days / 365.25

    raw_biomarkers = provider.get_latest_biomarkers(customer_id)
    biomarkers = standardize_units(raw_biomarkers)

    checkup_date = provider.get_latest_checkup_date(customer_id)
    checkup_age_days = (today - checkup_date).days if checkup_date else None

    if checkup_date:
        staleness = get_checkup_staleness(checkup_date)
        if staleness["weight"] == 0.0:
            return {
                "status": "missing",
                "reason": staleness["label"],
                "checkup_date": checkup_date.isoformat(),
            }

    bp_records = provider.get_bp_records(customer_id, days=7)
    bp_window_days = 7

    from .bp_aggregator import aggregate_bp
    bp_data = aggregate_bp(bp_records)

    if not bp_data and len(bp_records) == 0:
        # 扩展到 30 天
        bp_records = provider.get_bp_records(customer_id, days=30)
        bp_data = aggregate_bp(bp_records)
        bp_window_days = 30

    from .engine import assess_readiness
    readiness = assess_readiness(biomarkers, bp_data)
    if not readiness["can_calculate"]:
        return {"status": "missing", "readiness": readiness}

    return {
        "status": "ready",
        "inputs": {
            "age": age,
            "gender": gender,
            "biomarkers": biomarkers,
            "sbp_mean": bp_data["sbp_mean"] if bp_data else None,
            "dbp_mean": bp_data["dbp_mean"] if bp_data else None,
            "param_version": param_version,
            "checkup_age_days": checkup_age_days,
            "bp_window_days": bp_window_days,
            "bp_record_count": bp_data["n_records"] if bp_data else 0,
            "customer_name": basic.get("name", ""),
            "checkup_date": checkup_date.isoformat() if checkup_date else None,
        },
        "readiness": readiness,
    }
