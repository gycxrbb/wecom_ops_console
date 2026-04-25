"""Service scope module — groups, coaches, staff assignments."""
from __future__ import annotations

import logging

from ...schemas.context import ModulePayload

_log = logging.getLogger(__name__)

MODULE_KEY = "service_scope"


def load(conn, customer_id: int) -> ModulePayload:
    warnings: list[str] = []

    # A) Groups — customer_groups has no end_at; groups has no type
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT g.id, g.name
            FROM customer_groups cg
            JOIN `groups` g ON g.id = cg.group_id
            WHERE cg.customer_id = %s
            """,
            (customer_id,),
        )
        groups = [dict(r) for r in cur.fetchall()]

    # B) Staff / coaches (current — customer_staff has end_at)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT cs.admin_id, a.real_name, a.nick_name, cs.start_at, cs.end_at
            FROM customer_staff cs
            JOIN admins a ON a.id = cs.admin_id
            WHERE cs.customer_id = %s
              AND (cs.end_at IS NULL OR cs.end_at > NOW())
            """,
            (customer_id,),
        )
        staff = [dict(r) for r in cur.fetchall()]

    if not groups and not staff:
        return ModulePayload(key=MODULE_KEY, status="empty", payload={})

    group_names = "、".join(g["name"] for g in groups if g.get("name")) or None
    coach_names = "、".join(
        s.get("real_name") or s.get("nick_name") or f"教练{s.get('admin_id', '')}"
        for s in staff
    ) or None

    return ModulePayload(
        key=MODULE_KEY,
        status="ok",
        payload={
            "group_names": group_names,
            "group_count": len(groups),
            "current_coach_names": coach_names,
            "staff_count": len(staff),
        },
        source_tables=["customer_groups", "groups", "customer_staff", "admins"],
        freshness="today",
        warnings=warnings,
    )
