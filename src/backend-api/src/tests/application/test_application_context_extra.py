"""Additional comprehensive tests for AppContext and related classes."""
import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Optional

from libs.application.application_context import (
    AppContext,
    ServiceDescriptor,
    ServiceLifetime,
    ServiceScope,
)
from libs.application.application_configuration import Configuration


# Service interfaces and implementations
class ITestService:
    pass


class SimpleTestServiceImpl(ITestService):
    def __init__(self):
        self.value = "test"


class IAnotherService:
    pass


class AnotherServiceImpl(IAnotherService):
    def __init__(self):
        self.name = "another"


class IAsyncService:
    pass


class SimpleAsyncServiceImpl(IAsyncService):
    def __init__(self):
        self.initialized = False

    async def __aenter__(self):
        self.initialized = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.initialized = False

    async def close(self):
        pass


# ServiceDescriptor tests
def test_service_descriptor_initialization():
    """Test ServiceDescriptor initialization."""
    descriptor = ServiceDescriptor(
        service_type=ITestService,
        implementation=SimpleTestServiceImpl,
        lifetime=ServiceLifetime.SINGLETON,
    )

    assert descriptor.service_type is ITestService
    assert descriptor.implementation is SimpleTestServiceImpl
    assert descriptor.lifetime == ServiceLifetime.SINGLETON
    assert descriptor.instance is None
    assert descriptor.is_async is False


def test_service_descriptor_with_async():
    """Test ServiceDescriptor with async settings."""
    descriptor = ServiceDescriptor(
        service_type=IAsyncService,
        implementation=SimpleAsyncServiceImpl,
        lifetime=ServiceLifetime.ASYNC_SINGLETON,
        is_async=True,
        cleanup_method="close",
    )

    assert descriptor.is_async is True
    assert descriptor.cleanup_method == "close"


def test_service_descriptor_default_cleanup_method():
    """Test ServiceDescriptor default cleanup method."""
    descriptor = ServiceDescriptor(
        service_type=ITestService,
        implementation=SimpleTestServiceImpl,
        lifetime=ServiceLifetime.SINGLETON,
    )

    assert descriptor.cleanup_method == "close"


# ServiceScope tests
def test_service_scope_initialization():
    """Test ServiceScope initialization."""
    app_context = AppContext()
    scope = ServiceScope(app_context, "test-scope-id")

    assert scope._app_context is app_context
    assert scope._scope_id == "test-scope-id"


def test_service_scope_get_service():
    """Test ServiceScope get_service method."""
    app_context = AppContext()
    app_context.add_scoped(ITestService, SimpleTestServiceImpl)

    scope = ServiceScope(app_context, "test-scope-id")

    service = scope.get_service(ITestService)

    assert isinstance(service, SimpleTestServiceImpl)


def test_service_scope_restores_previous_scope():
    """Test that ServiceScope restores previous scope context."""
    app_context = AppContext()
    app_context.add_scoped(ITestService, SimpleTestServiceImpl)

    original_scope = app_context._current_scope_id
    scope1 = ServiceScope(app_context, "scope-1")
    old_scope = app_context._current_scope_id

    app_context._current_scope_id = original_scope

    service = scope1.get_service(ITestService)

    assert app_context._current_scope_id == original_scope


@pytest.mark.asyncio
async def test_service_scope_get_service_async():
    """Test ServiceScope get_service_async method."""
    app_context = AppContext()
    app_context.add_async_scoped(IAsyncService, SimpleAsyncServiceImpl)

    scope = ServiceScope(app_context, "test-scope-id")

    service = await scope.get_service_async(IAsyncService)

    assert isinstance(service, SimpleAsyncServiceImpl)


# AppContext tests
def test_app_context_initialization():
    """Test AppContext initialization."""
    app_context = AppContext()

    assert app_context._services == {}
    assert app_context._instances == {}
    assert app_context._scoped_instances == {}
    assert app_context._current_scope_id is None
    assert app_context._async_cleanup_tasks == []


def test_app_context_set_configuration():
    """Test setting configuration."""
    app_context = AppContext()
    config = Configuration()

    app_context.set_configuration(config)

    assert app_context.configuration is config


def test_app_context_set_credential():
    """Test setting credential."""
    from azure.identity import DefaultAzureCredential

    app_context = AppContext()
    cred = Mock(spec=DefaultAzureCredential)

    app_context.set_credential(cred)

    assert app_context.credential is cred


def test_app_context_add_singleton_with_class():
    """Test adding singleton with class type."""
    app_context = AppContext()

    app_context.add_singleton(ITestService, SimpleTestServiceImpl)

    assert app_context.is_registered(ITestService)


def test_app_context_add_singleton_returns_self():
    """Test that add_singleton returns self for chaining."""
    app_context = AppContext()

    result = app_context.add_singleton(ITestService, SimpleTestServiceImpl)

    assert result is app_context


def test_app_context_add_singleton_with_factory():
    """Test adding singleton with factory function."""
    app_context = AppContext()

    factory = lambda: SimpleTestServiceImpl()
    app_context.add_singleton(ITestService, factory)

    service = app_context.get_service(ITestService)
    assert isinstance(service, SimpleTestServiceImpl)


def test_app_context_add_singleton_with_instance():
    """Test adding singleton with pre-created instance."""
    app_context = AppContext()
    instance = SimpleTestServiceImpl()

    app_context.add_singleton(ITestService, instance)

    service = app_context.get_service(ITestService)
    assert service is instance


def test_app_context_add_transient():
    """Test adding transient service."""
    app_context = AppContext()

    app_context.add_transient(ITestService, SimpleTestServiceImpl)

    service1 = app_context.get_service(ITestService)
    service2 = app_context.get_service(ITestService)

    assert service1 is not service2


def test_app_context_add_scoped():
    """Test adding scoped service."""
    app_context = AppContext()

    app_context.add_scoped(ITestService, SimpleTestServiceImpl)

    assert app_context.is_registered(ITestService)


def test_app_context_add_async_singleton():
    """Test adding async singleton service."""
    app_context = AppContext()

    app_context.add_async_singleton(IAsyncService, SimpleAsyncServiceImpl)

    assert app_context.is_registered(IAsyncService)


def test_app_context_add_async_scoped():
    """Test adding async scoped service."""
    app_context = AppContext()

    app_context.add_async_scoped(IAsyncService, SimpleAsyncServiceImpl)

    assert app_context.is_registered(IAsyncService)


def test_app_context_get_service_singleton():
    """Test getting singleton service returns same instance."""
    app_context = AppContext()
    app_context.add_singleton(ITestService, SimpleTestServiceImpl)

    service1 = app_context.get_service(ITestService)
    service2 = app_context.get_service(ITestService)

    assert service1 is service2


def test_app_context_get_service_transient():
    """Test getting transient service returns different instances."""
    app_context = AppContext()
    app_context.add_transient(ITestService, SimpleTestServiceImpl)

    service1 = app_context.get_service(ITestService)
    service2 = app_context.get_service(ITestService)

    assert service1 is not service2


@pytest.mark.asyncio
async def test_app_context_get_service_scoped():
    """Test getting scoped service within a scope."""
    app_context = AppContext()
    app_context.add_scoped(ITestService, SimpleTestServiceImpl)

    async with app_context.create_scope() as scope:
        service1 = scope.get_service(ITestService)
        service2 = scope.get_service(ITestService)

        assert service1 is service2


def test_app_context_get_service_not_registered():
    """Test getting unregistered service raises KeyError."""
    app_context = AppContext()

    with pytest.raises(KeyError, match="Service ITestService is not registered"):
        app_context.get_service(ITestService)


def test_app_context_get_service_scoped_without_scope():
    """Test getting scoped service without active scope raises ValueError."""
    app_context = AppContext()
    app_context.add_scoped(ITestService, SimpleTestServiceImpl)

    with pytest.raises(ValueError, match="requires an active scope"):
        app_context.get_service(ITestService)


@pytest.mark.asyncio
async def test_app_context_get_service_async_singleton():
    """Test getting async singleton service."""
    app_context = AppContext()
    app_context.add_async_singleton(IAsyncService, SimpleAsyncServiceImpl)

    service1 = await app_context.get_service_async(IAsyncService)
    service2 = await app_context.get_service_async(IAsyncService)

    assert service1 is service2


@pytest.mark.asyncio
async def test_app_context_get_service_async_not_async_registered():
    """Test getting async service when registered as sync raises ValueError."""
    app_context = AppContext()
    app_context.add_singleton(ITestService, SimpleTestServiceImpl)

    with pytest.raises(ValueError, match="not registered as an async service"):
        await app_context.get_service_async(ITestService)


@pytest.mark.asyncio
async def test_app_context_create_scope():
    """Test creating a service scope."""
    app_context = AppContext()

    async with app_context.create_scope() as scope:
        assert isinstance(scope, ServiceScope)
        assert scope._app_context is app_context


@pytest.mark.asyncio
async def test_app_context_create_scope_cleanup():
    """Test that scope cleanup is called."""
    app_context = AppContext()
    app_context.add_async_scoped(IAsyncService, SimpleAsyncServiceImpl)

    scope_id = None
    async with app_context.create_scope() as scope:
        scope_id = scope._scope_id
        service = await scope.get_service_async(IAsyncService)
        assert service.initialized is True

    # After scope exits, service should be cleaned up
    assert scope_id not in app_context._scoped_instances


def test_app_context_is_registered():
    """Test is_registered method."""
    app_context = AppContext()
    app_context.add_singleton(ITestService, SimpleTestServiceImpl)

    assert app_context.is_registered(ITestService)
    assert not app_context.is_registered(IAnotherService)


def test_app_context_get_registered_services():
    """Test get_registered_services method."""
    app_context = AppContext()
    app_context.add_singleton(ITestService, SimpleTestServiceImpl)
    app_context.add_transient(IAnotherService, AnotherServiceImpl)

    services = app_context.get_registered_services()

    assert len(services) == 2
    assert services[ITestService] == ServiceLifetime.SINGLETON
    assert services[IAnotherService] == ServiceLifetime.TRANSIENT


def test_app_context_method_chaining():
    """Test that service registration methods support chaining."""
    app_context = AppContext()

    result = (
        app_context.add_singleton(ITestService, SimpleTestServiceImpl).add_transient(
            IAnotherService, AnotherServiceImpl
        )
    )

    assert result is app_context
    assert app_context.is_registered(ITestService)
    assert app_context.is_registered(IAnotherService)


def test_app_context_add_singleton_without_implementation():
    """Test adding singleton without explicit implementation uses service_type."""
    app_context = AppContext()

    app_context.add_singleton(SimpleTestServiceImpl)

    service = app_context.get_service(SimpleTestServiceImpl)
    assert isinstance(service, SimpleTestServiceImpl)


def test_app_context_add_transient_without_implementation():
    """Test adding transient without explicit implementation."""
    app_context = AppContext()

    app_context.add_transient(SimpleTestServiceImpl)

    service1 = app_context.get_service(SimpleTestServiceImpl)
    service2 = app_context.get_service(SimpleTestServiceImpl)

    assert service1 is not service2


def test_app_context_create_instance_with_class():
    """Test _create_instance with class type."""
    app_context = AppContext()
    descriptor = ServiceDescriptor(
        service_type=ITestService,
        implementation=SimpleTestServiceImpl,
        lifetime=ServiceLifetime.SINGLETON,
    )

    instance = app_context._create_instance(descriptor)

    assert isinstance(instance, SimpleTestServiceImpl)


def test_app_context_create_instance_with_factory():
    """Test _create_instance with factory function."""
    app_context = AppContext()
    factory = lambda: SimpleTestServiceImpl()
    descriptor = ServiceDescriptor(
        service_type=ITestService,
        implementation=factory,
        lifetime=ServiceLifetime.SINGLETON,
    )

    instance = app_context._create_instance(descriptor)

    assert isinstance(instance, SimpleTestServiceImpl)


def test_app_context_create_instance_with_instance():
    """Test _create_instance with pre-created instance."""
    app_context = AppContext()
    preinstance = SimpleTestServiceImpl()
    descriptor = ServiceDescriptor(
        service_type=ITestService,
        implementation=preinstance,
        lifetime=ServiceLifetime.SINGLETON,
    )

    instance = app_context._create_instance(descriptor)

    assert instance is preinstance


def test_app_context_create_instance_invalid_type():
    """Test _create_instance with invalid implementation type."""
    app_context = AppContext()
    # For integers and non-callable objects, _create_instance returns them as-is
    # This is by design - pre-created instances are allowed
    descriptor = ServiceDescriptor(
        service_type=ITestService, 
        implementation=123, 
        lifetime=ServiceLifetime.SINGLETON
    )

    # The implementation check: if not callable and not a type, return it as-is
    # So we pass an integer - it will be returned as-is
    instance = app_context._create_instance(descriptor)
    assert instance == 123


@pytest.mark.asyncio
async def test_app_context_create_async_instance_with_class():
    """Test _create_async_instance with class type."""
    app_context = AppContext()
    descriptor = ServiceDescriptor(
        service_type=IAsyncService,
        implementation=SimpleAsyncServiceImpl,
        lifetime=ServiceLifetime.ASYNC_SINGLETON,
        is_async=True,
    )

    instance = await app_context._create_async_instance(descriptor)

    assert isinstance(instance, SimpleAsyncServiceImpl)
    assert instance.initialized is True


@pytest.mark.asyncio
async def test_app_context_create_async_instance_with_factory():
    """Test _create_async_instance with factory function."""
    app_context = AppContext()
    factory = lambda: SimpleAsyncServiceImpl()
    descriptor = ServiceDescriptor(
        service_type=IAsyncService,
        implementation=factory,
        lifetime=ServiceLifetime.ASYNC_SINGLETON,
        is_async=True,
    )

    instance = await app_context._create_async_instance(descriptor)

    assert isinstance(instance, SimpleAsyncServiceImpl)


@pytest.mark.asyncio
async def test_app_context_shutdown_async():
    """Test shutdown_async method."""
    app_context = AppContext()
    app_context.add_async_singleton(IAsyncService, SimpleAsyncServiceImpl)

    service = await app_context.get_service_async(IAsyncService)

    await app_context.shutdown_async()

    assert app_context._instances == {}
    assert app_context._scoped_instances == {}


def test_app_context_get_service_lifecycle_enum():
    """Test all ServiceLifetime constants."""
    assert ServiceLifetime.SINGLETON == "singleton"
    assert ServiceLifetime.TRANSIENT == "transient"
    assert ServiceLifetime.SCOPED == "scoped"
    assert ServiceLifetime.ASYNC_SINGLETON == "async_singleton"
    assert ServiceLifetime.ASYNC_SCOPED == "async_scoped"
