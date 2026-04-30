"""Tests for src/app/libs/sas/storage/__init__.py"""


def test_storage_exports_blob_helper():
    """Test that storage module exports StorageBlobHelper"""
    from libs.sas.storage import StorageBlobHelper
    assert StorageBlobHelper is not None


def test_storage_exports_async_blob_helper():
    """Test that storage module exports AsyncStorageBlobHelper"""
    from libs.sas.storage import AsyncStorageBlobHelper
    assert AsyncStorageBlobHelper is not None


def test_storage_exports_queue_helper():
    """Test that storage module exports StorageQueueHelper"""
    from libs.sas.storage import StorageQueueHelper
    assert StorageQueueHelper is not None


def test_storage_exports_async_queue_helper():
    """Test that storage module exports AsyncStorageQueueHelper"""
    from libs.sas.storage import AsyncStorageQueueHelper
    assert AsyncStorageQueueHelper is not None


def test_storage_exports_storage_config():
    """Test that storage module exports StorageConfig"""
    from libs.sas.storage import StorageConfig
    assert StorageConfig is not None


def test_storage_exports_config_functions():
    """Test that storage module exports config functions"""
    from libs.sas.storage import (
        get_shared_config,
        set_shared_config,
        create_shared_config,
    )
    assert get_shared_config is not None
    assert set_shared_config is not None
    assert create_shared_config is not None


def test_storage_all_exports():
    """Test that __all__ is properly defined"""
    from libs.sas import storage
    
    expected_exports = [
        "StorageBlobHelper",
        "AsyncStorageBlobHelper",
        "StorageQueueHelper",
        "AsyncStorageQueueHelper",
        "StorageConfig",
        "get_shared_config",
        "set_shared_config",
        "create_shared_config",
    ]
    
    for export in expected_exports:
        assert hasattr(storage, export), f"storage module missing export: {export}"


def test_storage_version():
    """Test that storage module has a version"""
    from libs.sas.storage import __version__
    assert __version__ == "1.0.0"
