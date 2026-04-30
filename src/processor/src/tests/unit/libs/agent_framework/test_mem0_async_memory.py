# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for Mem0AsyncMemoryManager."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from libs.agent_framework.mem0_async_memory import Mem0AsyncMemoryManager


def test_init_starts_with_no_instance() -> None:
    mgr = Mem0AsyncMemoryManager()
    assert mgr._memory_instance is None


def test_get_memory_creates_instance_with_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "my-chat")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "my-embed")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2025-01-01")

    sentinel = object()

    async def _run() -> None:
        with patch(
            "libs.agent_framework.mem0_async_memory.AsyncMemory.from_config",
            new=AsyncMock(return_value=sentinel),
        ) as mock_from_config:
            mgr = Mem0AsyncMemoryManager()
            instance = await mgr.get_memory()

            assert instance is sentinel
            assert mgr._memory_instance is sentinel

            mock_from_config.assert_awaited_once()
            cfg = mock_from_config.await_args.args[0]
            assert cfg["llm"]["config"]["model"] == "my-chat"
            assert (
                cfg["llm"]["config"]["azure_kwargs"]["azure_endpoint"]
                == "https://example.openai.azure.com/"
            )
            assert (
                cfg["embedder"]["config"]["azure_kwargs"]["api_version"]
                == "2025-01-01"
            )
            assert cfg["embedder"]["config"]["model"] == "my-embed"
            assert cfg["vector_store"]["provider"] == "redis"
            assert cfg["version"] == "v1.1"

            # Second call returns cached instance without calling from_config again
            again = await mgr.get_memory()
            assert again is sentinel
            mock_from_config.assert_awaited_once()

    asyncio.run(_run())


def test_get_memory_uses_defaults_when_env_missing(monkeypatch) -> None:
    for var in (
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME",
        "AZURE_OPENAI_API_VERSION",
    ):
        monkeypatch.delenv(var, raising=False)

    async def _run() -> None:
        with patch(
            "libs.agent_framework.mem0_async_memory.AsyncMemory.from_config",
            new=AsyncMock(return_value="ok"),
        ) as mock_from_config:
            mgr = Mem0AsyncMemoryManager()
            await mgr.get_memory()
            cfg = mock_from_config.await_args.args[0]
            assert cfg["llm"]["config"]["model"] == "gpt-5.1"
            assert (
                cfg["embedder"]["config"]["model"] == "text-embedding-3-large"
            )
            assert (
                cfg["llm"]["config"]["azure_kwargs"]["api_version"]
                == "2024-12-01-preview"
            )

    asyncio.run(_run())
