# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for SharedMemoryContextProvider."""

from __future__ import annotations

import asyncio
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
    msg.role = MagicMock()
    msg.role.value = role
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


# ---------------------------------------------------------------------------
# invoking() — Pre-LLM memory injection
# ---------------------------------------------------------------------------


def test_invoking_injects_memories():
    async def _run():
        provider, store = _make_provider()
        store.search.return_value = [
            _make_memory_entry("GKE Filestore CSI", agent_name="GKE Expert"),
            _make_memory_entry("Azure Files for AKS", agent_name="AKS Expert"),
        ]
        messages = [_make_chat_message("How should we handle storage configuration?")]

        context = await provider.invoking(messages)

        assert context.instructions is not None
        assert "GKE Filestore CSI" in context.instructions
        assert "Azure Files for AKS" in context.instructions
        store.search.assert_called_once()

    asyncio.run(_run())


def test_invoking_empty_messages_returns_empty():
    async def _run():
        provider, _ = _make_provider()
        context = await provider.invoking([])
        assert context.instructions is None
        assert context.messages == []

    asyncio.run(_run())


def test_invoking_no_memories_returns_empty():
    async def _run():
        provider, store = _make_provider()
        store.search.return_value = []
        messages = [_make_chat_message("What is the overall migration plan for AKS?")]

        context = await provider.invoking(messages)
        assert context.instructions is None

    asyncio.run(_run())


def test_invoking_search_failure_graceful():
    async def _run():
        provider, store = _make_provider()
        store.search.side_effect = Exception("search failed")
        messages = [_make_chat_message("What is the networking plan for AKS?")]

        context = await provider.invoking(messages)
        assert context.instructions is None

    asyncio.run(_run())


def test_invoking_truncates_long_query():
    async def _run():
        provider, store = _make_provider()
        long_text = "x" * 5000
        messages = [_make_chat_message(long_text)]

        await provider.invoking(messages)

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

        await provider.invoking(messages)

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

        context = await provider.invoking(messages)

        assert context.instructions is not None
        assert len(context.instructions) <= MAX_MEMORY_CONTEXT_CHARS + 200

    asyncio.run(_run())


def test_invoking_formats_with_agent_and_step():
    async def _run():
        provider, store = _make_provider()
        store.search.return_value = [
            _make_memory_entry("Use Premium SSD", agent_name="Chief Architect", step="design"),
        ]
        messages = [_make_chat_message("What storage class should we choose for the cluster?")]

        context = await provider.invoking(messages)

        assert "Chief Architect" in context.instructions
        assert "design" in context.instructions

    asyncio.run(_run())


def test_invoking_with_single_message():
    async def _run():
        provider, store = _make_provider()
        store.search.return_value = [_make_memory_entry("some memory")]
        single = _make_chat_message("What about networking configuration for AKS?")

        context = await provider.invoking(single)

        assert context.instructions is not None
        store.search.assert_called_once()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# invoked() — Post-LLM memory storage
# ---------------------------------------------------------------------------


def test_invoked_stores_response():
    async def _run():
        provider, store = _make_provider()
        request = [_make_chat_message("What is the networking plan for AKS?")]
        response = [_make_chat_message("We should use Azure CNI for networking configuration in the AKS cluster")]

        await provider.invoked(request, response)
        await provider.flush()

        store.add.assert_called_once()
        kwargs = store.add.call_args
        assert kwargs.kwargs["agent_name"] == "AKS Expert"
        assert kwargs.kwargs["step"] == "design"

    asyncio.run(_run())


def test_invoked_skips_on_exception():
    async def _run():
        provider, store = _make_provider()
        request = [_make_chat_message("Q")]
        response = [_make_chat_message("A" * 100)]

        await provider.invoked(request, response, invoke_exception=Exception("fail"))
        store.add.assert_not_called()

    asyncio.run(_run())


def test_invoked_skips_none_response():
    async def _run():
        provider, store = _make_provider()
        request = [_make_chat_message("Q")]

        await provider.invoked(request, None)
        store.add.assert_not_called()

    asyncio.run(_run())


def test_invoked_skips_short_response():
    async def _run():
        provider, store = _make_provider()
        request = [_make_chat_message("Q")]
        short = [_make_chat_message("x" * (MIN_CONTENT_LENGTH_TO_STORE - 1))]

        await provider.invoked(request, short)
        store.add.assert_not_called()

    asyncio.run(_run())


def test_invoked_stores_long_response():
    async def _run():
        provider, store = _make_provider()
        request = [_make_chat_message("Q")]
        long_resp = [_make_chat_message("x" * (MIN_CONTENT_LENGTH_TO_STORE + 1))]

        await provider.invoked(request, long_resp)
        await provider.flush()
        store.add.assert_called_once()

    asyncio.run(_run())


def test_invoked_increments_turn_counter():
    async def _run():
        provider, store = _make_provider()
        request = [_make_chat_message("Q")]
        response = [_make_chat_message("A" * 100)]

        await provider.invoked(request, response)
        await provider.invoked(request, response)
        assert provider._turn_counter == 2

    asyncio.run(_run())


def test_invoked_store_failure_does_not_raise():
    async def _run():
        provider, store = _make_provider()
        store.add.side_effect = Exception("store failed")
        request = [_make_chat_message("Q")]
        response = [_make_chat_message("A" * 100)]

        await provider.invoked(request, response)
        await provider.flush()  # Should not raise

    asyncio.run(_run())


def test_invoked_with_single_message():
    async def _run():
        provider, store = _make_provider()
        request = _make_chat_message("What is the question about networking?")
        response = _make_chat_message("We should use Azure CNI Overlay for the networking configuration in AKS")

        await provider.invoked(request, response)
        await provider.flush()
        store.add.assert_called_once()

    asyncio.run(_run())
