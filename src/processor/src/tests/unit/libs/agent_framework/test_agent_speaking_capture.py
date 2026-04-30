# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for AgentSpeakingCaptureMiddleware."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from libs.agent_framework.agent_speaking_capture import AgentSpeakingCaptureMiddleware


def _make_ctx(*, agent_name="Agent1", is_streaming=False, result=None, messages=None):
    return SimpleNamespace(
        agent=SimpleNamespace(name=agent_name),
        is_streaming=is_streaming,
        result=result,
        messages=messages or [],
        metadata={},
    )


async def _noop_next(_ctx):  # pragma: no cover - simple stub
    return None


def test_init_with_store_responses_true_creates_list() -> None:
    mw = AgentSpeakingCaptureMiddleware()
    assert mw.captured_responses == []
    assert mw.callback is None
    assert mw.on_stream_response_complete is None
    assert mw.store_responses is True


def test_init_with_store_responses_false_uses_none() -> None:
    mw = AgentSpeakingCaptureMiddleware(store_responses=False)
    assert mw.captured_responses is None
    assert mw.get_all_responses() == []
    assert mw.get_responses_by_agent("any") == []
    mw.clear()  # should be a no-op


def test_process_non_streaming_with_messages_text() -> None:
    captured = []

    def cb(data):
        captured.append(data)

    mw = AgentSpeakingCaptureMiddleware(callback=cb)
    msgs = [SimpleNamespace(text="hello"), SimpleNamespace(text="world")]
    result = SimpleNamespace(messages=msgs)
    ctx = _make_ctx(agent_name="A1", result=result)

    asyncio.run(mw.process(ctx, _noop_next))

    assert len(mw.captured_responses) == 1
    rec = mw.captured_responses[0]
    assert rec["agent_name"] == "A1"
    assert rec["response"] == "hello\nworld"
    assert rec["is_streaming"] is False
    assert captured == mw.captured_responses


def test_process_non_streaming_falls_back_to_text_attr() -> None:
    mw = AgentSpeakingCaptureMiddleware()
    result = SimpleNamespace(text="single-text")
    ctx = _make_ctx(result=result)

    asyncio.run(mw.process(ctx, _noop_next))

    assert mw.captured_responses[0]["response"] == "single-text"


def test_process_non_streaming_falls_back_to_str() -> None:
    mw = AgentSpeakingCaptureMiddleware()

    class Obj:
        def __str__(self):
            return "stringified"

    ctx = _make_ctx(result=Obj())

    asyncio.run(mw.process(ctx, _noop_next))

    assert mw.captured_responses[0]["response"] == "stringified"


def test_process_agent_without_name_uses_str_agent() -> None:
    mw = AgentSpeakingCaptureMiddleware()
    ctx = SimpleNamespace(
        agent="raw-agent-string",
        is_streaming=False,
        result=SimpleNamespace(text="x"),
        messages=[],
        metadata={},
    )

    asyncio.run(mw.process(ctx, _noop_next))

    assert mw.captured_responses[0]["agent_name"] == "raw-agent-string"


def test_process_streaming_records_placeholder_and_clears_buffer() -> None:
    stream_complete = []

    async def on_complete(data):
        stream_complete.append(data)

    mw = AgentSpeakingCaptureMiddleware(on_stream_response_complete=on_complete)
    ctx = _make_ctx(is_streaming=True, result=object())

    asyncio.run(mw.process(ctx, _noop_next))

    assert len(mw.captured_responses) == 1
    rec = mw.captured_responses[0]
    assert rec["is_streaming"] is True
    assert "[Streaming response" in rec["response"]
    assert mw._streaming_buffers == {}
    assert stream_complete == [rec]


def test_process_with_async_callback() -> None:
    received = []

    async def cb(data):
        received.append(data)

    mw = AgentSpeakingCaptureMiddleware(callback=cb)
    ctx = _make_ctx(result=SimpleNamespace(text="t"))

    asyncio.run(mw.process(ctx, _noop_next))

    assert len(received) == 1


def test_process_callback_exception_does_not_break_chain(capsys) -> None:
    def bad_callback(_data):
        raise RuntimeError("oops")

    mw = AgentSpeakingCaptureMiddleware(callback=bad_callback)
    ctx = _make_ctx(result=SimpleNamespace(text="t"))

    asyncio.run(mw.process(ctx, _noop_next))

    out = capsys.readouterr().out
    assert "Callback error" in out
    assert len(mw.captured_responses) == 1


def test_process_stream_complete_callback_exception_does_not_break(capsys) -> None:
    async def bad(_data):
        raise RuntimeError("oops-stream")

    mw = AgentSpeakingCaptureMiddleware(on_stream_response_complete=bad)
    ctx = _make_ctx(is_streaming=True, result=object())

    asyncio.run(mw.process(ctx, _noop_next))

    out = capsys.readouterr().out
    assert "Stream complete callback error" in out


def test_process_with_store_responses_false_skips_storage_but_calls_callback() -> None:
    received = []

    def cb(data):
        received.append(data)

    mw = AgentSpeakingCaptureMiddleware(callback=cb, store_responses=False)
    ctx = _make_ctx(result=SimpleNamespace(text="x"))

    asyncio.run(mw.process(ctx, _noop_next))

    assert mw.captured_responses is None
    assert len(received) == 1


def test_get_responses_by_agent_filters() -> None:
    mw = AgentSpeakingCaptureMiddleware()
    asyncio.run(mw.process(_make_ctx(agent_name="A1", result=SimpleNamespace(text="x")), _noop_next))
    asyncio.run(mw.process(_make_ctx(agent_name="A2", result=SimpleNamespace(text="y")), _noop_next))
    asyncio.run(mw.process(_make_ctx(agent_name="A1", result=SimpleNamespace(text="z")), _noop_next))

    a1 = mw.get_responses_by_agent("A1")
    assert len(a1) == 2
    assert all(r["agent_name"] == "A1" for r in a1)


def test_get_all_responses_and_clear() -> None:
    mw = AgentSpeakingCaptureMiddleware()
    asyncio.run(mw.process(_make_ctx(result=SimpleNamespace(text="x")), _noop_next))
    assert len(mw.get_all_responses()) == 1
    mw.clear()
    assert mw.get_all_responses() == []


def test_process_skips_capture_when_no_result_and_not_streaming() -> None:
    mw = AgentSpeakingCaptureMiddleware()
    ctx = _make_ctx(is_streaming=False, result=None)

    asyncio.run(mw.process(ctx, _noop_next))

    assert mw.captured_responses == []
