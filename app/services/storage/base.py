from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from io import BytesIO
from typing import BinaryIO


@dataclass(slots=True)
class StorageResult:
    provider: str
    object_key: str
    public_url: str
    original_filename: str
    stored_filename: str
    mime_type: str
    file_size: int
    bucket: str = ''
    local_path: str = ''
    extra: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class UploadPayload:
    content: bytes
    filename: str
    mime_type: str = 'application/octet-stream'


class StorageProvider(ABC):
    provider_name: str

    @abstractmethod
    def upload(self, payload: UploadPayload) -> StorageResult:
        raise NotImplementedError

    @abstractmethod
    def delete(self, handle: StorageResult) -> None:
        raise NotImplementedError

    @abstractmethod
    def download_bytes(self, handle: StorageResult) -> bytes:
        raise NotImplementedError

    def open_stream(self, handle: StorageResult) -> BinaryIO:
        return BytesIO(self.download_bytes(handle))

    @abstractmethod
    def build_public_url(self, handle: StorageResult) -> str:
        raise NotImplementedError
