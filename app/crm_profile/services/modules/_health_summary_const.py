"""Constants and thresholds for the health summary module."""
from __future__ import annotations

MODULE_KEY = "health_summary_7d"  # kept for backward compat; real window read from payload.window_days

VALID_WINDOWS = (7, 14, 30)

# Blood glucose thresholds (mmol/L)
GLUCOSE_HIGH_THRESHOLD = 10.0
GLUCOSE_LOW_THRESHOLD = 3.9

# Daily water target (ml)
WATER_TARGET_ML = 2000

# customer_health.weight is stored x100 (6500 → 65.0 kg)
WEIGHT_DIVISOR = 100

# SQL columns for customer_health — base set + meal/water columns
HEALTH_SQL_COLUMNS = """record_date, weight, blood_sbp, blood_dbp,
       fbs, pbs, hba1c, water_ml, sleep_min, sleep_des,
       step_count, symptoms, kcal, cho, fat, protein,
       fiber, kcal_out, stress, medication,
       breakfast_data, lunch_data, dinner_data, snack_data"""


def clamp_window(days: int) -> int:
    """Return *days* if it is a valid window, else 7."""
    return days if days in VALID_WINDOWS else 7
