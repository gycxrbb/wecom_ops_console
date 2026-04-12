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
        with conn.cursor() as cur:
            cur.execute('''
                SELECT g.id, g.name,
                       COUNT(DISTINCT cg.customer_id) AS member_count,
                       COALESCE(SUM(c.points), 0)      AS points_sum,
                       COALESCE(SUM(c.total_points), 0) AS total_points_sum
                FROM groups g
                LEFT JOIN customer_groups cg ON cg.group_id = g.id
                LEFT JOIN customers c ON c.id = cg.customer_id
                GROUP BY g.id, g.name
                ORDER BY g.id
            ''')
            rows = cur.fetchall()

        groups = []
        for r in rows:
            mc = int(r.get('member_count', 0) or 0)
            ps = float(r.get('points_sum', 0) or 0)
            tps = float(r.get('total_points_sum', 0) or 0)
            groups.append({
                'id': r['id'],
                'name': r['name'],
                'member_count': mc,
                'points_sum': ps,
                'total_points_sum': tps,
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
    """返回指定外部群的成员列表（姓名、当前积分、累计积分）"""
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
            cur.execute('SELECT id, name FROM groups WHERE id = %s LIMIT 1', (group_id,))
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

        members = [{
            'id': r['id'],
            'name': r['name'],
            'points': float(r.get('points', 0) or 0),
            'total_points': float(r.get('total_points', 0) or 0),
        } for r in rows]

        result = {
            'available': True,
            'group_id': group_id,
            'group_name': grp['name'],
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


def fetch_crm_group_stats() -> dict[str, Any]:
    """全局统计：总群数、总客户数、总积分"""
    if not crm_group_enabled():
        return {'available': False, 'total_groups': 0, 'total_customers': 0, 'total_points': 0}

    cached = _get_cached('crm_stats')
    if cached is not None:
        return cached

    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) AS cnt FROM groups')
            grp_count = cur.fetchone()['cnt']
            cur.execute('SELECT COUNT(*) AS cnt FROM customers')
            cust_count = cur.fetchone()['cnt']
            cur.execute('SELECT COALESCE(SUM(total_points), 0) AS s FROM customers')
            total_pts = float(cur.fetchone()['s'])

        result = {
            'available': True,
            'total_groups': grp_count,
            'total_customers': cust_count,
            'total_points': total_pts,
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
