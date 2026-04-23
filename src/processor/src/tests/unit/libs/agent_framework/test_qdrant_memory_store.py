# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for QdrantMemoryStore."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from libs.agent_framework.qdrant_memory_store import QdrantMemoryStore


def _make_embedding_client():
    """Create a mock Azure OpenAI embedding client."""
    client = AsyncMock()
    embedding_obj = MagicMock()
    embedding_obj.embedding = [0.1] * 3072
    response = MagicMock()
    response.data = [embedding_obj]
    client.embeddings.create = AsyncMock(return_value=response)
    return client


def _make_failing_embedding_client():
    """Create a mock embedding client that fails."""
    client = AsyncMock()
    client.embeddings.create = AsyncMock(side_effect=Exception("API error"))
    return client


# ---------------------------------------------------------------------------
# Initialization & Lifecycle
# ---------------------------------------------------------------------------


def test_initialize_creates_collection():
    async def _run():
        client = _make_embedding_client()
        store = QdrantMemoryStore(process_id="test-001")
        assert not store._initialized

        await store.initialize(
            embedding_client=client, embedding_deployment="text-embedding-3-large"
        )
        assert store._initialized
        assert store._client is not None
        assert await store.get_count() == 0

        await store.close()

    asyncio.run(_run())


def test_initialize_idempotent():
    async def _run():
        client = _make_embedding_client()
        store = QdrantMemoryStore(process_id="test-002")
        await store.initialize(embedding_client=client, embedding_deployment="emb")
        qdrant_before = store._client

        await store.initialize(embedding_client=client, embedding_deployment="emb")
        assert store._client is qdrant_before

        await store.close()

    asyncio.run(_run())


def test_close_releases_resources():
    async def _run():
        client = _make_embedding_client()
        store = QdrantMemoryStore(process_id="test-003")
        await store.initialize(embedding_client=client, embedding_deployment="emb")
        await store.close()

        assert store._client is None
        assert not store._initialized

    asyncio.run(_run())


def test_close_idempotent():
    async def _run():
        client = _make_embedding_client()
        store = QdrantMemoryStore(process_id="test-004")
        await store.initialize(embedding_client=client, embedding_deployment="emb")
        await store.close()
        await store.close()  # Should not raise

    asyncio.run(_run())


def test_collection_name_from_process_id():
    store = QdrantMemoryStore(process_id="abc-def-123")
    assert store.collection_name == "migration_abc_def_123"


# ---------------------------------------------------------------------------
# Add
# ---------------------------------------------------------------------------


def test_add_stores_memory():
    async def _run():
        client = _make_embedding_client()
        store = QdrantMemoryStore(process_id="add-001")
        await store.initialize(embedding_client=client, embedding_deployment="emb")

        memory_id = await store.add(
            "AKS supports Karpenter", agent_name="AKS Expert", step="analysis", turn=1
        )
        assert memory_id
        assert await store.get_count() == 1

        await store.close()

    asyncio.run(_run())


def test_add_multiple_memories():
    async def _run():
        client = _make_embedding_client()
        store = QdrantMemoryStore(process_id="add-002")
        await store.initialize(embedding_client=client, embedding_deployment="emb")

        await store.add("Mem 1", agent_name="A", step="analysis", turn=1)
        await store.add("Mem 2", agent_name="B", step="analysis", turn=2)
        await store.add("Mem 3", agent_name="C", step="design", turn=3)
        assert await store.get_count() == 3

        await store.close()

    asyncio.run(_run())


def test_add_empty_content_skipped():
    async def _run():
        client = _make_embedding_client()
        store = QdrantMemoryStore(process_id="add-003")
        await store.initialize(embedding_client=client, embedding_deployment="emb")

        result = await store.add("", agent_name="A", step="analysis")
        assert result == ""
        assert await store.get_count() == 0

        await store.close()

    asyncio.run(_run())


def test_add_whitespace_content_skipped():
    async def _run():
        client = _make_embedding_client()
        store = QdrantMemoryStore(process_id="add-004")
        await store.initialize(embedding_client=client, embedding_deployment="emb")

        result = await store.add("   ", agent_name="A", step="analysis")
        assert result == ""

        await store.close()

    asyncio.run(_run())


def test_add_auto_increments_turn():
    async def _run():
        client = _make_embedding_client()
        store = QdrantMemoryStore(process_id="add-005")
        await store.initialize(embedding_client=client, embedding_deployment="emb")

        await store.add("First", agent_name="A", step="analysis")
        await store.add("Second", agent_name="B", step="analysis")
        assert store._turn_counter == 2

        await store.close()

    asyncio.run(_run())


def test_add_without_initialization_raises():
    async def _run():
        store = QdrantMemoryStore(process_id="add-006")
        try:
            await store.add("test", agent_name="A", step="analysis")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "not initialized" in str(e)

    asyncio.run(_run())


def test_add_with_embedding_failure_returns_empty():
    async def _run():
        client = _make_failing_embedding_client()
        store = QdrantMemoryStore(process_id="add-007")
        await store.initialize(embedding_client=client, embedding_deployment="emb")

        result = await store.add("content", agent_name="A", step="analysis")
        assert result == ""

        await store.close()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def test_search_returns_results():
    async def _run():
        client = _make_embedding_client()
        store = QdrantMemoryStore(process_id="search-001")
        await store.initialize(embedding_client=client, embedding_deployment="emb")

        await store.add("GKE Filestore CSI", agent_name="GKE", step="analysis", turn=1)
        await store.add("AKS Azure Files", agent_name="AKS", step="analysis", turn=2)

        results = await store.search("storage drivers", top_k=5)
        assert len(results) == 2
        assert all(r.content for r in results)
        assert all(r.score > 0 for r in results)

        await store.close()

    asyncio.run(_run())


def test_search_empty_store():
    async def _run():
        client = _make_embedding_client()
        store = QdrantMemoryStore(process_id="search-002")
        await store.initialize(embedding_client=client, embedding_deployment="emb")

        results = await store.search("anything")
        assert results == []

        await store.close()

    asyncio.run(_run())


def test_search_respects_top_k():
    async def _run():
        client = _make_embedding_client()
        store = QdrantMemoryStore(process_id="search-003")
        await store.initialize(embedding_client=client, embedding_deployment="emb")

        for i in range(5):
            await store.add(f"Entry {i}", agent_name="A", step="analysis", turn=i)

        results = await store.search("entry", top_k=3)
        assert len(results) <= 3

        await store.close()

    asyncio.run(_run())


def test_search_uninitialized_returns_empty():
    async def _run():
        store = QdrantMemoryStore(process_id="search-004")
        results = await store.search("anything")
        assert results == []

    asyncio.run(_run())


def test_search_with_embedding_failure():
    async def _run():
        embedding_obj = MagicMock()
        embedding_obj.embedding = [0.1] * 3072
        ok_response = MagicMock()
        ok_response.data = [embedding_obj]

        client = AsyncMock()
        client.embeddings.create = AsyncMock(
            side_effect=[ok_response, Exception("API error")]
        )

        store = QdrantMemoryStore(process_id="search-005")
        await store.initialize(embedding_client=client, embedding_deployment="emb")
        await store.add("content", agent_name="A", step="analysis", turn=1)

        results = await store.search("query")
        assert results == []

        await store.close()

    asyncio.run(_run())


def test_search_result_fields():
    async def _run():
        client = _make_embedding_client()
        store = QdrantMemoryStore(process_id="search-006")
        await store.initialize(embedding_client=client, embedding_deployment="emb")

        await store.add(
            "Karpenter for scaling", agent_name="AKS Expert", step="design", turn=5
        )

        results = await store.search("scaling")
        assert len(results) == 1
        entry = results[0]
        assert entry.content == "Karpenter for scaling"
        assert entry.agent_name == "AKS Expert"
        assert entry.step == "design"
        assert entry.turn == 5
        assert entry.memory_id
        assert isinstance(entry.score, float)

        await store.close()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Workflow Lifecycle
# ---------------------------------------------------------------------------


def test_memories_persist_across_steps():
    """Analysis adds memories, design reads them — simulating workflow scope."""
    async def _run():
        client = _make_embedding_client()
        store = QdrantMemoryStore(process_id="lifecycle-001")
        await store.initialize(embedding_client=client, embedding_deployment="emb")

        # Analysis step
        await store.add("GKE 3 node pools", agent_name="GKE", step="analysis", turn=1)
        await store.add("GPU training nodes", agent_name="AKS", step="analysis", turn=2)

        # Design step reads analysis
        results = await store.search("node pools", top_k=5)
        assert len(results) == 2

        # Design adds its own
        await store.add("Use NC6s_v3 for GPU", agent_name="Arch", step="design", turn=3)
        assert await store.get_count() == 3

        # Convert step sees all
        results = await store.search("GPU", top_k=10)
        assert len(results) == 3

        await store.close()

    asyncio.run(_run())


def test_fresh_store_per_process():
    """Different process IDs get independent stores."""
    async def _run():
        client = _make_embedding_client()
        s1 = QdrantMemoryStore(process_id="proc-1")
        s2 = QdrantMemoryStore(process_id="proc-2")

        await s1.initialize(embedding_client=client, embedding_deployment="emb")
        await s2.initialize(embedding_client=client, embedding_deployment="emb")

        await s1.add("Only in proc 1", agent_name="A", step="analysis")
        assert await s1.get_count() == 1
        assert await s2.get_count() == 0

        await s1.close()
        await s2.close()

    asyncio.run(_run())


def test_close_disposes_all_memories():
    async def _run():
        client = _make_embedding_client()
        store = QdrantMemoryStore(process_id="dispose-001")
        await store.initialize(embedding_client=client, embedding_deployment="emb")
        await store.add("content", agent_name="A", step="analysis")
        assert await store.get_count() == 1

        await store.close()
        assert await store.get_count() == 0
        assert await store.search("anything") == []

    asyncio.run(_run())
