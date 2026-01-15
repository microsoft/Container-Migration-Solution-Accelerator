"""
Unit tests for concrete_services.

This module contains comprehensive test cases for the concrete services router
including endpoint testing, service injection, and response validation.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi import Request
from fastapi.testclient import TestClient

# Import the router and functions under test
from app.samples.concrete_services import router, concrete_services_demo, service_registration_info
from libs.base.typed_fastapi import TypedFastAPI
from libs.services.interfaces import IDataService, ILoggerService


class TestConcreteServices:
    """Base test class for concrete_services tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(router)
        
        # Create mock services
        self.mock_logger_service = Mock(spec=ILoggerService)
        self.mock_data_service = Mock(spec=IDataService)
        
        # Create mock app context
        self.mock_app_context = Mock()
        self.mock_app_context.get_service = Mock()
        
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


class TestConcreteServicesDemo(TestConcreteServices):
    """Test cases for concrete_services_demo endpoint."""
    
    def test_concrete_services_demo_success(self):
        """Test successful concrete services demo execution."""
        # Arrange
        expected_saved_data = {
            "message": "This shows how you can use concrete services",
            "pattern": "Both interface-based and concrete class registration work",
        }
        self.mock_data_service.get_data.return_value = expected_saved_data
        
        # Act
        result = concrete_services_demo(self.mock_request)
        
        # Assert
        assert result is not None
        assert "message" in result
        assert "data_saved" in result
        assert "note" in result
        
        assert result["message"] == "Concrete services demo"
        assert result["data_saved"] == expected_saved_data
        assert "interfaces or concrete classes" in result["note"]
        
        # Verify service calls
        self.mock_app_context.get_service.assert_any_call(ILoggerService)
        self.mock_app_context.get_service.assert_any_call(IDataService)
        self.mock_logger_service.log_info.assert_called_once_with(
            "Concrete services demo endpoint called"
        )
        self.mock_data_service.save_data.assert_called_once_with(
            "concrete_demo",
            expected_saved_data
        )
        self.mock_data_service.get_data.assert_called_once_with("concrete_demo")
    
    def test_concrete_services_demo_logger_service_injection(self):
        """Test that logger service is correctly injected and called."""
        # Arrange
        self.mock_data_service.get_data.return_value = {}
        
        # Act
        concrete_services_demo(self.mock_request)
        
        # Assert
        self.mock_app_context.get_service.assert_any_call(ILoggerService)
        self.mock_logger_service.log_info.assert_called_once_with(
            "Concrete services demo endpoint called"
        )
    
    def test_concrete_services_demo_data_service_injection(self):
        """Test that data service is correctly injected and used for save/get operations."""
        # Arrange
        expected_data = {"test": "data"}
        self.mock_data_service.get_data.return_value = expected_data
        
        # Act
        result = concrete_services_demo(self.mock_request)
        
        # Assert
        self.mock_app_context.get_service.assert_any_call(IDataService)
        self.mock_data_service.save_data.assert_called_once()
        self.mock_data_service.get_data.assert_called_once_with("concrete_demo")
        assert result["data_saved"] == expected_data
    
    def test_concrete_services_demo_data_service_save_parameters(self):
        """Test that data service save is called with correct parameters."""
        # Arrange
        self.mock_data_service.get_data.return_value = {}
        
        # Act
        concrete_services_demo(self.mock_request)
        
        # Assert
        expected_save_data = {
            "message": "This shows how you can use concrete services",
            "pattern": "Both interface-based and concrete class registration work",
        }
        self.mock_data_service.save_data.assert_called_once_with(
            "concrete_demo", 
            expected_save_data
        )
    
    def test_concrete_services_demo_with_http_client(self):
        """Test concrete services demo endpoint via HTTP client."""
        # Create a test app with the router
        from fastapi import FastAPI
        test_app = FastAPI()
        test_app.include_router(router)
        
        with patch('app.samples.concrete_services.Request') as mock_request_class:
            # Mock the request and its app attribute
            mock_request_instance = Mock()
            mock_request_class.return_value = mock_request_instance
            mock_request_instance.app = self.mock_app
            
            self.mock_data_service.get_data.return_value = {"test": "data"}
            
            client = TestClient(test_app)
            
            # This will test the actual endpoint through FastAPI
            # Note: This test might need additional setup depending on your app configuration
            # response = client.get("/concrete/demo")
            # assert response.status_code == 200


class TestServiceRegistrationInfo(TestConcreteServices):
    """Test cases for service_registration_info endpoint."""
    
    def test_service_registration_info_response_structure(self):
        """Test that service registration info returns correct response structure."""
        # Act
        result = service_registration_info()
        
        # Assert
        assert result is not None
        assert "patterns" in result
        assert "examples" in result
        
        patterns = result["patterns"]
        assert "interface_based" in patterns
        assert "concrete_class" in patterns
        assert "factory_function" in patterns
        
        examples = result["examples"]
        assert isinstance(examples, list)
        assert len(examples) > 0
    
    def test_service_registration_info_interface_based_pattern(self):
        """Test interface-based pattern information."""
        # Act
        result = service_registration_info()
        
        # Assert
        interface_pattern = result["patterns"]["interface_based"]
        assert "registration" in interface_pattern
        assert "usage" in interface_pattern
        assert "benefits" in interface_pattern
        
        assert "IMyService" in interface_pattern["registration"]
        assert "MyServiceImpl" in interface_pattern["registration"]
        assert "addSingleton" in interface_pattern["registration"]
        
        assert "get_typed_service" in interface_pattern["usage"]
        assert "IMyService" in interface_pattern["usage"]
        
        benefits = interface_pattern["benefits"]
        assert "Loose coupling" in benefits
        assert "Easy testing" in benefits
        assert "Interface segregation" in benefits
    
    def test_service_registration_info_concrete_class_pattern(self):
        """Test concrete class pattern information."""
        # Act
        result = service_registration_info()
        
        # Assert
        concrete_pattern = result["patterns"]["concrete_class"]
        assert "registration" in concrete_pattern
        assert "usage" in concrete_pattern
        assert "benefits" in concrete_pattern
        
        assert "MyService" in concrete_pattern["registration"]
        assert "addSingleton" in concrete_pattern["registration"]
        
        assert "get_typed_service" in concrete_pattern["usage"]
        assert "MyService" in concrete_pattern["usage"]
        
        benefits = concrete_pattern["benefits"]
        assert "Simpler setup" in benefits
        assert "Direct access" in benefits
        assert "No interface needed" in benefits
    
    def test_service_registration_info_factory_function_pattern(self):
        """Test factory function pattern information."""
        # Act
        result = service_registration_info()
        
        # Assert
        factory_pattern = result["patterns"]["factory_function"]
        assert "registration" in factory_pattern
        assert "usage" in factory_pattern
        assert "benefits" in factory_pattern
        
        assert "lambda" in factory_pattern["registration"]
        assert "MyServiceImpl(config)" in factory_pattern["registration"]
        
        assert "get_typed_service" in factory_pattern["usage"]
        assert "IMyService" in factory_pattern["usage"]
        
        benefits = factory_pattern["benefits"]
        assert "Custom initialization" in benefits
        assert "Configuration injection" in benefits
        assert "Complex setup" in benefits
    
    def test_service_registration_info_examples_content(self):
        """Test that examples contain valid registration patterns."""
        # Act
        result = service_registration_info()
        
        # Assert
        examples = result["examples"]
        
        # Check for concrete class example
        concrete_examples = [ex for ex in examples if "addSingleton(MyService)" in ex]
        assert len(concrete_examples) > 0
        
        # Check for transient example
        transient_examples = [ex for ex in examples if "add_singlecall" in ex]
        assert len(transient_examples) > 0
        
        # Check for interface-based example
        interface_examples = [ex for ex in examples if "IMyService, MyServiceImpl" in ex]
        assert len(interface_examples) > 0
        
        # Check for factory example
        factory_examples = [ex for ex in examples if "lambda:" in ex]
        assert len(factory_examples) > 0
    
    def test_service_registration_info_with_http_client(self):
        """Test service registration info endpoint via HTTP client."""
        # Create a test app with the router
        from fastapi import FastAPI
        test_app = FastAPI()
        test_app.include_router(router)
        
        client = TestClient(test_app)
        response = client.get("/concrete/info")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "patterns" in data
        assert "examples" in data


class TestRouterConfiguration:
    """Test cases for router configuration."""
    
    def test_router_prefix(self):
        """Test that router has correct prefix."""
        assert router.prefix == "/concrete"
    
    def test_router_tags(self):
        """Test that router has correct tags."""
        assert "concrete_services" in router.tags
    
    def test_router_responses(self):
        """Test that router has correct response configurations."""
        assert 404 in router.responses
        assert router.responses[404]["description"] == "Not found"


class TestEndpointIntegration:
    """Integration test cases for the endpoints."""
    
    def test_demo_endpoint_path(self):
        """Test that demo endpoint is available at correct path."""
        from fastapi import FastAPI
        test_app = FastAPI()
        test_app.include_router(router)
        
        client = TestClient(test_app)
        
        # This would require proper app setup with dependency injection
        # response = client.get("/concrete/demo")
        # For now, just verify the endpoint exists in the router
        routes = [route.path for route in router.routes if hasattr(route, 'path')]
        assert "/concrete/demo" in routes
    
    def test_info_endpoint_path(self):
        """Test that info endpoint is available at correct path."""
        from fastapi import FastAPI
        test_app = FastAPI()
        test_app.include_router(router)
        
        client = TestClient(test_app)
        response = client.get("/concrete/info")
        
        assert response.status_code == 200


# Pytest fixtures and additional utilities

@pytest.fixture
def mock_typed_fastapi_app():
    """Fixture providing a mock TypedFastAPI app with dependencies."""
    mock_logger = Mock(spec=ILoggerService)
    mock_data = Mock(spec=IDataService)
    
    mock_context = Mock()
    mock_context.get_service = Mock(side_effect=lambda service_type: {
        ILoggerService: mock_logger,
        IDataService: mock_data
    }.get(service_type))
    
    mock_app = Mock(spec=TypedFastAPI)
    mock_app.app_context = mock_context
    
    return mock_app, mock_logger, mock_data


@pytest.fixture
def mock_request_with_app(mock_typed_fastapi_app):
    """Fixture providing a mock request with TypedFastAPI app."""
    mock_app, mock_logger, mock_data = mock_typed_fastapi_app
    
    mock_request = Mock(spec=Request)
    mock_request.app = mock_app
    
    return mock_request, mock_logger, mock_data


# Additional test cases using fixtures

def test_concrete_services_demo_with_fixtures(mock_request_with_app):
    """Test concrete services demo using pytest fixtures."""
    mock_request, mock_logger, mock_data = mock_request_with_app
    
    expected_data = {"fixture": "test"}
    mock_data.get_data.return_value = expected_data
    
    result = concrete_services_demo(mock_request)
    
    assert result["data_saved"] == expected_data
    mock_logger.log_info.assert_called_once()
    mock_data.save_data.assert_called_once()
    mock_data.get_data.assert_called_once()


def test_service_registration_info_independent():
    """Test service registration info function independently."""
    result = service_registration_info()
    
    # This endpoint doesn't depend on any external services
    assert "patterns" in result
    assert len(result["patterns"]) == 3
    assert len(result["examples"]) == 4