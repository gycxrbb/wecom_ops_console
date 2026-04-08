from .base import StorageProvider, StorageResult, UploadPayload
from .facade import StorageFacade, storage_facade
from .local import LocalStorageProvider
from .qiniu import QiniuStorageProvider

__all__ = [
    'StorageFacade',
    'StorageProvider',
    'StorageResult',
    'UploadPayload',
    'LocalStorageProvider',
    'QiniuStorageProvider',
    'storage_facade',
]
