"""
Unit tests for BlobHelperConfig class and related functions
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, Any

# Import the modules under test
from app.libs.sas.storage.blob.config import (
    BlobHelperConfig,
    get_config,
    set_config,
    create_config,
    default_config
)


class TestBlobHelperConfig:
    """Test cases for BlobHelperConfig class"""
    
    def test_default_config_values(self):
        """Test that default configuration values are set correctly"""
        config = BlobHelperConfig()
        
        # Test shared config values inherited from StorageConfig
        assert config.get("retry_attempts") == 3
        assert config.get("timeout_seconds") == 30
        assert config.get("logging_level") == "INFO"
        
        # Test blob-specific config values
        assert config.get("max_single_upload_size") == 64 * 1024 * 1024  # 64MB
        assert config.get("max_block_size") == 4 * 1024 * 1024  # 4MB
        assert config.get("max_single_get_size") == 32 * 1024 * 1024  # 32MB
        assert config.get("max_chunk_get_size") == 4 * 1024 * 1024  # 4MB
        assert config.get("default_blob_tier") == "Hot"
        assert config.get("default_container_access") is None
        
        # Test sync exclude patterns
        expected_patterns = ["*.tmp", "*.log", "*.swp", ".DS_Store", "Thumbs.db"]
        assert config.get("sync_exclude_patterns") == expected_patterns

    def test_content_type_mappings(self):
        """Test content type mappings are correctly configured"""
        config = BlobHelperConfig()
        content_mappings = config.get("content_type_mappings")
        
        # Test common file types
        assert content_mappings[".txt"] == "text/plain"
        assert content_mappings[".html"] == "text/html"
        assert content_mappings[".json"] == "application/json"
        assert content_mappings[".pdf"] == "application/pdf"
        assert content_mappings[".jpg"] == "image/jpeg"
        assert content_mappings[".png"] == "image/png"
        assert content_mappings[".mp4"] == "video/mp4"
        assert content_mappings[".mp3"] == "audio/mpeg"
        assert content_mappings[".zip"] == "application/zip"

    def test_init_with_config_dict(self):
        """Test initialization with custom configuration dictionary"""
        custom_config = {
            "max_single_upload_size": 128 * 1024 * 1024,  # 128MB
            "default_blob_tier": "Cool",
            "custom_setting": "test_value"
        }
        
        config = BlobHelperConfig(custom_config)
        
        # Test that custom values override defaults
        assert config.get("max_single_upload_size") == 128 * 1024 * 1024
        assert config.get("default_blob_tier") == "Cool"
        assert config.get("custom_setting") == "test_value"
        
        # Test that non-overridden defaults remain
        assert config.get("max_block_size") == 4 * 1024 * 1024
        assert config.get("retry_attempts") == 3

    def test_init_with_none_config_dict(self):
        """Test initialization with None config dict uses defaults"""
        config = BlobHelperConfig(None)
        
        assert config.get("max_single_upload_size") == 64 * 1024 * 1024
        assert config.get("default_blob_tier") == "Hot"
        assert config.get("retry_attempts") == 3

    @patch.dict(os.environ, {
        'AZURE_STORAGE_MAX_UPLOAD_SIZE': '134217728',  # 128MB
        'AZURE_STORAGE_MAX_BLOCK_SIZE': '8388608',     # 8MB
        'AZURE_STORAGE_DEFAULT_TIER': 'Archive',
        'AZURE_STORAGE_RETRY_ATTEMPTS': '5'  # From parent class
    })
    def test_load_from_environment_valid_values(self):
        """Test loading valid environment variables"""
        config = BlobHelperConfig()
        
        # Test blob-specific environment variables
        assert config.get("max_single_upload_size") == 134217728
        assert config.get("max_block_size") == 8388608
        assert config.get("default_blob_tier") == "Archive"
        
        # Test inherited environment variables
        assert config.get("retry_attempts") == 5

    @patch.dict(os.environ, {
        'AZURE_STORAGE_MAX_UPLOAD_SIZE': 'invalid_number',
        'AZURE_STORAGE_MAX_BLOCK_SIZE': '',
        'AZURE_STORAGE_DEFAULT_TIER': 'Cool'
    })
    def test_load_from_environment_invalid_values(self):
        """Test loading invalid environment variables uses defaults"""
        config = BlobHelperConfig()
        
        # Invalid/empty values should not override defaults
        assert config.get("max_single_upload_size") == 64 * 1024 * 1024  # Default
        assert config.get("max_block_size") == 4 * 1024 * 1024  # Default
        
        # Valid values should still work
        assert config.get("default_blob_tier") == "Cool"

    @patch.dict(os.environ, {}, clear=True)
    def test_load_from_environment_no_vars(self):
        """Test loading when no environment variables are set"""
        config = BlobHelperConfig()
        
        # All values should be defaults
        assert config.get("max_single_upload_size") == 64 * 1024 * 1024
        assert config.get("max_block_size") == 4 * 1024 * 1024
        assert config.get("default_blob_tier") == "Hot"

    def test_get_method(self):
        """Test get method functionality"""
        config = BlobHelperConfig()
        
        # Test getting existing key
        assert config.get("max_single_upload_size") == 64 * 1024 * 1024
        
        # Test getting non-existent key with default
        assert config.get("non_existent_key", "default_value") == "default_value"
        
        # Test getting non-existent key without default
        assert config.get("non_existent_key") is None

    def test_set_method(self):
        """Test set method functionality"""
        config = BlobHelperConfig()
        
        # Set a new value
        config.set("test_key", "test_value")
        assert config.get("test_key") == "test_value"
        
        # Override existing value
        config.set("max_single_upload_size", 100 * 1024 * 1024)
        assert config.get("max_single_upload_size") == 100 * 1024 * 1024

    def test_get_content_type(self):
        """Test get_content_type method"""
        config = BlobHelperConfig()
        
        # Test known extensions
        assert config.get_content_type(".txt") == "text/plain"
        assert config.get_content_type(".json") == "application/json"
        assert config.get_content_type(".png") == "image/png"
        
        # Test case insensitivity
        assert config.get_content_type(".TXT") == "text/plain"
        assert config.get_content_type(".PNG") == "image/png"
        
        # Test unknown extension
        assert config.get_content_type(".unknown") == "application/octet-stream"
        assert config.get_content_type(".xyz") == "application/octet-stream"

    def test_get_all_method(self):
        """Test get_all method returns copy of config"""
        config = BlobHelperConfig()
        
        all_config = config.get_all()
        
        # Test that it contains expected keys
        assert "max_single_upload_size" in all_config
        assert "retry_attempts" in all_config
        assert "content_type_mappings" in all_config
        
        # Test that it's a copy (modifying returned dict doesn't affect original)
        all_config["test_key"] = "test_value"
        assert config.get("test_key") is None

    def test_update_method(self):
        """Test update method"""
        config = BlobHelperConfig()
        
        updates = {
            "max_single_upload_size": 200 * 1024 * 1024,
            "default_blob_tier": "Archive",
            "new_setting": "new_value"
        }
        
        config.update(updates)
        
        # Test that values were updated
        assert config.get("max_single_upload_size") == 200 * 1024 * 1024
        assert config.get("default_blob_tier") == "Archive"
        assert config.get("new_setting") == "new_value"
        
        # Test that other values remain unchanged
        assert config.get("max_block_size") == 4 * 1024 * 1024

    def test_update_method_with_empty_dict(self):
        """Test update method with empty dictionary"""
        config = BlobHelperConfig()
        original_upload_size = config.get("max_single_upload_size")
        
        config.update({})
        
        # Nothing should change
        assert config.get("max_single_upload_size") == original_upload_size

    @patch.dict(os.environ, {
        'AZURE_STORAGE_MAX_UPLOAD_SIZE': '134217728',
        'AZURE_STORAGE_DEFAULT_TIER': 'Cool'
    })
    def test_reset_to_defaults(self):
        """Test reset_to_defaults method"""
        config = BlobHelperConfig()
        
        # Modify some values
        config.set("max_single_upload_size", 500 * 1024 * 1024)
        config.set("custom_setting", "custom_value")
        
        # Reset to defaults
        config.reset_to_defaults()
        
        # Test that values are back to environment/defaults
        assert config.get("max_single_upload_size") == 134217728  # From env var
        assert config.get("default_blob_tier") == "Cool"  # From env var
        assert config.get("max_block_size") == 4 * 1024 * 1024  # Default
        assert config.get("custom_setting") is None  # Removed


class TestGlobalConfigFunctions:
    """Test cases for global configuration functions"""
    
    def test_get_config_returns_default_instance(self):
        """Test that get_config returns the default config instance"""
        config = get_config()
        
        assert isinstance(config, BlobHelperConfig)
        assert config is default_config

    def test_set_config_updates_default_instance(self):
        """Test that set_config updates the global default instance"""
        # Create a custom config
        custom_config = BlobHelperConfig({"max_single_upload_size": 200 * 1024 * 1024})
        
        # Set as global config
        set_config(custom_config)
        
        # Verify global config was updated
        global_config = get_config()
        assert global_config is custom_config
        assert global_config.get("max_single_upload_size") == 200 * 1024 * 1024
        
        # Reset to original default for other tests
        set_config(BlobHelperConfig())

    def test_create_config_with_dict(self):
        """Test create_config function with configuration dictionary"""
        config_dict = {
            "max_single_upload_size": 100 * 1024 * 1024,
            "default_blob_tier": "Cool"
        }
        
        config = create_config(config_dict)
        
        assert isinstance(config, BlobHelperConfig)
        assert config.get("max_single_upload_size") == 100 * 1024 * 1024
        assert config.get("default_blob_tier") == "Cool"
        
        # Test that it's a separate instance from global config
        assert config is not get_config()

    def test_create_config_with_none(self):
        """Test create_config function with None parameter"""
        config = create_config(None)
        
        assert isinstance(config, BlobHelperConfig)
        assert config.get("max_single_upload_size") == 64 * 1024 * 1024  # Default
        assert config.get("default_blob_tier") == "Hot"  # Default

    def test_create_config_without_parameters(self):
        """Test create_config function without parameters"""
        config = create_config()
        
        assert isinstance(config, BlobHelperConfig)
        assert config.get("max_single_upload_size") == 64 * 1024 * 1024  # Default
        assert config.get("default_blob_tier") == "Hot"  # Default


class TestConfigIntegration:
    """Integration tests for config functionality"""
    
    def test_config_inheritance_from_storage_config(self):
        """Test that BlobHelperConfig properly inherits from StorageConfig"""
        config = BlobHelperConfig()
        
        # Test that shared config values are available
        assert config.get("retry_attempts") == 3
        assert config.get("timeout_seconds") == 30
        assert config.get("logging_level") == "INFO"
        
        # Test that blob-specific values are also available
        assert config.get("max_single_upload_size") == 64 * 1024 * 1024
        assert config.get("default_blob_tier") == "Hot"

    def test_config_override_precedence(self):
        """Test that configuration override precedence works correctly"""
        # Environment variables should override defaults
        with patch.dict(os.environ, {'AZURE_STORAGE_RETRY_ATTEMPTS': '10'}):
            config = BlobHelperConfig()
            assert config.get("retry_attempts") == 10
        
        # Constructor dict should be overridden by environment variables
        # (Based on actual implementation: env vars are loaded after constructor dict)
        with patch.dict(os.environ, {'AZURE_STORAGE_RETRY_ATTEMPTS': '10'}):
            config = BlobHelperConfig({"retry_attempts": 15})
            assert config.get("retry_attempts") == 10  # Environment wins
        
        # Test that constructor dict works when no environment variable
        config = BlobHelperConfig({"retry_attempts": 15})
        assert config.get("retry_attempts") == 15

    def test_content_type_mapping_completeness(self):
        """Test that content type mappings cover common file types"""
        config = BlobHelperConfig()
        
        # Test various categories of file types
        text_types = [".txt", ".html", ".css", ".js", ".json", ".xml"]
        image_types = [".jpg", ".png", ".gif", ".bmp", ".svg"]
        video_types = [".mp4", ".avi", ".mov"]
        audio_types = [".mp3", ".wav", ".flac"]
        document_types = [".pdf", ".doc", ".docx", ".xls", ".xlsx"]
        
        all_types = text_types + image_types + video_types + audio_types + document_types
        
        for file_type in all_types:
            content_type = config.get_content_type(file_type)
            assert content_type != "application/octet-stream"  # Should have specific mapping
            assert isinstance(content_type, str)
            assert len(content_type) > 0

    @patch.dict(os.environ, {}, clear=True)
    def test_config_isolation_between_instances(self):
        """Test that different config instances are properly isolated"""
        config1 = BlobHelperConfig({"max_single_upload_size": 100 * 1024 * 1024})
        config2 = BlobHelperConfig({"max_single_upload_size": 200 * 1024 * 1024})
        
        # Test that instances have different values
        assert config1.get("max_single_upload_size") == 100 * 1024 * 1024
        assert config2.get("max_single_upload_size") == 200 * 1024 * 1024
        
        # Test that modifying one doesn't affect the other
        config1.set("test_setting", "value1")
        config2.set("test_setting", "value2")
        
        assert config1.get("test_setting") == "value1"
        assert config2.get("test_setting") == "value2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])