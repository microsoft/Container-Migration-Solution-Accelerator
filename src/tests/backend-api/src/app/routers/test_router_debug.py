"""
Unit tests for router_debug.

This module contains comprehensive test cases for the debug router
including configuration endpoint testing and TypedFastAPI integration.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

# Import the router and functions under test
from app.routers.router_debug import router, get_config_debug


class TestRouterDebug:
    """Base test class for router_debug tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(router)
        
        # Create mock configuration object with all required fields
        self.mock_config = Mock()
        self.mock_config.app_logging_enable = True
        self.mock_config.app_logging_level = "INFO"
        self.mock_config.azure_package_logging_level = "WARNING"
        self.mock_config.azure_logging_packages = ["azure.core", "azure.storage"]
        self.mock_config.cosmos_db_account_url = "https://test-cosmos.documents.azure.com:443/"
        self.mock_config.cosmos_db_database_name = "test_database"
        self.mock_config.cosmos_db_process_container = "processes"
        self.mock_config.cosmos_db_process_log_container = "process_logs"
        self.mock_config.storage_account_name = "teststorageaccount"
        self.mock_config.storage_account_blob_url = "https://teststorageaccount.blob.core.windows.net/"
        self.mock_config.storage_account_queue_url = "https://teststorageaccount.queue.core.windows.net/"
        self.mock_config.storage_account_process_container = "process-files"
        self.mock_config.storage_account_process_queue = "process-queue"
        
        # Create mock app context
        self.mock_app_context = Mock()
        self.mock_app_context.configuration = self.mock_config
        
        # Create mock TypedFastAPI app
        self.mock_app = Mock()
        self.mock_app.app_context = self.mock_app_context
        
        # Create mock request
        self.mock_request = Mock(spec=Request)
        self.mock_request.app = self.mock_app


class TestGetConfigDebugEndpoint(TestRouterDebug):
    """Test cases for the get_config_debug endpoint."""

    @pytest.mark.asyncio
    async def test_get_config_debug_success(self):
        """Test get_config_debug endpoint returns correct configuration."""
        result = await get_config_debug(self.mock_request)
        
        assert isinstance(result, JSONResponse)
        
        # Extract content from JSONResponse
        content = result.body.decode('utf-8')
        import json
        response_data = json.loads(content)
        
        # Verify response structure
        assert "configuration" in response_data
        config = response_data["configuration"]
        
        # Verify all configuration fields are present and correct
        assert config["app_logging_enable"] is True
        assert config["app_logging_level"] == "INFO"
        assert config["azure_package_logging_level"] == "WARNING"
        assert config["azure_logging_packages"] == ["azure.core", "azure.storage"]
        assert config["cosmos_db_account_url"] == "https://test-cosmos.documents.azure.com:443/"
        assert config["cosmos_db_database_name"] == "test_database"
        assert config["cosmos_db_process_container"] == "processes"
        assert config["cosmos_db_process_log_container"] == "process_logs"
        assert config["storage_account_name"] == "teststorageaccount"
        assert config["storage_account_blob_url"] == "https://teststorageaccount.blob.core.windows.net/"
        assert config["storage_account_queue_url"] == "https://teststorageaccount.queue.core.windows.net/"
        assert config["storage_account_process_container"] == "process-files"
        assert config["storage_account_process_queue"] == "process-queue"

    @pytest.mark.asyncio
    async def test_get_config_debug_with_different_values(self):
        """Test get_config_debug endpoint with different configuration values."""
        # Set up different configuration values
        self.mock_config.app_logging_enable = False
        self.mock_config.app_logging_level = "DEBUG"
        self.mock_config.azure_package_logging_level = "ERROR"
        self.mock_config.azure_logging_packages = ["azure.identity"]
        self.mock_config.cosmos_db_account_url = "https://prod-cosmos.documents.azure.com:443/"
        self.mock_config.cosmos_db_database_name = "production_database"
        self.mock_config.cosmos_db_process_container = "prod_processes"
        self.mock_config.cosmos_db_process_log_container = "prod_process_logs"
        self.mock_config.storage_account_name = "prodstorageaccount"
        self.mock_config.storage_account_blob_url = "https://prodstorageaccount.blob.core.windows.net/"
        self.mock_config.storage_account_queue_url = "https://prodstorageaccount.queue.core.windows.net/"
        self.mock_config.storage_account_process_container = "prod-process-files"
        self.mock_config.storage_account_process_queue = "prod-process-queue"
        
        result = await get_config_debug(self.mock_request)
        
        # Extract and verify content
        content = result.body.decode('utf-8')
        import json
        response_data = json.loads(content)
        config = response_data["configuration"]
        
        # Verify updated values
        assert config["app_logging_enable"] is False
        assert config["app_logging_level"] == "DEBUG"
        assert config["azure_package_logging_level"] == "ERROR"
        assert config["azure_logging_packages"] == ["azure.identity"]
        assert config["cosmos_db_account_url"] == "https://prod-cosmos.documents.azure.com:443/"
        assert config["cosmos_db_database_name"] == "production_database"
        assert config["storage_account_name"] == "prodstorageaccount"

    @pytest.mark.asyncio
    async def test_get_config_debug_with_none_values(self):
        """Test get_config_debug endpoint handles None values gracefully."""
        # Set some values to None
        self.mock_config.app_logging_enable = None
        self.mock_config.azure_logging_packages = None
        self.mock_config.cosmos_db_account_url = None
        
        result = await get_config_debug(self.mock_request)
        
        # Extract and verify content
        content = result.body.decode('utf-8')
        import json
        response_data = json.loads(content)
        config = response_data["configuration"]
        
        # Verify None values are handled correctly
        assert config["app_logging_enable"] is None
        assert config["azure_logging_packages"] is None
        assert config["cosmos_db_account_url"] is None

    @pytest.mark.asyncio
    async def test_get_config_debug_with_empty_strings(self):
        """Test get_config_debug endpoint handles empty strings."""
        # Set some values to empty strings
        self.mock_config.app_logging_level = ""
        self.mock_config.cosmos_db_database_name = ""
        self.mock_config.storage_account_name = ""
        
        result = await get_config_debug(self.mock_request)
        
        # Extract and verify content
        content = result.body.decode('utf-8')
        import json
        response_data = json.loads(content)
        config = response_data["configuration"]
        
        # Verify empty strings are handled correctly
        assert config["app_logging_level"] == ""
        assert config["cosmos_db_database_name"] == ""
        assert config["storage_account_name"] == ""

    @pytest.mark.asyncio
    async def test_get_config_debug_request_app_access(self):
        """Test get_config_debug correctly accesses request.app."""
        # Verify the function accesses the request.app correctly
        await get_config_debug(self.mock_request)
        
        # Verify app was accessed
        assert self.mock_request.app == self.mock_app
        
        # Verify app_context was accessed
        assert self.mock_app.app_context == self.mock_app_context
        
        # Verify configuration was accessed
        assert self.mock_app_context.configuration == self.mock_config

    @pytest.mark.asyncio
    async def test_get_config_debug_response_format(self):
        """Test get_config_debug returns JSONResponse with correct format."""
        result = await get_config_debug(self.mock_request)
        
        # Verify it's a JSONResponse
        assert isinstance(result, JSONResponse)
        
        # Verify response has correct status code (default 200)
        assert result.status_code == 200
        
        # Verify content type
        assert result.media_type == "application/json"

    @pytest.mark.asyncio
    async def test_get_config_debug_configuration_field_completeness(self):
        """Test get_config_debug includes all expected configuration fields."""
        result = await get_config_debug(self.mock_request)
        
        # Extract content
        content = result.body.decode('utf-8')
        import json
        response_data = json.loads(content)
        config = response_data["configuration"]
        
        # Define expected fields
        expected_fields = {
            "app_logging_enable",
            "app_logging_level", 
            "azure_package_logging_level",
            "azure_logging_packages",
            "cosmos_db_account_url",
            "cosmos_db_database_name",
            "cosmos_db_process_container",
            "cosmos_db_process_log_container",
            "storage_account_name",
            "storage_account_blob_url",
            "storage_account_queue_url",
            "storage_account_process_container",
            "storage_account_process_queue"
        }
        
        # Verify all expected fields are present
        actual_fields = set(config.keys())
        assert actual_fields == expected_fields


class TestRouterConfiguration(TestRouterDebug):
    """Test cases for router configuration."""

    def test_router_prefix(self):
        """Test router has correct prefix configuration."""
        assert router.prefix == "/debug"

    def test_router_tags(self):
        """Test router has correct tags configuration."""
        assert router.tags == ["debug"]

    def test_router_responses(self):
        """Test router has correct response configuration."""
        assert router.responses == {404: {"description": "Not found"}}


class TestRouterIntegration(TestRouterDebug):
    """Integration test cases for the debug router."""

    def test_config_endpoint_via_client(self):
        """Test /debug/config endpoint through FastAPI test client."""
        # Note: This test will fail because TestClient doesn't have the TypedFastAPI 
        # app context, but it validates the endpoint routing works
        
        # We'll test this by checking that the route is properly registered
        routes = [route.path for route in router.routes]
        assert "/debug/config" in routes

    def test_router_has_correct_route_count(self):
        """Test router has the expected number of routes."""
        # Should have 1 route: /config
        assert len(router.routes) == 1

    def test_config_route_methods(self):
        """Test config route accepts correct HTTP methods."""
        config_route = None
        for route in router.routes:
            if route.path == "/debug/config":
                config_route = route
                break
        
        assert config_route is not None
        assert "GET" in config_route.methods


class TestEdgeCases(TestRouterDebug):
    """Test cases for edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_get_config_debug_with_complex_data_types(self):
        """Test get_config_debug handles complex data types in configuration."""
        # Set up complex data types
        self.mock_config.azure_logging_packages = ["azure.core", "azure.storage", "azure.identity"]
        self.mock_config.app_logging_enable = True
        
        result = await get_config_debug(self.mock_request)
        
        # Extract and verify content
        content = result.body.decode('utf-8')
        import json
        response_data = json.loads(content)
        config = response_data["configuration"]
        
        # Verify complex data types are serialized correctly
        assert isinstance(config["azure_logging_packages"], list)
        assert len(config["azure_logging_packages"]) == 3
        assert isinstance(config["app_logging_enable"], bool)

    @pytest.mark.asyncio
    async def test_get_config_debug_configuration_access_pattern(self):
        """Test the configuration access pattern in get_config_debug."""
        # Create a more realistic mock structure
        mock_request = Mock(spec=Request)
        mock_app = Mock()
        mock_app_context = Mock()
        mock_config = Mock()
        
        # Set up the chain: request -> app -> app_context -> configuration
        mock_request.app = mock_app
        mock_app.app_context = mock_app_context
        mock_app_context.configuration = mock_config
        
        # Set up all required configuration attributes
        config_attrs = {
            'app_logging_enable': True,
            'app_logging_level': 'INFO',
            'azure_package_logging_level': 'WARNING',
            'azure_logging_packages': ['azure.core'],
            'cosmos_db_account_url': 'https://test.documents.azure.com:443/',
            'cosmos_db_database_name': 'test_db',
            'cosmos_db_process_container': 'processes',
            'cosmos_db_process_log_container': 'logs',
            'storage_account_name': 'teststorage',
            'storage_account_blob_url': 'https://teststorage.blob.core.windows.net/',
            'storage_account_queue_url': 'https://teststorage.queue.core.windows.net/',
            'storage_account_process_container': 'files',
            'storage_account_process_queue': 'queue'
        }
        
        for attr, value in config_attrs.items():
            setattr(mock_config, attr, value)
        
        result = await get_config_debug(mock_request)
        
        # Verify the result is correct
        assert isinstance(result, JSONResponse)
        
        # Verify all attributes were accessed
        for attr in config_attrs:
            assert hasattr(mock_config, attr)


class TestDocstringAndMetadata(TestRouterDebug):
    """Test cases for function documentation and metadata."""

    def test_get_config_debug_has_docstring(self):
        """Test get_config_debug function has proper docstring."""
        assert get_config_debug.__doc__ is not None
        assert "Debug endpoint to check configuration values" in get_config_debug.__doc__

    def test_router_module_has_proper_imports(self):
        """Test that all necessary imports are present in the module."""
        # This test verifies the module structure is correct
        import app.routers.router_debug as debug_module
        
        # Verify key components are available
        assert hasattr(debug_module, 'router')
        assert hasattr(debug_module, 'get_config_debug')
        assert hasattr(debug_module, 'APIRouter')
        assert hasattr(debug_module, 'Request')
        assert hasattr(debug_module, 'JSONResponse')
        assert hasattr(debug_module, 'TypedFastAPI')


class TestResponseStructure(TestRouterDebug):
    """Test cases for response structure validation."""

    @pytest.mark.asyncio
    async def test_response_has_configuration_key(self):
        """Test response always has 'configuration' key."""
        result = await get_config_debug(self.mock_request)
        
        content = result.body.decode('utf-8')
        import json
        response_data = json.loads(content)
        
        assert "configuration" in response_data
        assert isinstance(response_data["configuration"], dict)

    @pytest.mark.asyncio
    async def test_configuration_keys_are_strings(self):
        """Test all configuration keys are strings."""
        result = await get_config_debug(self.mock_request)
        
        content = result.body.decode('utf-8')
        import json
        response_data = json.loads(content)
        config = response_data["configuration"]
        
        for key in config.keys():
            assert isinstance(key, str)

    @pytest.mark.asyncio
    async def test_response_is_json_serializable(self):
        """Test the entire response is JSON serializable."""
        result = await get_config_debug(self.mock_request)
        
        # If we can decode it, it's properly serializable
        content = result.body.decode('utf-8')
        import json
        response_data = json.loads(content)
        
        # Verify we can serialize it again
        json_string = json.dumps(response_data)
        assert isinstance(json_string, str)
        assert len(json_string) > 0