"""
Unit tests for StorageConfig and shared configuration functionality

This module contains comprehensive unit tests for the StorageConfig class
and all shared configuration functions, covering initialization, environment
variable loading, configuration management, and global configuration handling.
"""

import os
import pytest
from unittest.mock import patch, Mock
from typing import Dict, Any

# Import the classes and functions under test
from app.libs.sas.storage.shared_config import (
    StorageConfig,
    get_config,
    set_config,
    create_config,
    default_config
)


class TestStorageConfig:
    """Test cases for StorageConfig class"""

    def test_init_with_no_config_dict(self):
        """Test StorageConfig initialization without config dictionary"""
        config = StorageConfig()
        
        # Should have default configuration
        assert config.get("retry_attempts") == 3
        assert config.get("timeout_seconds") == 30
        assert config.get("logging_level") == "INFO"

    def test_init_with_empty_config_dict(self):
        """Test StorageConfig initialization with empty config dictionary"""
        config = StorageConfig({})
        
        # Should have default configuration
        assert config.get("retry_attempts") == 3
        assert config.get("timeout_seconds") == 30
        assert config.get("logging_level") == "INFO"

    def test_init_with_config_dict_overrides(self):
        """Test StorageConfig initialization with configuration overrides"""
        custom_config = {
            "retry_attempts": 5,
            "timeout_seconds": 60,
            "custom_setting": "test_value"
        }
        
        config = StorageConfig(custom_config)
        
        # Should have overridden values
        assert config.get("retry_attempts") == 5
        assert config.get("timeout_seconds") == 60
        assert config.get("logging_level") == "INFO"  # Default value
        assert config.get("custom_setting") == "test_value"

    def test_init_with_partial_config_dict(self):
        """Test StorageConfig initialization with partial configuration"""
        custom_config = {"retry_attempts": 10}
        
        config = StorageConfig(custom_config)
        
        # Should have mix of custom and default values
        assert config.get("retry_attempts") == 10
        assert config.get("timeout_seconds") == 30  # Default
        assert config.get("logging_level") == "INFO"  # Default

    @patch.dict(os.environ, {}, clear=True)
    def test_load_from_environment_no_env_vars(self):
        """Test environment variable loading when no environment variables are set"""
        config = StorageConfig()
        
        # Should have default values since no env vars are set
        assert config.get("retry_attempts") == 3
        assert config.get("timeout_seconds") == 30
        assert config.get("logging_level") == "INFO"

    @patch.dict(os.environ, {
        "AZURE_STORAGE_RETRY_ATTEMPTS": "7",
        "AZURE_STORAGE_TIMEOUT_SECONDS": "45",
        "AZURE_STORAGE_LOGGING_LEVEL": "DEBUG"
    }, clear=True)
    def test_load_from_environment_with_valid_env_vars(self):
        """Test environment variable loading with valid environment variables"""
        config = StorageConfig()
        
        # Should load values from environment
        assert config.get("retry_attempts") == 7
        assert config.get("timeout_seconds") == 45
        assert config.get("logging_level") == "DEBUG"

    @patch.dict(os.environ, {
        "AZURE_STORAGE_RETRY_ATTEMPTS": "invalid_number",
        "AZURE_STORAGE_TIMEOUT_SECONDS": "not_a_number",
        "AZURE_STORAGE_LOGGING_LEVEL": "WARNING"
    }, clear=True)
    def test_load_from_environment_with_invalid_env_vars(self):
        """Test environment variable loading with invalid values"""
        config = StorageConfig()
        
        # Invalid numeric values should be ignored, valid string values should be used
        assert config.get("retry_attempts") == 3  # Default, invalid env var ignored
        assert config.get("timeout_seconds") == 30  # Default, invalid env var ignored
        assert config.get("logging_level") == "WARNING"  # Valid string value

    @patch.dict(os.environ, {
        "AZURE_STORAGE_RETRY_ATTEMPTS": "15",
        "SOME_OTHER_VAR": "ignored"
    }, clear=True)
    def test_load_from_environment_mixed_vars(self):
        """Test environment variable loading with mixed relevant and irrelevant variables"""
        config = StorageConfig()
        
        # Only relevant env vars should be processed
        assert config.get("retry_attempts") == 15
        assert config.get("timeout_seconds") == 30  # Default
        assert config.get("logging_level") == "INFO"  # Default

    @patch.dict(os.environ, {"AZURE_STORAGE_RETRY_ATTEMPTS": "8"}, clear=True)
    def test_config_dict_overrides_environment(self):
        """Test that environment variables are loaded after config_dict initialization"""
        custom_config = {"retry_attempts": 12}
        config = StorageConfig(custom_config)
        
        # Environment variables are loaded after config_dict, so they override
        assert config.get("retry_attempts") == 8

    @patch.dict(os.environ, {"AZURE_STORAGE_RETRY_ATTEMPTS": "20"}, clear=True)
    def test_environment_variable_precedence(self):
        """Test that environment variables have the final say in configuration"""
        # Test with config_dict value
        config = StorageConfig({"retry_attempts": 15})
        
        # Environment variable should override config_dict
        assert config.get("retry_attempts") == 20
        
        # But other values from config_dict should remain
        config = StorageConfig({"retry_attempts": 15, "custom_key": "custom_value"})
        assert config.get("retry_attempts") == 20  # From env
        assert config.get("custom_key") == "custom_value"  # From config_dict

    def test_get_existing_key(self):
        """Test getting an existing configuration key"""
        config = StorageConfig({"test_key": "test_value"})
        
        result = config.get("test_key")
        assert result == "test_value"

    def test_get_non_existing_key_with_default(self):
        """Test getting a non-existing key with default value"""
        config = StorageConfig()
        
        result = config.get("non_existing_key", "default_value")
        assert result == "default_value"

    def test_get_non_existing_key_without_default(self):
        """Test getting a non-existing key without default value"""
        config = StorageConfig()
        
        result = config.get("non_existing_key")
        assert result is None

    def test_set_new_key(self):
        """Test setting a new configuration key"""
        config = StorageConfig()
        
        config.set("new_key", "new_value")
        assert config.get("new_key") == "new_value"

    def test_set_existing_key(self):
        """Test updating an existing configuration key"""
        config = StorageConfig()
        
        # Default value
        assert config.get("retry_attempts") == 3
        
        # Update value
        config.set("retry_attempts", 10)
        assert config.get("retry_attempts") == 10

    def test_set_various_data_types(self):
        """Test setting various data types"""
        config = StorageConfig()
        
        config.set("string_val", "test")
        config.set("int_val", 42)
        config.set("float_val", 3.14)
        config.set("bool_val", True)
        config.set("list_val", [1, 2, 3])
        config.set("dict_val", {"key": "value"})
        
        assert config.get("string_val") == "test"
        assert config.get("int_val") == 42
        assert config.get("float_val") == 3.14
        assert config.get("bool_val") is True
        assert config.get("list_val") == [1, 2, 3]
        assert config.get("dict_val") == {"key": "value"}

    def test_get_all(self):
        """Test getting all configuration values"""
        custom_config = {"custom_key": "custom_value"}
        config = StorageConfig(custom_config)
        
        all_config = config.get_all()
        
        # Should include both default and custom values
        assert "retry_attempts" in all_config
        assert "timeout_seconds" in all_config
        assert "logging_level" in all_config
        assert "custom_key" in all_config
        assert all_config["custom_key"] == "custom_value"
        
        # Should be a copy (modifications shouldn't affect original)
        all_config["new_key"] = "new_value"
        assert config.get("new_key") is None

    def test_update_single_value(self):
        """Test updating configuration with single value"""
        config = StorageConfig()
        
        config.update({"retry_attempts": 15})
        assert config.get("retry_attempts") == 15

    def test_update_multiple_values(self):
        """Test updating configuration with multiple values"""
        config = StorageConfig()
        
        updates = {
            "retry_attempts": 8,
            "timeout_seconds": 120,
            "new_setting": "test"
        }
        config.update(updates)
        
        assert config.get("retry_attempts") == 8
        assert config.get("timeout_seconds") == 120
        assert config.get("new_setting") == "test"
        assert config.get("logging_level") == "INFO"  # Unchanged

    def test_update_empty_dict(self):
        """Test updating configuration with empty dictionary"""
        config = StorageConfig()
        original_values = config.get_all()
        
        config.update({})
        
        # Should remain unchanged
        assert config.get_all() == original_values

    @patch.dict(os.environ, {"AZURE_STORAGE_RETRY_ATTEMPTS": "20"}, clear=True)
    def test_reset_to_defaults(self):
        """Test resetting configuration to defaults"""
        config = StorageConfig()
        
        # Modify some values
        config.set("retry_attempts", 100)
        config.set("custom_key", "custom_value")
        
        # Verify changes
        assert config.get("retry_attempts") == 100
        assert config.get("custom_key") == "custom_value"
        
        # Reset to defaults
        config.reset_to_defaults()
        
        # Should have default + environment values
        assert config.get("retry_attempts") == 20  # From environment
        assert config.get("timeout_seconds") == 30  # Default
        assert config.get("logging_level") == "INFO"  # Default
        assert config.get("custom_key") is None  # Custom key removed

    def test_default_config_constants(self):
        """Test that DEFAULT_CONFIG contains expected values"""
        expected_defaults = {
            "retry_attempts": 3,
            "timeout_seconds": 30,
            "logging_level": "INFO",
        }
        
        assert StorageConfig.DEFAULT_CONFIG == expected_defaults

    def test_config_isolation(self):
        """Test that different StorageConfig instances are isolated"""
        config1 = StorageConfig()
        config2 = StorageConfig()
        
        config1.set("test_key", "value1")
        config2.set("test_key", "value2")
        
        assert config1.get("test_key") == "value1"
        assert config2.get("test_key") == "value2"

    def test_config_modification_after_init(self):
        """Test that configuration can be modified after initialization"""
        config = StorageConfig({"initial_key": "initial_value"})
        
        # Test various modifications
        config.set("new_key", "new_value")
        config.update({"another_key": "another_value"})
        
        assert config.get("initial_key") == "initial_value"
        assert config.get("new_key") == "new_value"
        assert config.get("another_key") == "another_value"


class TestGlobalConfigurationFunctions:
    """Test cases for global configuration functions"""

    def setup_method(self):
        """Setup for each test method"""
        # Store original config to restore later
        self.original_config = get_config()

    def teardown_method(self):
        """Teardown for each test method"""
        # Restore original config
        set_config(self.original_config)

    def test_get_config_returns_default(self):
        """Test that get_config returns the default configuration instance"""
        config = get_config()
        
        assert isinstance(config, StorageConfig)
        # Should have default values
        assert config.get("retry_attempts") == 3
        assert config.get("timeout_seconds") == 30
        assert config.get("logging_level") == "INFO"

    def test_set_config_changes_global(self):
        """Test that set_config changes the global configuration"""
        new_config = StorageConfig({"retry_attempts": 99})
        
        set_config(new_config)
        
        retrieved_config = get_config()
        assert retrieved_config is new_config
        assert retrieved_config.get("retry_attempts") == 99

    def test_global_config_persistence(self):
        """Test that global configuration changes persist"""
        # Get initial config and modify it
        config = get_config()
        config.set("test_persistence", "persistent_value")
        
        # Get config again and verify persistence
        config_again = get_config()
        assert config_again is config
        assert config_again.get("test_persistence") == "persistent_value"

    def test_create_config_with_no_args(self):
        """Test create_config with no arguments"""
        config = create_config()
        
        assert isinstance(config, StorageConfig)
        assert config.get("retry_attempts") == 3
        assert config.get("timeout_seconds") == 30
        assert config.get("logging_level") == "INFO"

    def test_create_config_with_args(self):
        """Test create_config with configuration dictionary"""
        config_dict = {"retry_attempts": 7, "custom_key": "custom_value"}
        config = create_config(config_dict)
        
        assert isinstance(config, StorageConfig)
        assert config.get("retry_attempts") == 7
        assert config.get("timeout_seconds") == 30  # Default
        assert config.get("custom_key") == "custom_value"

    def test_create_config_independence(self):
        """Test that create_config creates independent instances"""
        config1 = create_config({"key": "value1"})
        config2 = create_config({"key": "value2"})
        global_config = get_config()
        
        # All should be different instances
        assert config1 is not config2
        assert config1 is not global_config
        assert config2 is not global_config
        
        # Values should be independent
        assert config1.get("key") == "value1"
        assert config2.get("key") == "value2"
        assert global_config.get("key") is None

    def test_multiple_set_get_cycles(self):
        """Test multiple set/get cycles for global configuration"""
        config1 = StorageConfig({"cycle": 1})
        config2 = StorageConfig({"cycle": 2})
        config3 = StorageConfig({"cycle": 3})
        
        set_config(config1)
        assert get_config().get("cycle") == 1
        
        set_config(config2)
        assert get_config().get("cycle") == 2
        
        set_config(config3)
        assert get_config().get("cycle") == 3


class TestEnvironmentVariableEdgeCases:
    """Test cases for edge cases in environment variable handling"""

    @patch.dict(os.environ, {"AZURE_STORAGE_RETRY_ATTEMPTS": ""}, clear=True)
    def test_empty_string_env_var(self):
        """Test handling of empty string environment variables"""
        config = StorageConfig()
        
        # Empty string should result in ValueError and use default
        assert config.get("retry_attempts") == 3

    @patch.dict(os.environ, {"AZURE_STORAGE_RETRY_ATTEMPTS": "0"}, clear=True)
    def test_zero_value_env_var(self):
        """Test handling of zero value in environment variables"""
        config = StorageConfig()
        
        # Zero is a valid integer
        assert config.get("retry_attempts") == 0

    @patch.dict(os.environ, {"AZURE_STORAGE_RETRY_ATTEMPTS": "-5"}, clear=True)
    def test_negative_value_env_var(self):
        """Test handling of negative values in environment variables"""
        config = StorageConfig()
        
        # Negative numbers are valid integers
        assert config.get("retry_attempts") == -5

    @patch.dict(os.environ, {"AZURE_STORAGE_TIMEOUT_SECONDS": "3.14"}, clear=True)
    def test_float_for_int_env_var(self):
        """Test handling of float values for integer environment variables"""
        config = StorageConfig()
        
        # Float string should cause ValueError and use default
        assert config.get("timeout_seconds") == 30

    @patch.dict(os.environ, {"AZURE_STORAGE_LOGGING_LEVEL": ""}, clear=True)
    def test_empty_string_for_string_env_var(self):
        """Test handling of empty string for string environment variables"""
        config = StorageConfig()
        
        # Empty string is a valid string value
        assert config.get("logging_level") == ""

    def test_os_getenv_exception_handling(self):
        """Test exception handling during environment variable access"""
        # Test the actual behavior - if os.getenv raises exception, it propagates
        with patch('os.getenv', side_effect=OSError("Environment access error")):
            with pytest.raises(OSError, match="Environment access error"):
                StorageConfig()


class TestConfigurationIntegration:
    """Integration test cases for complete configuration scenarios"""

    @patch.dict(os.environ, {
        "AZURE_STORAGE_RETRY_ATTEMPTS": "10",
        "AZURE_STORAGE_LOGGING_LEVEL": "DEBUG"
    }, clear=True)
    def test_full_configuration_workflow(self):
        """Test complete configuration workflow with all features"""
        # Create config with custom values + environment
        custom_config = {
            "retry_attempts": 5,  # Will be overridden by env var
            "custom_setting": "test_value"
        }
        
        config = StorageConfig(custom_config)
        
        # Verify initial state (environment vars override config_dict)
        assert config.get("retry_attempts") == 10  # From environment (overrides custom)
        assert config.get("timeout_seconds") == 30  # Default
        assert config.get("logging_level") == "DEBUG"  # From environment
        assert config.get("custom_setting") == "test_value"  # Custom
        
        # Test get_all
        all_config = config.get_all()
        assert len(all_config) == 4
        
        # Test updates
        config.update({"timeout_seconds": 60, "another_setting": "another_value"})
        assert config.get("timeout_seconds") == 60
        assert config.get("another_setting") == "another_value"
        
        # Test reset
        config.reset_to_defaults()
        assert config.get("retry_attempts") == 10  # From environment
        assert config.get("timeout_seconds") == 30  # Default
        assert config.get("logging_level") == "DEBUG"  # From environment
        assert config.get("custom_setting") is None  # Removed
        assert config.get("another_setting") is None  # Removed

    def test_configuration_immutability_of_defaults(self):
        """Test that DEFAULT_CONFIG is not accidentally modified"""
        original_defaults = StorageConfig.DEFAULT_CONFIG.copy()
        
        # Create multiple configs and modify them
        config1 = StorageConfig()
        config2 = StorageConfig({"retry_attempts": 100})
        
        config1.set("retry_attempts", 50)
        config2.update({"timeout_seconds": 200})
        
        # DEFAULT_CONFIG should remain unchanged
        assert StorageConfig.DEFAULT_CONFIG == original_defaults

    def test_global_and_local_config_independence(self):
        """Test that local configs don't affect global config"""
        global_config = get_config()
        original_retry_attempts = global_config.get("retry_attempts")
        
        # Create and modify local config
        local_config = create_config({"retry_attempts": 999})
        local_config.set("local_key", "local_value")
        
        # Global config should be unchanged
        assert get_config().get("retry_attempts") == original_retry_attempts
        assert get_config().get("local_key") is None
        
        # Local config should have its own values
        assert local_config.get("retry_attempts") == 999
        assert local_config.get("local_key") == "local_value"