from unittest.mock import Mock

import pytest

from libs.application.application_configuration import Configuration
from libs.application.application_context import AppContext
from libs.services.implementations import (
    ConsoleLoggerService,
    HttpClientService,
    InMemoryDataService,
)
from libs.services.interfaces import IDataService, IHttpService, ILoggerService


def test_app_context_dependency_injection():
    """Test basic dependency injection functionality"""
    app_context = AppContext()
    app_context.set_configuration(Configuration())

    # Register services
    app_context.add_singleton(IDataService, InMemoryDataService)
    app_context.add_singleton(ILoggerService, ConsoleLoggerService)
    app_context.add_transient(IHttpService, HttpClientService)

    # Test service registration
    assert app_context.is_registered(IDataService)
    assert app_context.is_registered(ILoggerService)
    assert app_context.is_registered(IHttpService)

    # Test service resolution
    data_service = app_context.get_typed_service(IDataService)
    logger_service = app_context.get_typed_service(ILoggerService)
    http_service = app_context.get_typed_service(IHttpService)

    assert isinstance(data_service, InMemoryDataService)
    assert isinstance(logger_service, ConsoleLoggerService)
    assert isinstance(http_service, HttpClientService)


def test_singleton_lifetime():
    """Test that singleton services return the same instance"""
    app_context = AppContext()
    app_context.add_singleton(IDataService, InMemoryDataService)

    instance1 = app_context.get_typed_service(IDataService)
    instance2 = app_context.get_typed_service(IDataService)

    assert instance1 is instance2
    assert id(instance1) == id(instance2)


def test_transient_lifetime():
    """Test that transient services return different instances"""
    app_context = AppContext()
    app_context.add_transient(IHttpService, HttpClientService)

    instance1 = app_context.get_typed_service(IHttpService)
    instance2 = app_context.get_typed_service(IHttpService)

    assert instance1 is not instance2
    assert id(instance1) != id(instance2)


def test_service_with_mock():
    """Test dependency injection with mock services"""
    app_context = AppContext()

    # Create mock service that won't be treated as callable
    mock_logger = Mock(spec=ILoggerService)
    mock_logger.log_info.return_value = None

    # Create a wrapper function to return the mock
    def mock_factory():
        return mock_logger

    # Register mock factory
    app_context.add_singleton(ILoggerService, mock_factory)

    # Get service and test
    logger_service = app_context.get_typed_service(ILoggerService)
    assert logger_service is mock_logger

    # Test mock functionality
    logger_service.log_info("test message")
    mock_logger.log_info.assert_called_once_with("test message")


def test_service_not_registered():
    """Test behavior when service is not registered"""
    app_context = AppContext()

    with pytest.raises(KeyError, match="Service IDataService is not registered"):
        app_context.get_typed_service(IDataService)


def test_get_registered_services():
    """Test getting information about registered services"""
    app_context = AppContext()

    app_context.add_singleton(IDataService, InMemoryDataService)
    app_context.add_transient(IHttpService, HttpClientService)

    services = app_context.get_registered_services()

    assert len(services) == 2
    assert services[IDataService] == "singleton"
    assert services[IHttpService] == "transient"


def test_method_chaining():
    """Test that service registration methods support chaining"""
    app_context = AppContext()

    # Test method chaining
    result = app_context.add_singleton(IDataService, InMemoryDataService).add_transient(
        IHttpService, HttpClientService
    )

    assert result is app_context
    assert app_context.is_registered(IDataService)
    assert app_context.is_registered(IHttpService)


def test_factory_registration():
    """Test registering services with factory functions"""
    app_context = AppContext()

    # Register with factory function
    app_context.add_singleton(IDataService, lambda: InMemoryDataService())

    data_service = app_context.get_typed_service(IDataService)
    assert isinstance(data_service, InMemoryDataService)


def test_instance_registration():
    """Test registering existing service instances"""
    app_context = AppContext()

    # Create instance
    existing_instance = InMemoryDataService()

    # Register existing instance
    app_context.add_singleton(IDataService, existing_instance)

    # Get service
    retrieved_instance = app_context.get_typed_service(IDataService)

    assert retrieved_instance is existing_instance


def test_concrete_class_registration():
    """Test registering concrete classes without interfaces"""
    app_context = AppContext()

    # Register concrete classes directly
    app_context.add_singleton(InMemoryDataService)
    app_context.add_transient(HttpClientService)

    # Test that they are registered
    assert app_context.is_registered(InMemoryDataService)
    assert app_context.is_registered(HttpClientService)

    # Test service resolution
    data_service1 = app_context.get_typed_service(InMemoryDataService)
    data_service2 = app_context.get_typed_service(InMemoryDataService)

    http_service1 = app_context.get_typed_service(HttpClientService)
    http_service2 = app_context.get_typed_service(HttpClientService)

    # Test types
    assert isinstance(data_service1, InMemoryDataService)
    assert isinstance(http_service1, HttpClientService)

    # Test lifetimes
    assert data_service1 is data_service2  # Singleton
    assert http_service1 is not http_service2  # Transient

    # Test functionality
    data_service1.save_data("test", {"value": "concrete class test"})
    assert data_service1.get_data("test") == {"value": "concrete class test"}
