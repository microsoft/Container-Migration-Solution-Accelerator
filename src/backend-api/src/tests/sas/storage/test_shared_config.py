"""Tests for src/app/libs/sas/storage/shared_config.py"""

import os
from unittest.mock import patch
from libs.sas.storage.shared_config import (
    StorageConfig,
    get_config,
    set_config,
    create_config,
)


def test_storage_config_init_default():
    """Test StorageConfig initialization with defaults"""
    config = StorageConfig()
    assert config is not None
    assert config.get("retry_attempts") == 3
    assert config.get("timeout_seconds") == 30
    assert config.get("logging_level") == "INFO"


def test_storage_config_init_with_dict():
    """Test StorageConfig initialization with custom dict"""
    custom_config = {
        "retry_attempts": 5,
        "timeout_seconds": 60,
        "logging_level": "DEBUG",
    }
    config = StorageConfig(custom_config)
    assert config.get("retry_attempts") == 5
    assert config.get("timeout_seconds") == 60
    assert config.get("logging_level") == "DEBUG"


def test_storage_config_partial_override():
    """Test StorageConfig with partial configuration override"""
    config = StorageConfig({"retry_attempts": 10})
    assert config.get("retry_attempts") == 10
    # Other values should remain as defaults
    assert config.get("timeout_seconds") == 30
    assert config.get("logging_level") == "INFO"


def test_storage_config_get_method():
    """Test StorageConfig.get() method"""
    config = StorageConfig()
    assert config.get("retry_attempts") == 3
    assert config.get("nonexistent_key", "default_value") == "default_value"
    assert config.get("nonexistent_key") is None


def test_storage_config_set_method():
    """Test StorageConfig.set() method"""
    config = StorageConfig()
    config.set("custom_key", "custom_value")
    assert config.get("custom_key") == "custom_value"
    
    config.set("retry_attempts", 7)
    assert config.get("retry_attempts") == 7


def test_storage_config_get_all():
    """Test StorageConfig.get_all() method"""
    custom_config = {"retry_attempts": 5}
    config = StorageConfig(custom_config)
    all_config = config.get_all()
    
    assert isinstance(all_config, dict)
    assert all_config["retry_attempts"] == 5
    assert all_config["timeout_seconds"] == 30
    assert all_config["logging_level"] == "INFO"


def test_storage_config_update():
    """Test StorageConfig.update() method"""
    config = StorageConfig()
    config.update({
        "retry_attempts": 8,
        "custom_key": "custom_value",
    })
    assert config.get("retry_attempts") == 8
    assert config.get("custom_key") == "custom_value"
    # timeout_seconds should still be the default
    assert config.get("timeout_seconds") == 30


def test_storage_config_reset_to_defaults():
    """Test StorageConfig.reset_to_defaults() method"""
    config = StorageConfig({"retry_attempts": 100})
    assert config.get("retry_attempts") == 100
    
    config.reset_to_defaults()
    assert config.get("retry_attempts") == 3
    assert config.get("timeout_seconds") == 30
    assert config.get("logging_level") == "INFO"


@patch.dict(os.environ, {
    "AZURE_STORAGE_RETRY_ATTEMPTS": "5",
    "AZURE_STORAGE_TIMEOUT_SECONDS": "45",
    "AZURE_STORAGE_LOGGING_LEVEL": "DEBUG",
})
def test_storage_config_load_from_environment():
    """Test StorageConfig loads from environment variables"""
    config = StorageConfig()
    assert config.get("retry_attempts") == 5
    assert config.get("timeout_seconds") == 45
    assert config.get("logging_level") == "DEBUG"


@patch.dict(os.environ, {"AZURE_STORAGE_RETRY_ATTEMPTS": "invalid"}, clear=False)
def test_storage_config_invalid_env_value():
    """Test StorageConfig skips invalid environment variable values"""
    config = StorageConfig()
    # Should skip invalid value and use default
    assert config.get("retry_attempts") == 3


@patch.dict(os.environ, {"AZURE_STORAGE_RETRY_ATTEMPTS": "10"}, clear=False)
def test_storage_config_env_override_precedence():
    """Test environment variables take precedence over dict config"""
    # When using dict config with env var, env var should override
    config = StorageConfig({"retry_attempts": 5})
    # The config dict is applied first, then env vars override
    assert config.get("retry_attempts") == 10


def test_get_config_returns_global_instance():
    """Test get_config returns a StorageConfig instance"""
    config = get_config()
    assert isinstance(config, StorageConfig)


def test_set_config_updates_global():
    """Test set_config updates the global configuration"""
    original_config = get_config()
    original_retry = original_config.get("retry_attempts")
    
    new_config = StorageConfig({"retry_attempts": 99})
    set_config(new_config)
    
    global_config = get_config()
    assert global_config.get("retry_attempts") == 99
    
    # Restore original config
    set_config(original_config)


def test_create_config_returns_new_instance():
    """Test create_config returns a new StorageConfig instance"""
    config1 = create_config()
    config2 = create_config()
    
    assert isinstance(config1, StorageConfig)
    assert isinstance(config2, StorageConfig)
    assert config1 is not config2


def test_create_config_with_dict():
    """Test create_config with custom dictionary"""
    custom = {"retry_attempts": 15, "timeout_seconds": 90}
    config = create_config(custom)
    
    assert config.get("retry_attempts") == 15
    assert config.get("timeout_seconds") == 90


def test_storage_config_get_all_is_copy():
    """Test that get_all() returns a copy, not reference"""
    config = StorageConfig()
    all_config = config.get_all()
    
    # Modify the returned dict
    all_config["retry_attempts"] = 999
    
    # Original config should be unchanged
    assert config.get("retry_attempts") == 3


def test_storage_config_default_config_dict():
    """Test that DEFAULT_CONFIG contains expected keys"""
    config = StorageConfig()
    defaults = StorageConfig.DEFAULT_CONFIG
    
    assert "retry_attempts" in defaults
    assert "timeout_seconds" in defaults
    assert "logging_level" in defaults
    assert defaults["retry_attempts"] == 3
    assert defaults["timeout_seconds"] == 30
    assert defaults["logging_level"] == "INFO"
