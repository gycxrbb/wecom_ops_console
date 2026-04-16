"""CRM 外部群只读聚合查询服务

数据来源：CRM 库 mfgcrmdb.groups / customer_groups / customers
仅读取，不写入。返回结果带 2 分钟内存缓存。
"""
from __future__ import annotations

import logging
import time
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from ..config import settings
from .crm_admin_auth import CrmAdminAuthUnavailable

_log = logging.getLogger(__name__)

_CACHE_TTL = 120  # 2 分钟
_cache: dict[str, tuple[Any, float]] = {}
_indexes_ensured = False


def _get_cached(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry and (time.time() - entry[1]) < _CACHE_TTL:
        return entry[0]
    return None


def _set_cached(key: str, data: Any) -> None:
    _cache[key] = (data, time.time())


def clear_cache() -> None:
    _cache.clear()


def crm_group_enabled() -> bool:
    """CRM 外部群查询是否可用（复用 CRM 认证的同一套配置）"""
    return bool(
        settings.crm_admin_auth_enabled
        and settings.crm_admin_db_host
        and settings.crm_admin_db_user
        and settings.crm_admin_db_name
    )


def _get_connection() -> pymysql.connections.Connection:
    try:
        return pymysql.connect(
            host=settings.crm_admin_db_host,
            port=settings.crm_admin_db_port,
            user=settings.crm_admin_db_user,
            password=settings.crm_admin_db_password,
            database=settings.crm_admin_db_name,
            charset='utf8mb4',
            cursorclass=DictCursor,
            connect_timeout=5,
            read_timeout=5,
            write_timeout=5,
        )
    except Exception as exc:
        _log.warning('CRM 数据库连接失败: %s', exc)
        raise CrmAdminAuthUnavailable(str(exc)) from exc


def _ensure_indexes(conn) -> None:
    """检查并创建 CRM 表必要索引（幂等，仅首次连接时执行）

    MySQL 5.x 不支持 CREATE INDEX IF NOT EXISTS，改用先查后建。
    """
    global _indexes_ensured
    if _indexes_ensured:
        return

    desired = {
        'customer_groups': [
            ('ix_cg_group_id', 'group_id'),
            ('ix_cg_customer_id', 'customer_id'),
        ],
        'customers': [
            ('ix_customers_total_points', 'total_points'),
        ],
        'point_logs': [
            ('ix_pl_customer_created', 'customer_id, created_at'),
        ],
    }

    with conn.cursor() as cur:
        for table, idx_list in desired.items():
            try:
                cur.execute(
                    "SELECT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
                    "AND INDEX_NAME != 'PRIMARY'",
                    (table,)
                )
                existing = {r['INDEX_NAME'] for r in cur.fetchall()}
            except Exception as exc:
                _log.warning('CRM 索引检查跳过 (%s): %s', table, exc)
                continue

            for idx_name, column in idx_list:
                if idx_name in existing:
                    continue
                try:
                    cur.execute(
                        f'ALTER TABLE `{table}` ADD INDEX `{idx_name}` (`{column}`)'
                    )
                    _log.info('CRM 索引已创建: %s on %s(%s)', idx_name, table, column)
                except Exception as exc:
                    _log.warning('CRM 索引创建跳过: %s', exc)

    try:
        conn.commit()
    except Exception:
        pass
    _indexes_ensured = True
    _log.info('CRM 索引检查完成')


def _enrich_with_period_points(
    result: dict[str, Any],
    group_ids: list[int] | None = None,
    customer_ids: list[int] | None = None,
) -> None:
    """为结果注入 week_points / month_points 指标（就地修改 result）。"""
    try:
        from .crm_points_metrics import (
            get_week_range, get_month_range,
            fetch_customer_period_points, fetch_group_period_points,
        )
    except Exception as exc:
        _log.warning('积分指标模块导入失败，跳过周期积分: %s', exc)
        return

    try:
        week_start, week_end = get_week_range()
        month_start, month_end = get_month_range()

        if group_ids:
            week_grp = fetch_group_period_points(group_ids, week_start, week_end)
            month_grp = fetch_group_period_points(group_ids, month_start, month_end)
            result['_week_group_points'] = week_grp
            result['_month_group_points'] = month_grp

        if customer_ids:
            week_cust = fetch_customer_period_points(customer_ids, week_start, week_end)
            month_cust = fetch_customer_period_points(customer_ids, month_start, month_end)
            result['_week_customer_points'] = week_cust
            result['_month_customer_points'] = month_cust
    except Exception as exc:
        _log.warning('积分周期指标查询失败，跳过: %s', exc)


def fetch_crm_groups() -> dict[str, Any]:
    """返回所有外部群列表 + 成员数 + 积分汇总"""
    if not crm_group_enabled():
        return {'available': False, 'groups': []}

    cached = _get_cached('crm_groups')
    if cached is not None:
        return cached

    conn = None
    try:
        conn = _get_connection()
        _ensure_indexes(conn)
        with conn.cursor() as cur:
            cur.execute('''
                SELECT g.id, g.name,
                       COUNT(DISTINCT cg.customer_id) AS member_count,
                       COALESCE(SUM(c.points), 0)      AS points_sum,
                       COALESCE(SUM(c.total_points), 0) AS total_points_sum
                FROM `groups` g
                LEFT JOIN customer_groups cg ON cg.group_id = g.id
                LEFT JOIN customers c ON c.id = cg.customer_id
                GROUP BY g.id, g.name
                ORDER BY g.id
            ''')
            rows = cur.fetchall()

        group_ids = [r['id'] for r in rows]
        enrich = {}
        _enrich_with_period_points(enrich, group_ids=group_ids)
        week_grp = enrich.get('_week_group_points', {})
        month_grp = enrich.get('_month_group_points', {})

        groups = []
        for r in rows:
            mc = int(r.get('member_count', 0) or 0)
            ps = float(r.get('points_sum', 0) or 0)
            tps = float(r.get('total_points_sum', 0) or 0)
            groups.append({
                'id': r['id'],
                'name': r['name'] or f'未命名群组#{r["id"]}',
                'member_count': mc,
                'points_sum': ps,
                'total_points_sum': tps,
                'current_points_sum': tps,
                'week_points_sum': week_grp.get(r['id'], 0.0),
                'month_points_sum': month_grp.get(r['id'], 0.0),
                'avg_points': round(ps / mc, 1) if mc > 0 else 0,
            })
        result = {'available': True, 'groups': groups}
        _set_cached('crm_groups', result)
        return result
    except CrmAdminAuthUnavailable:
        return {'available': False, 'groups': []}
    except Exception as exc:
        _log.warning('CRM 外部群查询失败: %s', exc)
        return {'available': False, 'groups': []}
    finally:
        if conn:
            conn.close()


def fetch_crm_group_members(group_id: int) -> dict[str, Any]:
    """返回指定外部群的成员列表（姓名、当前积分、累计积分、周/月积分）"""
    if not crm_group_enabled():
        return {'available': False, 'members': []}

    cache_key = f'crm_members_{group_id}'
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            # 群名
            cur.execute('SELECT id, name FROM `groups` WHERE id = %s LIMIT 1', (group_id,))
            grp = cur.fetchone()
            if not grp:
                return {'available': True, 'group_id': group_id, 'group_name': '', 'members': []}

            # 成员
            cur.execute('''
                SELECT c.id, c.name, c.points, c.total_points
                FROM customers c
                INNER JOIN customer_groups cg ON cg.customer_id = c.id
                WHERE cg.group_id = %s
                ORDER BY c.total_points DESC, c.name
            ''', (group_id,))
            rows = cur.fetchall()

        customer_ids = [r['id'] for r in rows]
        enrich = {}
        _enrich_with_period_points(enrich, customer_ids=customer_ids)
        week_cust = enrich.get('_week_customer_points', {})
        month_cust = enrich.get('_month_customer_points', {})

        members = [{
            'id': r['id'],
            'name': r['name'] or f'未命名成员#{r["id"]}',
            'points': float(r.get('points', 0) or 0),
            'total_points': float(r.get('total_points', 0) or 0),
            'current_points': float(r.get('total_points', 0) or 0),
            'week_points': week_cust.get(r['id'], 0.0),
            'month_points': month_cust.get(r['id'], 0.0),
        } for r in rows]

        result = {
            'available': True,
            'group_id': group_id,
            'group_name': grp['name'] or f'未命名群组#{group_id}',
            'members': members,
        }
        _set_cached(cache_key, result)
        return result
    except CrmAdminAuthUnavailable:
        return {'available': False, 'members': []}
    except Exception as exc:
        _log.warning('CRM 外部群成员查询失败: %s', exc)
        return {'available': False, 'members': []}
    finally:
        if conn:
            conn.close()


def fetch_crm_individual_leaderboard(
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """个人积分榜单（按累计积分降序），带分页，标注所属群组"""
    if not crm_group_enabled():
        return {'available': False, 'list': [], 'pagination': {'page': page, 'page_size': page_size, 'total': 0}}

    cache_key = f'crm_lb_ind_{page}_{page_size}'
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) AS cnt FROM customers')
            total = int(cur.fetchone()['cnt'])

            offset = (page - 1) * page_size
            cur.execute('''
                SELECT c.id, c.name, c.points, c.total_points,
                       GROUP_CONCAT(g.name SEPARATOR '、') AS group_names
                FROM customers c
                LEFT JOIN customer_groups cg ON cg.customer_id = c.id
                LEFT JOIN `groups` g ON g.id = cg.group_id
                GROUP BY c.id, c.name, c.points, c.total_points
                ORDER BY c.total_points DESC, c.name
                LIMIT %s OFFSET %s
            ''', (page_size, offset))
            rows = cur.fetchall()

        customer_ids = [r['id'] for r in rows]
        enrich = {}
        _enrich_with_period_points(enrich, customer_ids=customer_ids)
        week_cust = enrich.get('_week_customer_points', {})
        month_cust = enrich.get('_month_customer_points', {})

        items = []
        for idx, r in enumerate(rows):
            tp = float(r.get('total_points', 0) or 0)
            items.append({
                'id': r['id'],
                'name': r['name'] or f'未命名成员#{r["id"]}',
                'points': float(r.get('points', 0) or 0),
                'total_points': tp,
                'current_points': tp,
                'week_points': week_cust.get(r['id'], 0.0),
                'month_points': month_cust.get(r['id'], 0.0),
                'group_names': r.get('group_names') or '',
                'rank': offset + idx + 1,
            })

        result = {
            'available': True,
            'list': items,
            'pagination': {'page': page, 'page_size': page_size, 'total': total},
        }
        _set_cached(cache_key, result)
        return result
    except CrmAdminAuthUnavailable:
        return {'available': False, 'list': [], 'pagination': {'page': page, 'page_size': page_size, 'total': 0}}
    except Exception as exc:
        _log.warning('CRM 个人榜单查询失败: %s', exc)
        return {'available': False, 'list': [], 'pagination': {'page': page, 'page_size': page_size, 'total': 0}}
    finally:
        if conn:
            conn.close()


def fetch_crm_group_leaderboard(
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """群组积分榜单（按累计总积分降序），带分页"""
    if not crm_group_enabled():
        return {'available': False, 'list': [], 'pagination': {'page': page, 'page_size': page_size, 'total': 0}}

    cache_key = f'crm_lb_grp_{page}_{page_size}'
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) AS cnt FROM `groups`')
            total = int(cur.fetchone()['cnt'])

            offset = (page - 1) * page_size
            cur.execute('''
                SELECT g.id, g.name,
                       COUNT(DISTINCT cg.customer_id) AS member_count,
                       COALESCE(SUM(c.points), 0)      AS points_sum,
                       COALESCE(SUM(c.total_points), 0) AS total_points_sum
                FROM `groups` g
                LEFT JOIN customer_groups cg ON cg.group_id = g.id
                LEFT JOIN customers c ON c.id = cg.customer_id
                GROUP BY g.id, g.name
                ORDER BY total_points_sum DESC, g.name
                LIMIT %s OFFSET %s
            ''', (page_size, offset))
            rows = cur.fetchall()

        group_ids = [r['id'] for r in rows]
        enrich = {}
        _enrich_with_period_points(enrich, group_ids=group_ids)
        week_grp = enrich.get('_week_group_points', {})
        month_grp = enrich.get('_month_group_points', {})

        items = []
        for idx, r in enumerate(rows):
            mc = int(r.get('member_count', 0) or 0)
            ps = float(r.get('points_sum', 0) or 0)
            tps = float(r.get('total_points_sum', 0) or 0)
            items.append({
                'id': r['id'],
                'name': r['name'] or f'未命名群组#{r["id"]}',
                'member_count': mc,
                'points_sum': ps,
                'total_points_sum': tps,
                'current_points_sum': tps,
                'week_points_sum': week_grp.get(r['id'], 0.0),
                'month_points_sum': month_grp.get(r['id'], 0.0),
                'avg_points': round(ps / mc, 1) if mc > 0 else 0,
                'rank': offset + idx + 1,
            })

        result = {
            'available': True,
            'list': items,
            'pagination': {'page': page, 'page_size': page_size, 'total': total},
        }
        _set_cached(cache_key, result)
        return result
    except CrmAdminAuthUnavailable:
        return {'available': False, 'list': [], 'pagination': {'page': page, 'page_size': page_size, 'total': 0}}
    except Exception as exc:
        _log.warning('CRM 群组榜单查询失败: %s', exc)
        return {'available': False, 'list': [], 'pagination': {'page': page, 'page_size': page_size, 'total': 0}}
    finally:
        if conn:
            conn.close()


def fetch_crm_group_stats() -> dict[str, Any]:
    """全局统计：总群数、总客户数、总积分、周/月总积分"""
    if not crm_group_enabled():
        return {'available': False, 'total_groups': 0, 'total_customers': 0, 'total_points': 0}

    cached = _get_cached('crm_stats')
    if cached is not None:
        return cached

    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) AS cnt FROM `groups`')
            grp_count = cur.fetchone()['cnt']
            cur.execute('SELECT COUNT(*) AS cnt FROM customers')
            cust_count = cur.fetchone()['cnt']
            cur.execute('SELECT COALESCE(SUM(total_points), 0) AS s FROM customers')
            total_pts = float(cur.fetchone()['s'])

        # 查询全局周/月积分（所有客户）
        total_week = 0.0
        total_month = 0.0
        try:
            from .crm_points_metrics import get_week_range, get_month_range, fetch_customer_period_points
            week_start, week_end = get_week_range()
            month_start, month_end = get_month_range()
            # 获取所有客户 ID
            with conn.cursor() as cur:
                cur.execute('SELECT id FROM customers')
                all_ids = [r['id'] for r in cur.fetchall()]
            if all_ids:
                week_map = fetch_customer_period_points(all_ids, week_start, week_end)
                month_map = fetch_customer_period_points(all_ids, month_start, month_end)
                total_week = sum(week_map.values())
                total_month = sum(month_map.values())
        except Exception as exc:
            _log.warning('CRM 全局周期积分查询失败，跳过: %s', exc)

        result = {
            'available': True,
            'total_groups': grp_count,
            'total_customers': cust_count,
            'total_points': total_pts,
            'total_week_points': round(total_week, 2),
            'total_month_points': round(total_month, 2),
        }
        _set_cached('crm_stats', result)
        return result
    except CrmAdminAuthUnavailable:
        return {'available': False, 'total_groups': 0, 'total_customers': 0, 'total_points': 0}
    except Exception as exc:
        _log.warning('CRM 统计查询失败: %s', exc)
        return {'available': False, 'total_groups': 0, 'total_customers': 0, 'total_points': 0}
    finally:
        if conn:
            conn.close()


def search_crm_customers(query: str, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    """按用户名模糊搜索客户，返回匹配的用户及其所属群组"""
    if not crm_group_enabled():
        return {'available': False, 'list': [], 'pagination': {'page': page, 'page_size': page_size, 'total': 0}}

    if not query or not query.strip():
        return {'available': True, 'list': [], 'pagination': {'page': page, 'page_size': page_size, 'total': 0}}

    pattern = f'%{query.strip()}%'
    cache_key = f'crm_search_{query.strip()}_{page}_{page_size}'
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                'SELECT COUNT(*) AS cnt FROM customers c WHERE c.name LIKE %s',
                (pattern,)
            )
            total = int(cur.fetchone()['cnt'])

            offset = (page - 1) * page_size
            cur.execute('''
                SELECT c.id, c.name, c.points, c.total_points,
                       GROUP_CONCAT(g.name SEPARATOR '、') AS group_names
                FROM customers c
                LEFT JOIN customer_groups cg ON cg.customer_id = c.id
                LEFT JOIN `groups` g ON g.id = cg.group_id
                WHERE c.name LIKE %s
                GROUP BY c.id, c.name, c.points, c.total_points
                ORDER BY c.total_points DESC
                LIMIT %s OFFSET %s
            ''', (pattern, page_size, offset))
            rows = cur.fetchall()

        customer_ids = [r['id'] for r in rows]
        enrich = {}
        _enrich_with_period_points(enrich, customer_ids=customer_ids)
        week_cust = enrich.get('_week_customer_points', {})
        month_cust = enrich.get('_month_customer_points', {})

        items = [{
            'id': r['id'],
            'name': r['name'] or f'未命名成员#{r["id"]}',
            'points': float(r.get('points', 0) or 0),
            'total_points': float(r.get('total_points', 0) or 0),
            'current_points': float(r.get('total_points', 0) or 0),
            'week_points': week_cust.get(r['id'], 0.0),
            'month_points': month_cust.get(r['id'], 0.0),
            'group_names': r.get('group_names') or '',
        } for r in rows]

        result = {
            'available': True,
            'list': items,
            'pagination': {'page': page, 'page_size': page_size, 'total': total},
        }
        _set_cached(cache_key, result)
        return result
    except CrmAdminAuthUnavailable:
        return {'available': False, 'list': [], 'pagination': {'page': page, 'page_size': page_size, 'total': 0}}
    except Exception as exc:
        _log.warning('CRM 用户搜索失败: %s', exc)
        return {'available': False, 'list': [], 'pagination': {'page': page, 'page_size': page_size, 'total': 0}}
    finally:
        if conn:
            conn.close()
