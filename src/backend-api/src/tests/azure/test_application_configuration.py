import pytest
from azure.core.exceptions import (
    ClientAuthenticationError,
)

from libs.azure.app_configuration import AppConfigurationHelper

app_config_url = "https://example.azconfig.io"


def test_app_configuration_helper_initialization():
    helper = AppConfigurationHelper(app_config_url)

    assert helper.app_config_endpoint == app_config_url
    assert helper.app_config_client is not None


def test_app_configuration_helper_read_configuration():
    helper = AppConfigurationHelper(app_config_url)
    assert helper.read_configuration()._page_iterator is None


def test_app_configuration_helper_read_and_set_environmental_variables():
    helper = AppConfigurationHelper(app_config_url)
    with pytest.raises(ClientAuthenticationError):
        list(helper.read_configuration())
