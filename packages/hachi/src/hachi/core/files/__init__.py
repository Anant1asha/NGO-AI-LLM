"""File / Attachment Platform (Initiative E, Slice 2.4).

Public API::

    from hachi.core.files import FileMeta, FilePipeline, FileMetaStore
    from hachi.core.files import LocalStorageProvider, NoOpScanner
    from hachi.core.files import ContentExtractor, StorageProvider, VirusScanHook
"""

from hachi.core.files.store import (
    ContentExtractor,
    FileMeta,
    FileMetaStore,
    FilePipeline,
    LocalStorageProvider,
    NoOpScanner,
    ScanResult,
    StorageProvider,
    VirusScanHook,
)

__all__ = [
    "ContentExtractor",
    "FileMeta",
    "FileMetaStore",
    "FilePipeline",
    "LocalStorageProvider",
    "NoOpScanner",
    "ScanResult",
    "StorageProvider",
    "VirusScanHook",
]
