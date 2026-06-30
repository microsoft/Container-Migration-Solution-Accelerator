"""
Configuration settings for Azure Storage Blob Helper
"""

import os
from typing import Dict, Any
from ..shared_config import StorageConfig


class BlobHelperConfig(StorageConfig):
    """Configuration class for StorageBlobHelper"""

    # Default settings for blob operations
    DEFAULT_CONFIG = {
        **StorageConfig.DEFAULT_CONFIG,  # Inherit shared settings
        "max_single_upload_size": 64 * 1024 * 1024,  # 64MB
        "max_block_size": 4 * 1024 * 1024,  # 4MB
        "max_single_get_size": 32 * 1024 * 1024,  # 32MB
        "max_chunk_get_size": 4 * 1024 * 1024,  # 4MB
        "default_blob_tier": "Hot",
        "default_container_access": None,
        "sync_exclude_patterns": ["*.tmp", "*.log", "*.swp", ".DS_Store", "Thumbs.db"],
        "content_type_mappings": {
            ".txt": "text/plain",
            ".html": "text/html",
            ".htm": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".xml": "application/xml",
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".ppt": "application/vnd.ms-powerpoint",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".webp": "image/webp",
            ".mp4": "video/mp4",
            ".avi": "video/x-msvideo",
            ".mov": "video/quicktime",
            ".wmv": "video/x-ms-wmv",
            ".flv": "video/x-flv",
            ".webm": "video/webm",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".flac": "audio/flac",
            ".aac": "audio/aac",
            ".ogg": "audio/ogg",
            ".zip": "application/zip",
            ".rar": "application/x-rar-compressed",
            ".7z": "application/x-7z-compressed",
            ".tar": "application/x-tar",
            ".gz": "application/gzip",
            ".bz2": "application/x-bzip2",
            ".exe": "application/x-msdownload",
            ".msi": "application/x-msdownload",
            ".deb": "application/x-debian-package",
            ".rpm": "application/x-redhat-package-manager",
        },
    }

    def __init__(self, config_dict: Dict[str, Any] = None):
        """
        Initialize configuration

        Args:
            config_dict: Dictionary of configuration overrides
        """
        super().__init__(config_dict)

    def _load_from_environment(self):
        """Load configuration from environment variables"""
        # Load shared environment variables first
        super()._load_from_environment()

        # Add blob-specific environment variables
        blob_env_mappings = {
            "AZURE_STORAGE_MAX_UPLOAD_SIZE": ("max_single_upload_size", int),
            "AZURE_STORAGE_MAX_BLOCK_SIZE": ("max_block_size", int),
            "AZURE_STORAGE_DEFAULT_TIER": ("default_blob_tier", str),
        }

        for env_var, (config_key, data_type) in blob_env_mappings.items():
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

    def get_content_type(self, file_extension: str) -> str:
        """Get content type for file extension"""
        return self.config["content_type_mappings"].get(
            file_extension.lower(), "application/octet-stream"
        )

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
default_config = BlobHelperConfig()


def get_config() -> BlobHelperConfig:
    """Get the global configuration instance"""
    return default_config


def set_config(config: BlobHelperConfig):
    """Set the global configuration instance"""
    global default_config
    default_config = config


def create_config(config_dict: Dict[str, Any] = None) -> BlobHelperConfig:
    """Create a new configuration instance"""
    return BlobHelperConfig(config_dict)
