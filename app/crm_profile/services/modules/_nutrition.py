"""Nutrition aggregation from customer_health macro-nutrient fields."""
from __future__ import annotations

from typing import Any


def build_nutrition_summary(records: list[dict]) -> dict | None:
    """Aggregate nutrition fields from customer_health rows.

    Uses cho (carbs/g), fat (g), protein (g), fiber (g), kcal_out (consumption).
    These are already queried by HEALTH_SQL_COLUMNS.

    Returns dict with daily averages, or None if no data.
    """
    cho_list = [r["cho"] for r in records if r.get("cho") is not None]
    fat_list = [r["fat"] for r in records if r.get("fat") is not None]
    protein_list = [r["protein"] for r in records if r.get("protein") is not None]
    fiber_list = [r["fiber"] for r in records if r.get("fiber") is not None]
    kcal_list = [r["kcal"] for r in records if r.get("kcal") is not None]
    kcal_out_list = [r["kcal_out"] for r in records if r.get("kcal_out") is not None]

    if not any([cho_list, fat_list, protein_list, fiber_list, kcal_list, kcal_out_list]):
        return None

    result: dict[str, Any] = {"source": "customer_health"}
    if cho_list:
        result["cho_avg_g"] = int(round(sum(cho_list) / len(cho_list)))
    if fat_list:
        result["fat_avg_g"] = int(round(sum(fat_list) / len(fat_list)))
    if protein_list:
        result["protein_avg_g"] = int(round(sum(protein_list) / len(protein_list)))
    if fiber_list:
        result["fiber_avg_g"] = int(round(sum(fiber_list) / len(fiber_list)))
    if kcal_list:
        result["kcal_avg"] = int(round(sum(kcal_list) / len(kcal_list)))
    if kcal_out_list:
        result["kcal_out_avg"] = int(round(sum(kcal_out_list) / len(kcal_out_list)))

    return result
