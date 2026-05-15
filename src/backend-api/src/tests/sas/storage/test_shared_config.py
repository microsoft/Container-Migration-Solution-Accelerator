"""Tests for libs/sas/storage/shared_config.py."""

import pytest

from libs.sas.storage import shared_config as shared_config_module
from libs.sas.storage.shared_config import (
    StorageConfig,
    create_config,
    get_config,
    set_config,
)


class TestStorageConfigDefaults:
    def test_default_values(self):
        cfg = StorageConfig()
        assert cfg.get("retry_attempts") == 3
        assert cfg.get("timeout_seconds") == 30
        assert cfg.get("logging_level") == "INFO"

    def test_init_with_overrides(self):
        cfg = StorageConfig({"retry_attempts": 7, "extra": "v"})
        assert cfg.get("retry_attempts") == 7
        assert cfg.get("extra") == "v"
        # Other defaults preserved
        assert cfg.get("logging_level") == "INFO"

    def test_init_none_overrides(self):
        cfg = StorageConfig(None)
        assert cfg.get("retry_attempts") == 3


class TestStorageConfigEnvironment:
    def test_loads_env_vars_with_correct_types(self, monkeypatch):
        monkeypatch.setenv("AZURE_STORAGE_RETRY_ATTEMPTS", "10")
        monkeypatch.setenv("AZURE_STORAGE_TIMEOUT_SECONDS", "60")
        monkeypatch.setenv("AZURE_STORAGE_LOGGING_LEVEL", "DEBUG")
        cfg = StorageConfig()
        assert cfg.get("retry_attempts") == 10
        assert cfg.get("timeout_seconds") == 60
        assert cfg.get("logging_level") == "DEBUG"

    def test_skips_invalid_int_env_var(self, monkeypatch):
        monkeypatch.setenv("AZURE_STORAGE_RETRY_ATTEMPTS", "garbage")
        cfg = StorageConfig()
        # Falls back to default
        assert cfg.get("retry_attempts") == 3

    def test_skips_invalid_timeout_env_var(self, monkeypatch):
        monkeypatch.setenv("AZURE_STORAGE_TIMEOUT_SECONDS", "not-an-int")
        cfg = StorageConfig()
        assert cfg.get("timeout_seconds") == 30


class TestStorageConfigGetSet:
    def test_get_with_default(self):
        cfg = StorageConfig()
        assert cfg.get("missing") is None
        assert cfg.get("missing", "fallback") == "fallback"

    def test_set_then_get(self):
        cfg = StorageConfig()
        cfg.set("foo", "bar")
        assert cfg.get("foo") == "bar"

    def test_get_all_returns_copy(self):
        cfg = StorageConfig()
        snapshot = cfg.get_all()
        assert isinstance(snapshot, dict)
        snapshot["new_key"] = "x"
        assert cfg.get("new_key") is None  # underlying dict not affected

    def test_update_multiple(self):
        cfg = StorageConfig()
        cfg.update({"a": 1, "b": 2})
        assert cfg.get("a") == 1
        assert cfg.get("b") == 2

    def test_reset_to_defaults_restores(self):
        cfg = StorageConfig()
        cfg.set("retry_attempts", 99)
        cfg.reset_to_defaults()
        assert cfg.get("retry_attempts") == 3


class TestModuleLevelHelpers:
    def test_get_config_returns_default(self):
        assert get_config() is shared_config_module.default_config

    def test_set_config_replaces_default(self):
        original = get_config()
        try:
            new_cfg = StorageConfig({"x": 1})
            set_config(new_cfg)
            assert get_config() is new_cfg
            assert get_config().get("x") == 1
        finally:
            set_config(original)

    def test_create_config_returns_new_instance(self):
        cfg = create_config({"y": "z"})
        assert isinstance(cfg, StorageConfig)
        assert cfg.get("y") == "z"

    def test_create_config_no_overrides(self):
        cfg = create_config()
        assert isinstance(cfg, StorageConfig)
        assert cfg.get("retry_attempts") == 3
