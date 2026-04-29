import asyncio
from unittest.mock import MagicMock

import pytest

from libs.application.application_context import (
    AppContext,
    ServiceDescriptor,
    ServiceLifetime,
    ServiceScope,
)


class _DummyService:
    def __init__(self):
        self.created = True


class _AsyncResource:
    def __init__(self):
        self.entered = False
        self.exited = False
        self.closed = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True

    async def close(self):
        self.closed = True


class TestServiceLifetimeConstants:
    def test_constants_exist(self):
        assert ServiceLifetime.SINGLETON == "singleton"
        assert ServiceLifetime.TRANSIENT == "transient"
        assert ServiceLifetime.SCOPED == "scoped"
        assert ServiceLifetime.ASYNC_SINGLETON == "async_singleton"
        assert ServiceLifetime.ASYNC_SCOPED == "async_scoped"


class TestServiceDescriptor:
    def test_defaults(self):
        d = ServiceDescriptor(
            service_type=_DummyService,
            implementation=_DummyService,
            lifetime=ServiceLifetime.SINGLETON,
        )
        assert d.is_async is False
        assert d.cleanup_method == "close"
        assert d.instance is None

    def test_custom_cleanup_method(self):
        d = ServiceDescriptor(
            service_type=_DummyService,
            implementation=_DummyService,
            lifetime=ServiceLifetime.ASYNC_SINGLETON,
            is_async=True,
            cleanup_method="dispose",
        )
        assert d.cleanup_method == "dispose"
        assert d.is_async is True


class TestScopedServices:
    def test_scoped_service_requires_active_scope(self):
        ctx = AppContext()
        ctx.add_scoped(_DummyService, _DummyService)
        with pytest.raises(ValueError, match="requires an active scope"):
            ctx.get_service(_DummyService)

    def test_scoped_service_returns_same_instance_within_scope(self):
        ctx = AppContext()
        ctx.add_scoped(_DummyService, _DummyService)

        async def run():
            async with ctx.create_scope() as scope:
                a = scope.get_service(_DummyService)
                b = scope.get_service(_DummyService)
                assert a is b

        asyncio.run(run())

    def test_scoped_service_returns_different_instances_in_separate_scopes(self):
        ctx = AppContext()
        ctx.add_scoped(_DummyService, _DummyService)

        async def run():
            async with ctx.create_scope() as scope1:
                a = scope1.get_service(_DummyService)
            async with ctx.create_scope() as scope2:
                b = scope2.get_service(_DummyService)
            assert a is not b

        asyncio.run(run())


class TestAsyncSingleton:
    def test_async_singleton_returns_same_instance(self):
        ctx = AppContext()
        ctx.add_async_singleton(_AsyncResource, _AsyncResource)

        async def run():
            a = await ctx.get_service_async(_AsyncResource)
            b = await ctx.get_service_async(_AsyncResource)
            assert a is b
            assert a.entered is True

        asyncio.run(run())

    def test_get_service_async_raises_for_unregistered(self):
        ctx = AppContext()

        async def run():
            with pytest.raises(KeyError):
                await ctx.get_service_async(_DummyService)

        asyncio.run(run())

    def test_get_service_async_raises_for_non_async_service(self):
        ctx = AppContext()
        ctx.add_singleton(_DummyService, _DummyService)

        async def run():
            with pytest.raises(ValueError, match="not registered as an async service"):
                await ctx.get_service_async(_DummyService)

        asyncio.run(run())


class TestAsyncScoped:
    def test_async_scoped_requires_active_scope(self):
        ctx = AppContext()
        ctx.add_async_scoped(_AsyncResource, _AsyncResource)

        async def run():
            with pytest.raises(ValueError, match="requires an active scope"):
                await ctx.get_service_async(_AsyncResource)

        asyncio.run(run())

    def test_async_scoped_same_instance_in_scope(self):
        ctx = AppContext()
        ctx.add_async_scoped(_AsyncResource, _AsyncResource)

        async def run():
            async with ctx.create_scope() as scope:
                a = await scope.get_service_async(_AsyncResource)
                b = await scope.get_service_async(_AsyncResource)
                assert a is b
            # After scope exit, __aexit__ should be called
            assert a.exited is True

        asyncio.run(run())


class TestCreateInstance:
    def test_create_instance_supports_pre_created_instance(self):
        ctx = AppContext()
        existing = _DummyService()
        ctx.add_singleton(_DummyService, existing)
        assert ctx.get_service(_DummyService) is existing

    def test_create_instance_supports_callable(self):
        ctx = AppContext()
        ctx.add_transient(_DummyService, lambda: _DummyService())
        a = ctx.get_service(_DummyService)
        b = ctx.get_service(_DummyService)
        assert a is not b
        assert isinstance(a, _DummyService)


class TestShutdownAsync:
    def test_shutdown_calls_cleanup_method(self):
        ctx = AppContext()
        ctx.add_async_singleton(_AsyncResource, _AsyncResource)

        async def run():
            instance = await ctx.get_service_async(_AsyncResource)
            await ctx.shutdown_async()
            return instance

        instance = asyncio.run(run())
        # After shutdown, internal caches are cleared
        assert ctx._instances == {}
        assert ctx._scoped_instances == {}
        assert instance.closed is True

    def test_shutdown_with_no_services_is_noop(self):
        ctx = AppContext()
        asyncio.run(ctx.shutdown_async())  # should not raise


class TestCreateAsyncInstance:
    def test_async_factory_returning_coroutine(self):
        ctx = AppContext()

        async def factory():
            return _AsyncResource()

        ctx.add_async_singleton(_AsyncResource, factory)

        async def run():
            instance = await ctx.get_service_async(_AsyncResource)
            assert isinstance(instance, _AsyncResource)
            assert instance.entered is True

        asyncio.run(run())

    def test_async_instance_passthrough(self):
        ctx = AppContext()
        existing = _AsyncResource()
        # Pre-created instance (not callable, not a class)
        ctx.add_async_singleton(_AsyncResource, existing)

        async def run():
            instance = await ctx.get_service_async(_AsyncResource)
            assert instance is existing

        asyncio.run(run())


class TestServiceScope:
    def test_scope_restores_previous_scope_id(self):
        ctx = AppContext()
        ctx._current_scope_id = "outer"

        ctx.add_singleton(_DummyService, _DummyService)
        scope = ServiceScope(ctx, "inner")
        scope.get_service(_DummyService)
        assert ctx._current_scope_id == "outer"
