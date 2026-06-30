"""
Shared configuration settings for Azure Storage Helpers
"""

import os
from typing import Dict, Any


class StorageConfig:
    """Shared configuration class for Azure Storage helpers"""

    # Default settings shared across storage helpers
    DEFAULT_CONFIG = {
        "retry_attempts": 3,
        "timeout_seconds": 30,
        "logging_level": "INFO",
    }

    def __init__(self, config_dict: Dict[str, Any] = None):
        """
        Initialize configuration

        Args:
            config_dict: Dictionary of configuration overrides
        """
        self.config = self.DEFAULT_CONFIG.copy()

        if config_dict:
            self.config.update(config_dict)

        # Load from environment variables
        self._load_from_environment()

    def _load_from_environment(self):
        """Load configuration from environment variables"""
        env_mappings = {
            "AZURE_STORAGE_RETRY_ATTEMPTS": ("retry_attempts", int),
            "AZURE_STORAGE_TIMEOUT_SECONDS": ("timeout_seconds", int),
            "AZURE_STORAGE_LOGGING_LEVEL": ("logging_level", str),
        }

        for env_var, (config_key, data_type) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    self.config[config_key] = data_type(value)
                except ValueError:
                    # Skip invalid values
                    pass

    def get(self, key: str, default=None):
        """Get configuration value"""
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """Set configuration value"""
        self.config[key] = value

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values"""
        return self.config.copy()

    def update(self, updates: Dict[str, Any]):
        """Update multiple configuration values"""
        self.config.update(updates)

    def reset_to_defaults(self):
        """Reset configuration to default values"""
        self.config = self.DEFAULT_CONFIG.copy()
        self._load_from_environment()


# Global configuration instance
default_config = StorageConfig()


def get_config() -> StorageConfig:
    """Get the global configuration instance"""
    return default_config


def set_config(config: StorageConfig):
    """Set the global configuration instance"""
    global default_config
    default_config = config


def create_config(config_dict: Dict[str, Any] = None) -> StorageConfig:
    """Create a new configuration instance"""
    return StorageConfig(config_dict)
