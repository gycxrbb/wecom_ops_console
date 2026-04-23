from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx

from ...config import settings
from .base import StorageProvider, StorageResult, UploadPayload


def _b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode('utf-8')


def _safe_slug(text: str) -> str:
    normalized = unicodedata.normalize('NFKD', text)
    ascii_text = normalized.encode('ascii', 'ignore').decode('ascii').lower()
    ascii_text = re.sub(r'[^a-z0-9]+', '-', ascii_text).strip('-')
    return ascii_text or 'asset'


@dataclass(slots=True)
class QiniuConfig:
    enabled: bool
    access_key: str
    secret_key: str
    bucket: str
    region: str
    public_domain: str
    use_https: bool
    prefix: str
    private_bucket: bool
    signed_url_expire_seconds: int


class QiniuStorageProvider(StorageProvider):
    provider_name = 'qiniu'

    def __init__(self, config: QiniuConfig | None = None):
        self.config = config or self._load_config()
        self._upload_host = self._resolve_upload_host(self.config.region)

    @staticmethod
    def _setting(name: str, default=None):
        return getattr(settings, name, default) if settings else default

    @classmethod
    def _load_config(cls) -> QiniuConfig:
        enabled = str(os.getenv('ASSET_STORAGE_PROVIDER', getattr(settings, 'asset_storage_provider', 'local'))).lower() == 'qiniu'
        return QiniuConfig(
            enabled=enabled,
            access_key=os.getenv('QINIU_ACCESS_KEY', cls._setting('qiniu_access_key', '')),
            secret_key=os.getenv('QINIU_SECRET_KEY', cls._setting('qiniu_secret_key', '')),
            bucket=os.getenv('QINIU_BUCKET', cls._setting('qiniu_bucket', '')),
            region=os.getenv('QINIU_REGION', cls._setting('qiniu_region', 'z2')),
            public_domain=os.getenv('QINIU_PUBLIC_DOMAIN', cls._setting('qiniu_public_domain', '')),
            use_https=str(os.getenv('QINIU_USE_HTTPS', str(cls._setting('qiniu_use_https', True)))).lower() != 'false',
            prefix=os.getenv('QINIU_PREFIX', cls._setting('qiniu_prefix', 'materials/')).strip('/'),
            private_bucket=str(os.getenv('QINIU_PRIVATE_BUCKET', str(cls._setting('qiniu_private_bucket', False)))).lower() == 'true',
            signed_url_expire_seconds=int(os.getenv('QINIU_SIGNED_URL_EXPIRE_SECONDS', cls._setting('qiniu_signed_url_expire_seconds', 3600))),
        )

    @staticmethod
    def _resolve_upload_host(region: str) -> str:
        mapping = {
            'z0': 'https://up.qiniup.com',
            'z1': 'https://up-z1.qiniup.com',
            'z2': 'https://up-z2.qiniup.com',
            'na0': 'https://up-na0.qiniup.com',
            'as0': 'https://up-as0.qiniup.com',
        }
        return mapping.get((region or '').lower(), 'https://up.qiniup.com')

    def _ensure_ready(self) -> None:
        if not self.config.access_key or not self.config.secret_key or not self.config.bucket or not self.config.public_domain:
            raise RuntimeError('七牛配置不完整，请检查 QINIU_ACCESS_KEY / QINIU_SECRET_KEY / QINIU_BUCKET / QINIU_PUBLIC_DOMAIN')

    def _object_key(self, filename: str, custom_object_key: str = '') -> str:
        if custom_object_key:
            return custom_object_key.strip('/').replace('\\', '/')
        suffix = Path(filename).suffix.lower()
        base = _safe_slug(Path(filename).stem)
        date_part = datetime.now().strftime('%Y/%m/%d')
        unique = uuid4().hex[:16]
        return f"{self.config.prefix}/{date_part}/{base}-{unique}{suffix}".lstrip('/')

    def _upload_token(self, object_key: str) -> str:
        expire_at = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        scope = f"{self.config.bucket}:{object_key}"
        put_policy = {
            'scope': scope,
            'deadline': expire_at,
        }
        encoded_policy = _b64_encode(json.dumps(put_policy, separators=(',', ':')).encode('utf-8'))
        sign = hmac.new(self.config.secret_key.encode('utf-8'), encoded_policy.encode('utf-8'), hashlib.sha1).digest()
        encoded_sign = _b64_encode(sign)
        return f"{self.config.access_key}:{encoded_sign}:{encoded_policy}"

    def _normalize_domain(self) -> str:
        domain = self.config.public_domain.strip()
        if not domain:
            return ''
        if domain.startswith('http://') or domain.startswith('https://'):
            return domain.rstrip('/')
        scheme = 'https' if self.config.use_https else 'http'
        return f"{scheme}://{domain.rstrip('/')}"

    def _public_url(self, object_key: str) -> str:
        domain = self._normalize_domain()
        return f"{domain}/{object_key.lstrip('/')}"

    def _signed_url(self, public_url: str) -> str:
        expire_at = int((datetime.now(timezone.utc) + timedelta(seconds=self.config.signed_url_expire_seconds)).timestamp())
        sep = '&' if '?' in public_url else '?'
        return f"{public_url}{sep}e={expire_at}"

    def upload(self, payload: UploadPayload) -> StorageResult:
        self._ensure_ready()
        object_key = self._object_key(payload.filename, payload.object_key)
        token = self._upload_token(object_key)
        files = {'file': (Path(payload.filename).name, payload.content, payload.mime_type or 'application/octet-stream')}
        data = {'token': token, 'key': object_key}
        resp = self._post_upload(self._upload_host, data=data, files=files)
        if resp.status_code == 400:
            body = resp.json()
            hint_host = self._extract_region_upload_host(body.get('error', ''))
            if hint_host and hint_host != self._upload_host:
                resp = self._post_upload(hint_host, data=data, files=files)
        resp.raise_for_status()
        body = resp.json()
        if body.get('error'):
            raise RuntimeError(f"七牛上传失败: {body.get('error')}")

        public_url = self._public_url(object_key)
        if self.config.private_bucket:
            public_url = self._signed_url(public_url)

        return StorageResult(
            provider=self.provider_name,
            object_key=object_key,
            public_url=public_url,
            original_filename=Path(payload.filename).name,
            stored_filename=Path(object_key).name,
            mime_type=payload.mime_type,
            file_size=len(payload.content),
            bucket=self.config.bucket,
            extra={
                'hash': body.get('hash', ''),
                'key': body.get('key', object_key),
            },
        )

    def prepare_client_upload(self, filename: str, mime_type: str) -> dict:
        """生成客户端直传所需的 token 和元信息，跳过服务器中转。"""
        self._ensure_ready()
        object_key = self._object_key(filename)
        token = self._upload_token(object_key)
        public_url = self._public_url(object_key)
        if self.config.private_bucket:
            public_url = self._signed_url(public_url)
        return {
            'mode': 'qiniu',
            'upload_url': self._upload_host,
            'token': token,
            'object_key': object_key,
            'public_url': public_url,
            'bucket': self.config.bucket,
        }
        self._ensure_ready()
        object_key = self._object_key(payload.filename)
        token = self._upload_token(object_key)
        files = {'file': (Path(payload.filename).name, payload.content, payload.mime_type or 'application/octet-stream')}
        data = {'token': token, 'key': object_key}
        resp = self._post_upload(self._upload_host, data=data, files=files)
        if resp.status_code == 400:
            body = resp.json()
            hint_host = self._extract_region_upload_host(body.get('error', ''))
            if hint_host and hint_host != self._upload_host:
                resp = self._post_upload(hint_host, data=data, files=files)
        resp.raise_for_status()
        body = resp.json()
        if body.get('error'):
            raise RuntimeError(f"七牛上传失败: {body.get('error')}")

        public_url = self._public_url(object_key)
        if self.config.private_bucket:
            public_url = self._signed_url(public_url)

        return StorageResult(
            provider=self.provider_name,
            object_key=object_key,
            public_url=public_url,
            original_filename=Path(payload.filename).name,
            stored_filename=Path(object_key).name,
            mime_type=payload.mime_type,
            file_size=len(payload.content),
            bucket=self.config.bucket,
            extra={
                'hash': body.get('hash', ''),
                'key': body.get('key', object_key),
            },
        )

    @staticmethod
    def _post_upload(upload_host: str, *, data: dict, files: dict) -> httpx.Response:
        return httpx.post(upload_host, data=data, files=files, timeout=300)

    @staticmethod
    def _extract_region_upload_host(message: str) -> str:
        match = re.search(r"(up(?:-[a-z0-9]+)?\.qiniup\.com)", message or "", re.IGNORECASE)
        if not match:
            return ''
        return f"https://{match.group(1).lower()}"

    def delete(self, handle: StorageResult) -> None:
        self._ensure_ready()
        entry = _b64_encode(f"{self.config.bucket}:{handle.object_key}".encode('utf-8'))
        url = f"https://rs.qiniuapi.com/delete/{entry}"
        token = self._auth_token(url)
        resp = httpx.post(url, headers={'Authorization': f'QBox {token}'}, timeout=30)
        resp.raise_for_status()

    def _auth_token(self, url: str, body: bytes = b'') -> str:
        parsed = httpx.URL(url)
        path = parsed.raw_path.decode('utf-8')
        query = f"?{parsed.query.decode('utf-8')}" if parsed.query else ''
        signing_str = f"{path}{query}\n".encode('utf-8') + body
        digest = hmac.new(self.config.secret_key.encode('utf-8'), signing_str, hashlib.sha1).digest()
        return f"{self.config.access_key}:{_b64_encode(digest)}"

    def download_bytes(self, handle: StorageResult) -> bytes:
        url = self.build_public_url(handle)
        resp = httpx.get(url, timeout=60)
        resp.raise_for_status()
        return resp.content

    def build_public_url(self, handle: StorageResult) -> str:
        if handle.public_url and not self.config.private_bucket:
            return handle.public_url
        public_url = self._public_url(handle.object_key)
        return self._signed_url(public_url) if self.config.private_bucket else public_url
