# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from libs.agent_framework.agent_speaking_capture import AgentSpeakingCaptureMiddleware


def _ctx(agent_name="A1", is_streaming=False, result=None, messages=None):
    agent = SimpleNamespace(name=agent_name)
    return SimpleNamespace(
        agent=agent,
        is_streaming=is_streaming,
        result=result,
        messages=messages or [],
    )


def _result_with_messages(*texts):
    msgs = [SimpleNamespace(text=t) for t in texts]
    return SimpleNamespace(messages=msgs)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


class TestAgentSpeakingCaptureMiddleware:
    def test_captures_non_streaming_response_with_messages(self):
        mw = AgentSpeakingCaptureMiddleware()

        async def _next(_ctx_):
            return None

        ctx = _ctx(result=_result_with_messages("hello", "world"))
        _run(mw.process(ctx, _next))

        all_responses = mw.get_all_responses()
        assert len(all_responses) == 1
        assert all_responses[0]["agent_name"] == "A1"
        assert "hello" in all_responses[0]["response"]
        assert "world" in all_responses[0]["response"]
        assert all_responses[0]["is_streaming"] is False

    def test_captures_response_with_text_attr(self):
        mw = AgentSpeakingCaptureMiddleware()
        result = SimpleNamespace(text="just text")

        async def _next(_):
            return None

        ctx = _ctx(result=result)
        _run(mw.process(ctx, _next))
        assert mw.get_all_responses()[0]["response"] == "just text"

    def test_captures_response_falls_back_to_str(self):
        mw = AgentSpeakingCaptureMiddleware()
        # No messages, no text -> str(result)
        result = "raw-string-value"

        async def _next(_):
            return None

        ctx = _ctx(result=result)
        _run(mw.process(ctx, _next))
        assert mw.get_all_responses()[0]["response"] == "raw-string-value"

    def test_streaming_records_placeholder(self):
        mw = AgentSpeakingCaptureMiddleware()

        async def _next(c):
            c.result = None  # generator already consumed
            return None

        ctx = _ctx(is_streaming=True, result=None)
        _run(mw.process(ctx, _next))
        responses = mw.get_all_responses()
        assert responses[0]["is_streaming"] is True
        assert "Streaming response" in responses[0]["response"]

    def test_no_storage_returns_empty(self):
        mw = AgentSpeakingCaptureMiddleware(store_responses=False)

        async def _next(_):
            return None

        ctx = _ctx(result=_result_with_messages("x"))
        _run(mw.process(ctx, _next))
        assert mw.get_all_responses() == []
        assert mw.get_responses_by_agent("A1") == []

    def test_clear_resets_storage(self):
        mw = AgentSpeakingCaptureMiddleware()

        async def _next(_):
            return None

        ctx = _ctx(result=_result_with_messages("hi"))
        _run(mw.process(ctx, _next))
        assert mw.get_all_responses()
        mw.clear()
        assert mw.get_all_responses() == []

    def test_get_responses_by_agent_filters(self):
        mw = AgentSpeakingCaptureMiddleware()

        async def _next(_):
            return None

        for name in ("A", "B", "A"):
            _run(mw.process(_ctx(agent_name=name, result=_result_with_messages("x")), _next))

        assert len(mw.get_responses_by_agent("A")) == 2
        assert len(mw.get_responses_by_agent("B")) == 1

    def test_async_callback_invoked(self):
        cb = AsyncMock()
        mw = AgentSpeakingCaptureMiddleware(callback=cb)

        async def _next(_):
            return None

        _run(mw.process(_ctx(result=_result_with_messages("hi")), _next))
        cb.assert_awaited_once()

    def test_sync_callback_invoked(self):
        seen = []

        def cb(data):
            seen.append(data["agent_name"])

        mw = AgentSpeakingCaptureMiddleware(callback=cb)

        async def _next(_):
            return None

        _run(mw.process(_ctx(agent_name="X", result=_result_with_messages("h")), _next))
        assert seen == ["X"]

    def test_callback_exception_swallowed(self, capsys):
        def cb(_):
            raise RuntimeError("boom")

        mw = AgentSpeakingCaptureMiddleware(callback=cb)

        async def _next(_):
            return None

        _run(mw.process(_ctx(result=_result_with_messages("h")), _next))
        captured = capsys.readouterr()
        assert "WARNING" in captured.out

    def test_stream_complete_callback_invoked(self):
        cb = AsyncMock()
        mw = AgentSpeakingCaptureMiddleware(on_stream_response_complete=cb)

        async def _next(_):
            return None

        _run(mw.process(_ctx(is_streaming=True), _next))
        cb.assert_awaited_once()

    def test_agent_without_name_uses_str(self):
        mw = AgentSpeakingCaptureMiddleware()

        async def _next(_):
            return None

        # Use an object that does not have 'name'
        class A:
            def __str__(self):
                return "AGENT_STR"

        ctx = SimpleNamespace(
            agent=A(), is_streaming=False, result=_result_with_messages("x"), messages=[]
        )
        _run(mw.process(ctx, _next))
        assert mw.get_all_responses()[0]["agent_name"] == "AGENT_STR"
