"""
Tests for blob storage configuration module.
"""

import os
import pytest
from libs.sas.storage.blob.config import (
    BlobHelperConfig,
    get_config,
    set_config,
    create_config,
)


def test_blob_helper_config_default_initialization():
    """Test that BlobHelperConfig initializes with default settings."""
    config = BlobHelperConfig()
    assert config.get("max_single_upload_size") == 64 * 1024 * 1024
    assert config.get("max_block_size") == 4 * 1024 * 1024
    assert config.get("max_single_get_size") == 32 * 1024 * 1024
    assert config.get("max_chunk_get_size") == 4 * 1024 * 1024
    assert config.get("default_blob_tier") == "Hot"
    assert config.get("default_container_access") is None


def test_blob_helper_config_with_dict():
    """Test BlobHelperConfig initialization with custom dictionary."""
    custom_dict = {
        "max_single_upload_size": 128 * 1024 * 1024,
        "max_block_size": 8 * 1024 * 1024,
    }
    config = BlobHelperConfig(custom_dict)
    assert config.get("max_single_upload_size") == 128 * 1024 * 1024
    assert config.get("max_block_size") == 8 * 1024 * 1024


def test_blob_helper_config_get_method():
    """Test get method returns correct values and defaults."""
    config = BlobHelperConfig()
    assert config.get("max_single_upload_size") == 64 * 1024 * 1024
    assert config.get("nonexistent_key") is None
    assert config.get("nonexistent_key", "default_value") == "default_value"


def test_blob_helper_config_set_method():
    """Test set method updates configuration values."""
    config = BlobHelperConfig()
    config.set("max_single_upload_size", 256 * 1024 * 1024)
    assert config.get("max_single_upload_size") == 256 * 1024 * 1024


def test_blob_helper_config_get_all():
    """Test get_all returns all configuration values."""
    config = BlobHelperConfig()
    all_config = config.get_all()
    assert isinstance(all_config, dict)
    assert "max_single_upload_size" in all_config
    assert "max_block_size" in all_config
    assert "default_blob_tier" in all_config
    # Verify it's a copy, not a reference
    all_config["max_single_upload_size"] = 999
    assert config.get("max_single_upload_size") != 999


def test_blob_helper_config_update():
    """Test update method updates multiple values."""
    config = BlobHelperConfig()
    updates = {
        "max_single_upload_size": 128 * 1024 * 1024,
        "max_block_size": 8 * 1024 * 1024,
        "default_blob_tier": "Cool",
    }
    config.update(updates)
    assert config.get("max_single_upload_size") == 128 * 1024 * 1024
    assert config.get("max_block_size") == 8 * 1024 * 1024
    assert config.get("default_blob_tier") == "Cool"


def test_blob_helper_config_reset_to_defaults():
    """Test reset_to_defaults restores default configuration."""
    config = BlobHelperConfig()
    config.set("max_single_upload_size", 256 * 1024 * 1024)
    config.set("default_blob_tier", "Archive")
    config.reset_to_defaults()
    assert config.get("max_single_upload_size") == 64 * 1024 * 1024
    assert config.get("default_blob_tier") == "Hot"


def test_blob_helper_config_get_content_type():
    """Test get_content_type returns correct MIME types."""
    config = BlobHelperConfig()
    assert config.get_content_type(".txt") == "text/plain"
    assert config.get_content_type(".html") == "text/html"
    assert config.get_content_type(".json") == "application/json"
    assert config.get_content_type(".pdf") == "application/pdf"
    assert config.get_content_type(".jpg") == "image/jpeg"
    assert config.get_content_type(".png") == "image/png"
    assert config.get_content_type(".mp4") == "video/mp4"
    assert config.get_content_type(".mp3") == "audio/mpeg"
    assert config.get_content_type(".zip") == "application/zip"


def test_blob_helper_config_get_content_type_case_insensitive():
    """Test get_content_type works with different cases."""
    config = BlobHelperConfig()
    assert config.get_content_type(".TXT") == "text/plain"
    assert config.get_content_type(".Json") == "application/json"
    assert config.get_content_type(".PDF") == "application/pdf"


def test_blob_helper_config_get_content_type_unknown_extension():
    """Test get_content_type returns default for unknown extensions."""
    config = BlobHelperConfig()
    assert config.get_content_type(".xyz") == "application/octet-stream"
    assert config.get_content_type(".unknown") == "application/octet-stream"
    assert config.get_content_type("") == "application/octet-stream"


def test_blob_helper_config_content_type_all_mappings():
    """Test that all content type mappings are accessible."""
    config = BlobHelperConfig()
    mappings = config.config["content_type_mappings"]
    assert len(mappings) > 40  # Verify we have many mappings
    assert ".docx" in mappings
    assert ".xlsx" in mappings
    assert ".pptx" in mappings


def test_blob_helper_config_inherits_shared_config():
    """Test that BlobHelperConfig inherits shared config values."""
    config = BlobHelperConfig()
    assert config.get("retry_attempts") == 3
    assert config.get("timeout_seconds") == 30
    assert config.get("logging_level") == "INFO"


def test_blob_helper_config_load_from_environment(monkeypatch):
    """Test loading configuration from environment variables."""
    monkeypatch.setenv("AZURE_STORAGE_MAX_UPLOAD_SIZE", "128000000")
    monkeypatch.setenv("AZURE_STORAGE_MAX_BLOCK_SIZE", "8000000")
    monkeypatch.setenv("AZURE_STORAGE_DEFAULT_TIER", "Cool")
    
    config = BlobHelperConfig()
    assert config.get("max_single_upload_size") == 128000000
    assert config.get("max_block_size") == 8000000
    assert config.get("default_blob_tier") == "Cool"


def test_blob_helper_config_load_from_environment_invalid_values(monkeypatch):
    """Test that invalid environment values are skipped."""
    monkeypatch.setenv("AZURE_STORAGE_MAX_UPLOAD_SIZE", "not_a_number")
    monkeypatch.setenv("AZURE_STORAGE_MAX_BLOCK_SIZE", "invalid")
    
    config = BlobHelperConfig()
    # Should use default values since env values are invalid
    assert config.get("max_single_upload_size") == 64 * 1024 * 1024
    assert config.get("max_block_size") == 4 * 1024 * 1024


def test_get_config_returns_global_instance():
    """Test get_config returns the global configuration instance."""
    config = get_config()
    assert isinstance(config, BlobHelperConfig)
    # Verify it's a persistent instance
    config.set("test_key", "test_value")
    config2 = get_config()
    assert config2.get("test_key") == "test_value"
    # Clean up
    config.config.pop("test_key", None)


def test_set_config_updates_global_instance():
    """Test set_config replaces the global configuration instance."""
    original_config = get_config()
    new_config = BlobHelperConfig({"test_new": "value"})
    set_config(new_config)
    
    retrieved_config = get_config()
    assert retrieved_config.get("test_new") == "value"
    
    # Restore original
    set_config(original_config)


def test_create_config_creates_new_instance():
    """Test create_config creates a new independent instance."""
    config1 = create_config({"custom_key": "custom_value"})
    config2 = create_config({"another_key": "another_value"})
    
    assert config1.get("custom_key") == "custom_value"
    assert config2.get("another_key") == "another_value"
    assert config1.get("another_key") is None
    assert config2.get("custom_key") is None


def test_create_config_without_arguments():
    """Test create_config without arguments creates a default instance."""
    config = create_config()
    assert config.get("max_single_upload_size") == 64 * 1024 * 1024
    assert config.get("max_block_size") == 4 * 1024 * 1024


def test_blob_helper_config_independence():
    """Test that multiple instances are independent."""
    config1 = BlobHelperConfig({"max_single_upload_size": 100})
    config2 = BlobHelperConfig({"max_single_upload_size": 200})
    
    assert config1.get("max_single_upload_size") == 100
    assert config2.get("max_single_upload_size") == 200
    
    config1.set("max_single_upload_size", 300)
    assert config1.get("max_single_upload_size") == 300
    assert config2.get("max_single_upload_size") == 200


def test_blob_helper_config_preserve_shared_defaults():
    """Test that shared config defaults are preserved."""
    config = BlobHelperConfig()
    # Verify inherited defaults from StorageConfig
    assert "retry_attempts" in config.get_all()
    assert "timeout_seconds" in config.get_all()
    assert "logging_level" in config.get_all()
