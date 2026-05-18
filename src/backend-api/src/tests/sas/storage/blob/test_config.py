"""Tests for libs/sas/storage/blob/config.py."""

from libs.sas.storage.blob import config as blob_config_module
from libs.sas.storage.blob.config import (
    BlobHelperConfig,
    create_config,
    get_config,
    set_config,
)


class TestBlobHelperConfigDefaults:
    def test_inherits_shared_defaults(self):
        cfg = BlobHelperConfig()
        assert cfg.get("retry_attempts") == 3
        assert cfg.get("timeout_seconds") == 30
        assert cfg.get("logging_level") == "INFO"

    def test_blob_specific_defaults(self):
        cfg = BlobHelperConfig()
        assert cfg.get("max_single_upload_size") == 64 * 1024 * 1024
        assert cfg.get("max_block_size") == 4 * 1024 * 1024
        assert cfg.get("default_blob_tier") == "Hot"
        assert "*.tmp" in cfg.get("sync_exclude_patterns")

    def test_init_with_overrides(self):
        cfg = BlobHelperConfig({"max_block_size": 999, "custom_key": "v"})
        assert cfg.get("max_block_size") == 999
        assert cfg.get("custom_key") == "v"
        # Other defaults preserved
        assert cfg.get("default_blob_tier") == "Hot"


class TestBlobHelperConfigEnvironment:
    def test_loads_env_vars_with_correct_types(self, monkeypatch):
        monkeypatch.setenv("AZURE_STORAGE_MAX_UPLOAD_SIZE", "12345")
        monkeypatch.setenv("AZURE_STORAGE_MAX_BLOCK_SIZE", "678")
        monkeypatch.setenv("AZURE_STORAGE_DEFAULT_TIER", "Cool")
        cfg = BlobHelperConfig()
        assert cfg.get("max_single_upload_size") == 12345
        assert cfg.get("max_block_size") == 678
        assert cfg.get("default_blob_tier") == "Cool"

    def test_skips_invalid_int_env_var(self, monkeypatch):
        monkeypatch.setenv("AZURE_STORAGE_MAX_UPLOAD_SIZE", "not-a-number")
        cfg = BlobHelperConfig()
        # Falls back to default when conversion fails
        assert cfg.get("max_single_upload_size") == 64 * 1024 * 1024

    def test_inherits_shared_env_loading(self, monkeypatch):
        monkeypatch.setenv("AZURE_STORAGE_RETRY_ATTEMPTS", "9")
        cfg = BlobHelperConfig()
        assert cfg.get("retry_attempts") == 9


class TestBlobHelperConfigGetSet:
    def test_get_returns_default_for_unknown_key(self):
        cfg = BlobHelperConfig()
        assert cfg.get("missing_key") is None
        assert cfg.get("missing_key", "fallback") == "fallback"

    def test_set_then_get(self):
        cfg = BlobHelperConfig()
        cfg.set("new_key", "new_val")
        assert cfg.get("new_key") == "new_val"

    def test_get_all_returns_copy(self):
        cfg = BlobHelperConfig()
        all_cfg = cfg.get_all()
        assert isinstance(all_cfg, dict)
        all_cfg["mutate"] = "x"
        assert cfg.get("mutate") is None  # original untouched

    def test_update_multiple_keys(self):
        cfg = BlobHelperConfig()
        cfg.update({"a": 1, "b": 2})
        assert cfg.get("a") == 1
        assert cfg.get("b") == 2

    def test_reset_to_defaults_restores_defaults(self):
        cfg = BlobHelperConfig()
        cfg.set("max_block_size", 99)
        cfg.reset_to_defaults()
        assert cfg.get("max_block_size") == 4 * 1024 * 1024


class TestGetContentType:
    def test_known_extension(self):
        cfg = BlobHelperConfig()
        assert cfg.get_content_type(".txt") == "text/plain"
        assert cfg.get_content_type(".PDF") == "application/pdf"  # case-insensitive

    def test_unknown_extension_returns_octet_stream(self):
        cfg = BlobHelperConfig()
        assert cfg.get_content_type(".xyz123") == "application/octet-stream"


class TestModuleLevelHelpers:
    def test_get_config_returns_default(self):
        assert get_config() is blob_config_module.default_config

    def test_set_config_replaces_default(self):
        original = get_config()
        try:
            new_cfg = BlobHelperConfig({"flag": True})
            set_config(new_cfg)
            assert get_config() is new_cfg
            assert get_config().get("flag") is True
        finally:
            set_config(original)

    def test_create_config_returns_new_instance(self):
        cfg = create_config({"x": 1})
        assert isinstance(cfg, BlobHelperConfig)
        assert cfg.get("x") == 1

    def test_create_config_no_overrides(self):
        cfg = create_config()
        assert isinstance(cfg, BlobHelperConfig)
        assert cfg.get("default_blob_tier") == "Hot"
