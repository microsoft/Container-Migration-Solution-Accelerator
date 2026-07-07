# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for SharedMemoryContextProvider."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from libs.agent_framework.qdrant_memory_store import MemoryEntry
from libs.agent_framework.shared_memory_context_provider import (
    MAX_MEMORY_CONTEXT_CHARS,
    MIN_CONTENT_LENGTH_TO_STORE,
    SharedMemoryContextProvider,
)


def _make_chat_message(text: str, role: str = "assistant") -> MagicMock:
    msg = MagicMock()
    msg.text = text
    msg.content = text
    msg.role = role
    return msg


def _make_memory_entry(
    content: str,
    agent_name: str = "Agent",
    step: str = "analysis",
    turn: int = 1,
    score: float = 0.9,
) -> MemoryEntry:
    return MemoryEntry(
        content=content,
        agent_name=agent_name,
        step=step,
        turn=turn,
        score=score,
        memory_id="test-id",
    )


def _make_mock_store():
    store = AsyncMock()
    store.search = AsyncMock(return_value=[])
    store.add = AsyncMock(return_value="test-id")
    return store


def _make_provider(store=None):
    if store is None:
        store = _make_mock_store()
    return SharedMemoryContextProvider(
        memory_store=store,
        agent_name="AKS Expert",
        step="design",
        top_k=5,
        score_threshold=0.3,
    ), store


def _make_session_context(input_messages=None, response=None):
    """Create a fake SessionContext for testing."""
    ctx = SimpleNamespace(
        input_messages=input_messages or [],
        instructions=None,
        response=response,
    )
    return ctx


# ---------------------------------------------------------------------------
# before_run() - Pre-LLM memory injection
# ---------------------------------------------------------------------------


def test_invoking_injects_memories():
    async def _run():
        provider, store = _make_provider()
        store.search.return_value = [
            _make_memory_entry("GKE Filestore CSI", agent_name="GKE Expert"),
            _make_memory_entry("Azure Files for AKS", agent_name="AKS Expert"),
        ]
        messages = [_make_chat_message("How should we handle storage configuration?")]
        ctx = _make_session_context(input_messages=messages)

        await provider.before_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})

        assert ctx.instructions is not None
        assert "GKE Filestore CSI" in ctx.instructions[0]
        assert "Azure Files for AKS" in ctx.instructions[0]
        store.search.assert_called_once()

    asyncio.run(_run())


def test_invoking_empty_messages_returns_empty():
    async def _run():
        provider, _ = _make_provider()
        ctx = _make_session_context(input_messages=[])

        await provider.before_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})
        assert ctx.instructions is None

    asyncio.run(_run())


def test_invoking_no_memories_returns_empty():
    async def _run():
        provider, store = _make_provider()
        store.search.return_value = []
        messages = [_make_chat_message("What is the overall migration plan for AKS?")]
        ctx = _make_session_context(input_messages=messages)

        await provider.before_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})
        assert ctx.instructions is None

    asyncio.run(_run())


def test_invoking_search_failure_graceful():
    async def _run():
        provider, store = _make_provider()
        store.search.side_effect = Exception("search failed")
        messages = [_make_chat_message("What is the networking plan for AKS?")]
        ctx = _make_session_context(input_messages=messages)

        await provider.before_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})
        assert ctx.instructions is None

    asyncio.run(_run())


def test_invoking_truncates_long_query():
    async def _run():
        provider, store = _make_provider()
        long_text = "x" * 5000
        messages = [_make_chat_message(long_text)]
        ctx = _make_session_context(input_messages=messages)

        await provider.before_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})

        query = store.search.call_args.kwargs["query"]
        assert len(query) <= 2000

    asyncio.run(_run())


def test_invoking_uses_last_message_as_query():
    async def _run():
        provider, store = _make_provider()
        messages = [
            _make_chat_message("First"),
            _make_chat_message("Second"),
            _make_chat_message("Latest question about storage"),
        ]
        ctx = _make_session_context(input_messages=messages)

        await provider.before_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})

        query = store.search.call_args.kwargs["query"]
        assert "Latest question about storage" in query

    asyncio.run(_run())


def test_invoking_respects_max_context_chars():
    async def _run():
        provider, store = _make_provider()
        large_memories = [
            _make_memory_entry("x" * 4000, agent_name=f"Agent{i}") for i in range(10)
        ]
        store.search.return_value = large_memories
        messages = [_make_chat_message("What storage configuration should we use for persistent volumes?")]
        ctx = _make_session_context(input_messages=messages)

        await provider.before_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})

        assert ctx.instructions is not None
        assert len(ctx.instructions[0]) <= MAX_MEMORY_CONTEXT_CHARS + 200

    asyncio.run(_run())


def test_invoking_formats_with_agent_and_step():
    async def _run():
        provider, store = _make_provider()
        store.search.return_value = [
            _make_memory_entry("Use Premium SSD", agent_name="Chief Architect", step="design"),
        ]
        messages = [_make_chat_message("What storage class should we choose for the cluster?")]
        ctx = _make_session_context(input_messages=messages)

        await provider.before_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})

        assert "Chief Architect" in ctx.instructions[0]
        assert "design" in ctx.instructions[0]

    asyncio.run(_run())


def test_invoking_with_single_message():
    async def _run():
        provider, store = _make_provider()
        store.search.return_value = [_make_memory_entry("some memory")]
        single = _make_chat_message("What about networking configuration for AKS?")
        ctx = _make_session_context(input_messages=[single])

        await provider.before_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})

        assert ctx.instructions is not None
        store.search.assert_called_once()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# after_run() - Post-LLM memory storage
# ---------------------------------------------------------------------------


def _make_response_with_messages(messages):
    """Create a mock response object with messages attribute."""
    resp = SimpleNamespace(messages=messages)
    return resp


def test_invoked_stores_response():
    async def _run():
        provider, store = _make_provider()
        response_msgs = [_make_chat_message("We should use Azure CNI for networking configuration in the AKS cluster")]
        response = _make_response_with_messages(response_msgs)
        ctx = _make_session_context(response=response)

        await provider.after_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})
        await provider.flush()

        store.add.assert_called_once()
        kwargs = store.add.call_args
        assert kwargs.kwargs["agent_name"] == "AKS Expert"
        assert kwargs.kwargs["step"] == "design"

    asyncio.run(_run())


def test_invoked_skips_on_exception():
    async def _run():
        provider, store = _make_provider()
        # No response (simulating an exception scenario)
        ctx = _make_session_context(response=None)

        await provider.after_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})
        store.add.assert_not_called()

    asyncio.run(_run())


def test_invoked_skips_none_response():
    async def _run():
        provider, store = _make_provider()
        ctx = _make_session_context(response=None)

        await provider.after_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})
        store.add.assert_not_called()

    asyncio.run(_run())


def test_invoked_skips_short_response():
    async def _run():
        provider, store = _make_provider()
        short_msgs = [_make_chat_message("x" * (MIN_CONTENT_LENGTH_TO_STORE - 1))]
        response = _make_response_with_messages(short_msgs)
        ctx = _make_session_context(response=response)

        await provider.after_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})
        store.add.assert_not_called()

    asyncio.run(_run())


def test_invoked_stores_long_response():
    async def _run():
        provider, store = _make_provider()
        long_msgs = [_make_chat_message("x" * (MIN_CONTENT_LENGTH_TO_STORE + 1))]
        response = _make_response_with_messages(long_msgs)
        ctx = _make_session_context(response=response)

        await provider.after_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})
        await provider.flush()
        store.add.assert_called_once()

    asyncio.run(_run())


def test_invoked_increments_turn_counter():
    async def _run():
        provider, store = _make_provider()
        response_msgs = [_make_chat_message("A" * 100)]
        response = _make_response_with_messages(response_msgs)
        ctx = _make_session_context(response=response)

        await provider.after_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})
        await provider.after_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})
        assert provider._turn_counter == 2

    asyncio.run(_run())


def test_invoked_store_failure_does_not_raise():
    async def _run():
        provider, store = _make_provider()
        store.add.side_effect = Exception("store failed")
        response_msgs = [_make_chat_message("A" * 100)]
        response = _make_response_with_messages(response_msgs)
        ctx = _make_session_context(response=response)

        await provider.after_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})
        await provider.flush()  # Should not raise

    asyncio.run(_run())


def test_invoked_with_single_message():
    async def _run():
        provider, store = _make_provider()
        response_msgs = [_make_chat_message("We should use Azure CNI Overlay for the networking configuration in AKS")]
        response = _make_response_with_messages(response_msgs)
        ctx = _make_session_context(response=response)

        await provider.after_run(agent=MagicMock(), session=MagicMock(), context=ctx, state={})
        await provider.flush()
        store.add.assert_called_once()

    asyncio.run(_run())
