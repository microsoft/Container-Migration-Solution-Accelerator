# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock

# Add the backend-api src/app directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../../../backend-api/src/app')))

# Mock Azure modules to avoid import dependency issues  
import types

# Create specific module mocks for Azure packages
azure_module = types.ModuleType('azure')
azure_appconfiguration_module = types.ModuleType('azure.appconfiguration')
azure_identity_module = types.ModuleType('azure.identity')

# Mock the specific classes used
azure_appconfiguration_module.AzureAppConfigurationClient = MagicMock()
azure_identity_module.DefaultAzureCredential = MagicMock()

sys.modules['azure'] = azure_module
sys.modules['azure.appconfiguration'] = azure_appconfiguration_module
sys.modules['azure.identity'] = azure_identity_module

from libs.azure.app_configuration import AppConfigurationHelper


class MockConfigurationSetting:
    """Mock class for Azure App Configuration settings"""
    def __init__(self, key: str, value: str):
        self.key = key
        self.value = value


class TestAppConfigurationHelper:
    """Test cases for AppConfigurationHelper class"""

    def test_init_with_default_credential(self):
        """Test AppConfigurationHelper initialization with default credential"""
        test_url = "https://test-app-config.azconfig.io"
        
        with patch('libs.azure.app_configuration.DefaultAzureCredential') as mock_credential_class:
            mock_credential = Mock()
            mock_credential_class.return_value = mock_credential
            
            with patch.object(AppConfigurationHelper, '_initialize_client') as mock_init:
                helper = AppConfigurationHelper(test_url)
                
                assert helper.app_config_endpoint == test_url
                assert helper.credential == mock_credential
                mock_init.assert_called_once()

    def test_init_with_provided_credential(self):
        """Test AppConfigurationHelper initialization with provided credential"""
        test_url = "https://test-app-config.azconfig.io"
        mock_credential = Mock()
        
        with patch.object(AppConfigurationHelper, '_initialize_client') as mock_init:
            helper = AppConfigurationHelper(test_url, mock_credential)
            
            assert helper.app_config_endpoint == test_url
            assert helper.credential == mock_credential
            mock_init.assert_called_once()

    def test_initialize_client_success(self):
        """Test successful client initialization"""
        test_url = "https://test-app-config.azconfig.io"
        mock_credential = Mock()
        
        with patch('libs.azure.app_configuration.AzureAppConfigurationClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            helper = AppConfigurationHelper(test_url, mock_credential)
            
            assert helper.app_config_client == mock_client
            mock_client_class.assert_called_once_with(test_url, mock_credential)

    def test_initialize_client_with_none_endpoint(self):
        """Test client initialization with None endpoint raises ValueError"""
        mock_credential = Mock()
        
        with patch.object(AppConfigurationHelper, '_initialize_client', AppConfigurationHelper._initialize_client):
            helper = AppConfigurationHelper.__new__(AppConfigurationHelper)
            helper.credential = mock_credential
            helper.app_config_endpoint = None
            
            with pytest.raises(ValueError, match="App Configuration Endpoint is not set."):
                helper._initialize_client()

    def test_read_configuration_success(self):
        """Test successful configuration reading"""
        test_url = "https://test-app-config.azconfig.io"
        mock_credential = Mock()
        
        # Mock configuration settings
        mock_settings = [
            MockConfigurationSetting("setting1", "value1"),
            MockConfigurationSetting("setting2", "value2")
        ]
        
        with patch('libs.azure.app_configuration.AzureAppConfigurationClient') as mock_client_class:
            mock_client = Mock()
            mock_client.list_configuration_settings.return_value = mock_settings
            mock_client_class.return_value = mock_client
            
            helper = AppConfigurationHelper(test_url, mock_credential)
            result = helper.read_configuration()
            
            assert result == mock_settings
            mock_client.list_configuration_settings.assert_called_once()

    def test_read_configuration_empty(self):
        """Test reading configuration when no settings exist"""
        test_url = "https://test-app-config.azconfig.io"
        mock_credential = Mock()
        
        with patch('libs.azure.app_configuration.AzureAppConfigurationClient') as mock_client_class:
            mock_client = Mock()
            mock_client.list_configuration_settings.return_value = []
            mock_client_class.return_value = mock_client
            
            helper = AppConfigurationHelper(test_url, mock_credential)
            result = helper.read_configuration()
            
            assert result == []
            mock_client.list_configuration_settings.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    def test_read_and_set_environmental_variables_success(self):
        """Test successful reading and setting of environment variables"""
        test_url = "https://test-app-config.azconfig.io"
        mock_credential = Mock()
        
        # Mock configuration settings
        mock_settings = [
            MockConfigurationSetting("TEST_VAR1", "value1"),
            MockConfigurationSetting("TEST_VAR2", "value2"),
            MockConfigurationSetting("TEST_VAR3", "value3")
        ]
        
        with patch('libs.azure.app_configuration.AzureAppConfigurationClient') as mock_client_class:
            mock_client = Mock()
            mock_client.list_configuration_settings.return_value = mock_settings
            mock_client_class.return_value = mock_client
            
            helper = AppConfigurationHelper(test_url, mock_credential)
            result = helper.read_and_set_environmental_variables()
            
            # Verify environment variables were set
            assert os.environ.get("TEST_VAR1") == "value1"
            assert os.environ.get("TEST_VAR2") == "value2"
            assert os.environ.get("TEST_VAR3") == "value3"
            
            # Verify the method returns the environment dictionary
            assert isinstance(result, type(os.environ))
            assert result["TEST_VAR2"] == "value2"
            assert result["TEST_VAR3"] == "value3"

    @patch.dict(os.environ, {"EXISTING_VAR": "existing_value"}, clear=True)
    def test_read_and_set_environmental_variables_with_existing_vars(self):
        """Test setting environment variables when some already exist"""
        test_url = "https://test-app-config.azconfig.io"
        mock_credential = Mock()
        
        # Mock configuration settings (one conflicts with existing var)
        mock_settings = [
            MockConfigurationSetting("EXISTING_VAR", "new_value"),
            MockConfigurationSetting("NEW_VAR", "new_value")
        ]
        
        with patch('libs.azure.app_configuration.AzureAppConfigurationClient') as mock_client_class:
            mock_client = Mock()
            mock_client.list_configuration_settings.return_value = mock_settings
            mock_client_class.return_value = mock_client
            
            helper = AppConfigurationHelper(test_url, mock_credential)
            result = helper.read_and_set_environmental_variables()
            
            # Verify existing var was overwritten
            assert os.environ.get("EXISTING_VAR") == "new_value"
            assert os.environ.get("NEW_VAR") == "new_value"
            
            # Verify the method returns the complete environment dictionary
            assert isinstance(result, type(os.environ))
            assert result["EXISTING_VAR"] == "new_value"
            assert result["NEW_VAR"] == "new_value"

    @patch.dict(os.environ, {}, clear=True)
    def test_read_and_set_environmental_variables_empty_config(self):
        """Test setting environment variables when configuration is empty"""
        test_url = "https://test-app-config.azconfig.io"
        mock_credential = Mock()
        
        with patch('libs.azure.app_configuration.AzureAppConfigurationClient') as mock_client_class:
            mock_client = Mock()
            mock_client.list_configuration_settings.return_value = []
            mock_client_class.return_value = mock_client
            
            helper = AppConfigurationHelper(test_url, mock_credential)
            result = helper.read_and_set_environmental_variables()
            
            # Verify the method returns the environment dictionary (though empty)
            assert isinstance(result, type(os.environ))
            # No new environment variables should be set
            mock_client.list_configuration_settings.assert_called_once()

    def test_read_and_set_environmental_variables_with_special_characters(self):
        """Test setting environment variables with special characters in values"""
        test_url = "https://test-app-config.azconfig.io"
        mock_credential = Mock()
        
        # Mock configuration settings with special characters
        mock_settings = [
            MockConfigurationSetting("DB_CONNECTION", "Server=server;Database=db;User=user;Password=p@$$w0rd!"),
            MockConfigurationSetting("API_URL", "https://api.example.com/v1/endpoint?key=value&other=123"),
            MockConfigurationSetting("JSON_CONFIG", '{"key": "value", "nested": {"prop": "test"}}')
        ]
        
        with patch('libs.azure.app_configuration.AzureAppConfigurationClient') as mock_client_class:
            mock_client = Mock()
            mock_client.list_configuration_settings.return_value = mock_settings
            mock_client_class.return_value = mock_client
            
            with patch.dict(os.environ, {}, clear=True):
                helper = AppConfigurationHelper(test_url, mock_credential)
                result = helper.read_and_set_environmental_variables()
                
                # Verify complex values were set correctly
                assert os.environ.get("DB_CONNECTION") == "Server=server;Database=db;User=user;Password=p@$$w0rd!"
                assert os.environ.get("API_URL") == "https://api.example.com/v1/endpoint?key=value&other=123"
                assert os.environ.get("JSON_CONFIG") == '{"key": "value", "nested": {"prop": "test"}}'

    def test_read_and_set_environmental_variables_with_none_values(self):
        """Test handling of configuration settings with None values"""
        test_url = "https://test-app-config.azconfig.io"
        mock_credential = Mock()
        
        # Mock configuration setting with None value
        mock_setting = MockConfigurationSetting("TEST_VAR", None)
        mock_settings = [mock_setting]
        
        with patch('libs.azure.app_configuration.AzureAppConfigurationClient') as mock_client_class:
            mock_client = Mock()
            mock_client.list_configuration_settings.return_value = mock_settings
            mock_client_class.return_value = mock_client
            
            with patch.dict(os.environ, {}, clear=True):
                helper = AppConfigurationHelper(test_url, mock_credential)
                
                # This should raise a TypeError since os.environ doesn't accept None values  
                with pytest.raises(TypeError, match="str expected, not NoneType"):
                    helper.read_and_set_environmental_variables()

    def test_class_attributes_initialized_correctly(self):
        """Test that class attributes are initialized correctly"""
        # Test class attributes are initially None
        assert AppConfigurationHelper.credential is None
        assert AppConfigurationHelper.app_config_endpoint is None
        assert AppConfigurationHelper.app_config_client is None

    def test_integration_flow(self):
        """Test the complete flow from initialization to setting environment variables"""
        test_url = "https://test-app-config.azconfig.io"
        mock_credential = Mock()
        
        mock_settings = [
            MockConfigurationSetting("INTEGRATION_TEST", "success"),
            MockConfigurationSetting("FLOW_TEST", "complete")
        ]
        
        with patch('libs.azure.app_configuration.AzureAppConfigurationClient') as mock_client_class:
            mock_client = Mock()
            mock_client.list_configuration_settings.return_value = mock_settings
            mock_client_class.return_value = mock_client
            
            with patch.dict(os.environ, {}, clear=True):
                # Initialize helper
                helper = AppConfigurationHelper(test_url, mock_credential)
                
                # Verify initialization
                assert helper.app_config_endpoint == test_url
                assert helper.credential == mock_credential
                assert helper.app_config_client == mock_client
                
                # Read configuration
                config = helper.read_configuration()
                assert len(config) == 2
                assert config[0].key == "INTEGRATION_TEST"
                assert config[1].key == "FLOW_TEST"
                
                # Set environment variables
                env_vars = helper.read_and_set_environmental_variables()
                assert os.environ.get("INTEGRATION_TEST") == "success"
                assert os.environ.get("FLOW_TEST") == "complete"
                assert env_vars["INTEGRATION_TEST"] == "success"
                assert env_vars["FLOW_TEST"] == "complete"

    def test_multiple_instances_independence(self):
        """Test that multiple instances of AppConfigurationHelper are independent"""
        test_url1 = "https://test-app-config1.azconfig.io"
        test_url2 = "https://test-app-config2.azconfig.io"
        mock_credential1 = Mock()
        mock_credential2 = Mock()
        
        with patch('libs.azure.app_configuration.AzureAppConfigurationClient') as mock_client_class:
            mock_client1 = Mock()
            mock_client2 = Mock()
            mock_client_class.side_effect = [mock_client1, mock_client2]
            
            helper1 = AppConfigurationHelper(test_url1, mock_credential1)
            helper2 = AppConfigurationHelper(test_url2, mock_credential2)
            
            # Verify instances are independent
            assert helper1.app_config_endpoint == test_url1
            assert helper2.app_config_endpoint == test_url2
            assert helper1.credential == mock_credential1
            assert helper2.credential == mock_credential2
            assert helper1.app_config_client == mock_client1
            assert helper2.app_config_client == mock_client2
            assert helper1.app_config_client != helper2.app_config_client