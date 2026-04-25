"""共享 CRM 数据库连接池。

所有需要直连 CRM mfgcrmdb 的模块统一通过此模块获取连接，
避免各自维护独立的连接池。
"""
from __future__ import annotations

import logging
import threading

import pymysql
from pymysql.cursors import DictCursor

from ..config import settings
from ..services.crm_admin_auth import CrmAdminAuthUnavailable

_log = logging.getLogger(__name__)

_POOL_SIZE = 3
_POOL: list[pymysql.connections.Connection] = []
_POOL_LOCK = threading.Lock()


def _create_connection() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=settings.crm_admin_db_host,
        port=settings.crm_admin_db_port,
        user=settings.crm_admin_db_user,
        password=settings.crm_admin_db_password,
        database=settings.crm_admin_db_name,
        charset='utf8mb4',
        cursorclass=DictCursor,
        connect_timeout=10,
        read_timeout=30,
        write_timeout=10,
    )


def get_connection() -> pymysql.connections.Connection:
    try:
        with _POOL_LOCK:
            if _POOL:
                conn = _POOL.pop()
                try:
                    conn.ping(reconnect=True)
                    return conn
                except Exception:
                    try:
                        return_connection(conn)
                    except Exception:
                        pass
        return _create_connection()
    except Exception as exc:
        _log.warning('CRM 数据库连接失败: %s', exc)
        raise CrmAdminAuthUnavailable(str(exc)) from exc


def return_connection(conn: pymysql.connections.Connection) -> None:
    try:
        conn.rollback()
        with _POOL_LOCK:
            if len(_POOL) < _POOL_SIZE:
                _POOL.append(conn)
                return
    except Exception:
        pass
    try:
        conn.close()
    except Exception:
        pass
