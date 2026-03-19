# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Qdrant-backed shared memory store for multi-agent context sharing.

This module provides a vector memory store using Qdrant (in-process embedded mode)
that enables agents to share relevant context without carrying full conversation
history. Each migration process gets its own isolated collection.

Usage:
    store = QdrantMemoryStore(process_id="abc-123")
    await store.initialize(embedding_client)

    # Store a memory
    await store.add("AKS supports node auto-provisioning via Karpenter",
                     agent_name="AKS Expert", step="analysis", turn=3)

    # Retrieve relevant memories
    memories = await store.search("How should we handle node scaling?", top_k=5)

    # Cleanup when process completes
    await store.close()
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass

from openai import AsyncAzureOpenAI
from qdrant_client import AsyncQdrantClient, models

logger = logging.getLogger(__name__)

# Qdrant collection settings
EMBEDDING_DIM = 3072  # text-embedding-3-large dimension
DISTANCE_METRIC = models.Distance.COSINE


@dataclass
class MemoryEntry:
    """A single memory retrieved from the store."""

    content: str
    agent_name: str
    step: str
    turn: int
    score: float
    memory_id: str


class QdrantMemoryStore:
    """Qdrant-backed vector memory store for sharing context across agents.

    Uses Qdrant embedded (in-process) mode — no external server needed.
    Each migration process gets its own collection for isolation.
    """

    def __init__(self, process_id: str):
        self.process_id = process_id
        self.collection_name = f"migration_{process_id.replace('-', '_')}"
        self._client: AsyncQdrantClient | None = None
        self._embedding_client: AsyncAzureOpenAI | None = None
        self._embedding_deployment: str | None = None
        self._initialized = False
        self._turn_counter = 0

    async def initialize(
        self,
        embedding_client: AsyncAzureOpenAI,
        embedding_deployment: str,
    ) -> None:
        """Initialize the Qdrant client and create the collection.

        Args:
            embedding_client: Azure OpenAI async client for generating embeddings.
            embedding_deployment: Deployment name for the embedding model.
        """
        if self._initialized:
            return

        self._embedding_client = embedding_client
        self._embedding_deployment = embedding_deployment

        # In-memory Qdrant — no server, no persistence, auto-cleanup
        self._client = AsyncQdrantClient(":memory:")

        await self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=EMBEDDING_DIM,
                distance=DISTANCE_METRIC,
            ),
        )

        self._initialized = True
        logger.info(
            "[MEMORY] QdrantMemoryStore initialized for process %s (collection: %s)",
            self.process_id,
            self.collection_name,
        )

    async def add(
        self,
        content: str,
        *,
        agent_name: str,
        step: str,
        turn: int | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Store a memory entry with its embedding.

        Args:
            content: The text content to store.
            agent_name: Name of the agent that produced this content.
            step: Migration step (analysis, design, convert, documentation).
            turn: Conversation turn number (auto-incremented if None).
            metadata: Optional additional metadata.

        Returns:
            The unique ID of the stored memory.
        """
        if not self._initialized:
            raise RuntimeError(
                "QdrantMemoryStore not initialized. Call initialize() first."
            )

        if not content or not content.strip():
            return ""

        if turn is None:
            self._turn_counter += 1
            turn = self._turn_counter

        # Generate embedding
        embedding = await self._embed(content)
        if embedding is None:
            logger.warning("[MEMORY] Failed to generate embedding, skipping store")
            return ""

        memory_id = str(uuid.uuid4())
        payload = {
            "content": content,
            "agent_name": agent_name,
            "step": step,
            "turn": turn,
            "process_id": self.process_id,
            "timestamp": time.time(),
        }
        if metadata:
            payload["metadata"] = metadata

        await self._client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=memory_id,
                    vector=embedding,
                    payload=payload,
                )
            ],
        )

        logger.debug(
            "[MEMORY] Stored memory from %s (step=%s, turn=%d, %d chars)",
            agent_name,
            step,
            turn,
            len(content),
        )
        return memory_id

    async def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        step_filter: str | None = None,
        agent_filter: str | None = None,
        score_threshold: float = 0.3,
    ) -> list[MemoryEntry]:
        """Search for relevant memories using semantic similarity.

        Args:
            query: The search query text.
            top_k: Maximum number of results to return.
            step_filter: Optional filter by migration step.
            agent_filter: Optional filter by agent name.
            score_threshold: Minimum similarity score (0-1).

        Returns:
            List of MemoryEntry objects sorted by relevance.
        """
        if not self._initialized:
            return []

        embedding = await self._embed(query)
        if embedding is None:
            return []

        # Build optional filters
        conditions = []
        if step_filter:
            conditions.append(
                models.FieldCondition(
                    key="step",
                    match=models.MatchValue(value=step_filter),
                )
            )
        if agent_filter:
            conditions.append(
                models.FieldCondition(
                    key="agent_name",
                    match=models.MatchValue(value=agent_filter),
                )
            )

        query_filter = models.Filter(must=conditions) if conditions else None

        results = await self._client.query_points(
            collection_name=self.collection_name,
            query=embedding,
            query_filter=query_filter,
            limit=top_k,
            score_threshold=score_threshold,
        )

        memories = []
        for point in results.points:
            payload = point.payload or {}
            memories.append(
                MemoryEntry(
                    content=payload.get("content", ""),
                    agent_name=payload.get("agent_name", ""),
                    step=payload.get("step", ""),
                    turn=payload.get("turn", 0),
                    score=point.score,
                    memory_id=str(point.id),
                )
            )

        logger.debug(
            "[MEMORY] Search returned %d results (query: %.80s...)",
            len(memories),
            query,
        )
        return memories

    async def get_count(self) -> int:
        """Return the number of memories stored."""
        if not self._initialized:
            return 0
        info = await self._client.get_collection(self.collection_name)
        return info.points_count

    async def close(self) -> None:
        """Close the Qdrant client and release resources."""
        if self._client:
            try:
                await self._client.delete_collection(self.collection_name)
            except Exception:
                pass
            await self._client.close()
            self._client = None
        self._initialized = False
        logger.info("[MEMORY] QdrantMemoryStore closed for process %s", self.process_id)

    # Embedding retry config (lighter than chat — embeddings are fast and cheap)
    _EMBED_MAX_RETRIES = 3
    _EMBED_BASE_DELAY = 2.0
    _EMBED_MAX_DELAY = 30.0

    async def _embed(self, text: str) -> list[float] | None:
        """Generate an embedding vector for the given text with retry."""
        if not self._embedding_client or not self._embedding_deployment:
            logger.warning(
                "[MEMORY] _embed skipped — client=%s, deployment=%s",
                "set" if self._embedding_client else "None",
                self._embedding_deployment or "None",
            )
            return None

        last_error: Exception | None = None
        for attempt in range(self._EMBED_MAX_RETRIES + 1):
            try:
                response = await self._embedding_client.embeddings.create(
                    input=text,
                    model=self._embedding_deployment,
                )
                return response.data[0].embedding
            except Exception as e:
                last_error = e
                msg = str(e).lower()
                is_retryable = any(
                    s in msg
                    for s in ["429", "too many requests", "rate limit", "throttle",
                              "timeout", "connection", "server error", "502", "503", "504"]
                ) or (not msg)  # empty error message = transient

                if not is_retryable or attempt >= self._EMBED_MAX_RETRIES:
                    logger.warning(
                        "[MEMORY] Embedding call failed (attempt %d/%d, not retrying): %s",
                        attempt + 1,
                        self._EMBED_MAX_RETRIES + 1,
                        e,
                    )
                    return None

                delay = min(
                    self._EMBED_BASE_DELAY * (2 ** attempt),
                    self._EMBED_MAX_DELAY,
                )
                logger.warning(
                    "[MEMORY] Embedding call failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1,
                    self._EMBED_MAX_RETRIES + 1,
                    delay,
                    e,
                )
                await asyncio.sleep(delay)

        logger.warning("[MEMORY] Embedding exhausted all retries: %s", last_error)
        return None
