"""
Tests for blob storage module exports.
"""

import pytest
from libs.sas.storage.blob import (
    StorageBlobHelper,
    AsyncStorageBlobHelper,
    BlobHelperConfig,
    get_config,
    set_config,
    create_config,
)


def test_storage_blob_helper_is_exported():
    """Test that StorageBlobHelper is exported."""
    assert StorageBlobHelper is not None
    assert hasattr(StorageBlobHelper, "__init__")


def test_async_storage_blob_helper_is_exported():
    """Test that AsyncStorageBlobHelper is exported."""
    assert AsyncStorageBlobHelper is not None
    assert hasattr(AsyncStorageBlobHelper, "__init__")


def test_blob_helper_config_is_exported():
    """Test that BlobHelperConfig is exported."""
    assert BlobHelperConfig is not None


def test_get_config_is_exported():
    """Test that get_config function is exported."""
    assert callable(get_config)
    config = get_config()
    assert isinstance(config, BlobHelperConfig)


def test_set_config_is_exported():
    """Test that set_config function is exported."""
    assert callable(set_config)


def test_create_config_is_exported():
    """Test that create_config function is exported."""
    assert callable(create_config)
    config = create_config()
    assert isinstance(config, BlobHelperConfig)


def test_module_all_exports():
    """Test that __all__ contains expected exports."""
    import libs.sas.storage.blob as blob_module
    all_exports = blob_module.__all__
    assert "StorageBlobHelper" in all_exports
    assert "AsyncStorageBlobHelper" in all_exports
    assert "BlobHelperConfig" in all_exports
    assert "get_config" in all_exports
    assert "set_config" in all_exports
    assert "create_config" in all_exports
