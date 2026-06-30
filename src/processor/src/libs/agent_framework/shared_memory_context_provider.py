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

from agent_framework import AgentSession, ContextProvider, Message, SessionContext, SupportsAgentRun

if TYPE_CHECKING:
    from libs.agent_framework.qdrant_memory_store import QdrantMemoryStore

logger = logging.getLogger(__name__)

# Maximum characters of memory context to inject (prevents context bloat)
MAX_MEMORY_CONTEXT_CHARS = 15_000

# Minimum content length to store (skip trivial messages)
MIN_CONTENT_LENGTH_TO_STORE = 50


# Step order for determining cross-step queries
_STEP_ORDER = ["analysis", "design", "convert", "documentation"]


class SharedMemoryContextProvider(ContextProvider):
    """ContextProvider that reads/writes shared memory via Qdrant.

    Attached to each agent individually, but all agents share the same
    QdrantMemoryStore instance, enabling cross-agent knowledge sharing.

    Optimized for cross-step memory sharing:
    - invoking(): only searches memories from PREVIOUS steps (within-step context
      is already available via GroupChat conversation broadcast)
    - invoked(): only stores the LAST response per agent per step (avoids
      redundant embedding calls for intermediate turns)
    """

    DEFAULT_CONTEXT_PROMPT = (
        "The following are relevant memories from previous migration steps. "
        "Use them as additional context when formulating your response:"
    )

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
        super().__init__(source_id=f"shared_memory_{agent_name}_{step}")
        self._memory_store = memory_store
        self._agent_name = agent_name
        self._step = step
        self._top_k = top_k
        self._score_threshold = score_threshold
        self._turn_counter = 0
        self._last_content: str | None = (
            None  # Track last response for deferred storage
        )

        # Determine which prior steps to search (skip current step)
        step_lower = step.lower()
        step_idx = None
        for i, s in enumerate(_STEP_ORDER):
            if s == step_lower:
                step_idx = i
                break
        self._prior_steps = _STEP_ORDER[:step_idx] if step_idx else []

    async def before_run(
        self,
        *,
        agent: SupportsAgentRun,
        session: AgentSession,
        context: SessionContext,
        state: dict,
    ) -> None:
        """Called before the agent's LLM call. Injects relevant shared memories.

        Only searches memories from PREVIOUS steps. Within the current step,
        agents already see all messages via GroupChat broadcast.
        """
        # Skip if this is the first step (no prior memories exist)
        if not self._prior_steps:
            return

        # Extract query from the most recent messages
        query = self._extract_query(context.input_messages)
        if not query:
            return

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
            return

        if not memories:
            return

        # Format memories into context instructions
        formatted = self._format_memories(memories)
        if not formatted:
            return

        instructions = f"{self.DEFAULT_CONTEXT_PROMPT}\n\n{formatted}"

        logger.info(
            "[MEMORY] Injecting %d memories for %s (step=%s, %d chars)",
            len(memories),
            self._agent_name,
            self._step,
            len(instructions),
        )

        if context.instructions is None:
            context.instructions = []
        context.instructions.append(instructions)

    async def after_run(
        self,
        *,
        agent: SupportsAgentRun,
        session: AgentSession,
        context: SessionContext,
        state: dict,
    ) -> None:
        """Called after the agent's LLM response. Buffers the response for storage.

        Instead of storing every turn (expensive), we buffer the latest response
        and only store it when the next invocation happens or the step ends.
        This means only the agent's last response per step gets stored,
        which is the most complete and useful summary.
        """
        # Extract text from response messages
        response = context.response
        if response is None:
            logger.debug(
                "[MEMORY] after_run() skipped for %s — no response",
                self._agent_name,
            )
            return

        response_messages = getattr(response, "messages", None)
        if not response_messages:
            logger.debug(
                "[MEMORY] after_run() skipped for %s — no response_messages",
                self._agent_name,
            )
            return

        # Extract text from response
        content = self._extract_text(response_messages)
        if not content or len(content) < MIN_CONTENT_LENGTH_TO_STORE:
            logger.debug(
                "[MEMORY] after_run() skipped for %s — content too short (%d chars)",
                self._agent_name,
                len(content) if content else 0,
            )
            return

        logger.info(
            "[MEMORY] after_run() buffering for %s (step=%s, %d chars)",
            self._agent_name,
            self._step,
            len(content),
        )

        # Store previous buffered content before replacing
        if self._last_content is not None:
            await self._flush_memory()

        self._last_content = content
        self._turn_counter += 1

    async def flush(self) -> None:
        """Flush any buffered memory to the store.

        Called at step completion to ensure the last agent response is stored.
        """
        if self._last_content is not None:
            logger.info(
                "[MEMORY] flush() called for %s (step=%s, buffered=%d chars)",
                self._agent_name,
                self._step,
                len(self._last_content),
            )
            await self._flush_memory()
        else:
            logger.debug(
                "[MEMORY] flush() called for %s (step=%s) — nothing buffered",
                self._agent_name,
                self._step,
            )

    async def _flush_memory(self) -> None:
        """Store the buffered content into the memory store."""
        content = self._last_content
        self._last_content = None
        if not content:
            return

        # Guard: skip if memory store is no longer available
        if not getattr(self._memory_store, "_initialized", False):
            logger.warning(
                "[MEMORY] _flush_memory skipped for %s — memory store not initialized (initialized=%s)",
                self._agent_name,
                getattr(self._memory_store, "_initialized", "missing"),
            )
            return

        try:
            await self._memory_store.add(
                content=content,
                agent_name=self._agent_name,
                step=self._step,
                turn=self._turn_counter,
            )
            logger.info(
                "[MEMORY] Stored memory from %s (step=%s, turn=%d, %d chars)",
                self._agent_name,
                self._step,
                self._turn_counter,
                len(content),
            )
        except Exception as e:
            logger.warning(
                "[MEMORY] Failed to store memory for %s: %s",
                self._agent_name,
                e,
            )

    def _extract_query(
        self, messages: Message | MutableSequence[Message]
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
    def _get_text(message: Message) -> str:
        """Extract text content from a Message."""
        if hasattr(message, "text") and message.text:
            return message.text
        if hasattr(message, "content"):
            return str(message.content) if message.content else ""
        return str(message) if message else ""

    @staticmethod
    def _extract_text(
        messages: Message | Sequence[Message],
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
