"""
Storage subpackage for SAS package

This module provides Azure Storage utilities including blob and queue operations.
"""

from .blob import StorageBlobHelper, AsyncStorageBlobHelper
from .queue import StorageQueueHelper, AsyncStorageQueueHelper
from .shared_config import (
    StorageConfig,
    get_config as get_shared_config,
    set_config as set_shared_config,
    create_config as create_shared_config,
)

__all__ = [
    "StorageBlobHelper",
    "AsyncStorageBlobHelper",
    "StorageQueueHelper",
    "AsyncStorageQueueHelper",
    "StorageConfig",
    "get_shared_config",
    "set_shared_config",
    "create_shared_config",
]

__version__ = "1.0.0"
