from __future__ import annotations

import hashlib
import logging
import secrets
from typing import Any

import pymysql
from passlib.context import CryptContext
from pymysql.cursors import DictCursor
from sqlalchemy.orm import Session

from .. import models
from ..config import settings

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class CrmAdminAuthUnavailable(RuntimeError):
    pass


def crm_admin_auth_enabled() -> bool:
    return bool(
        settings.crm_admin_auth_enabled
        and settings.crm_admin_db_host
        and settings.crm_admin_db_user
        and settings.crm_admin_db_name
    )


def _candidate_hashes(password: str, salt: str) -> list[str]:
    md5_password = hashlib.md5(password.encode("utf-8")).hexdigest()
    sha1_password = hashlib.sha1(password.encode("utf-8")).hexdigest()
    return [
        hashlib.sha1(f"{password}{salt}".encode("utf-8")).hexdigest(),
        hashlib.sha1(f"{salt}{password}".encode("utf-8")).hexdigest(),
        hashlib.sha1(f"{md5_password}{salt}".encode("utf-8")).hexdigest(),
        hashlib.sha1(f"{salt}{md5_password}".encode("utf-8")).hexdigest(),
        hashlib.sha1(f"{sha1_password}{salt}".encode("utf-8")).hexdigest(),
        hashlib.sha1(password.encode("utf-8")).hexdigest(),
    ]


def _fetch_crm_admin(username: str) -> dict[str, Any] | None:
    try:
        connection = pymysql.connect(
            host=settings.crm_admin_db_host,
            port=settings.crm_admin_db_port,
            user=settings.crm_admin_db_user,
            password=settings.crm_admin_db_password,
            database=settings.crm_admin_db_name,
            charset="utf8mb4",
            cursorclass=DictCursor,
            connect_timeout=5,
            read_timeout=5,
            write_timeout=5,
        )
    except Exception as exc:  # pragma: no cover - depends on external db
        logger.exception("crm admin db connect failed")
        raise CrmAdminAuthUnavailable("CRM 用户库暂时不可用") from exc

    try:
        with connection.cursor() as cursor:
            sql = (
                f"SELECT id, username, password, salt, nick_name, real_name, status, type, wxwork "
                f"FROM {settings.crm_admin_table_name} WHERE username=%s LIMIT 1"
            )
            cursor.execute(sql, (username,))
            return cursor.fetchone()
    except Exception as exc:  # pragma: no cover - depends on external db
        logger.exception("crm admin query failed")
        raise CrmAdminAuthUnavailable("CRM 用户库查询失败") from exc
    finally:
        connection.close()


def authenticate_crm_admin(username: str, password: str) -> dict[str, Any] | None:
    if not crm_admin_auth_enabled():
        return None

    admin = _fetch_crm_admin(username)
    if not admin or int(admin.get("status") or 0) != 1:
        return None

    stored_password = str(admin.get("password") or "").strip().lower()
    salt = str(admin.get("salt") or "")
    if not stored_password:
        return None

    candidates = _candidate_hashes(password, salt)
    if stored_password not in candidates:
        return None
    return admin


def sync_crm_admin_to_local(db: Session, admin: dict[str, Any]) -> models.User:
    username = str(admin.get("username") or "").strip()
    if not username:
        raise ValueError("CRM admin username is empty")

    display_name = (
        str(admin.get("real_name") or "").strip()
        or str(admin.get("nick_name") or "").strip()
        or username
    )

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        user = models.User(
            username=username,
            display_name=display_name,
            avatar_url="",
            auth_source="crm",
            role="coach",
            password_hash=pwd_context.hash(secrets.token_hex(16)),
            status=1,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    changed = False
    if user.display_name != display_name:
        user.display_name = display_name
        changed = True
    if (user.auth_source or "local") != "crm":
        user.auth_source = "crm"
        changed = True
    if user.role != "coach":
        user.role = "coach"
        changed = True
    if user.status != 1:
        user.status = 1
        changed = True

    if changed:
        db.commit()
        db.refresh(user)
    return user
