from __future__ import annotations

import os
from dataclasses import dataclass

from ...config import settings
from .base import StorageProvider, StorageResult, UploadPayload
from .local import LocalStorageProvider
from .qiniu import QiniuStorageProvider


@dataclass(slots=True)
class StorageFacadeConfig:
    active_provider: str = 'local'
    fallback_provider: str = 'local'


class StorageFacade:
    def __init__(self, active_provider: StorageProvider | None = None, fallback_provider: StorageProvider | None = None):
        self.active_provider = active_provider or self._build_provider(self._active_provider_name())
        self.fallback_provider = fallback_provider or self._build_provider(self._fallback_provider_name())

    @staticmethod
    def _setting(name: str, default=None):
        return getattr(settings, name, default) if settings else default

    @classmethod
    def _active_provider_name(cls) -> str:
        return (os.getenv('ASSET_STORAGE_PROVIDER') or cls._setting('asset_storage_provider', 'local') or 'local').strip().lower()

    @classmethod
    def _fallback_provider_name(cls) -> str:
        value = (os.getenv('ASSET_STORAGE_FALLBACK_PROVIDER') or cls._setting('asset_storage_fallback_provider', 'local') or 'local').strip().lower()
        return value or 'local'

    def _build_provider(self, name: str) -> StorageProvider:
        if name == 'qiniu':
            return QiniuStorageProvider()
        return LocalStorageProvider()

    def get_provider(self, name: str) -> StorageProvider:
        normalized = (name or '').strip().lower()
        if normalized == self.active_provider.provider_name:
            return self.active_provider
        if normalized == self.fallback_provider.provider_name:
            return self.fallback_provider
        return self._build_provider(normalized or 'local')

    def upload_with_provider(self, provider_name: str, payload: UploadPayload) -> StorageResult:
        provider = self.get_provider(provider_name)
        return provider.upload(payload)

    def prepare_client_upload(self, filename: str, mime_type: str) -> dict | None:
        """如果 active provider 支持客户端直传，返回直传配置；否则返回 None。"""
        if isinstance(self.active_provider, QiniuStorageProvider):
            return self.active_provider.prepare_client_upload(filename, mime_type)
        return None

    def upload(self, payload: UploadPayload) -> StorageResult:
        try:
            return self.active_provider.upload(payload)
        except Exception:
            if self.fallback_provider.provider_name != self.active_provider.provider_name:
                return self.fallback_provider.upload(payload)
            raise

    def delete(self, handle: StorageResult) -> None:
        provider = self._provider_for_handle(handle)
        provider.delete(handle)

    def download_bytes(self, handle: StorageResult) -> bytes:
        provider = self._provider_for_handle(handle)
        try:
            return provider.download_bytes(handle)
        except Exception:
            fallback_local_path = (handle.local_path or '').strip()
            if provider.provider_name != 'local' and fallback_local_path:
                fallback_handle = StorageResult(
                    provider='local',
                    object_key=handle.object_key,
                    public_url=handle.public_url,
                    original_filename=handle.original_filename,
                    stored_filename=handle.stored_filename,
                    mime_type=handle.mime_type,
                    file_size=handle.file_size,
                    bucket='local',
                    local_path=fallback_local_path,
                    extra=handle.extra,
                )
                return LocalStorageProvider().download_bytes(fallback_handle)
            raise

    def open_stream(self, handle: StorageResult):
        provider = self._provider_for_handle(handle)
        try:
            return provider.open_stream(handle)
        except Exception:
            fallback_local_path = (handle.local_path or '').strip()
            if provider.provider_name != 'local' and fallback_local_path:
                fallback_handle = StorageResult(
                    provider='local',
                    object_key=handle.object_key,
                    public_url=handle.public_url,
                    original_filename=handle.original_filename,
                    stored_filename=handle.stored_filename,
                    mime_type=handle.mime_type,
                    file_size=handle.file_size,
                    bucket='local',
                    local_path=fallback_local_path,
                    extra=handle.extra,
                )
                return LocalStorageProvider().open_stream(fallback_handle)
            raise

    def build_public_url(self, handle: StorageResult) -> str:
        provider = self._provider_for_handle(handle)
        return provider.build_public_url(handle)

    def _provider_for_handle(self, handle: StorageResult) -> StorageProvider:
        if handle.provider == self.active_provider.provider_name:
            return self.active_provider
        if handle.provider == self.fallback_provider.provider_name:
            return self.fallback_provider
        if handle.provider == 'qiniu':
            return QiniuStorageProvider()
        return LocalStorageProvider()


storage_facade = StorageFacade()
