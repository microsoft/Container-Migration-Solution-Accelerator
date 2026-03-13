# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""ContextProvider that injects shared Qdrant-backed memories into agent context.

This provider is attached to each agent in a GroupChat. Before each LLM call,
it queries the shared QdrantMemoryStore for relevant memories and injects them
as additional context. After each LLM response, it stores the agent's response
back into the shared memory for other agents to discover.

This enables agents to share knowledge without carrying the full conversation
history in their context window.
"""

from __future__ import annotations

import logging
from collections.abc import MutableSequence, Sequence
from typing import TYPE_CHECKING

from agent_framework import ChatMessage, Context, ContextProvider

if TYPE_CHECKING:
    from libs.agent_framework.qdrant_memory_store import QdrantMemoryStore

logger = logging.getLogger(__name__)

# Maximum characters of memory context to inject (prevents context bloat)
MAX_MEMORY_CONTEXT_CHARS = 15_000

# Minimum content length to store (skip trivial messages)
MIN_CONTENT_LENGTH_TO_STORE = 50


class SharedMemoryContextProvider(ContextProvider):
    """ContextProvider that reads/writes shared memory via Qdrant.

    Attached to each agent individually, but all agents share the same
    QdrantMemoryStore instance, enabling cross-agent knowledge sharing.

    Lifecycle per agent turn:
        1. invoking() — query memory for relevant context → inject as instructions
        2. [LLM call happens]
        3. invoked() — store the agent's response into shared memory
    """

    def __init__(
        self,
        memory_store: QdrantMemoryStore,
        agent_name: str,
        step: str,
        top_k: int = 10,
        score_threshold: float = 0.3,
    ):
        """Initialize the shared memory context provider.

        Args:
            memory_store: Shared QdrantMemoryStore instance (same across all agents).
            agent_name: Name of the agent this provider is attached to.
            step: Current migration step (analysis, design, convert, documentation).
            top_k: Number of relevant memories to retrieve per turn.
            score_threshold: Minimum similarity score for memory retrieval.
        """
        self._memory_store = memory_store
        self._agent_name = agent_name
        self._step = step
        self._top_k = top_k
        self._score_threshold = score_threshold
        self._turn_counter = 0

    async def invoking(
        self,
        messages: ChatMessage | MutableSequence[ChatMessage],
        **kwargs,
    ) -> Context:
        """Called before the agent's LLM call. Injects relevant shared memories.

        Extracts the latest message as a search query, retrieves semantically
        similar memories from the shared store, and returns them as additional
        context instructions.
        """
        # Extract query from the most recent messages
        query = self._extract_query(messages)
        if not query:
            return Context()

        try:
            memories = await self._memory_store.search(
                query=query,
                top_k=self._top_k,
                score_threshold=self._score_threshold,
            )
        except Exception as e:
            logger.warning(
                "[MEMORY] Failed to search memories for %s: %s",
                self._agent_name,
                e,
            )
            return Context()

        if not memories:
            return Context()

        # Format memories into context instructions
        formatted = self._format_memories(memories)
        if not formatted:
            return Context()

        instructions = (
            f"{self.DEFAULT_CONTEXT_PROMPT}\n\n{formatted}"
        )

        logger.debug(
            "[MEMORY] Injecting %d memories for %s (%d chars)",
            len(memories),
            self._agent_name,
            len(instructions),
        )

        return Context(instructions=instructions)

    async def invoked(
        self,
        request_messages: ChatMessage | Sequence[ChatMessage],
        response_messages: ChatMessage | Sequence[ChatMessage] | None = None,
        invoke_exception: Exception | None = None,
        **kwargs,
    ) -> None:
        """Called after the agent's LLM response. Stores the response in shared memory.

        Only stores substantive responses (above minimum length threshold).
        Skips storage on errors.
        """
        if invoke_exception is not None:
            return

        if response_messages is None:
            return

        # Extract text from response
        content = self._extract_text(response_messages)
        if not content or len(content) < MIN_CONTENT_LENGTH_TO_STORE:
            return

        self._turn_counter += 1

        try:
            await self._memory_store.add(
                content=content,
                agent_name=self._agent_name,
                step=self._step,
                turn=self._turn_counter,
            )
        except Exception as e:
            logger.warning(
                "[MEMORY] Failed to store memory for %s: %s",
                self._agent_name,
                e,
            )

    def _extract_query(
        self, messages: ChatMessage | MutableSequence[ChatMessage]
    ) -> str:
        """Extract a search query from the input messages.

        Uses the last non-system message as the query, truncated for embedding.
        """
        # Single message (not a list/sequence)
        if not isinstance(messages, (list, MutableSequence)):
            return self._get_text(messages)[:2000]

        if not messages:
            return ""

        # Search from the end for the most recent substantive message
        for msg in reversed(messages):
            text = self._get_text(msg)
            if text and len(text) > 20:
                return text[:2000]

        return ""

    def _format_memories(self, memories: list) -> str:
        """Format retrieved memories into a readable context block."""
        if not memories:
            return ""

        lines = []
        total_chars = 0

        for mem in memories:
            # Truncate individual memories to prevent a single one from dominating
            content = mem.content[:3000] if len(mem.content) > 3000 else mem.content
            entry = f"- [{mem.agent_name} / {mem.step}] {content}"

            if total_chars + len(entry) > MAX_MEMORY_CONTEXT_CHARS:
                break

            lines.append(entry)
            total_chars += len(entry)

        return "\n".join(lines)

    @staticmethod
    def _get_text(message: ChatMessage) -> str:
        """Extract text content from a ChatMessage."""
        if hasattr(message, "text") and message.text:
            return message.text
        if hasattr(message, "content"):
            return str(message.content) if message.content else ""
        return str(message) if message else ""

    @staticmethod
    def _extract_text(
        messages: ChatMessage | Sequence[ChatMessage],
    ) -> str:
        """Extract text content from response message(s)."""
        if not isinstance(messages, (list, Sequence)) or isinstance(messages, str):
            return SharedMemoryContextProvider._get_text(messages)

        parts = []
        for msg in messages:
            text = SharedMemoryContextProvider._get_text(msg)
            if text:
                parts.append(text)
        return "\n".join(parts)
