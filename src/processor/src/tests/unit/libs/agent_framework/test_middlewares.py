# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for DebuggingMiddleware and LoggingFunctionMiddleware."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from libs.agent_framework.middlewares import (
    DebuggingMiddleware,
    LoggingFunctionMiddleware,
)


def test_debugging_middleware_sets_metadata_and_calls_next(capsys) -> None:
    called = []

    async def _next(ctx):
        called.append(ctx)

    ctx = SimpleNamespace(messages=[1, 2, 3], is_streaming=False, metadata={"existing": "v"})
    mw = DebuggingMiddleware()

    asyncio.run(mw.process(ctx, _next))

    assert ctx.metadata["debug_enabled"] is True
    assert ctx.metadata["existing"] == "v"
    assert called == [ctx]
    out = capsys.readouterr().out
    assert "Debug mode enabled" in out
    assert "Messages count: 3" in out
    assert "Debug information collected" in out


def test_debugging_middleware_with_empty_metadata(capsys) -> None:
    async def _next(ctx):
        pass

    ctx = SimpleNamespace(messages=[], is_streaming=True, metadata={})
    mw = DebuggingMiddleware()

    asyncio.run(mw.process(ctx, _next))

    assert ctx.metadata == {"debug_enabled": True}


def _function_ctx(*, name="my_func", arguments=None, result=None):
    fn = SimpleNamespace(name=name)
    args = (
        SimpleNamespace(model_dump=lambda: arguments)
        if arguments is not None
        else None
    )
    return SimpleNamespace(function=fn, arguments=args, result=result)


def test_logging_function_middleware_logs_arguments_and_result(capsys) -> None:
    async def _next(ctx):
        pass

    ctx = _function_ctx(
        name="weather_lookup",
        arguments={"city": "Seattle", "units": "C"},
        result="sunny",
    )
    mw = LoggingFunctionMiddleware()

    asyncio.run(mw.process(ctx, _next))

    out = capsys.readouterr().out
    assert "Function Name: weather_lookup" in out
    assert "city: Seattle" in out
    assert "units: C" in out
    assert "sunny" in out


def test_logging_function_middleware_without_args_or_result(capsys) -> None:
    async def _next(ctx):
        pass

    ctx = _function_ctx(name="no_args", arguments=None, result=None)
    mw = LoggingFunctionMiddleware()

    asyncio.run(mw.process(ctx, _next))

    out = capsys.readouterr().out
    assert "Arguments: None" in out
    assert "Output Results: None" in out


def test_logging_function_middleware_handles_raw_representation(capsys) -> None:
    async def _next(ctx):
        pass

    raw = {"data": "x"}
    result_obj = SimpleNamespace(raw_representation=raw, is_error=False)
    ctx = _function_ctx(arguments={}, result=result_obj)

    mw = LoggingFunctionMiddleware()
    asyncio.run(mw.process(ctx, _next))

    out = capsys.readouterr().out
    assert "Type: dict" in out
    assert "Is Error: False" in out


def test_logging_function_middleware_truncates_large_output(capsys) -> None:
    async def _next(ctx):
        pass

    big = "x" * 2000
    ctx = _function_ctx(arguments={}, result=big)

    mw = LoggingFunctionMiddleware()
    asyncio.run(mw.process(ctx, _next))

    out = capsys.readouterr().out
    assert "(truncated)" in out


def test_logging_function_middleware_handles_list_results(capsys) -> None:
    async def _next(ctx):
        pass

    results = [
        SimpleNamespace(raw_representation="r1" * 600, is_error=True),
        "plain-string-" + ("y" * 1500),
    ]
    ctx = _function_ctx(arguments={}, result=results)

    mw = LoggingFunctionMiddleware()
    asyncio.run(mw.process(ctx, _next))

    out = capsys.readouterr().out
    assert "Result #1" in out
    assert "Result #2" in out
    assert "Is Error: True" in out
    assert "(truncated)" in out
