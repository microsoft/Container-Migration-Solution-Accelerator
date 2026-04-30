"""Tests for app_configuration helper module."""
import os
from unittest.mock import Mock, patch, MagicMock
import pytest
from azure.identity import DefaultAzureCredential
from azure.appconfiguration import AzureAppConfigurationClient

from libs.azure.app_configuration import AppConfigurationHelper


def test_app_configuration_helper_initialization():
    """Test AppConfigurationHelper initialization."""
    with patch("libs.azure.app_configuration.AzureAppConfigurationClient") as mock_client:
        helper = AppConfigurationHelper(
            app_configuration_url="https://test.azconfig.io", credential=None
        )

        assert helper.app_config_endpoint == "https://test.azconfig.io"
        assert helper.credential is not None  # DefaultAzureCredential created


def test_app_configuration_helper_with_provided_credential():
    """Test AppConfigurationHelper initialization with provided credential."""
    with patch("libs.azure.app_configuration.AzureAppConfigurationClient") as mock_client:
        credential = Mock(spec=DefaultAzureCredential)
        helper = AppConfigurationHelper(
            app_configuration_url="https://test.azconfig.io", credential=credential
        )

        assert helper.credential is credential


def test_app_configuration_helper_initialize_client_valid_endpoint():
    """Test client initialization with valid endpoint."""
    with patch("libs.azure.app_configuration.AzureAppConfigurationClient") as mock_client:
        helper = AppConfigurationHelper(
            app_configuration_url="https://test.azconfig.io"
        )

        # Verify AzureAppConfigurationClient was called with correct parameters
        assert mock_client.called


def test_app_configuration_helper_initialize_client_none_endpoint():
    """Test client initialization raises error with None endpoint."""
    with pytest.raises(ValueError, match="App Configuration Endpoint is not set"):
        # Should raise error during initialization
        AppConfigurationHelper(app_configuration_url=None)


def test_app_configuration_helper_read_configuration():
    """Test reading configuration settings."""
    mock_client = Mock(spec=AzureAppConfigurationClient)
    mock_setting1 = Mock()
    mock_setting1.key = "TEST_KEY1"
    mock_setting1.value = "test_value1"

    mock_setting2 = Mock()
    mock_setting2.key = "TEST_KEY2"
    mock_setting2.value = "test_value2"

    mock_client.list_configuration_settings.return_value = [
        mock_setting1,
        mock_setting2,
    ]

    with patch(
        "libs.azure.app_configuration.AzureAppConfigurationClient",
        return_value=mock_client,
    ):
        helper = AppConfigurationHelper(app_configuration_url="https://test.azconfig.io")
        settings = helper.read_configuration()

        assert len(settings) == 2
        assert settings[0].key == "TEST_KEY1"
        assert settings[1].key == "TEST_KEY2"


def test_app_configuration_helper_read_and_set_environmental_variables():
    """Test reading configuration and setting environment variables."""
    mock_client = Mock(spec=AzureAppConfigurationClient)
    mock_setting1 = Mock()
    mock_setting1.key = "TEST_ENV_VAR1"
    mock_setting1.value = "env_value1"

    mock_setting2 = Mock()
    mock_setting2.key = "TEST_ENV_VAR2"
    mock_setting2.value = "env_value2"

    mock_client.list_configuration_settings.return_value = [
        mock_setting1,
        mock_setting2,
    ]

    with patch(
        "libs.azure.app_configuration.AzureAppConfigurationClient",
        return_value=mock_client,
    ):
        helper = AppConfigurationHelper(app_configuration_url="https://test.azconfig.io")

        # Clear test env vars if they exist
        if "TEST_ENV_VAR1" in os.environ:
            del os.environ["TEST_ENV_VAR1"]
        if "TEST_ENV_VAR2" in os.environ:
            del os.environ["TEST_ENV_VAR2"]

        result = helper.read_and_set_environmental_variables()

        # Verify environment variables were set
        assert "TEST_ENV_VAR1" in result
        assert result["TEST_ENV_VAR1"] == "env_value1"
        assert "TEST_ENV_VAR2" in result
        assert result["TEST_ENV_VAR2"] == "env_value2"

        # Clean up
        del os.environ["TEST_ENV_VAR1"]
        del os.environ["TEST_ENV_VAR2"]


def test_app_configuration_helper_multiple_calls():
    """Test multiple calls to read configuration."""
    mock_client = Mock(spec=AzureAppConfigurationClient)
    mock_setting = Mock()
    mock_setting.key = "TEST_KEY"
    mock_setting.value = "test_value"

    mock_client.list_configuration_settings.return_value = [mock_setting]

    with patch(
        "libs.azure.app_configuration.AzureAppConfigurationClient",
        return_value=mock_client,
    ):
        helper = AppConfigurationHelper(app_configuration_url="https://test.azconfig.io")

        settings1 = helper.read_configuration()
        settings2 = helper.read_configuration()

        assert len(settings1) == len(settings2)
        assert mock_client.list_configuration_settings.call_count == 2
