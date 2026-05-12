# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils import credential_util


@pytest.fixture(autouse=True)
def _clear_azure_env(monkeypatch):
    """Ensure each test starts with a clean env."""
    for key in [
        "WEBSITE_SITE_NAME",
        "AZURE_CLIENT_ID",
        "MSI_ENDPOINT",
        "IDENTITY_ENDPOINT",
        "KUBERNETES_SERVICE_HOST",
        "CONTAINER_REGISTRY_LOGIN",
    ]:
        monkeypatch.delenv(key, raising=False)


class TestGetAzureCredentialSync:
    def test_azure_environment_with_user_assigned_returns_managed_identity(
        self, monkeypatch
    ):
        monkeypatch.setenv("AZURE_CLIENT_ID", "client-123")
        with patch.object(credential_util, "ManagedIdentityCredential") as mic:
            mic.return_value = MagicMock(name="managed")
            cred = credential_util.get_azure_credential()
            mic.assert_called_once_with(client_id="client-123")
            assert cred is mic.return_value

    def test_azure_environment_without_client_id_uses_system_assigned(
        self, monkeypatch
    ):
        monkeypatch.setenv("WEBSITE_SITE_NAME", "site")
        with patch.object(credential_util, "ManagedIdentityCredential") as mic:
            mic.return_value = MagicMock(name="managed")
            credential_util.get_azure_credential()
            mic.assert_called_once_with()

    def test_local_returns_first_successful_cli_credential(self):
        with patch.object(credential_util, "AzureCliCredential") as cli, patch.object(
            credential_util, "AzureDeveloperCliCredential"
        ) as azd:
            cli.return_value = MagicMock(name="cli")
            azd.return_value = MagicMock(name="azd")
            cred = credential_util.get_azure_credential()
            assert cred is cli.return_value

    def test_local_falls_back_to_default_when_all_cli_fail(self):
        with patch.object(
            credential_util, "AzureCliCredential", side_effect=RuntimeError("nope")
        ), patch.object(
            credential_util,
            "AzureDeveloperCliCredential",
            side_effect=RuntimeError("nope"),
        ), patch.object(credential_util, "DefaultAzureCredential") as default:
            default.return_value = MagicMock(name="default")
            cred = credential_util.get_azure_credential()
            assert cred is default.return_value


class TestGetAsyncAzureCredential:
    def test_async_azure_environment_user_assigned(self, monkeypatch):
        monkeypatch.setenv("AZURE_CLIENT_ID", "client-xyz")
        with patch.object(credential_util, "AsyncManagedIdentityCredential") as mic:
            mic.return_value = MagicMock(name="async-managed")
            cred = credential_util.get_async_azure_credential()
            mic.assert_called_once_with(client_id="client-xyz")
            assert cred is mic.return_value

    def test_async_azure_environment_system_assigned(self, monkeypatch):
        monkeypatch.setenv("MSI_ENDPOINT", "http://msi/")
        with patch.object(credential_util, "AsyncManagedIdentityCredential") as mic:
            mic.return_value = MagicMock(name="async-managed")
            credential_util.get_async_azure_credential()
            mic.assert_called_once_with()

    def test_async_local_uses_first_successful(self):
        with patch.object(credential_util, "AsyncAzureCliCredential") as cli, patch.object(
            credential_util, "AsyncAzureDeveloperCliCredential"
        ) as azd:
            cli.return_value = MagicMock(name="async-cli")
            azd.return_value = MagicMock(name="async-azd")
            cred = credential_util.get_async_azure_credential()
            assert cred is cli.return_value

    def test_async_local_falls_back_to_default(self):
        with patch.object(
            credential_util,
            "AsyncAzureCliCredential",
            side_effect=RuntimeError("nope"),
        ), patch.object(
            credential_util,
            "AsyncAzureDeveloperCliCredential",
            side_effect=RuntimeError("nope"),
        ), patch.object(credential_util, "AsyncDefaultAzureCredential") as default:
            default.return_value = MagicMock(name="async-default")
            cred = credential_util.get_async_azure_credential()
            assert cred is default.return_value


class TestBearerTokenProviders:
    def test_get_bearer_token_provider_uses_credential(self):
        with patch.object(
            credential_util, "get_azure_credential", return_value=MagicMock()
        ) as cred_fn, patch.object(
            credential_util, "identity_get_bearer_token_provider"
        ) as token_fn:
            token_fn.return_value = "token-callable"
            res = credential_util.get_bearer_token_provider()
            cred_fn.assert_called_once()
            token_fn.assert_called_once()
            assert res == "token-callable"

    def test_async_get_bearer_token_provider_uses_credential(self):
        import asyncio

        with patch.object(
            credential_util, "get_async_azure_credential", new=AsyncMock(return_value=MagicMock())
        ) as cred_fn, patch.object(
            credential_util, "identity_get_async_bearer_token_provider"
        ) as token_fn:
            token_fn.return_value = "async-token-callable"
            res = asyncio.run(credential_util.get_async_bearer_token_provider())
            cred_fn.assert_called_once()
            token_fn.assert_called_once()
            assert res == "async-token-callable"


class TestValidateAzureAuthentication:
    def test_local_environment_recommendations(self):
        # Use a real dummy class so __class__.__name__ is set naturally,
        # without mutating MagicMock's class name globally (which leaks across tests).
        class AzureCliCredential:
            pass

        cred = AzureCliCredential()
        with patch.object(credential_util, "get_azure_credential", return_value=cred):
            info = credential_util.validate_azure_authentication()
            assert info["environment"] == "local_development"
            assert info["status"] == "configured"

    def test_azure_hosted_with_user_assigned(self, monkeypatch):
        monkeypatch.setenv("AZURE_CLIENT_ID", "uami-id")
        with patch.object(
            credential_util, "get_azure_credential", return_value=MagicMock()
        ):
            info = credential_util.validate_azure_authentication()
            assert info["environment"] == "azure_hosted"
            assert info["credential_type"] == "managed_identity"

    def test_azure_hosted_system_assigned(self, monkeypatch):
        monkeypatch.setenv("WEBSITE_SITE_NAME", "site")
        with patch.object(
            credential_util, "get_azure_credential", return_value=MagicMock()
        ):
            info = credential_util.validate_azure_authentication()
            assert info["environment"] == "azure_hosted"

    def test_credential_failure_reports_error(self):
        with patch.object(
            credential_util,
            "get_azure_credential",
            side_effect=RuntimeError("creds bad"),
        ):
            info = credential_util.validate_azure_authentication()
            assert info["status"] == "error"
            assert "creds bad" in info["error"]
