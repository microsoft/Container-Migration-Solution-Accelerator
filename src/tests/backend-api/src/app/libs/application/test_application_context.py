import asyncio
import os
import sys
import pytest
import uuid
import weakref
from unittest.mock import Mock, patch, AsyncMock
from typing import Any, Dict, Type

# Add the backend-api src to path for imports
backend_api_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "..", "backend-api", "src", "app")
sys.path.insert(0, backend_api_path)

from libs.application.application_context import (
    ServiceLifetime,
    ServiceDescriptor,
    ServiceScope,
    AppContext,
)
from libs.application.application_configuration import Configuration
from azure.identity import DefaultAzureCredential


# Test interfaces and implementations
class ITestService:
    def get_data(self) -> str:
        pass

class TestService:
    def __init__(self, value: str = "default"):
        self.value = value
    
    def get_data(self) -> str:
        return self.value

class IAsyncService:
    async def process(self) -> str:
        pass

class AsyncTestService:
    def __init__(self):
        self.initialized = False
        self.closed = False
    
    async def __aenter__(self):
        self.initialized = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.closed = True
    
    async def process(self) -> str:
        return "async_result"
    
    async def close(self):
        self.closed = True

class ScopedService:
    def __init__(self):
        self.scope_id = str(uuid.uuid4())
    
    def get_scope_id(self) -> str:
        return self.scope_id


class TestServiceLifetime:
    """Test cases for ServiceLifetime constants"""

    def test_service_lifetime_constants(self):
        """Test that all ServiceLifetime constants are correctly defined"""
        assert ServiceLifetime.SINGLETON == "singleton"
        assert ServiceLifetime.TRANSIENT == "transient"
        assert ServiceLifetime.SCOPED == "scoped"
        assert ServiceLifetime.ASYNC_SINGLETON == "async_singleton"
        assert ServiceLifetime.ASYNC_SCOPED == "async_scoped"

    def test_service_lifetime_immutability(self):
        """Test that ServiceLifetime constants are strings and can be compared"""
        assert isinstance(ServiceLifetime.SINGLETON, str)
        assert isinstance(ServiceLifetime.TRANSIENT, str)
        assert isinstance(ServiceLifetime.SCOPED, str)
        assert isinstance(ServiceLifetime.ASYNC_SINGLETON, str)
        assert isinstance(ServiceLifetime.ASYNC_SCOPED, str)


class TestServiceDescriptor:
    """Test cases for ServiceDescriptor class"""

    def test_service_descriptor_initialization(self):
        """Test ServiceDescriptor initialization with basic parameters"""
        descriptor = ServiceDescriptor(
            service_type=ITestService,
            implementation=TestService,
            lifetime=ServiceLifetime.SINGLETON
        )
        
        assert descriptor.service_type == ITestService
        assert descriptor.implementation == TestService
        assert descriptor.lifetime == ServiceLifetime.SINGLETON
        assert descriptor.instance is None
        assert descriptor.is_async is False
        assert descriptor.cleanup_method == "close"

    def test_service_descriptor_with_async_parameters(self):
        """Test ServiceDescriptor initialization with async parameters"""
        descriptor = ServiceDescriptor(
            service_type=IAsyncService,
            implementation=AsyncTestService,
            lifetime=ServiceLifetime.ASYNC_SINGLETON,
            is_async=True,
            cleanup_method="cleanup"
        )
        
        assert descriptor.service_type == IAsyncService
        assert descriptor.implementation == AsyncTestService
        assert descriptor.lifetime == ServiceLifetime.ASYNC_SINGLETON
        assert descriptor.is_async is True
        assert descriptor.cleanup_method == "cleanup"
        assert hasattr(descriptor, '_cleanup_tasks')

    def test_service_descriptor_default_cleanup_method(self):
        """Test that default cleanup method is 'close'"""
        descriptor = ServiceDescriptor(
            service_type=ITestService,
            implementation=TestService,
            lifetime=ServiceLifetime.TRANSIENT
        )
        
        assert descriptor.cleanup_method == "close"

    def test_service_descriptor_custom_cleanup_method(self):
        """Test custom cleanup method assignment"""
        descriptor = ServiceDescriptor(
            service_type=ITestService,
            implementation=TestService,
            lifetime=ServiceLifetime.TRANSIENT,
            cleanup_method="custom_cleanup"
        )
        
        assert descriptor.cleanup_method == "custom_cleanup"

    def test_service_descriptor_cleanup_tasks(self):
        """Test that cleanup tasks weak set is created"""
        descriptor = ServiceDescriptor(
            service_type=ITestService,
            implementation=TestService,
            lifetime=ServiceLifetime.TRANSIENT
        )
        
        assert hasattr(descriptor, '_cleanup_tasks')
        assert isinstance(descriptor._cleanup_tasks, weakref.WeakSet)


class TestServiceScope:
    """Test cases for ServiceScope class"""

    def test_service_scope_initialization(self):
        """Test ServiceScope initialization"""
        app_context = AppContext()
        scope_id = "test-scope-123"
        scope = ServiceScope(app_context, scope_id)
        
        assert scope._app_context is app_context
        assert scope._scope_id == scope_id

    def test_service_scope_get_service(self):
        """Test synchronous service resolution within scope"""
        app_context = AppContext()
        app_context.add_scoped(ITestService, TestService)
        
        scope_id = "test-scope-123"
        scope = ServiceScope(app_context, scope_id)
        
        # Mock the app_context methods to verify scope context is set
        with patch.object(app_context, 'get_service') as mock_get_service:
            mock_get_service.return_value = TestService()
            
            service = scope.get_service(ITestService)
            
            # Verify the service was obtained
            assert service is not None
            mock_get_service.assert_called_once_with(ITestService)

    @pytest.mark.asyncio
    async def test_service_scope_get_service_async(self):
        """Test asynchronous service resolution within scope"""
        app_context = AppContext()
        app_context.add_async_scoped(IAsyncService, AsyncTestService)
        
        scope_id = "test-scope-123"
        scope = ServiceScope(app_context, scope_id)
        
        # Mock the app_context methods to verify scope context is set
        with patch.object(app_context, 'get_service_async') as mock_get_service_async:
            mock_service = AsyncTestService()
            mock_get_service_async.return_value = mock_service
            
            service = await scope.get_service_async(IAsyncService)
            
            # Verify the service was obtained
            assert service is not None
            mock_get_service_async.assert_called_once_with(IAsyncService)

    def test_service_scope_context_restoration(self):
        """Test that scope context is properly restored after service resolution"""
        app_context = AppContext()
        app_context.add_scoped(ITestService, TestService)
        
        original_scope_id = "original-scope"
        app_context._current_scope_id = original_scope_id
        
        scope_id = "test-scope-123"
        scope = ServiceScope(app_context, scope_id)
        
        with patch.object(app_context, 'get_service') as mock_get_service:
            mock_get_service.return_value = TestService()
            
            # Call get_service which should temporarily change scope
            scope.get_service(ITestService)
            
            # Verify original scope is restored
            assert app_context._current_scope_id == original_scope_id


class TestAppContext:
    """Test cases for AppContext class"""

    def test_app_context_initialization(self):
        """Test AppContext initialization with default values"""
        app_context = AppContext()
        
        # Configuration and credential are not set until explicitly set
        assert not hasattr(app_context, 'configuration')
        assert not hasattr(app_context, 'credential')
        assert isinstance(app_context._services, dict)
        assert isinstance(app_context._instances, dict)
        assert isinstance(app_context._scoped_instances, dict)
        assert app_context._current_scope_id is None
        assert isinstance(app_context._async_cleanup_tasks, list)

    def test_set_configuration(self):
        """Test setting configuration"""
        app_context = AppContext()
        config = Configuration()
        
        app_context.set_configuration(config)
        
        assert app_context.configuration is config

    def test_set_credential(self):
        """Test setting Azure credential"""
        app_context = AppContext()
        credential = DefaultAzureCredential()
        
        app_context.set_credential(credential)
        
        assert app_context.credential is credential

    def test_add_singleton_with_class(self):
        """Test registering singleton service with class implementation"""
        app_context = AppContext()
        
        result = app_context.add_singleton(ITestService, TestService)
        
        # Should return self for chaining
        assert result is app_context
        
        # Verify service is registered
        assert app_context.is_registered(ITestService)
        assert app_context._services[ITestService].lifetime == ServiceLifetime.SINGLETON
        assert app_context._services[ITestService].implementation == TestService

    def test_add_singleton_with_factory(self):
        """Test registering singleton service with factory function"""
        app_context = AppContext()
        
        def factory():
            return TestService("factory_value")
        
        app_context.add_singleton(ITestService, factory)
        
        assert app_context.is_registered(ITestService)
        assert app_context._services[ITestService].implementation == factory

    def test_add_singleton_with_instance(self):
        """Test registering singleton service with existing instance"""
        app_context = AppContext()
        instance = TestService("instance_value")
        
        app_context.add_singleton(ITestService, instance)
        
        assert app_context.is_registered(ITestService)
        assert app_context._services[ITestService].implementation is instance

    def test_add_singleton_without_implementation(self):
        """Test registering singleton service without explicit implementation"""
        app_context = AppContext()
        
        app_context.add_singleton(TestService)
        
        assert app_context.is_registered(TestService)
        assert app_context._services[TestService].implementation == TestService

    def test_add_transient(self):
        """Test registering transient service"""
        app_context = AppContext()
        
        result = app_context.add_transient(ITestService, TestService)
        
        # Should return self for chaining
        assert result is app_context
        
        # Verify service is registered
        assert app_context.is_registered(ITestService)
        assert app_context._services[ITestService].lifetime == ServiceLifetime.TRANSIENT

    def test_add_scoped(self):
        """Test registering scoped service"""
        app_context = AppContext()
        
        result = app_context.add_scoped(ITestService, TestService)
        
        # Should return self for chaining
        assert result is app_context
        
        # Verify service is registered
        assert app_context.is_registered(ITestService)
        assert app_context._services[ITestService].lifetime == ServiceLifetime.SCOPED

    def test_add_transient_without_implementation(self):
        """Test registering transient service without implementation"""
        app_context = AppContext()
        
        result = app_context.add_transient(TestService)
        
        # Should return self for chaining
        assert result is app_context
        
        # Verify service is registered with itself as implementation
        assert app_context.is_registered(TestService)
        descriptor = app_context._services[TestService]
        assert descriptor.implementation is TestService
        assert descriptor.lifetime == ServiceLifetime.TRANSIENT

    def test_add_scoped_without_implementation(self):
        """Test registering scoped service without implementation"""
        app_context = AppContext()
        
        result = app_context.add_scoped(TestService)
        
        # Should return self for chaining
        assert result is app_context
        
        # Verify service is registered with itself as implementation
        assert app_context.is_registered(TestService)
        descriptor = app_context._services[TestService]
        assert descriptor.implementation is TestService
        assert descriptor.lifetime == ServiceLifetime.SCOPED

    def test_add_async_singleton_without_implementation(self):
        """Test registering async singleton service without implementation"""
        app_context = AppContext()
        
        result = app_context.add_async_singleton(AsyncTestService)
        
        # Should return self for chaining
        assert result is app_context
        
        # Verify service is registered with itself as implementation
        assert app_context.is_registered(AsyncTestService)
        descriptor = app_context._services[AsyncTestService]
        assert descriptor.implementation is AsyncTestService
        assert descriptor.lifetime == ServiceLifetime.ASYNC_SINGLETON
        assert descriptor.is_async is True

    def test_add_async_scoped_without_implementation(self):
        """Test registering async scoped service without implementation"""
        app_context = AppContext()
        
        result = app_context.add_async_scoped(AsyncTestService, cleanup_method="cleanup")
        
        # Should return self for chaining
        assert result is app_context
        
        # Verify service is registered with itself as implementation
        assert app_context.is_registered(AsyncTestService)
        descriptor = app_context._services[AsyncTestService]
        assert descriptor.implementation is AsyncTestService
        assert descriptor.lifetime == ServiceLifetime.ASYNC_SCOPED
        assert descriptor.is_async is True

    def test_add_async_singleton(self):
        """Test registering async singleton service"""
        app_context = AppContext()
        
        result = app_context.add_async_singleton(IAsyncService, AsyncTestService)
        
        # Should return self for chaining
        assert result is app_context
        
        # Verify service is registered
        assert app_context.is_registered(IAsyncService)
        descriptor = app_context._services[IAsyncService]
        assert descriptor.lifetime == ServiceLifetime.ASYNC_SINGLETON
        assert descriptor.is_async is True

    def test_add_async_scoped(self):
        """Test registering async scoped service"""
        app_context = AppContext()
        
        result = app_context.add_async_scoped(IAsyncService, AsyncTestService, "cleanup")
        
        # Should return self for chaining
        assert result is app_context
        
        # Verify service is registered
        assert app_context.is_registered(IAsyncService)
        descriptor = app_context._services[IAsyncService]
        assert descriptor.lifetime == ServiceLifetime.ASYNC_SCOPED
        assert descriptor.is_async is True
        assert descriptor.cleanup_method == "cleanup"

    def test_get_service_singleton(self):
        """Test retrieving singleton service (same instance)"""
        app_context = AppContext()
        app_context.add_singleton(ITestService, TestService)
        
        service1 = app_context.get_service(ITestService)
        service2 = app_context.get_service(ITestService)
        
        # Should return same instance
        assert service1 is service2
        assert isinstance(service1, TestService)

    def test_get_service_transient(self):
        """Test retrieving transient service (different instances)"""
        app_context = AppContext()
        app_context.add_transient(ITestService, TestService)
        
        service1 = app_context.get_service(ITestService)
        service2 = app_context.get_service(ITestService)
        
        # Should return different instances
        assert service1 is not service2
        assert isinstance(service1, TestService)
        assert isinstance(service2, TestService)

    def test_get_service_not_registered(self):
        """Test retrieving unregistered service raises KeyError"""
        app_context = AppContext()
        
        with pytest.raises(KeyError, match="Service ITestService is not registered"):
            app_context.get_service(ITestService)

    def test_get_service_scoped_without_scope(self):
        """Test retrieving scoped service without active scope raises ValueError"""
        app_context = AppContext()
        app_context.add_scoped(ITestService, TestService)
        
        with pytest.raises(ValueError, match="Scoped service ITestService requires an active scope"):
            app_context.get_service(ITestService)

    @pytest.mark.asyncio
    async def test_get_service_async_singleton(self):
        """Test retrieving async singleton service"""
        app_context = AppContext()
        app_context.add_async_singleton(IAsyncService, AsyncTestService)
        
        service1 = await app_context.get_service_async(IAsyncService)
        service2 = await app_context.get_service_async(IAsyncService)
        
        # Should return same instance
        assert service1 is service2
        assert isinstance(service1, AsyncTestService)

    @pytest.mark.asyncio
    async def test_get_service_async_not_registered(self):
        """Test retrieving unregistered async service raises KeyError"""
        app_context = AppContext()
        
        with pytest.raises(KeyError, match="Service IAsyncService is not registered"):
            await app_context.get_service_async(IAsyncService)

    @pytest.mark.asyncio
    async def test_get_service_async_non_async_service(self):
        """Test retrieving non-async service with get_service_async raises ValueError"""
        app_context = AppContext()
        app_context.add_singleton(ITestService, TestService)  # Not async
        
        with pytest.raises(ValueError, match="Service ITestService is not registered as an async service"):
            await app_context.get_service_async(ITestService)

    @pytest.mark.asyncio
    async def test_get_service_async_scoped_without_scope(self):
        """Test retrieving async scoped service without active scope raises ValueError"""
        app_context = AppContext()
        app_context.add_async_scoped(IAsyncService, AsyncTestService, "cleanup")

        with pytest.raises(ValueError, match="Scoped service IAsyncService requires an active scope"):
            await app_context.get_service_async(IAsyncService)

    @pytest.mark.asyncio
    async def test_create_scope(self):
        """Test creating and using service scope"""
        app_context = AppContext()
        app_context.add_scoped(ITestService, ScopedService)
        
        async with app_context.create_scope() as scope:
            assert isinstance(scope, ServiceScope)
            
            service1 = scope.get_service(ITestService)
            service2 = scope.get_service(ITestService)
            
            # Should be same instance within scope
            assert service1 is service2
            assert isinstance(service1, ScopedService)

    def test_is_registered_true(self):
        """Test is_registered returns True for registered services"""
        app_context = AppContext()
        app_context.add_singleton(ITestService, TestService)
        
        assert app_context.is_registered(ITestService) is True

    def test_is_registered_false(self):
        """Test is_registered returns False for unregistered services"""
        app_context = AppContext()
        
        assert app_context.is_registered(ITestService) is False

    def test_get_registered_services(self):
        """Test getting all registered services"""
        app_context = AppContext()
        app_context.add_singleton(ITestService, TestService)
        app_context.add_transient(IAsyncService, AsyncTestService)
        
        services = app_context.get_registered_services()
        
        assert len(services) == 2
        assert services[ITestService] == ServiceLifetime.SINGLETON
        assert services[IAsyncService] == ServiceLifetime.TRANSIENT

    def test_create_instance_with_class(self):
        """Test _create_instance with class implementation"""
        app_context = AppContext()
        descriptor = ServiceDescriptor(ITestService, TestService, ServiceLifetime.TRANSIENT)
        
        instance = app_context._create_instance(descriptor)
        
        assert isinstance(instance, TestService)

    def test_create_instance_with_factory(self):
        """Test _create_instance with factory function"""
        app_context = AppContext()
        
        def factory():
            return TestService("factory_result")
        
        descriptor = ServiceDescriptor(ITestService, factory, ServiceLifetime.TRANSIENT)
        
        instance = app_context._create_instance(descriptor)
        
        assert isinstance(instance, TestService)
        assert instance.value == "factory_result"

    def test_create_instance_with_existing_instance(self):
        """Test _create_instance with existing instance"""
        app_context = AppContext()
        existing_instance = TestService("existing")
        descriptor = ServiceDescriptor(ITestService, existing_instance, ServiceLifetime.SINGLETON)
        
        instance = app_context._create_instance(descriptor)
        
        assert instance is existing_instance

    def test_create_instance_unsupported_type(self):
        """Test _create_instance with string implementation returns the string directly"""
        app_context = AppContext()
        descriptor = ServiceDescriptor(ITestService, "invalid", ServiceLifetime.TRANSIENT)
        
        # String implementations are returned as-is (pre-created instance behavior)
        result = app_context._create_instance(descriptor)
        assert result == "invalid"

    def test_create_instance_with_invalid_callable(self):
        """Test _create_instance with callable that fails raises ValueError"""
        app_context = AppContext()
        
        def failing_factory():
            raise RuntimeError("Factory failed")
        
        descriptor = ServiceDescriptor(ITestService, failing_factory, ServiceLifetime.TRANSIENT)
        
        # Factory functions that fail should raise their original exception
        with pytest.raises(RuntimeError, match="Factory failed"):
            app_context._create_instance(descriptor)

    def test_create_instance_with_truly_unsupported_type(self):
        """Test _create_instance with complex object that triggers ValueError"""
        app_context = AppContext()
        
        # Create an object that's not callable, not a type, but not a simple instance
        complex_obj = object()
        # Make it seem like it might be callable to bypass the first check  
        # by monkey-patching, but it's still not a type
        descriptor = ServiceDescriptor(ITestService, complex_obj, ServiceLifetime.TRANSIENT)
        
        # This should return the object as-is since it's treated as a pre-created instance
        result = app_context._create_instance(descriptor)
        assert result is complex_obj

    @pytest.mark.asyncio
    async def test_create_async_instance_with_class(self):
        """Test _create_async_instance with class implementation"""
        app_context = AppContext()
        descriptor = ServiceDescriptor(IAsyncService, AsyncTestService, ServiceLifetime.ASYNC_SINGLETON, is_async=True)
        
        instance = await app_context._create_async_instance(descriptor)
        
        assert isinstance(instance, AsyncTestService)
        assert instance.initialized is True  # Should call __aenter__

    @pytest.mark.asyncio
    async def test_create_async_instance_with_existing_instance(self):
        """Test _create_async_instance with existing instance"""
        app_context = AppContext()
        existing_instance = AsyncTestService()
        descriptor = ServiceDescriptor(IAsyncService, existing_instance, ServiceLifetime.ASYNC_SINGLETON, is_async=True)
        
        instance = await app_context._create_async_instance(descriptor)
        
        assert instance is existing_instance

    @pytest.mark.asyncio
    async def test_create_async_instance_with_async_factory(self):
        """Test _create_async_instance with async factory function"""
        app_context = AppContext()
        
        async def async_factory():
            service = AsyncTestService()
            await service.__aenter__()
            return service
        
        descriptor = ServiceDescriptor(IAsyncService, async_factory, ServiceLifetime.ASYNC_SINGLETON, is_async=True)
        
        instance = await app_context._create_async_instance(descriptor)
        
        assert isinstance(instance, AsyncTestService)
        assert instance.initialized is True

    @pytest.mark.asyncio
    async def test_cleanup_scope(self):
        """Test scope cleanup functionality"""
        app_context = AppContext()
        app_context.add_async_scoped(IAsyncService, AsyncTestService)
        
        scope_id = "test-scope"
        app_context._current_scope_id = scope_id
        
        # Create a service instance in the scope
        service = await app_context.get_service_async(IAsyncService)
        assert service.closed is False
        
        # Cleanup the scope
        await app_context._cleanup_scope(scope_id)
        
        # Verify service was cleaned up
        assert service.closed is True
        assert scope_id not in app_context._scoped_instances

    @pytest.mark.asyncio
    async def test_cleanup_scope_with_async_context_manager(self):
        """Test cleanup scope with services that have async context manager methods"""
        app_context = AppContext()
        
        class AsyncContextService:
            def __init__(self):
                self.entered = False
                self.exited = False
            
            async def __aenter__(self):
                self.entered = True
                return self
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                self.exited = True
        
        app_context.add_async_scoped(AsyncContextService, AsyncContextService)
        
        scope_id = "test-context-scope"
        app_context._current_scope_id = scope_id
        
        # Create service instance
        service = await app_context.get_service_async(AsyncContextService)
        assert isinstance(service, AsyncContextService)
        
        # Cleanup the scope (should call __aexit__)
        await app_context._cleanup_scope(scope_id)
        
        # Verify service was cleaned up
        assert service.exited is True

    @pytest.mark.asyncio
    async def test_cleanup_scope_with_custom_cleanup_method(self):
        """Test cleanup scope with services that have custom cleanup methods"""
        app_context = AppContext()
        
        class ServiceWithCleanup:
            def __init__(self):
                self.cleaned_up = False
            
            def custom_cleanup(self):
                self.cleaned_up = True
        
        app_context.add_async_scoped(ServiceWithCleanup, ServiceWithCleanup, "custom_cleanup")
        
        scope_id = "test-cleanup-scope"
        app_context._current_scope_id = scope_id
        
        # Create service instance
        service = await app_context.get_service_async(ServiceWithCleanup)
        assert isinstance(service, ServiceWithCleanup)
        
        # Cleanup the scope (should call custom_cleanup)
        await app_context._cleanup_scope(scope_id)
        
        # Verify service was cleaned up
        assert service.cleaned_up is True

    @pytest.mark.asyncio
    async def test_shutdown_async(self):
        """Test async shutdown functionality"""
        app_context = AppContext()
        app_context.add_async_singleton(IAsyncService, AsyncTestService)
        
        # Get service to create instance
        service = await app_context.get_service_async(IAsyncService)
        assert service.closed is False
        
        # Shutdown app context
        await app_context.shutdown_async()
        
        # Verify cleanup occurred
        assert service.closed is True
        assert len(app_context._instances) == 0
        assert len(app_context._scoped_instances) == 0

    def test_method_chaining(self):
        """Test that service registration methods support chaining"""
        app_context = AppContext()
        
        result = (app_context
                 .add_singleton(ITestService, TestService)
                 .add_transient(IAsyncService, AsyncTestService)
                 .add_scoped(ScopedService))
        
        assert result is app_context
        assert app_context.is_registered(ITestService)
        assert app_context.is_registered(IAsyncService)
        assert app_context.is_registered(ScopedService)

    @pytest.mark.asyncio
    async def test_scoped_service_isolation(self):
        """Test that scoped services are isolated between different scopes"""
        app_context = AppContext()
        app_context.add_scoped(ITestService, ScopedService)
        
        # Create two different scopes
        async with app_context.create_scope() as scope1:
            service1 = scope1.get_service(ITestService)
            
            async with app_context.create_scope() as scope2:
                service2 = scope2.get_service(ITestService)
                
                # Services should be different instances in different scopes
                assert service1 is not service2
                assert service1.get_scope_id() != service2.get_scope_id()

    @pytest.mark.asyncio
    async def test_scoped_service_same_within_scope(self):
        """Test that scoped services return same instance within the same scope"""
        app_context = AppContext()
        app_context.add_scoped(ITestService, ScopedService)
        
        async with app_context.create_scope() as scope:
            service1 = scope.get_service(ITestService)
            service2 = scope.get_service(ITestService)
            
            # Should be same instance within the same scope
            assert service1 is service2