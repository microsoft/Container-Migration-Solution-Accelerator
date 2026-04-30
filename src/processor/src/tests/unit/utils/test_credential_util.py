# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Tests for utils.credential_util."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils import credential_util


_AZURE_INDICATORS = [
    "WEBSITE_SITE_NAME",
    "AZURE_CLIENT_ID",
    "MSI_ENDPOINT",
    "IDENTITY_ENDPOINT",
    "KUBERNETES_SERVICE_HOST",
    "CONTAINER_REGISTRY_LOGIN",
]


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for name in _AZURE_INDICATORS:
        monkeypatch.delenv(name, raising=False)


# ---------- get_azure_credential ----------


def test_get_azure_credential_uses_user_assigned_managed_identity(monkeypatch):
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-123")
    fake_cred = MagicMock(name="MICredential")
    with patch.object(
        credential_util, "ManagedIdentityCredential", return_value=fake_cred
    ) as mi:
        out = credential_util.get_azure_credential()
    assert out is fake_cred
    mi.assert_called_once_with(client_id="client-123")


def test_get_azure_credential_uses_system_assigned_managed_identity(monkeypatch):
    monkeypatch.setenv("MSI_ENDPOINT", "https://example/msi")
    fake_cred = MagicMock(name="MICredential")
    with patch.object(
        credential_util, "ManagedIdentityCredential", return_value=fake_cred
    ) as mi:
        out = credential_util.get_azure_credential()
    assert out is fake_cred
    mi.assert_called_once_with()


def test_get_azure_credential_returns_first_cli_credential():
    cli_cred = MagicMock(name="cli")
    azd_cred = MagicMock(name="azd")
    with (
        patch.object(credential_util, "AzureCliCredential", return_value=cli_cred),
        patch.object(
            credential_util, "AzureDeveloperCliCredential", return_value=azd_cred
        ),
    ):
        out = credential_util.get_azure_credential()
    assert out is cli_cred


def test_get_azure_credential_falls_back_to_azd_when_cli_fails():
    azd_cred = MagicMock(name="azd")
    with (
        patch.object(
            credential_util, "AzureCliCredential", side_effect=RuntimeError("boom")
        ),
        patch.object(
            credential_util, "AzureDeveloperCliCredential", return_value=azd_cred
        ),
    ):
        out = credential_util.get_azure_credential()
    assert out is azd_cred


def test_get_azure_credential_falls_back_to_default_when_both_fail():
    default_cred = MagicMock(name="default")
    with (
        patch.object(
            credential_util, "AzureCliCredential", side_effect=RuntimeError("a")
        ),
        patch.object(
            credential_util,
            "AzureDeveloperCliCredential",
            side_effect=RuntimeError("b"),
        ),
        patch.object(
            credential_util, "DefaultAzureCredential", return_value=default_cred
        ),
    ):
        out = credential_util.get_azure_credential()
    assert out is default_cred


# ---------- get_async_azure_credential ----------


def test_get_async_azure_credential_user_assigned(monkeypatch):
    monkeypatch.setenv("AZURE_CLIENT_ID", "x")
    fake_cred = MagicMock()
    with patch.object(
        credential_util, "AsyncManagedIdentityCredential", return_value=fake_cred
    ) as mi:
        out = credential_util.get_async_azure_credential()
    assert out is fake_cred
    mi.assert_called_once_with(client_id="x")


def test_get_async_azure_credential_system_assigned(monkeypatch):
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "1.2.3.4")
    fake_cred = MagicMock()
    with patch.object(
        credential_util, "AsyncManagedIdentityCredential", return_value=fake_cred
    ) as mi:
        out = credential_util.get_async_azure_credential()
    assert out is fake_cred
    mi.assert_called_once_with()


def test_get_async_azure_credential_first_cli_wins():
    cli_cred = MagicMock()
    azd_cred = MagicMock()
    with (
        patch.object(credential_util, "AsyncAzureCliCredential", return_value=cli_cred),
        patch.object(
            credential_util,
            "AsyncAzureDeveloperCliCredential",
            return_value=azd_cred,
        ),
    ):
        out = credential_util.get_async_azure_credential()
    assert out is cli_cred


def test_get_async_azure_credential_fallback_to_default():
    default_cred = MagicMock()
    with (
        patch.object(
            credential_util, "AsyncAzureCliCredential", side_effect=RuntimeError("x")
        ),
        patch.object(
            credential_util,
            "AsyncAzureDeveloperCliCredential",
            side_effect=RuntimeError("y"),
        ),
        patch.object(
            credential_util, "AsyncDefaultAzureCredential", return_value=default_cred
        ),
    ):
        out = credential_util.get_async_azure_credential()
    assert out is default_cred


# ---------- bearer token providers ----------


def test_get_bearer_token_provider_wraps_credential():
    cred = MagicMock()
    sentinel_provider = MagicMock(name="provider")
    with (
        patch.object(credential_util, "get_azure_credential", return_value=cred),
        patch.object(
            credential_util,
            "identity_get_bearer_token_provider",
            return_value=sentinel_provider,
        ) as gp,
    ):
        out = credential_util.get_bearer_token_provider()
    assert out is sentinel_provider
    gp.assert_called_once_with(cred, "https://cognitiveservices.azure.com/.default")


def test_get_async_bearer_token_provider_wraps_async_credential():
    import asyncio

    cred = MagicMock()
    sentinel_provider = MagicMock(name="async-provider")
    with (
        patch.object(
            credential_util,
            "get_async_azure_credential",
            new=AsyncMock(return_value=cred),
        ),
        patch.object(
            credential_util,
            "identity_get_async_bearer_token_provider",
            return_value=sentinel_provider,
        ) as gp,
    ):
        out = asyncio.run(credential_util.get_async_bearer_token_provider())
    assert out is sentinel_provider
    gp.assert_called_once_with(cred, "https://cognitiveservices.azure.com/.default")


# ---------- validate_azure_authentication ----------


def test_validate_authentication_local_development_path():
    fake_cred = MagicMock()
    fake_cred.__class__.__name__ = "AzureCliCredential"
    with patch.object(credential_util, "get_azure_credential", return_value=fake_cred):
        info = credential_util.validate_azure_authentication()
    assert info["environment"] == "local_development"
    assert info["credential_type"] == "cli_credentials"
    assert info["status"] == "configured"
    assert info["azure_env_indicators"] == {}
    assert any("Azure Developer CLI" in r for r in info["recommendations"])


def test_validate_authentication_azure_user_assigned_mi(monkeypatch):
    monkeypatch.setenv("WEBSITE_SITE_NAME", "site")
    monkeypatch.setenv("AZURE_CLIENT_ID", "uami-id")
    fake_cred = MagicMock()
    with patch.object(credential_util, "get_azure_credential", return_value=fake_cred):
        info = credential_util.validate_azure_authentication()
    assert info["environment"] == "azure_hosted"
    assert info["credential_type"] == "managed_identity"
    assert "WEBSITE_SITE_NAME" in info["azure_env_indicators"]
    assert any("user-assigned" in r for r in info["recommendations"])
    assert info["status"] == "configured"


def test_validate_authentication_azure_system_assigned_mi(monkeypatch):
    monkeypatch.setenv("MSI_ENDPOINT", "https://msi")
    fake_cred = MagicMock()
    with patch.object(credential_util, "get_azure_credential", return_value=fake_cred):
        info = credential_util.validate_azure_authentication()
    assert info["environment"] == "azure_hosted"
    assert any("system-assigned" in r for r in info["recommendations"])


def test_validate_authentication_records_error_when_credential_setup_fails():
    with patch.object(
        credential_util,
        "get_azure_credential",
        side_effect=RuntimeError("nope"),
    ):
        info = credential_util.validate_azure_authentication()
    assert info["status"] == "error"
    assert info["error"] == "nope"
    assert any("Authentication setup failed" in r for r in info["recommendations"])
