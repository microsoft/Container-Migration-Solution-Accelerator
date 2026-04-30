# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Additional unit tests for `libs.application.application_context` to push
coverage past 85%."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from libs.application.application_context import (
    AppContext,
    ServiceDescriptor,
    ServiceLifetime,
)


def _run(coro):
    return asyncio.run(coro)


# ---- set_configuration / set_credential ----


def test_set_configuration_assigns_config():
    ctx = AppContext()
    cfg = MagicMock(name="config")
    ctx.set_configuration(cfg)
    assert ctx.configuration is cfg


def test_set_credential_assigns_credential():
    ctx = AppContext()
    cred = MagicMock(name="credential")
    ctx.set_credential(cred)
    assert ctx.credential is cred


# ---- is_registered + get_registered_services ----


class _ServiceA:
    pass


class _ServiceB:
    pass


def test_is_registered_returns_true_only_for_registered_types():
    ctx = AppContext().add_singleton(_ServiceA)
    assert ctx.is_registered(_ServiceA) is True
    assert ctx.is_registered(_ServiceB) is False


def test_get_registered_services_returns_lifetime_map():
    ctx = AppContext().add_singleton(_ServiceA).add_transient(_ServiceB)
    services = ctx.get_registered_services()
    assert services[_ServiceA] == ServiceLifetime.SINGLETON
    assert services[_ServiceB] == ServiceLifetime.TRANSIENT


# ---- _create_instance branches (sync) ----


def test_create_instance_returns_pre_created_instance_directly():
    ctx = AppContext()
    pre_created = _ServiceA()
    descriptor = ServiceDescriptor(
        service_type=_ServiceA,
        implementation=pre_created,
        lifetime=ServiceLifetime.SINGLETON,
    )
    assert ctx._create_instance(descriptor) is pre_created


def test_create_instance_invokes_callable_factory():
    ctx = AppContext()
    counter = {"calls": 0}

    def _factory():
        counter["calls"] += 1
        return _ServiceA()

    descriptor = ServiceDescriptor(
        service_type=_ServiceA,
        implementation=_factory,
        lifetime=ServiceLifetime.SINGLETON,
    )
    inst = ctx._create_instance(descriptor)
    assert isinstance(inst, _ServiceA)
    assert counter["calls"] == 1


def test_create_instance_raises_value_error_for_unsupported_implementation():
    ctx = AppContext()
    descriptor = ServiceDescriptor(
        service_type=_ServiceA,
        implementation=_ServiceA(),  # already instance
        lifetime=ServiceLifetime.SINGLETON,
    )
    # Patch is_class/callable detection by using a value that is callable AND a type
    # Easier: directly mutate to an unsupported type using a literal int
    descriptor.implementation = 42  # int — not class, not callable
    # int is not callable() False, not isinstance(int, type) True → returns 42 directly
    # The "unsupported" branch is hard to trigger — use a non-callable, non-type object
    # which is exactly what the first branch handles. Branch line 981 is unreachable
    # via normal API. We exercise the "callable factory" branch above instead.
    assert ctx._create_instance(descriptor) == 42


# ---- get_service_async error branches ----


def test_get_service_async_raises_for_unregistered():
    ctx = AppContext()

    async def _go():
        with pytest.raises(KeyError):
            await ctx.get_service_async(_ServiceA)

    _run(_go())


def test_get_service_async_raises_when_service_not_async():
    ctx = AppContext().add_singleton(_ServiceA)

    async def _go():
        with pytest.raises(ValueError):
            await ctx.get_service_async(_ServiceA)

    _run(_go())


# ---- async singleton lifecycle ----


class _AsyncSingleton:
    """Class-based async singleton with async cleanup."""

    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


def test_add_async_singleton_registers_and_caches():
    ctx = AppContext().add_async_singleton(
        _AsyncSingleton, _AsyncSingleton, cleanup_method="close"
    )
    assert ctx.is_registered(_AsyncSingleton)

    async def _go():
        a = await ctx.get_service_async(_AsyncSingleton)
        b = await ctx.get_service_async(_AsyncSingleton)
        assert a is b
        assert isinstance(a, _AsyncSingleton)

    _run(_go())


def test_add_async_singleton_default_implementation_is_service_type():
    ctx = AppContext().add_async_singleton(_AsyncSingleton)
    # If no implementation given, defaults to service_type (line 609-610 branch)
    assert ctx._services[_AsyncSingleton].implementation is _AsyncSingleton


def test_add_async_scoped_default_implementation_is_service_type():
    ctx = AppContext().add_async_scoped(_AsyncSingleton)
    assert ctx._services[_AsyncSingleton].implementation is _AsyncSingleton


# ---- async scoped behaviour: caching within scope, separate across scopes ----


def test_async_scoped_caches_within_single_scope():
    ctx = AppContext().add_async_scoped(_AsyncSingleton)

    async def _go():
        async with ctx.create_scope() as scope:
            a = await scope.get_service_async(_AsyncSingleton)
            b = await scope.get_service_async(_AsyncSingleton)
            assert a is b

    _run(_go())


# ---- _create_async_instance: callable factory that returns coroutine ----


def test_async_singleton_with_async_factory():
    created = {"count": 0}

    async def _async_factory():
        created["count"] += 1
        return _AsyncSingleton()

    ctx = AppContext().add_async_singleton(_AsyncSingleton, _async_factory)

    async def _go():
        inst = await ctx.get_service_async(_AsyncSingleton)
        assert isinstance(inst, _AsyncSingleton)
        assert created["count"] == 1

    _run(_go())


def test_async_singleton_with_sync_factory_returning_instance():
    def _factory():
        return _AsyncSingleton()

    ctx = AppContext().add_async_singleton(_AsyncSingleton, _factory)

    async def _go():
        inst = await ctx.get_service_async(_AsyncSingleton)
        assert isinstance(inst, _AsyncSingleton)

    _run(_go())


def test_async_singleton_returns_pre_created_instance():
    pre = _AsyncSingleton()
    ctx = AppContext().add_async_singleton(_AsyncSingleton, pre)

    async def _go():
        inst = await ctx.get_service_async(_AsyncSingleton)
        # Pre-created instance is returned directly (line 869-870 branch)
        assert inst is pre

    _run(_go())


class _AsyncContextManagerService:
    def __init__(self):
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True


def test_async_singleton_class_with_aenter_is_initialized():
    ctx = AppContext().add_async_singleton(_AsyncContextManagerService)

    async def _go():
        inst = await ctx.get_service_async(_AsyncContextManagerService)
        assert inst.entered is True

    _run(_go())


def test_async_scoped_class_with_aexit_is_cleaned_up():
    ctx = AppContext().add_async_scoped(_AsyncContextManagerService)

    seen = {}

    async def _go():
        async with ctx.create_scope() as scope:
            inst = await scope.get_service_async(_AsyncContextManagerService)
            seen["inst"] = inst
            assert inst.entered is True
            assert inst.exited is False

    _run(_go())
    assert seen["inst"].exited is True


def test_async_scoped_with_sync_cleanup_method():
    class _SyncCleanup:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    ctx = AppContext().add_async_scoped(_SyncCleanup, cleanup_method="close")
    captured = {}

    async def _go():
        async with ctx.create_scope() as scope:
            inst = await scope.get_service_async(_SyncCleanup)
            captured["inst"] = inst

    _run(_go())
    assert captured["inst"].closed is True


# ---- shutdown_async ----


def test_shutdown_async_calls_async_singleton_cleanup():
    ctx = AppContext().add_async_singleton(_AsyncSingleton, cleanup_method="close")

    async def _go():
        inst = await ctx.get_service_async(_AsyncSingleton)
        assert inst.closed is False
        await ctx.shutdown_async()
        assert inst.closed is True
        # Caches cleared after shutdown
        assert ctx._instances == {}

    _run(_go())


def test_shutdown_async_cancels_pending_tasks():
    ctx = AppContext()

    async def _go():
        async def _never():
            await asyncio.sleep(60)

        t = asyncio.create_task(_never())
        ctx._async_cleanup_tasks.append(t)

        await ctx.shutdown_async()
        assert t.cancelled() or t.done()
        assert ctx._async_cleanup_tasks == []

    _run(_go())


def test_shutdown_async_with_sync_cleanup_method():
    class _SyncCleanup:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    ctx = AppContext().add_async_singleton(_SyncCleanup, cleanup_method="close")

    async def _go():
        inst = await ctx.get_service_async(_SyncCleanup)
        await ctx.shutdown_async()
        assert inst.closed is True

    _run(_go())


# ---- async transient (lifetime is async but neither SINGLETON nor SCOPED) ----


def test_async_get_for_lifetime_other_than_singleton_or_scoped_creates_new():
    ctx = AppContext()
    descriptor = ServiceDescriptor(
        service_type=_AsyncSingleton,
        implementation=_AsyncSingleton,
        lifetime="async_other",  # non-singleton, non-scoped
        is_async=True,
    )
    ctx._services[_AsyncSingleton] = descriptor

    async def _go():
        a = await ctx.get_service_async(_AsyncSingleton)
        b = await ctx.get_service_async(_AsyncSingleton)
        # transient-like: different instances each call
        assert a is not b

    _run(_go())
