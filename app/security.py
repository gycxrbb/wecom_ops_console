import base64
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from fastapi import HTTPException, Request, status
from jwt.exceptions import PyJWTError
from sqlalchemy.orm import Session

from .config import settings
from . import models
from .password_utils import pwd_context
from .services.crm_admin_auth import CrmAdminAuthUnavailable, authenticate_crm_admin, crm_admin_auth_enabled, sync_crm_admin_to_local

_log = logging.getLogger(__name__)


def _build_deterministic_rsa_key() -> rsa.RSAPrivateKey:
    """Load or generate a persistent RSA key for login password encryption.

    Key is cached in data/ directory (same as SQLite DB) so it survives
    restarts and OS temp-file cleanup. All workers share the same key.
    """
    import os
    from .config import DATA_DIR

    # Try pycryptodome deterministic path first
    seed = hashlib.sha256(f"rsa-login-{settings.app_secret_key}".encode()).digest()
    try:
        import random as _rnd
        det_rng = _rnd.Random(seed)
        from Crypto.PublicKey import RSA as _CryptoRSA
        det_key = _CryptoRSA.generate(2048, randfunc=lambda n: bytes(det_rng.getrandbits(8) for _ in range(n)))
        return serialization.load_der_private_key(
            det_key.export_key('DER'),
            password=None,
            backend=default_backend(),
        )
    except ImportError:
        pass

    # Fallback: persistent file cache in data/ (not temp dir)
    cache_name = hashlib.sha256(f"rsa-cache-{settings.app_secret_key}".encode()).hexdigest()[:16]
    cache_path = DATA_DIR / f".rsa_key_{cache_name}.pem"

    if cache_path.exists():
        try:
            return serialization.load_pem_private_key(
                cache_path.read_bytes(), password=None, backend=default_backend()
            )
        except Exception:
            _log.warning("Cached RSA key corrupted, regenerating: %s", cache_path)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        cache_path.write_bytes(pem)
        _log.info("Generated and cached RSA key at %s", cache_path)
    except Exception as exc:
        _log.warning("Failed to cache RSA key: %s", exc)
    return key


_RSA_PRIVATE_KEY = _build_deterministic_rsa_key()
_RSA_PUBLIC_KEY_PEM = _RSA_PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode('utf-8')

def get_rsa_public_key() -> str:
    return _RSA_PUBLIC_KEY_PEM

def decrypt_rsa_password(encrypted_b64_str: str) -> str:
    if not encrypted_b64_str:
        return ""
    try:
        if len(encrypted_b64_str) < 50:
            return encrypted_b64_str
        encrypted_bytes = base64.b64decode(encrypted_b64_str)
        decrypted_bytes = _RSA_PRIVATE_KEY.decrypt(
            encrypted_bytes,
            padding.PKCS1v15()
        )
        return decrypted_bytes.decode('utf-8')
    except Exception as exc:
        _log.error(
            'RSA decryption failed — likely key mismatch (len=%d, prefix=%s): %s',
            len(encrypted_b64_str),
            encrypted_b64_str[:20],
            exc,
        )
        return encrypted_b64_str

def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.app_secret_key.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(digest))

fernet = _fernet()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def encrypt_webhook(webhook: str) -> str:
    if not webhook:
        return ''
    return fernet.encrypt(webhook.encode('utf-8')).decode('utf-8')


def decrypt_webhook(value: str) -> str:
    if not value:
        return ''
    return fernet.decrypt(value.encode('utf-8')).decode('utf-8')


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def json_loads(text: str | None, default: Any):
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def authenticate(db: Session, username: str, password: str):
    username = (username or '').strip()
    if not username:
        return None

    local_user = db.query(models.User).filter(models.User.username == username, models.User.status == 1).first()

    # 先查本地 users 表，只要本地 hash 能通过就直接登录。
    # 这样本地账号不会被 CRM 链路拖慢；CRM 镜像账号在本地 hash 不匹配时再回源 CRM。
    if local_user and local_user.password_hash and verify_password(password, local_user.password_hash):
        local_user.last_login_at = datetime.utcnow()
        local_user.auth_source = local_user.auth_source or 'local'
        db.commit()
        db.refresh(local_user)
        return local_user

    # 本地正式账号本地校验失败后直接拒绝，不再继续尝试 CRM，避免同名外部账号误登录。
    if local_user and (local_user.auth_source or 'local') == 'local':
        return None

    # 仅在本地未命中或当前是 CRM 镜像账号时，才尝试 CRM 认证。
    if crm_admin_auth_enabled():
        try:
            crm_admin = authenticate_crm_admin(username, password)
            if crm_admin:
                user = sync_crm_admin_to_local(db, crm_admin)
                user.last_login_at = datetime.utcnow()
                db.commit()
                db.refresh(user)
                return user
        except CrmAdminAuthUnavailable:
            pass

    # CRM 未启用 / CRM 认证失败 / CRM 不可用 → 对已有镜像账号做最后的本地兜底。
    if not local_user:
        return None
    if not verify_password(password, local_user.password_hash):
        return None
    local_user.last_login_at = datetime.utcnow()
    local_user.auth_source = local_user.auth_source or 'local'
    db.commit()
    db.refresh(local_user)
    return local_user


def get_current_user(request: Request, db: Session):
    user_id = None

    # 1. JWT Bearer token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            user_id = payload.get("sub")
        except PyJWTError:
            pass

    # 2. Session fallback
    if not user_id:
        user_id = request.session.get('user_id')

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')

    user = db.query(models.User).filter(models.User.id == int(user_id), models.User.status == 1).first()
    if not user:
        if 'user_id' in request.session:
            request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
    return user


def require_role(user: models.User, *roles: str):
    if user.role not in roles:
        raise HTTPException(status_code=403, detail='Insufficient permission')


ALL_PERMISSIONS = [
    'send', 'schedule', 'group', 'template',
    'plan', 'asset', 'log', 'approval', 'sop',
    'speech_template', 'crm_profile',
]

PERMISSION_LABELS = {
    'send': '消息发送',
    'schedule': '定时任务',
    'group': '群管理',
    'template': '模板管理',
    'plan': '运营编排',
    'asset': '素材管理',
    'log': '发送记录',
    'approval': '审批操作',
    'sop': '飞书文档',
    'speech_template': '话术管理',
    'crm_profile': '客户档案',
}

PERMISSION_GROUPS = {
    '核心业务': ['send', 'schedule'],
    '数据管理': ['group', 'template', 'plan', 'asset', 'sop', 'speech_template'],
    '客户运营': ['crm_profile'],
    '系统设置': ['log', 'approval'],
}


def require_permission(user: models.User, key: str):
    if user.role == 'admin':
        return
    perms = json_loads(user.permissions_json, {})
    if not perms.get(key):
        raise HTTPException(status_code=403, detail=f'缺少 {PERMISSION_LABELS.get(key, key)} 权限')

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt
