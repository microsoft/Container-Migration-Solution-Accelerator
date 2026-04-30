# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for AgentFrameworkSettings."""

from __future__ import annotations

import os

import pytest

from libs.agent_framework.agent_framework_settings import AgentFrameworkSettings


def _set_default_env(monkeypatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-x")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-01-01")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "secret")


def test_init_discovers_default_service(monkeypatch) -> None:
    _set_default_env(monkeypatch)

    settings = AgentFrameworkSettings()

    assert settings.has_service("default")
    assert settings.get_service_config("default") is not None
    assert "default" in settings.get_available_services()


def test_init_with_custom_service_prefix(monkeypatch) -> None:
    _set_default_env(monkeypatch)
    monkeypatch.setenv("MYSVC_ENDPOINT", "https://other.openai.azure.com/")
    monkeypatch.setenv("MYSVC_CHAT_DEPLOYMENT_NAME", "gpt-other")
    monkeypatch.setenv("MYSVC_API_VERSION", "2024-02-01")
    monkeypatch.setenv("MYSVC_API_KEY", "k")

    settings = AgentFrameworkSettings(custom_service_prefixes={"mysvc": "MYSVC"})

    assert settings.has_service("default")
    assert settings.has_service("mysvc")


def test_init_skips_invalid_service_with_missing_endpoint(monkeypatch, capsys) -> None:
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

    settings = AgentFrameworkSettings(use_entra_id=False)

    out = capsys.readouterr().out
    assert "Incomplete service configuration" in out
    assert not settings.has_service("default")
    assert settings.get_service_config("default") is None
    assert settings.get_available_services() == []


def test_load_env_file_sets_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("MYTEST_VAR", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        '# comment line\nMYTEST_VAR="value with spaces"\nAZURE_OPENAI_ENDPOINT=https://from-env.azure.com/\nAZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-y\nAZURE_OPENAI_API_KEY=k\n\n'
    )

    settings = AgentFrameworkSettings(env_file_path=str(env_file), use_entra_id=False)

    assert os.environ.get("MYTEST_VAR") == "value with spaces"
    # Cleanup so other tests aren't polluted
    monkeypatch.delenv("MYTEST_VAR", raising=False)
    assert settings.has_service("default")


def test_load_env_file_does_not_overwrite_existing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MYTEST_EXISTING", "preserved")
    _set_default_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text("MYTEST_EXISTING=overwritten\n")

    AgentFrameworkSettings(env_file_path=str(env_file))

    assert os.environ["MYTEST_EXISTING"] == "preserved"


def test_load_env_file_missing_path_is_ignored(monkeypatch) -> None:
    _set_default_env(monkeypatch)
    # Path doesn't exist on disk → __init__ never calls _load_env_file
    s = AgentFrameworkSettings(env_file_path="/no/such/file/.env")
    assert s.has_service("default")


def test_load_env_file_invalid_content_raises_value_error(monkeypatch, tmp_path) -> None:
    _set_default_env(monkeypatch)
    bad = tmp_path / "bad.env"
    bad.write_bytes(b"\xff\xfe invalid utf-8 \xc3\x28")

    with pytest.raises(ValueError):
        AgentFrameworkSettings(env_file_path=str(bad))


def test_refresh_services_repopulates(monkeypatch) -> None:
    _set_default_env(monkeypatch)

    settings = AgentFrameworkSettings()
    assert settings.has_service("default")

    # Add custom prefix vars then refresh
    monkeypatch.setenv("EXTRA_ENDPOINT", "https://extra.openai.azure.com/")
    monkeypatch.setenv("EXTRA_CHAT_DEPLOYMENT_NAME", "gpt-e")
    monkeypatch.setenv("EXTRA_API_VERSION", "2024-03-01")
    monkeypatch.setenv("EXTRA_API_KEY", "k")
    settings.custom_service_prefixes["extra"] = "EXTRA"

    settings.refresh_services()
    assert settings.has_service("extra")


def test_get_service_config_unknown_returns_none(monkeypatch) -> None:
    _set_default_env(monkeypatch)
    settings = AgentFrameworkSettings()
    assert settings.get_service_config("unknown") is None


def test_init_default_when_custom_prefixes_none(monkeypatch) -> None:
    _set_default_env(monkeypatch)
    s = AgentFrameworkSettings(custom_service_prefixes=None)
    assert s.custom_service_prefixes == {}
