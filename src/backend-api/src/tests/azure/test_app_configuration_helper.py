import os
from unittest.mock import MagicMock, patch

import pytest

from libs.azure.app_configuration import AppConfigurationHelper


def _patch_client():
    return patch("libs.azure.app_configuration.AzureAppConfigurationClient")


class TestInitialization:
    def test_uses_provided_credential(self):
        cred = MagicMock()
        with _patch_client() as MockClient:
            helper = AppConfigurationHelper(
                "https://example.azconfig.io", credential=cred
            )
            MockClient.assert_called_once_with("https://example.azconfig.io", cred)
        assert helper.credential is cred
        assert helper.app_config_endpoint == "https://example.azconfig.io"
        assert helper.app_config_client is MockClient.return_value

    def test_raises_value_error_when_endpoint_is_none(self):
        with pytest.raises(ValueError, match="App Configuration Endpoint is not set"):
            AppConfigurationHelper(None, credential=MagicMock())

    def test_creates_default_credential_when_none_provided(self):
        with patch(
            "libs.azure.app_configuration.DefaultAzureCredential"
        ) as MockCred, _patch_client():
            MockCred.return_value = MagicMock()
            helper = AppConfigurationHelper("https://example.azconfig.io")
            MockCred.assert_called_once()
            assert helper.credential is MockCred.return_value


class TestReadAndSetEnvironmentalVariables:
    def test_sets_environment_variables_from_settings(self):
        with _patch_client():
            helper = AppConfigurationHelper(
                "https://example.azconfig.io", credential=MagicMock()
            )

        item1 = MagicMock()
        item1.key = "TEST_KEY_ONE"
        item1.value = "value-one"
        item2 = MagicMock()
        item2.key = "TEST_KEY_TWO"
        item2.value = "value-two"

        helper.app_config_client = MagicMock()
        helper.app_config_client.list_configuration_settings.return_value = iter(
            [item1, item2]
        )

        try:
            result = helper.read_and_set_environmental_variables()
            assert os.environ["TEST_KEY_ONE"] == "value-one"
            assert os.environ["TEST_KEY_TWO"] == "value-two"
            assert result is os.environ
        finally:
            os.environ.pop("TEST_KEY_ONE", None)
            os.environ.pop("TEST_KEY_TWO", None)

    def test_read_configuration_delegates_to_client(self):
        with _patch_client():
            helper = AppConfigurationHelper(
                "https://example.azconfig.io", credential=MagicMock()
            )
        helper.app_config_client = MagicMock()
        helper.app_config_client.list_configuration_settings.return_value = "settings"
        assert helper.read_configuration() == "settings"
        helper.app_config_client.list_configuration_settings.assert_called_once()
