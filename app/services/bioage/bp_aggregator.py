"""血压均值聚合处理。"""


def aggregate_bp(bp_records: list[dict]) -> dict | None:
    """
    从血压记录列表中计算代表性均值。

    bp_records 格式: [{"sbp": int, "dbp": int, "ts": str}, ...]
    策略：先剔除异常值，再按窗口优先级（7天→30天→90天→全部）选取。

    返回:
        {"sbp_mean": float, "dbp_mean": float, "n_records": int, "window_days": int}
        或 None（无有效记录时）
    """
    if not bp_records:
        return None

    valid = _filter_valid(bp_records)
    if not valid:
        return None

    # 按窗口优先级选取（7天→30天→90天→全部）
    for days in [7, 30, 90]:
        window = _filter_by_days(valid, days)
        if len(window) >= 3:
            return _compute_mean(window, days)

    # 不足 3 条则用全部有效记录
    if len(valid) < 1:
        return None

    return _compute_mean(valid, 0)


def _filter_valid(records: list[dict]) -> list[dict]:
    """剔除异常血压值。"""
    return [
        r for r in records
        if 70 <= r.get("sbp", 0) <= 220
        and 40 <= r.get("dbp", 0) <= 130
        and (r.get("sbp", 0) - r.get("dbp", 0)) >= 15
    ]


def _filter_by_days(records: list[dict], days: int) -> list[dict]:
    """按时间窗口过滤（简化版：基于记录序号，实际应由调用方传已过滤的数据）。"""
    # CRM 查询时已按日期范围过滤，此处按最近 N 条模拟
    # 实际 CRMDataProvider 中会直接用 SQL WHERE time >= DATE_SUB(NOW(), INTERVAL N DAY)
    return records[-days * 3:] if len(records) > days * 3 else records


def _compute_mean(records: list[dict], window_days: int) -> dict:
    """计算均值。"""
    sbp_sum = sum(r["sbp"] for r in records)
    dbp_sum = sum(r["dbp"] for r in records)
    n = len(records)
    return {
        "sbp_mean": round(sbp_sum / n, 1),
        "dbp_mean": round(dbp_sum / n, 1),
        "n_records": n,
        "window_days": window_days,
    }
