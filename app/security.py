import base64
import hashlib
import json
from typing import Any
from cryptography.fernet import Fernet
from passlib.context import CryptContext
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session
from .config import settings
from . import models

pwd_context = CryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')

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
    user = db.query(models.User).filter(models.User.username == username, models.User.is_active == True).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def get_current_user(request: Request, db: Session):
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
    user = db.query(models.User).filter(models.User.id == user_id, models.User.is_active == True).first()
    if not user:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
    return user


def require_role(user: models.User, *roles: str):
    if user.role not in roles:
        raise HTTPException(status_code=403, detail='Insufficient permission')
