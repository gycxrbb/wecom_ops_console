from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import BASE_DIR, settings


def _resolve_database_ssl_ca(raw_path: str | None) -> str | None:
    """Resolve a CA file path for the business DB's SSL connection.

    与 ``app.clients.crm_db`` 的解析规则一致：
    - 空字符串/None → 返回 None（无 SSL）
    - 相对路径 → 基于 ``BASE_DIR`` 解析
    - 目录 → 优先取 ``rds-ca.pem``，否则第一个 ``*.pem``
    - 文件 → 原样返回
    - 路径不存在 → 抛 ``RuntimeError``，让 engine 创建失败，应用 fail-fast
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
        raise RuntimeError(f"DATABASE_SSL_PATH 目录下找不到 .pem 文件: {path}")

    if path.is_file():
        return str(path)

    raise RuntimeError(f"DATABASE_SSL_PATH 指向的证书不存在: {path}")


def _build_connect_args(database_url: str) -> dict:
    if database_url.startswith('sqlite'):
        return {'check_same_thread': False}

    args: dict = {}
    ca_path = _resolve_database_ssl_ca(settings.database_ssl_path)
    if ca_path:
        # PyMySQL 接受字典形式 ssl，等价于 mysql CLI 的 --ssl-ca。
        # SQLAlchemy 会把整个 connect_args 透传给 DBAPI 的 connect()。
        args['ssl'] = {'ca': ca_path}
    return args


connect_args = _build_connect_args(settings.database_url)
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
