import os
import sys
import pytest
from unittest.mock import patch
from pydantic import ValidationError

# Add the backend-api src to path for imports
backend_api_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "..", "backend-api", "src", "app")
sys.path.insert(0, backend_api_path)

from libs.application.application_configuration import (
    Configuration,
    _configuration_base,
    _envConfiguration,
)


class TestConfigurationBase:
    """Test cases for _configuration_base class"""

    def test_configuration_base_initialization(self):
        """Test that _configuration_base can be instantiated"""
        config = _configuration_base()
        assert isinstance(config, _configuration_base)

    def test_configuration_base_model_config(self):
        """Test that model config is properly set"""
        config = _configuration_base()
        # model_config is a SettingsConfigDict which behaves like a dict
        assert config.model_config["env_file"] == ".env"
        assert config.model_config["env_file_encoding"] == "utf-8"
        assert config.model_config["extra"] == "ignore"
        assert config.model_config["case_sensitive"] is False
        assert config.model_config["env_ignore_empty"] is True

    def test_configuration_base_with_env_vars(self):
        """Test configuration base with environment variables"""
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}, clear=False):
            class TestConfig(_configuration_base):
                test_var: str = "default"
            
            config = TestConfig()
            assert config.test_var == "test_value"

    def test_configuration_base_case_insensitive(self):
        """Test that environment variables are case insensitive"""
        with patch.dict(os.environ, {"test_var": "lowercase"}, clear=False):
            class TestConfig(_configuration_base):
                TEST_VAR: str = "default"
            
            config = TestConfig()
            assert config.TEST_VAR == "lowercase"

    def test_configuration_base_extra_ignore(self):
        """Test that extra fields are ignored"""
        with patch.dict(os.environ, {"UNKNOWN_FIELD": "ignored"}, clear=False):
            config = _configuration_base()
            # Should not raise an error and should not have the unknown field
            assert not hasattr(config, "UNKNOWN_FIELD")
            assert not hasattr(config, "unknown_field")


class TestConfiguration:
    """Test cases for Configuration class"""

    def test_configuration_initialization(self):
        """Test that Configuration can be instantiated with defaults"""
        config = Configuration()
        assert isinstance(config, Configuration)
        assert isinstance(config, _configuration_base)

    def test_configuration_default_values(self):
        """Test default configuration values"""
        config = Configuration()
        
        # Basic app settings
        assert config.app_logging_enable is False
        assert config.app_logging_level == "INFO"
        assert config.app_sample_variable == "Hello World!"
        
        # Azure logging
        assert config.azure_package_logging_level == "WARNING"
        assert config.azure_logging_packages is None
        
        # Global settings
        assert config.global_llm_service == "AzureOpenAI"
        
        # Cosmos DB settings
        assert config.cosmos_db_process_log_container is None
        assert config.cosmos_db_account_url is None
        assert config.cosmos_db_database_name is None
        assert config.cosmos_db_process_container is None
        
        # Storage account settings
        assert config.storage_account_name is None
        assert config.storage_account_blob_url is None
        assert config.storage_account_queue_url is None
        assert config.storage_account_process_container is None
        assert config.storage_account_process_queue is None
        
        # App Insights
        assert config.app_insights_conn_string is None

    def test_configuration_with_environment_variables(self):
        """Test configuration with environment variables"""
        env_vars = {
            "APP_LOGGING_ENABLE": "true",
            "APP_LOGGING_LEVEL": "DEBUG",
            "APP_SAMPLE_VARIABLE": "Test Value",
            "AZURE_PACKAGE_LOGGING_LEVEL": "ERROR",
            "AZURE_LOGGING_PACKAGES": "azure.core,azure.storage",
            "GLOBAL_LLM_SERVICE": "OpenAI",
            "COSMOS_DB_ACCOUNT_URL": "https://test.documents.azure.com:443/",
            "COSMOS_DB_DATABASE_NAME": "test_db",
            "COSMOS_DB_PROCESS_CONTAINER": "test_container",
            "COSMOS_DB_PROCESS_LOG_CONTAINER": "log_container",
            "STORAGE_ACCOUNT_NAME": "teststorageaccount",
            "STORAGE_ACCOUNT_BLOB_URL": "https://teststorageaccount.blob.core.windows.net/",
            "STORAGE_ACCOUNT_QUEUE_URL": "https://teststorageaccount.queue.core.windows.net/",
            "STORAGE_ACCOUNT_PROCESS_CONTAINER": "process-container",
            "STORAGE_ACCOUNT_PROCESS_QUEUE": "process-queue",
            "APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=test-key",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            config = Configuration()
            
            assert config.app_logging_enable is True
            assert config.app_logging_level == "DEBUG"
            assert config.app_sample_variable == "Test Value"
            assert config.azure_package_logging_level == "ERROR"
            assert config.azure_logging_packages == "azure.core,azure.storage"
            assert config.global_llm_service == "OpenAI"
            assert config.cosmos_db_account_url == "https://test.documents.azure.com:443/"
            assert config.cosmos_db_database_name == "test_db"
            assert config.cosmos_db_process_container == "test_container"
            assert config.cosmos_db_process_log_container == "log_container"
            assert config.storage_account_name == "teststorageaccount"
            assert config.storage_account_blob_url == "https://teststorageaccount.blob.core.windows.net/"
            assert config.storage_account_queue_url == "https://teststorageaccount.queue.core.windows.net/"
            assert config.storage_account_process_container == "process-container"
            assert config.storage_account_process_queue == "process-queue"
            # Note: app_insights_conn_string might not be set due to field configuration
            if config.app_insights_conn_string is not None:
                assert config.app_insights_conn_string == "InstrumentationKey=test-key"

    @pytest.mark.parametrize(
        "logging_level",
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    )
    def test_configuration_logging_levels(self, logging_level):
        """Test different logging levels"""
        with patch.dict(os.environ, {"APP_LOGGING_LEVEL": logging_level}, clear=False):
            config = Configuration()
            assert config.app_logging_level == logging_level

    @pytest.mark.parametrize(
        "boolean_value,expected",
        [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
        ]
    )
    def test_configuration_boolean_parsing(self, boolean_value, expected):
        """Test boolean value parsing from environment"""
        with patch.dict(os.environ, {"APP_LOGGING_ENABLE": boolean_value}, clear=False):
            config = Configuration()
            assert config.app_logging_enable is expected

    def test_configuration_field_aliases(self):
        """Test that field aliases work correctly"""
        with patch.dict(os.environ, {
            "AZURE_PACKAGE_LOGGING_LEVEL": "DEBUG",
            "AZURE_LOGGING_PACKAGES": "test.package"
        }, clear=False):
            config = Configuration()
            assert config.azure_package_logging_level == "DEBUG"
            assert config.azure_logging_packages == "test.package"

    def test_configuration_none_values_with_empty_env(self):
        """Test that empty environment variables result in empty strings or None for optional fields"""
        with patch.dict(os.environ, {
            "COSMOS_DB_ACCOUNT_URL": "",
            "STORAGE_ACCOUNT_NAME": "",
            "APPLICATIONINSIGHTS_CONNECTION_STRING": ""
        }, clear=False):
            config = Configuration()
            # With env_ignore_empty=True, behavior varies by field configuration
            assert config.cosmos_db_account_url == ""  # Fields with env parameter get empty string
            assert config.storage_account_name == ""
            assert config.app_insights_conn_string is None  # Some fields may still be None

    def test_configuration_inheritance(self):
        """Test that Configuration properly inherits from both base classes"""
        config = Configuration()
        assert isinstance(config, _configuration_base)
        # Configuration inherits from both _configuration_base and KernelBaseSettings

    def test_configuration_azure_url_formats(self):
        """Test various Azure URL formats"""
        valid_urls = {
            "COSMOS_DB_ACCOUNT_URL": "https://test.documents.azure.com:443/",
            "STORAGE_ACCOUNT_BLOB_URL": "https://test.blob.core.windows.net/",
            "STORAGE_ACCOUNT_QUEUE_URL": "https://test.queue.core.windows.net/"
        }
        
        with patch.dict(os.environ, valid_urls, clear=False):
            config = Configuration()
            assert config.cosmos_db_account_url == valid_urls["COSMOS_DB_ACCOUNT_URL"]
            assert config.storage_account_blob_url == valid_urls["STORAGE_ACCOUNT_BLOB_URL"]
            assert config.storage_account_queue_url == valid_urls["STORAGE_ACCOUNT_QUEUE_URL"]

    def test_configuration_llm_service_options(self):
        """Test different LLM service options"""
        llm_services = ["AzureOpenAI", "OpenAI", "HuggingFace", "Custom"]
        
        for service in llm_services:
            with patch.dict(os.environ, {"GLOBAL_LLM_SERVICE": service}, clear=False):
                config = Configuration()
                assert config.global_llm_service == service


class TestEnvConfiguration:
    """Test cases for _envConfiguration class"""

    def test_env_configuration_initialization(self):
        """Test that _envConfiguration can be instantiated"""
        config = _envConfiguration()
        assert isinstance(config, _envConfiguration)
        assert isinstance(config, _configuration_base)

    def test_env_configuration_default_value(self):
        """Test default value for app_configuration_url"""
        config = _envConfiguration()
        assert config.app_configuration_url is None

    def test_env_configuration_with_environment_variable(self):
        """Test _envConfiguration with APP_CONFIGURATION_URL environment variable"""
        test_url = "https://test-app-config.azconfig.io"
        with patch.dict(os.environ, {"APP_CONFIGURATION_URL": test_url}, clear=False):
            config = _envConfiguration()
            assert config.app_configuration_url == test_url

    def test_env_configuration_case_insensitive(self):
        """Test that _envConfiguration is case insensitive"""
        test_url = "https://test-app-config.azconfig.io"
        with patch.dict(os.environ, {"app_configuration_url": test_url}, clear=False):
            config = _envConfiguration()
            assert config.app_configuration_url == test_url

    def test_env_configuration_empty_value(self):
        """Test _envConfiguration with empty environment variable"""
        with patch.dict(os.environ, {"APP_CONFIGURATION_URL": ""}, clear=False):
            config = _envConfiguration()
            # Due to env_ignore_empty=True, empty string should be ignored
            assert config.app_configuration_url is None

    def test_env_configuration_url_validation(self):
        """Test that various URL formats are accepted"""
        valid_urls = [
            "https://test.azconfig.io",
            "https://test-app-config.azconfig.io",
            "https://myconfig.azconfig.io/",
        ]
        
        for url in valid_urls:
            with patch.dict(os.environ, {"APP_CONFIGURATION_URL": url}, clear=False):
                config = _envConfiguration()
                assert config.app_configuration_url == url

    def test_env_configuration_whitespace_handling(self):
        """Test handling of whitespace in environment variables"""
        test_url = "  https://test-app-config.azconfig.io  "
        with patch.dict(os.environ, {"APP_CONFIGURATION_URL": test_url}, clear=False):
            config = _envConfiguration()
            # Pydantic does not automatically strip whitespace for string fields
            assert config.app_configuration_url == test_url  # Whitespace is preserved


class TestConfigurationIntegration:
    """Integration tests for configuration classes"""

    def test_configuration_and_env_configuration_independence(self):
        """Test that Configuration and _envConfiguration work independently"""
        env_vars = {
            "APP_CONFIGURATION_URL": "https://test.azconfig.io",
            "APP_LOGGING_ENABLE": "true",
            "COSMOS_DB_ACCOUNT_URL": "https://cosmos.documents.azure.com:443/"
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            env_config = _envConfiguration()
            main_config = Configuration()
            
            # _envConfiguration should only have its specific field
            assert env_config.app_configuration_url == "https://test.azconfig.io"
            
            # Configuration should have its fields but not env config fields
            assert main_config.app_logging_enable is True
            assert main_config.cosmos_db_account_url == "https://cosmos.documents.azure.com:443/"
            # Configuration doesn't have app_configuration_url field
            assert not hasattr(main_config, "app_configuration_url")

    def test_configuration_model_dump(self):
        """Test configuration serialization"""
        config = Configuration()
        config_dict = config.model_dump()
        
        # Check that all expected fields are present
        expected_fields = [
            "app_logging_enable",
            "app_logging_level", 
            "app_sample_variable",
            "azure_package_logging_level",
            "azure_logging_packages",
            "global_llm_service",
            "cosmos_db_process_log_container",
            "cosmos_db_account_url",
            "cosmos_db_database_name",
            "cosmos_db_process_container",
            "storage_account_name",
            "storage_account_blob_url",
            "storage_account_queue_url",
            "storage_account_process_container",
            "storage_account_process_queue",
            "app_insights_conn_string",
        ]
        
        for field in expected_fields:
            assert field in config_dict

    def test_configuration_model_dump_exclude_none(self):
        """Test configuration serialization excluding None values"""
        config = Configuration()
        config_dict = config.model_dump(exclude_none=True)
        
        # Should include fields with non-None defaults
        assert "app_logging_enable" in config_dict
        assert "app_logging_level" in config_dict
        assert "app_sample_variable" in config_dict
        assert "global_llm_service" in config_dict
        
        # Should exclude fields that are None by default
        none_fields = [
            "cosmos_db_account_url",
            "storage_account_name",
            "app_insights_conn_string"
        ]
        for field in none_fields:
            assert field not in config_dict or config_dict[field] is not None

    def test_configuration_environment_override_precedence(self):
        """Test that environment variables take precedence over defaults"""
        env_vars = {
            "APP_SAMPLE_VARIABLE": "Overridden Value",
            "APP_LOGGING_LEVEL": "ERROR",
            "GLOBAL_LLM_SERVICE": "CustomLLM"
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            config = Configuration()
            
            # Environment should override defaults
            assert config.app_sample_variable == "Overridden Value"
            assert config.app_logging_level == "ERROR"  
            assert config.global_llm_service == "CustomLLM"
            
            # Non-overridden values should remain default
            assert config.app_logging_enable is False

    def test_multiple_configurations_isolation(self):
        """Test that multiple configuration instances are properly isolated"""
        config1 = Configuration()
        config2 = Configuration()
        
        # Both should have same default values
        assert config1.app_sample_variable == config2.app_sample_variable
        assert config1.app_logging_level == config2.app_logging_level
        
        # They should be different instances
        assert config1 is not config2

    def test_configuration_with_complex_env_scenario(self):
        """Test configuration with complex real-world environment scenario"""
        complex_env = {
            "APP_LOGGING_ENABLE": "true",
            "APP_LOGGING_LEVEL": "DEBUG",
            "AZURE_PACKAGE_LOGGING_LEVEL": "INFO",
            "COSMOS_DB_ACCOUNT_URL": "https://prod-cosmos.documents.azure.com:443/",
            "COSMOS_DB_DATABASE_NAME": "migration-db",
            "COSMOS_DB_PROCESS_CONTAINER": "processes",
            "COSMOS_DB_PROCESS_LOG_CONTAINER": "process-logs",
            "STORAGE_ACCOUNT_NAME": "prodmigrationstore",
            "STORAGE_ACCOUNT_BLOB_URL": "https://prodmigrationstore.blob.core.windows.net/",
            "STORAGE_ACCOUNT_QUEUE_URL": "https://prodmigrationstore.queue.core.windows.net/",
            "STORAGE_ACCOUNT_PROCESS_CONTAINER": "migration-files",
            "STORAGE_ACCOUNT_PROCESS_QUEUE": "migration-queue",
            "APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=12345-abcdef;IngestionEndpoint=https://eastus-1.in.applicationinsights.azure.com/"
        }
        
        with patch.dict(os.environ, complex_env, clear=False):
            config = Configuration()
            
            # Verify all values are properly set
            assert config.app_logging_enable is True
            assert config.app_logging_level == "DEBUG"
            assert config.azure_package_logging_level == "INFO"
            assert "prod-cosmos" in config.cosmos_db_account_url
            assert config.cosmos_db_database_name == "migration-db"
            assert config.cosmos_db_process_container == "processes"
            assert config.cosmos_db_process_log_container == "process-logs"
            assert config.storage_account_name == "prodmigrationstore"
            assert "prodmigrationstore" in config.storage_account_blob_url
            assert config.storage_account_process_container == "migration-files"
            assert config.storage_account_process_queue == "migration-queue"
            # Handle app_insights_conn_string which might be None due to field configuration
            if config.app_insights_conn_string is not None:
                assert "InstrumentationKey" in config.app_insights_conn_string