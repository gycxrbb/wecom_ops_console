"""Raw SQL data fetchers for the health summary module."""
from __future__ import annotations

import logging

from ._health_summary_const import HEALTH_SQL_COLUMNS

_log = logging.getLogger(__name__)


def fetch_health_rows(conn, customer_id: int, window_days: int) -> list[dict]:
    """Query customer_health for *window_days* and return row dicts."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {HEALTH_SQL_COLUMNS}
            FROM customer_health
            WHERE customer_id = %s
              AND record_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            ORDER BY record_date ASC
            """,
            (customer_id, window_days),
        )
        rows = cur.fetchall()

    records = []
    for r in rows:
        rec = dict(r)
        if rec.get("record_date"):
            rec["record_date"] = str(rec["record_date"])
        records.append(rec)
    return records


def fetch_glucose_rows(conn, customer_id: int, window_days: int) -> list[dict]:
    """Query customer_glucose for *window_days*. Each row has ``date`` + ``points`` (JSON)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT date, points
            FROM customer_glucose
            WHERE customer_id = %s
              AND date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            ORDER BY date ASC
            """,
            (customer_id, window_days),
        )
        rows = cur.fetchall()

    result = []
    for r in rows:
        rec = dict(r)
        if rec.get("date"):
            rec["date"] = str(rec["date"])
        result.append(rec)
    return result


def fetch_last_record_dates(conn, customer_id: int) -> dict:
    """Return the most recent record_date from each table (any date, not windowed)."""
    result: dict[str, str | None] = {"health": None, "glucose": None}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT MAX(record_date) as d FROM customer_health WHERE customer_id = %s",
            (customer_id,),
        )
        row = cur.fetchone()
        if row and row.get("d"):
            result["health"] = str(row["d"])

        cur.execute(
            "SELECT MAX(date) as d FROM customer_glucose WHERE customer_id = %s",
            (customer_id,),
        )
        row = cur.fetchone()
        if row and row.get("d"):
            result["glucose"] = str(row["d"])
    return result
