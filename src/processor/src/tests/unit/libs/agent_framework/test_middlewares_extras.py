# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import libs.agent_framework.middlewares as middlewares_module

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"


class Message:
    """Test stub for Message - the real Message in 1.3.0 uses contents= instead of text=."""

    def __init__(self, *, role, text=None, contents=None, author_name=None):
        self.role = role
        self.text = text
        self.contents = contents
        self.author_name = author_name


# Patch at module level: middleware code references Message at runtime for isinstance
# checks and construction. This is scoped to test execution only.
_original_message = getattr(middlewares_module, "Message", None)
middlewares_module.Message = Message
from libs.agent_framework.middlewares import (  # noqa: E402
    DebuggingMiddleware,
    LoggingFunctionMiddleware,
)


def teardown_module(module=None):
    """Restore the original Message class to avoid leaking into other tests."""
    if _original_message is not None:
        middlewares_module.Message = _original_message


def _run(coro):
    return asyncio.run(coro)


class TestDebuggingMiddleware:
    def test_process_sets_metadata_and_calls_next(self, capsys):
        ctx = MagicMock()
        ctx.messages = [MagicMock(), MagicMock()]
        ctx.is_streaming = True
        ctx.metadata = {"existing": "value"}
        next_fn = AsyncMock()
        mw = DebuggingMiddleware()
        _run(mw.process(ctx, next_fn))
        assert ctx.metadata["debug_enabled"] is True
        next_fn.assert_awaited_once_with(ctx)

    def test_process_with_empty_metadata(self):
        ctx = MagicMock()
        ctx.messages = []
        ctx.is_streaming = False
        ctx.metadata = {}
        next_fn = AsyncMock()
        mw = DebuggingMiddleware()
        _run(mw.process(ctx, next_fn))
        next_fn.assert_awaited_once()


class TestLoggingFunctionMiddleware:
    def _make_ctx(self, args=None, result=None):
        ctx = MagicMock()
        ctx.function = MagicMock()
        ctx.function.name = "do_thing"
        if args is not None:
            ctx.arguments = MagicMock()
            ctx.arguments.model_dump.return_value = args
        else:
            ctx.arguments = None
        ctx.result = result
        return ctx

    def test_process_with_no_args_no_result(self):
        ctx = self._make_ctx()
        next_fn = AsyncMock()
        _run(LoggingFunctionMiddleware().process(ctx, next_fn))
        next_fn.assert_awaited_once_with(ctx)

    def test_process_with_args_and_string_result(self):
        ctx = self._make_ctx(args={"x": 1, "y": "z"}, result="hello")
        next_fn = AsyncMock()
        _run(LoggingFunctionMiddleware().process(ctx, next_fn))
        next_fn.assert_awaited_once()

    def test_process_with_long_string_result_truncated(self):
        ctx = self._make_ctx(args={"x": 1}, result="A" * 2000)
        _run(LoggingFunctionMiddleware().process(ctx, AsyncMock()))

    def test_process_with_list_result_with_raw_representation(self):
        item = SimpleNamespace(raw_representation={"data": "ok"}, is_error=False)
        ctx = self._make_ctx(args={"x": 1}, result=[item])
        _run(LoggingFunctionMiddleware().process(ctx, AsyncMock()))

    def test_process_with_long_raw_representation_truncated(self):
        item = SimpleNamespace(raw_representation="B" * 2000, is_error=True)
        ctx = self._make_ctx(args={"x": 1}, result=[item])
        _run(LoggingFunctionMiddleware().process(ctx, AsyncMock()))


class TestInputObserverMiddleware:
    def test_replaces_user_messages_when_replacement_set(self):
        from libs.agent_framework.middlewares import InputObserverMiddleware

        msg_user = Message(role=ROLE_USER, text="orig user", contents="orig user")
        msg_assistant = Message(role=ROLE_ASSISTANT, text="hi", contents="hi")
        ctx = MagicMock()
        ctx.messages = [msg_user, msg_assistant]
        next_fn = AsyncMock()
        mw = InputObserverMiddleware(replacement="REDACTED")
        _run(mw.process(ctx, next_fn))
        # First message replaced, second untouched
        assert ctx.messages[0].contents == "REDACTED"
        assert ctx.messages[1].contents == "hi"
        next_fn.assert_awaited_once()

    def test_no_replacement_keeps_text(self):
        from libs.agent_framework.middlewares import InputObserverMiddleware

        msg = Message(role=ROLE_USER, text="keep me", contents="keep me")
        ctx = MagicMock()
        ctx.messages = [msg]
        mw = InputObserverMiddleware(replacement=None)
        _run(mw.process(ctx, AsyncMock()))
        assert ctx.messages[0].text == "keep me"
