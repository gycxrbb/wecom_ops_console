"""共享 CRM 数据库连接池。

所有需要直连 CRM 业务库（mfgcrmdb / habitilitydb）的模块统一通过此模块获取连接，
避免各自维护独立的连接池。

环境隔离规则（按优先级）：
1. `settings.crm_env` 显式指定 'test' 或 'production'，按显式值选择
2. 否则按 `settings.app_env`：production → 生产 CRM，其他（development/test）→ 测试 CRM
3. 若所选环境的 host 为空，**回退到旧字段 `crm_admin_db_*`**（向后兼容旧 .env）

这样：
- 新服务器 .env 设 `APP_ENV=production` + `CRM_PROD_DB_*` → 走 habitilitydb
- 本地/旧服务器 .env 设 `APP_ENV=development` + `CRM_TEST_DB_*` → 走 mfgcrmdb
- 仍在用旧版 .env（只填了 `CRM_ADMIN_DB_*`）的部署不需要立刻改
"""
from __future__ import annotations

import logging
import threading
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from ..config import settings
from ..services.crm_admin_auth import CrmAdminAuthUnavailable

_log = logging.getLogger(__name__)

_POOL_SIZE = 3
_POOL: list[pymysql.connections.Connection] = []
_POOL_LOCK = threading.Lock()
_PARAMS_LOGGED = False


def _resolve_crm_env() -> str:
    """Decide which CRM database to use: 'production' or 'test'."""
    explicit = (settings.crm_env or '').strip().lower()
    if explicit in {'production', 'prod'}:
        return 'production'
    if explicit in {'test', 'testing', 'development', 'dev'}:
        return 'test'
    # Follow app_env
    return 'production' if (settings.app_env or '').strip().lower() == 'production' else 'test'


def _resolve_crm_db_params() -> dict[str, Any]:
    """Pick CRM DB connection params based on environment, with legacy fallback."""
    env = _resolve_crm_env()
    if env == 'production':
        host = settings.crm_prod_db_host
        port = settings.crm_prod_db_port
        user = settings.crm_prod_db_user
        password = settings.crm_prod_db_password
        name = settings.crm_prod_db_name
    else:
        host = settings.crm_test_db_host
        port = settings.crm_test_db_port
        user = settings.crm_test_db_user
        password = settings.crm_test_db_password
        name = settings.crm_test_db_name

    fallback_used = False
    if not host:
        # Legacy single-set config still in effect
        host = settings.crm_admin_db_host
        port = settings.crm_admin_db_port
        user = settings.crm_admin_db_user
        password = settings.crm_admin_db_password
        name = settings.crm_admin_db_name
        fallback_used = True

    return {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'database': name,
        '_env': env,
        '_legacy_fallback': fallback_used,
    }


def _log_params_once(params: dict[str, Any]) -> None:
    global _PARAMS_LOGGED
    if _PARAMS_LOGGED:
        return
    _PARAMS_LOGGED = True
    _log.info(
        "CRM DB initialized: env=%s, host=%s, database=%s, legacy_fallback=%s",
        params.get('_env'), params.get('host'), params.get('database'),
        params.get('_legacy_fallback'),
    )


def _create_connection() -> pymysql.connections.Connection:
    params = _resolve_crm_db_params()
    _log_params_once(params)
    if not params['host']:
        raise CrmAdminAuthUnavailable(
            "CRM 数据库未配置：CRM_TEST_DB_HOST / CRM_PROD_DB_HOST / CRM_ADMIN_DB_HOST 全部为空"
        )
    return pymysql.connect(
        host=params['host'],
        port=params['port'],
        user=params['user'],
        password=params['password'],
        database=params['database'],
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
    except CrmAdminAuthUnavailable:
        raise
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


def current_crm_env() -> str:
    """Public helper: return the effective CRM env name ('production' / 'test')."""
    return _resolve_crm_env()
