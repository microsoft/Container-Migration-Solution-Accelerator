"""
Unit tests for router_one.

This module contains comprehensive test cases for the router_one router
including endpoint testing, service injection, and response validation.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi import Request
from fastapi.testclient import TestClient

# Import the router and functions under test
from app.samples.router_one import router, hello, get_services
from libs.base.typed_fastapi import TypedFastAPI
from libs.services.interfaces import IDataService, ILoggerService


class TestRouterOne:
    """Base test class for router_one tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(router)
        
        # Create mock services
        self.mock_logger_service = Mock(spec=ILoggerService)
        self.mock_data_service = Mock(spec=IDataService)
        
        # Create mock configuration
        self.mock_configuration = Mock()
        self.mock_configuration.app_sample_variable = "Test configuration value"
        
        # Create mock registered services
        self.mock_registered_services = {
            ILoggerService: "singleton",
            IDataService: "singleton"
        }
        
        # Create mock app context
        self.mock_app_context = Mock()
        self.mock_app_context.get_service = Mock()
        self.mock_app_context.configuration = self.mock_configuration
        self.mock_app_context.get_registered_services = Mock(return_value=self.mock_registered_services)
        
        # Configure the get_service method to return our mock services
        def get_service_side_effect(service_type):
            if service_type == ILoggerService:
                return self.mock_logger_service
            elif service_type == IDataService:
                return self.mock_data_service
            return None
        
        self.mock_app_context.get_service.side_effect = get_service_side_effect
        
        # Create mock TypedFastAPI app
        self.mock_app = Mock(spec=TypedFastAPI)
        self.mock_app.app_context = self.mock_app_context
        
        # Create mock request
        self.mock_request = Mock(spec=Request)
        self.mock_request.app = self.mock_app


class TestHelloEndpoint(TestRouterOne):
    """Test cases for hello endpoint."""
    
    def test_hello_success(self):
        """Test successful hello endpoint execution."""
        # Arrange
        expected_saved_data = {"endpoint": "/router_one/hello", "timestamp": "now"}
        self.mock_data_service.get_data.return_value = expected_saved_data
        
        # Act
        result = hello(self.mock_request)
        
        # Assert
        assert result is not None
        assert "message" in result
        assert "configuration_message" in result
        assert "saved_data" in result
        assert "services_registered" in result
        
        assert result["message"] == "Hello from Router One"
        assert result["configuration_message"] == "Test configuration value"
        assert result["saved_data"] == expected_saved_data
        assert result["services_registered"] == 2  # Two services registered
    
    def test_hello_logger_service_injection(self):
        """Test that logger service is correctly injected and called."""
        # Arrange
        self.mock_data_service.get_data.return_value = {}
        
        # Act
        hello(self.mock_request)
        
        # Assert
        self.mock_app_context.get_service.assert_any_call(ILoggerService)
        self.mock_logger_service.log_info.assert_called_once_with("Hello endpoint called")
    
    def test_hello_data_service_injection_and_operations(self):
        """Test that data service is correctly injected and used for save/get operations."""
        # Arrange
        expected_data = {"test": "data"}
        self.mock_data_service.get_data.return_value = expected_data
        
        # Act
        result = hello(self.mock_request)
        
        # Assert
        self.mock_app_context.get_service.assert_any_call(IDataService)
        self.mock_data_service.save_data.assert_called_once_with(
            "last_request", 
            {"endpoint": "/router_one/hello", "timestamp": "now"}
        )
        self.mock_data_service.get_data.assert_called_once_with("last_request")
        assert result["saved_data"] == expected_data
    
    def test_hello_configuration_access(self):
        """Test that configuration is correctly accessed."""
        # Arrange
        test_config_value = "Custom test configuration"
        self.mock_configuration.app_sample_variable = test_config_value
        self.mock_data_service.get_data.return_value = {}
        
        # Act
        result = hello(self.mock_request)
        
        # Assert
        assert result["configuration_message"] == test_config_value
    
    def test_hello_services_count(self):
        """Test that services count is correctly retrieved."""
        # Arrange
        custom_services = {ILoggerService: "singleton", IDataService: "transient", str: "singleton"}
        self.mock_app_context.get_registered_services.return_value = custom_services
        self.mock_data_service.get_data.return_value = {}
        
        # Act
        result = hello(self.mock_request)
        
        # Assert
        assert result["services_registered"] == 3
        self.mock_app_context.get_registered_services.assert_called_once()
    
    def test_hello_with_empty_data_service_response(self):
        """Test hello endpoint when data service returns empty data."""
        # Arrange
        self.mock_data_service.get_data.return_value = {}
        
        # Act
        result = hello(self.mock_request)
        
        # Assert
        assert result["saved_data"] == {}
        assert "message" in result
        assert "configuration_message" in result
        assert "services_registered" in result
    
    def test_hello_data_save_parameters(self):
        """Test that data service save is called with correct parameters."""
        # Arrange
        self.mock_data_service.get_data.return_value = {"test": "response"}
        
        # Act
        hello(self.mock_request)
        
        # Assert
        expected_save_data = {"endpoint": "/router_one/hello", "timestamp": "now"}
        self.mock_data_service.save_data.assert_called_once_with("last_request", expected_save_data)


class TestGetServicesEndpoint(TestRouterOne):
    """Test cases for get_services endpoint."""
    
    def test_get_services_success(self):
        """Test successful get_services endpoint execution."""
        # Act
        result = get_services(self.mock_request)
        
        # Assert
        assert result is not None
        assert "registered_services" in result
        
        registered_services = result["registered_services"]
        assert "ILoggerService" in registered_services
        assert "IDataService" in registered_services
        assert registered_services["ILoggerService"] == "singleton"
        assert registered_services["IDataService"] == "singleton"
    
    def test_get_services_logger_service_injection(self):
        """Test that logger service is correctly injected and called."""
        # Act
        get_services(self.mock_request)
        
        # Assert
        self.mock_app_context.get_service.assert_called_once_with(ILoggerService)
        self.mock_logger_service.log_info.assert_called_once_with("Services endpoint called")
    
    def test_get_services_with_different_service_types(self):
        """Test get_services with different service types and lifetimes."""
        # Arrange
        custom_services = {
            ILoggerService: "singleton",
            IDataService: "transient",
            str: "scoped"
        }
        self.mock_app_context.get_registered_services.return_value = custom_services
        
        # Act
        result = get_services(self.mock_request)
        
        # Assert
        registered_services = result["registered_services"]
        assert len(registered_services) == 3
        assert registered_services["ILoggerService"] == "singleton"
        assert registered_services["IDataService"] == "transient" 
        assert registered_services["str"] == "scoped"
    
    def test_get_services_with_empty_services(self):
        """Test get_services when no services are registered."""
        # Arrange
        self.mock_app_context.get_registered_services.return_value = {}
        
        # Act
        result = get_services(self.mock_request)
        
        # Assert
        assert result["registered_services"] == {}
    
    def test_get_services_service_name_mapping(self):
        """Test that service types are correctly mapped to their names."""
        # Arrange
        class CustomService:
            pass
        
        custom_services = {
            ILoggerService: "singleton",
            CustomService: "transient"
        }
        self.mock_app_context.get_registered_services.return_value = custom_services
        
        # Act
        result = get_services(self.mock_request)
        
        # Assert
        registered_services = result["registered_services"]
        assert "ILoggerService" in registered_services
        assert "CustomService" in registered_services
        assert registered_services["ILoggerService"] == "singleton"
        assert registered_services["CustomService"] == "transient"


class TestRouterConfiguration(TestRouterOne):
    """Test cases for router configuration."""
    
    def test_router_prefix(self):
        """Test that router has correct prefix."""
        assert router.prefix == "/router_one"
    
    def test_router_tags(self):
        """Test that router has correct tags."""
        assert "router_one" in router.tags
    
    def test_router_responses(self):
        """Test that router has correct response configurations."""
        assert 404 in router.responses
        assert router.responses[404]["description"] == "Not found"


class TestEndpointIntegration(TestRouterOne):
    """Integration test cases for the endpoints."""
    
    def test_hello_endpoint_path(self):
        """Test that hello endpoint is available at correct path."""
        from fastapi import FastAPI
        test_app = FastAPI()
        test_app.include_router(router)
        
        # Verify the endpoint exists in the router
        routes = [route.path for route in router.routes if hasattr(route, 'path')]
        assert "/router_one/hello" in routes
    
    def test_services_endpoint_path(self):
        """Test that services endpoint is available at correct path."""
        from fastapi import FastAPI
        test_app = FastAPI()
        test_app.include_router(router)
        
        # Verify the endpoint exists in the router
        routes = [route.path for route in router.routes if hasattr(route, 'path')]
        assert "/router_one/services" in routes
    
    def test_endpoints_http_methods(self):
        """Test that endpoints use correct HTTP methods."""
        # Check that both endpoints use GET method
        get_routes = [route for route in router.routes if hasattr(route, 'methods') and 'GET' in route.methods]
        get_paths = [route.path for route in get_routes]
        
        assert "/router_one/hello" in get_paths
        assert "/router_one/services" in get_paths


class TestErrorHandling(TestRouterOne):
    """Test cases for error handling scenarios."""
    
    def test_hello_with_service_resolution_error(self):
        """Test hello endpoint when service resolution fails."""
        # Arrange - make get_service raise an exception
        self.mock_app_context.get_service.side_effect = Exception("Service not found")
        
        # Act & Assert
        with pytest.raises(Exception, match="Service not found"):
            hello(self.mock_request)
    
    def test_get_services_with_service_resolution_error(self):
        """Test get_services endpoint when service resolution fails."""
        # Arrange - make get_service raise an exception for logger service
        def side_effect(service_type):
            if service_type == ILoggerService:
                raise Exception("Logger service not found")
            return self.mock_data_service
        
        self.mock_app_context.get_service.side_effect = side_effect
        
        # Act & Assert
        with pytest.raises(Exception, match="Logger service not found"):
            get_services(self.mock_request)
    
    def test_hello_with_data_service_save_error(self):
        """Test hello endpoint when data service save operation fails."""
        # Arrange
        self.mock_data_service.save_data.side_effect = Exception("Save failed")
        self.mock_data_service.get_data.return_value = {}
        
        # Act & Assert
        with pytest.raises(Exception, match="Save failed"):
            hello(self.mock_request)


# Pytest fixtures and additional utilities

@pytest.fixture
def mock_typed_fastapi_app():
    """Fixture providing a mock TypedFastAPI app with dependencies."""
    mock_logger = Mock(spec=ILoggerService)
    mock_data = Mock(spec=IDataService)
    mock_config = Mock()
    mock_config.app_sample_variable = "Fixture test value"
    
    mock_context = Mock()
    mock_context.get_service = Mock(side_effect=lambda service_type: {
        ILoggerService: mock_logger,
        IDataService: mock_data
    }.get(service_type))
    mock_context.configuration = mock_config
    mock_context.get_registered_services = Mock(return_value={
        ILoggerService: "singleton",
        IDataService: "singleton"
    })
    
    mock_app = Mock(spec=TypedFastAPI)
    mock_app.app_context = mock_context
    
    return mock_app, mock_logger, mock_data, mock_config


@pytest.fixture
def mock_request_with_app(mock_typed_fastapi_app):
    """Fixture providing a mock request with TypedFastAPI app."""
    mock_app, mock_logger, mock_data, mock_config = mock_typed_fastapi_app
    
    mock_request = Mock(spec=Request)
    mock_request.app = mock_app
    
    return mock_request, mock_logger, mock_data, mock_config


# Additional test cases using fixtures

def test_hello_with_fixtures(mock_request_with_app):
    """Test hello endpoint using pytest fixtures."""
    mock_request, mock_logger, mock_data, mock_config = mock_request_with_app
    
    expected_data = {"fixture": "test"}
    mock_data.get_data.return_value = expected_data
    
    result = hello(mock_request)
    
    assert result["saved_data"] == expected_data
    assert result["configuration_message"] == "Fixture test value"
    mock_logger.log_info.assert_called_once_with("Hello endpoint called")
    mock_data.save_data.assert_called_once()
    mock_data.get_data.assert_called_once_with("last_request")


def test_get_services_with_fixtures(mock_request_with_app):
    """Test get_services endpoint using pytest fixtures."""
    mock_request, mock_logger, mock_data, mock_config = mock_request_with_app
    
    result = get_services(mock_request)
    
    assert "registered_services" in result
    assert len(result["registered_services"]) == 2
    mock_logger.log_info.assert_called_once_with("Services endpoint called")


class TestServiceInteractionPatterns(TestRouterOne):
    """Test cases for service interaction patterns."""
    
    def test_hello_service_call_order(self):
        """Test that services are called in the correct order in hello endpoint."""
        # Arrange
        call_order = []
        
        def logger_side_effect(message):
            call_order.append(f"logger: {message}")
        
        def save_side_effect(key, data):
            call_order.append(f"save: {key}")
        
        def get_side_effect(key):
            call_order.append(f"get: {key}")
            return {"test": "data"}
        
        self.mock_logger_service.log_info.side_effect = logger_side_effect
        self.mock_data_service.save_data.side_effect = save_side_effect
        self.mock_data_service.get_data.side_effect = get_side_effect
        
        # Act
        hello(self.mock_request)
        
        # Assert
        expected_order = [
            "logger: Hello endpoint called",
            "save: last_request", 
            "get: last_request"
        ]
        assert call_order == expected_order
    
    def test_get_services_minimal_service_interaction(self):
        """Test that get_services endpoint only calls necessary services."""
        # Act
        get_services(self.mock_request)
        
        # Assert - should only call logger service, not data service
        self.mock_app_context.get_service.assert_called_once_with(ILoggerService)
        self.mock_logger_service.log_info.assert_called_once()
        
        # Data service should not be called
        self.mock_data_service.save_data.assert_not_called()
        self.mock_data_service.get_data.assert_not_called()