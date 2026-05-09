"""Customer list, search, and filter endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ...database import get_db
from ...route_helper import UnifiedResponseRoute
from ...security import get_current_user, require_permission
from ..schemas.api import (
    CustomerSearchItem, CustomerListWithFiltersResponse, FilterOptionsResponse,
)
from ..services.cache import get as cache_get, put as cache_put, FILTER_OPTIONS_TTL
from ..services.permission import resolve_visible_customers

router = APIRouter(route_class=UnifiedResponseRoute)


def _load_filter_options(conn) -> dict:
    """Shared helper: load coaches / groups / channels dropdown options."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, COALESCE(real_name, nick_name, username) AS label "
            "FROM admins ORDER BY id"
        )
        coaches = [{"value": r["id"], "label": r["label"] or f"Admin#{r['id']}"} for r in cur.fetchall()]

    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM `groups` ORDER BY id DESC")
        groups = [{"value": r["id"], "label": r["name"] or f"Group#{r['id']}"} for r in cur.fetchall()]

    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM channels WHERE is_del = 0 OR is_del IS NULL ORDER BY id")
        channels = [{"value": r["id"], "label": r["name"] or f"Channel#{r['id']}"} for r in cur.fetchall()]

    return {"coaches": coaches, "groups": groups, "channels": channels}


@router.get("/filters", response_model=FilterOptionsResponse)
def get_filter_options(
    request: Request,
    db: Session = Depends(get_db),
):
    """Return available filter options: coaches, groups, channels."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    from ...clients.crm_db import get_connection, return_connection

    cached = cache_get("filter_options")
    if cached:
        return cached

    conn = get_connection()
    try:
        result = _load_filter_options(conn)
        cache_put("filter_options", result, FILTER_OPTIONS_TTL)
        return result
    finally:
        return_connection(conn)


@router.get("/list", response_model=CustomerListWithFiltersResponse)
def list_customers(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str = Query("", max_length=100),
    coach_id: int | None = Query(None),
    group_id: int | None = Query(None),
    channel_id: int | None = Query(None),
    include_filters: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Paginated customer list with optional filters."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    from ...clients.crm_db import get_connection, return_connection

    list_cache_key = f"list:{user.id}:{page}:{page_size}:{q}:{coach_id}:{group_id}:{channel_id}:{include_filters}"
    cached = cache_get(list_cache_key)
    if cached:
        return cached

    conn = get_connection()
    try:
        visible = resolve_visible_customers(user)

        wheres: list[str] = []
        where_params: list = []
        joins: list[str] = []
        join_params: list = []

        if coach_id is not None:
            joins.append(
                "JOIN customer_staff cs_f ON cs_f.customer_id = c.id "
                "AND cs_f.admin_id = %s AND (cs_f.end_at IS NULL OR cs_f.end_at > NOW())"
            )
            join_params.append(coach_id)

        if group_id is not None:
            joins.append(
                "JOIN customer_groups cg_f ON cg_f.customer_id = c.id AND cg_f.group_id = %s"
            )
            join_params.append(group_id)

        if q.strip():
            wheres.append("c.name LIKE %s")
            where_params.append(f"%{q.strip()}%")

        if visible:
            placeholders = ",".join(["%s"] * len(visible))
            wheres.append(f"c.id IN ({placeholders})")
            where_params.extend(visible)

        if channel_id is not None:
            wheres.append("c.channel_id = %s")
            where_params.append(channel_id)

        join_clause = " ".join(joins)
        where_clause = (" WHERE " + " AND ".join(wheres)) if wheres else ""
        params = join_params + where_params

        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(DISTINCT c.id) AS cnt FROM customers c {join_clause}{where_clause}",
                params,
            )
            total = cur.fetchone()["cnt"]

        offset = (page - 1) * page_size
        data_params = list(params)
        data_sql = f"""
            SELECT c.id, c.name, c.gender, c.birthday, c.points, c.total_points,
                   c.status, c.city, c.created_at, c.channel_id,
                   ch.name AS channel_name,
                   (SELECT GROUP_CONCAT(
                       COALESCE(a.real_name, a.nick_name, a.username) SEPARATOR '、'
                    ) FROM customer_staff cs
                      JOIN admins a ON a.id = cs.admin_id
                     WHERE cs.customer_id = c.id
                       AND (cs.end_at IS NULL OR cs.end_at > NOW())
                   ) AS coach_names,
                   (SELECT GROUP_CONCAT(g.name SEPARATOR '、')
                      FROM customer_groups cg
                      JOIN `groups` g ON g.id = cg.group_id
                     WHERE cg.customer_id = c.id
                   ) AS group_names
            FROM customers c
            LEFT JOIN channels ch ON ch.id = c.channel_id
            {join_clause}
            {where_clause}
            GROUP BY c.id
            ORDER BY (
                (c.gender IS NOT NULL) +
                (c.birthday IS NOT NULL) +
                (c.channel_id IS NOT NULL) +
                (COALESCE(c.points, 0) > 0) +
                (c.city IS NOT NULL AND c.city != '') +
                (EXISTS(SELECT 1 FROM customer_staff cs2
                        WHERE cs2.customer_id = c.id
                          AND (cs2.end_at IS NULL OR cs2.end_at > NOW()))) +
                (EXISTS(SELECT 1 FROM customer_groups cg2
                        WHERE cg2.customer_id = c.id))
            ) DESC, c.id DESC
            LIMIT %s OFFSET %s
        """
        data_params.extend([page_size, offset])

        with conn.cursor() as cur:
            cur.execute(data_sql, data_params)
            rows = cur.fetchall()

        items = []
        for r in rows:
            item = dict(r)
            if item.get("birthday"):
                item["birthday"] = str(item["birthday"])
            if item.get("created_at"):
                item["created_at"] = str(item["created_at"])
            items.append(item)

        result: dict = {"items": items, "total": total, "page": page, "page_size": page_size}

        if include_filters:
            cached_filters = cache_get("filter_options")
            if cached_filters:
                result["filters"] = cached_filters
            else:
                fo = _load_filter_options(conn)
                cache_put("filter_options", fo, FILTER_OPTIONS_TTL)
                result["filters"] = fo

        cache_put(list_cache_key, result, 60)
        return result
    finally:
        return_connection(conn)


@router.get("/search", response_model=list[CustomerSearchItem])
def search_customers(
    request: Request,
    q: str = Query("", max_length=100),
    db: Session = Depends(get_db),
):
    """Fuzzy search customers by name. Admin sees all; coach sees only assigned."""
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')
    from ...clients.crm_db import get_connection, return_connection

    conn = get_connection()
    try:
        like = f"%{q}%"
        visible = resolve_visible_customers(user)

        with conn.cursor() as cur:
            if visible:
                placeholders = ",".join(["%s"] * len(visible))
                cur.execute(
                    f"""
                    SELECT id, name, gender, birthday, points, total_points, status
                    FROM customers
                    WHERE name LIKE %s
                      AND id IN ({placeholders})
                    ORDER BY id DESC
                    LIMIT 50
                    """,
                    (like, *visible),
                )
            else:
                cur.execute(
                    """
                    SELECT id, name, gender, birthday, points, total_points, status
                    FROM customers
                    WHERE name LIKE %s
                    ORDER BY id DESC
                    LIMIT 50
                    """,
                    (like,),
                )
            rows = cur.fetchall()

        results = []
        for r in rows:
            item = dict(r)
            if item.get("birthday"):
                item["birthday"] = str(item["birthday"])
            results.append(item)
        return results
    finally:
        return_connection(conn)
