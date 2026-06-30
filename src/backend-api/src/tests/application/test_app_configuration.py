import os

from pydantic_settings import BaseSettings

from libs.application.application_configuration import (
    Configuration,
    _configuration_base,
    _envConfiguration,
)


def test_configuration_base():
    config = _configuration_base()
    assert isinstance(config, BaseSettings)


def test_configuration_fields():
    config = Configuration()
    assert isinstance(config, _configuration_base)
    assert hasattr(config, "app_sample_variable")
    assert isinstance(config.app_sample_variable, str)
    assert (
        config.app_sample_variable
        == "Hello World!"  # Default value from Configuration class
    )
    assert hasattr(config, "app_logging_enable")
    assert isinstance(config.app_logging_enable, bool)
    assert config.app_logging_enable is False  # Default from Configuration class

    assert hasattr(config, "azure_package_logging_level")
    assert isinstance(config.azure_package_logging_level, str)
    assert config.azure_package_logging_level == "WARNING"  # Default from Configuration class

    assert hasattr(config, "azure_logging_packages")
    assert config.azure_logging_packages is None  # Default from Configuration class

    assert hasattr(config, "app_logging_level")
    assert isinstance(config.app_logging_level, str)
    assert config.app_logging_level == "INFO"

    # Test if the field can be overridden
    config.app_sample_variable = "new_value"
    assert config.app_sample_variable == "new_value"


def test_envConfiguration():
    os.environ["APP_CONFIGURATION_URL"] = "http://example.com/config"

    env_config = _envConfiguration()
    assert isinstance(env_config, _configuration_base)
    assert hasattr(env_config, "app_configuration_url")
    assert env_config.app_configuration_url == "http://example.com/config"
    os.environ["APP_CONFIGURATION_URL"] = ""
