# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import pytest

from libs.agent_framework.agent_framework_settings import AgentFrameworkSettings


@pytest.fixture
def clear_azure_env(monkeypatch):
    """Wipe AZURE_OPENAI_* env vars before each test so service discovery is deterministic."""
    for key in [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_BASE_URL",
        "AZURE_OPENAI_TEXT_DEPLOYMENT_NAME",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_init_with_no_custom_prefixes(clear_azure_env):
    s = AgentFrameworkSettings()
    assert s.use_entra_id is True
    assert s.custom_service_prefixes == {}
    assert s.service_configs == {}


def test_init_with_custom_prefixes(monkeypatch, clear_azure_env):
    monkeypatch.setenv("CUSTOM_ENDPOINT", "https://x.openai.azure.com/")
    monkeypatch.setenv("CUSTOM_CHAT_DEPLOYMENT_NAME", "gpt-4")
    s = AgentFrameworkSettings(custom_service_prefixes={"alt": "CUSTOM"})
    assert "alt" in s.service_configs
    assert s.has_service("alt") is True


def test_get_service_config_returns_none_for_unknown(clear_azure_env):
    s = AgentFrameworkSettings()
    assert s.get_service_config("unknown") is None


def test_discovers_default_when_env_present(monkeypatch, clear_azure_env):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4")
    s = AgentFrameworkSettings()
    assert "default" in s.service_configs
    assert s.get_available_services() == ["default"]
    cfg = s.get_service_config("default")
    assert cfg is not None
    assert cfg.endpoint == "https://x.openai.azure.com/"


def test_refresh_services(monkeypatch, clear_azure_env):
    s = AgentFrameworkSettings()
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4")
    s.refresh_services()
    assert s.has_service("default") is True


def test_load_env_file_loads_values(tmp_path, monkeypatch, clear_azure_env):
    f = tmp_path / "test.env"
    f.write_text(
        '# comment line\n'
        'AZURE_OPENAI_ENDPOINT="https://from-file.openai.azure.com/"\n'
        "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME='gpt-4'\n"
        "EMPTY_LINE_BELOW=\n"
        "\n"
    )
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", raising=False)
    s = AgentFrameworkSettings(env_file_path=str(f))
    # env loaded → discover_services should pick it up
    assert s.has_service("default") is True


def test_load_env_file_missing_path_is_ignored(clear_azure_env):
    # Non-existent file path passes the os.path.exists check and is silently ignored
    s = AgentFrameworkSettings(env_file_path="/nope/does/not/exist.env")
    assert s.use_entra_id is True


def test_load_env_file_unreadable_raises(tmp_path, monkeypatch, clear_azure_env):
    f = tmp_path / "bad.env"
    f.write_text("ok\n")
    s = AgentFrameworkSettings()
    # Open _load_env_file directly to test error wrapping
    monkeypatch.setattr(
        "builtins.open",
        lambda *a, **k: (_ for _ in ()).throw(OSError("permission denied")),
    )
    with pytest.raises(ValueError, match="Error loading environment file"):
        s._load_env_file(str(f))


def test_load_env_file_not_found_raises(clear_azure_env):
    s = AgentFrameworkSettings()
    with pytest.raises(ValueError, match="Environment file not found"):
        # Bypass os.path.exists check by calling private method directly
        s._load_env_file("/definitely/does/not/exist.env")
