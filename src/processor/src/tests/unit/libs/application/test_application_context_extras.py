# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio

import pytest

from libs.application.application_context import (
    AppContext,
    ServiceDescriptor,
    ServiceLifetime,
)


class _S:
    pass


class _AsyncSvc:
    def __init__(self) -> None:
        self.closed = False
        self.entered = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, *exc):
        self.closed = True

    async def close(self) -> None:
        self.closed = True


class _SyncCleanup:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_set_configuration_and_credential():
    ctx = AppContext()
    ctx.set_configuration(object())  # type: ignore[arg-type]
    ctx.set_credential(object())  # type: ignore[arg-type]
    assert ctx.configuration is not None
    assert ctx.credential is not None


def test_is_registered_and_get_registered_services():
    ctx = AppContext().add_singleton(_S)
    assert ctx.is_registered(_S) is True
    assert ctx.is_registered(int) is False
    services = ctx.get_registered_services()
    assert _S in services
    assert services[_S] == ServiceLifetime.SINGLETON


def test_async_singleton_caches():
    async def _run():
        ctx = AppContext().add_async_singleton(_AsyncSvc)
        a = await ctx.get_service_async(_AsyncSvc)
        b = await ctx.get_service_async(_AsyncSvc)
        assert a is b
        assert a.entered is True

    asyncio.run(_run())


def test_get_service_async_raises_for_unregistered():
    async def _run():
        ctx = AppContext()
        with pytest.raises(KeyError):
            await ctx.get_service_async(_S)

    asyncio.run(_run())


def test_get_service_async_raises_for_non_async():
    async def _run():
        ctx = AppContext().add_singleton(_S)
        with pytest.raises(ValueError):
            await ctx.get_service_async(_S)

    asyncio.run(_run())


def test_async_scoped_requires_scope():
    async def _run():
        ctx = AppContext().add_async_scoped(_AsyncSvc)
        with pytest.raises(ValueError):
            await ctx.get_service_async(_AsyncSvc)

    asyncio.run(_run())


def test_async_transient_creates_new_instances():
    async def _run():
        ctx = AppContext()
        # register as async singleton type but resolve via direct descriptor injection
        # to exercise non-singleton, non-scoped async path.
        descriptor = ServiceDescriptor(
            service_type=_AsyncSvc,
            implementation=_AsyncSvc,
            lifetime=ServiceLifetime.TRANSIENT,
            is_async=True,
        )
        ctx._services[_AsyncSvc] = descriptor
        a = await ctx.get_service_async(_AsyncSvc)
        b = await ctx.get_service_async(_AsyncSvc)
        assert a is not b

    asyncio.run(_run())


def test_create_async_instance_with_callable_factory():
    async def _run():
        ctx = AppContext().add_async_singleton(_AsyncSvc, lambda: _AsyncSvc())
        a = await ctx.get_service_async(_AsyncSvc)
        assert isinstance(a, _AsyncSvc)
        assert a.entered is True

    asyncio.run(_run())


def test_create_async_instance_with_async_factory():
    async def _run():
        async def factory():
            return _AsyncSvc()

        ctx = AppContext().add_async_singleton(_AsyncSvc, factory)
        a = await ctx.get_service_async(_AsyncSvc)
        assert isinstance(a, _AsyncSvc)

    asyncio.run(_run())


def test_create_async_instance_with_pre_built_instance():
    async def _run():
        instance = _AsyncSvc()
        ctx = AppContext().add_async_singleton(_AsyncSvc, instance)
        a = await ctx.get_service_async(_AsyncSvc)
        # add_async_singleton path: implementation is callable when passing class but
        # passing instance bypasses callable check and is returned as-is.
        assert a is instance

    asyncio.run(_run())


def test_create_instance_with_factory_callable():
    ctx = AppContext().add_singleton(_S, lambda: _S())
    a = ctx.get_service(_S)
    assert isinstance(a, _S)


def test_create_instance_with_pre_built_instance():
    instance = _S()
    ctx = AppContext().add_singleton(_S, instance)
    assert ctx.get_service(_S) is instance


def test_shutdown_async_clears_caches_and_calls_cleanup():
    async def _run():
        ctx = AppContext().add_async_singleton(
            _SyncCleanup, _SyncCleanup, cleanup_method="close"
        )
        instance = await ctx.get_service_async(_SyncCleanup)
        assert instance.closed is False
        await ctx.shutdown_async()
        assert instance.closed is True
        # caches cleared
        assert ctx._instances == {}

    asyncio.run(_run())


def test_async_scoped_cleanup_via_aexit():
    async def _run():
        ctx = AppContext().add_async_scoped(_AsyncSvc)
        async with ctx.create_scope() as scope:
            svc = await scope.get_service_async(_AsyncSvc)
            assert svc.closed is False
        # __aexit__ should have been called via _cleanup_scope
        assert svc.closed is True

    asyncio.run(_run())
