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
from pathlib import Path
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from ..config import BASE_DIR, settings
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
        ssl_path = settings.crm_prod_db_ssl_path
    else:
        host = settings.crm_test_db_host
        port = settings.crm_test_db_port
        user = settings.crm_test_db_user
        password = settings.crm_test_db_password
        name = settings.crm_test_db_name
        ssl_path = settings.crm_test_db_ssl_path

    fallback_used = False
    if not host:
        # Legacy single-set config still in effect
        host = settings.crm_admin_db_host
        port = settings.crm_admin_db_port
        user = settings.crm_admin_db_user
        password = settings.crm_admin_db_password
        name = settings.crm_admin_db_name
        ssl_path = settings.crm_admin_db_ssl_path
        fallback_used = True

    if not ssl_path:
        ssl_path = settings.crm_admin_db_ssl_path

    return {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'database': name,
        'ssl_path': ssl_path,
        '_env': env,
        '_legacy_fallback': fallback_used,
    }


def _resolve_ssl_ca_path(raw_path: str | None) -> str | None:
    """Return a CA file path for PyMySQL ssl config.

    The env value may point to a pem file or to a directory containing Aliyun's
    RDS CA certificate. Directories prefer rds-ca.pem, then any *.pem.

    相对路径基于 ``BASE_DIR``（项目根）解析，这样无论 CWD 是何处都能稳定找到，
    比如本地 uvicorn 在项目根跑、Docker 容器 WORKDIR=/app、或 systemd 服务从 / 启动。
    绝对路径原样使用。
    """
    value = (raw_path or '').strip().strip('"').strip("'")
    if not value:
        return None

    path = Path(value)
    if not path.is_absolute():
        path = BASE_DIR / path

    if path.is_dir():
        preferred = path / 'rds-ca.pem'
        if preferred.is_file():
            return str(preferred)
        pem_files = sorted(path.glob('*.pem'))
        if pem_files:
            return str(pem_files[0])
        raise CrmAdminAuthUnavailable(f"CRM 数据库 SSL 证书目录未找到 .pem 文件: {path}")

    if path.is_file():
        return str(path)

    raise CrmAdminAuthUnavailable(f"CRM 数据库 SSL 证书路径不存在: {path}")


def _build_ssl_options(raw_path: str | None) -> dict[str, str]:
    ca_path = _resolve_ssl_ca_path(raw_path)
    if not ca_path:
        return {}
    return {'ssl_ca': ca_path}


def _log_params_once(params: dict[str, Any]) -> None:
    global _PARAMS_LOGGED
    if _PARAMS_LOGGED:
        return
    _PARAMS_LOGGED = True
    _log.info(
        "CRM DB initialized: env=%s, host=%s, database=%s, ssl=%s, legacy_fallback=%s",
        params.get('_env'), params.get('host'), params.get('database'),
        bool((params.get('ssl_path') or '').strip()),
        params.get('_legacy_fallback'),
    )


def _create_connection() -> pymysql.connections.Connection:
    params = _resolve_crm_db_params()
    _log_params_once(params)
    if not params['host']:
        raise CrmAdminAuthUnavailable(
            "CRM 数据库未配置：CRM_TEST_DB_HOST / CRM_PROD_DB_HOST / CRM_ADMIN_DB_HOST 全部为空"
        )
    ssl_options = _build_ssl_options(params.get('ssl_path'))
    connect_kwargs = {
        'host': params['host'],
        'port': params['port'],
        'user': params['user'],
        'password': params['password'],
        'database': params['database'],
        'charset': 'utf8mb4',
        'cursorclass': DictCursor,
        'connect_timeout': 10,
        'read_timeout': 30,
        'write_timeout': 10,
        **ssl_options,
    }
    try:
        return pymysql.connect(**connect_kwargs)
    except pymysql.err.OperationalError as exc:
        if ssl_options and exc.args and exc.args[0] == 1043:
            raise CrmAdminAuthUnavailable(
                "CRM 数据库 SSL 握手失败：请确认目标 RDS 已开启 SSL、"
                "CRM_*_DB_SSL_PATH 指向正确的 CA 证书，并且当前连接地址支持 SSL"
            ) from exc
        raise


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


def log_effective_env_at_startup() -> None:
    """在应用启动时主动打一次 CRM 环境日志，不等懒加载首连。

    用于 lifespan 启动阶段，让运维能立刻在 docker logs 里看到本次部署连到了哪个 CRM 库。
    """
    params = _resolve_crm_db_params()
    _log_params_once(params)
