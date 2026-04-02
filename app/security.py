import base64
import hashlib
import json
from typing import Any
from cryptography.fernet import Fernet
from passlib.context import CryptContext
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session
import jwt
from jwt.exceptions import PyJWTError
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
    user = db.query(models.User).filter(models.User.username == username, models.User.status == 1).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def get_current_user(request: Request, db: Session):
    user_id = None
    
    # 1. Try JWT
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            user_id = payload.get("sub")
        except PyJWTError:
            pass

    if not user_id:
        token = request.query_params.get("token")
        if token:
            try:
                payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
                user_id = payload.get("sub")
            except PyJWTError:
                pass
            
    # 2. Try session (fallback)
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
import jwt
from datetime import datetime, timedelta

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt
