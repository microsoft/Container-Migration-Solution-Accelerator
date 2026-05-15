# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
from unittest.mock import AsyncMock, patch

from libs.agent_framework import mem0_async_memory as mam


class TestMem0AsyncMemoryManager:
    def test_lazy_initialization_caches_instance(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
        with patch.object(mam, "AsyncMemory") as mem:
            mem.from_config = AsyncMock(return_value="memory-instance")

            mgr = mam.Mem0AsyncMemoryManager()
            first = asyncio.run(mgr.get_memory())
            second = asyncio.run(mgr.get_memory())

            assert first == "memory-instance"
            assert first is second
            mem.from_config.assert_awaited_once()

    def test_uses_default_deployments_when_env_missing(self, monkeypatch):
        for k in [
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME",
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME",
            "AZURE_OPENAI_API_VERSION",
        ]:
            monkeypatch.delenv(k, raising=False)
        with patch.object(mam, "AsyncMemory") as mem:
            mem.from_config = AsyncMock(return_value="m")
            asyncio.run(mam.Mem0AsyncMemoryManager().get_memory())
            cfg = mem.from_config.await_args.args[0]
            assert cfg["llm"]["config"]["model"] == "gpt-5.1"
            assert cfg["embedder"]["config"]["model"] == "text-embedding-3-large"
            assert cfg["llm"]["config"]["azure_kwargs"]["api_version"] == "2024-12-01-preview"
