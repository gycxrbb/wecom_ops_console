"""Points & engagement (14-day) module — from point_logs + customers."""
from __future__ import annotations

import logging

from ...schemas.context import ModulePayload

_log = logging.getLogger(__name__)

MODULE_KEY = "points_engagement_14d"


def load(conn, customer_id: int) -> ModulePayload:
    # Current balance
    with conn.cursor() as cur:
        cur.execute(
            "SELECT points, total_points FROM customers WHERE id = %s",
            (customer_id,),
        )
        cust = cur.fetchone()

    if not cust:
        return ModulePayload(key=MODULE_KEY, status="empty", payload={})

    # 14-day logs
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT type, num, des, category, created_at
            FROM point_logs
            WHERE customer_id = %s
              AND created_at >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
            ORDER BY created_at DESC
            """,
            (customer_id,),
        )
        rows = cur.fetchall()

    earned = 0
    spent = 0
    active_dates: set[str] = set()
    category_counts: dict[str, int] = {}
    positive_events: list[dict] = []

    for r in rows:
        rec = dict(r)
        num = rec.get("num") or 0
        if rec.get("type") == 0:
            earned += num
            # Collect positive events (latest 10)
            if len(positive_events) < 10:
                positive_events.append({
                    "description": rec.get("des") or "",
                    "category": rec.get("category") or "",
                    "num": num,
                    "date": str(rec["created_at"])[:10] if rec.get("created_at") else "",
                })
        else:
            spent += num
        if rec.get("created_at"):
            active_dates.add(str(rec["created_at"])[:10])
        cat = rec.get("category") or "其他"
        category_counts[cat] = category_counts.get(cat, 0) + 1

    active_days = len(active_dates)

    # Build summary text
    parts = []
    if earned > 0:
        parts.append(f"获得{earned}积分")
    if spent > 0:
        parts.append(f"消费{spent}积分")
    if active_days > 0:
        parts.append(f"{active_days}天活跃")
    summary = "，".join(parts) if parts else "近14天无积分变动"

    return ModulePayload(
        key=MODULE_KEY,
        status="ok",
        payload={
            "points_current": cust.get("points", 0),
            "points_total": cust.get("total_points", 0),
            "earned_14d": earned,
            "spent_14d": spent,
            "active_days_14d": active_days,
            "activity_category_counts": category_counts if category_counts else None,
            "latest_positive_events": positive_events if positive_events else None,
            "summary": summary,
        },
        source_tables=["customers", "point_logs"],
        freshness="14d",
        warnings=[],
    )
