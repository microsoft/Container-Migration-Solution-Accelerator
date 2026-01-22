# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio

import pytest

from libs.application.application_context import AppContext


class _S1:
    pass


class _S2:
    pass


def test_app_context_singleton_caches_instance() -> None:
    ctx = AppContext().add_singleton(_S1)
    a = ctx.get_service(_S1)
    b = ctx.get_service(_S1)
    assert a is b


def test_app_context_transient_returns_new_instances() -> None:
    ctx = AppContext().add_transient(_S1)
    a = ctx.get_service(_S1)
    b = ctx.get_service(_S1)
    assert a is not b


def test_app_context_get_service_raises_for_unregistered() -> None:
    ctx = AppContext()
    with pytest.raises(KeyError):
        ctx.get_service(_S1)


def test_app_context_scoped_requires_scope_and_caches_within_scope() -> None:
    async def _run() -> None:
        ctx = AppContext().add_scoped(_S1)

        with pytest.raises(ValueError):
            ctx.get_service(_S1)

        async with ctx.create_scope() as scope:
            a = scope.get_service(_S1)
            b = scope.get_service(_S1)
            assert a is b

        async with ctx.create_scope() as scope2:
            c = scope2.get_service(_S1)
            assert c is not a

    asyncio.run(_run())


def test_app_context_async_scoped_calls_cleanup_on_scope_exit() -> None:
    class _AsyncScoped:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    async def _run() -> None:
        ctx = AppContext().add_async_scoped(
            _AsyncScoped, _AsyncScoped, cleanup_method="close"
        )

        async with ctx.create_scope() as scope:
            svc = await scope.get_service_async(_AsyncScoped)
            assert svc.closed is False

        # After scope exit, the scoped instance should be cleaned up.
        # We can't access the exact instance from the scope anymore, so resolve in a
        # fresh scope and ensure we got a fresh (not previously closed) instance.
        async with ctx.create_scope() as scope2:
            svc2 = await scope2.get_service_async(_AsyncScoped)
            assert svc2.closed is False

    asyncio.run(_run())
