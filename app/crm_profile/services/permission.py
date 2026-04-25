"""Permission resolution for CRM customer visibility."""
from __future__ import annotations

import logging

from fastapi import HTTPException

from ...clients.crm_db import get_connection, return_connection
from ... import models

_log = logging.getLogger(__name__)

_MAX_VISIBLE = 50_000


def resolve_visible_customers(user: models.User) -> set[int]:
    """Return set of customer IDs the user can view.

    * admin  -> empty set (means *no filter*, i.e. can see all)
    * coach  -> query CRM; union of staff + group assignments
    * no crm_admin_id -> empty set (coach without CRM link sees nothing)
    """
    if user.role == "admin":
        return set()

    crm_admin_id = user.crm_admin_id
    if not crm_admin_id:
        return set()

    conn = get_connection()
    try:
        ids: set[int] = set()

        # A + B combined: direct staff + group-based in one UNION
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT customer_id FROM customer_staff
                WHERE admin_id = %s AND (end_at IS NULL OR end_at > NOW())
                UNION
                SELECT cg.customer_id
                FROM group_coachs gc
                JOIN customer_groups cg ON cg.group_id = gc.group_id
                WHERE gc.coach_id = %s AND (cg.end_at IS NULL OR cg.end_at > NOW())
                """,
                (crm_admin_id, crm_admin_id),
            )
            ids.update(row["customer_id"] for row in cur.fetchall())

        # Performance guard: if too many, return empty = no filter
        if len(ids) > _MAX_VISIBLE:
            _log.warning("Visible customers for admin_id=%s exceeds %d, skipping filter", crm_admin_id, _MAX_VISIBLE)
            return set()

        return ids
    except Exception:
        _log.exception("Failed to resolve visible customers for user %s", user.id)
        return set()
    finally:
        return_connection(conn)


def assert_can_view(user: models.User, customer_id: int) -> None:
    """Raise 403 if the user is not allowed to view *customer_id*."""
    if user.role == "admin":
        return
    visible = resolve_visible_customers(user)
    if not visible:
        raise HTTPException(status_code=403, detail="无权查看该客户")
    if customer_id not in visible:
        raise HTTPException(status_code=403, detail="无权查看该客户")
