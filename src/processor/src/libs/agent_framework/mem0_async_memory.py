# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Lazy-initialized async wrapper around the Mem0 vector-store memory backend."""

import os

from mem0 import AsyncMemory


class Mem0AsyncMemoryManager:
    def __init__(self):
        self._memory_instance: AsyncMemory | None = None

    async def get_memory(self):
        """Get or create the AsyncMemory instance."""
        if self._memory_instance is None:
            self._memory_instance = await self._create_memory()
        return self._memory_instance

    async def _create_memory(self):
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        chat_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-5.1")
        embedding_deployment = os.getenv(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-large"
        )
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

        config = {
            "vector_store": {
                "provider": "redis",
                "config": {
                    "redis_url": "redis://localhost:6379",
                    "collection_name": "container_migration",
                    "embedding_model_dims": 3072,
                },
            },
            "llm": {
                "provider": "azure_openai",
                "config": {
                    "model": chat_deployment,
                    "temperature": 0.1,
                    "max_tokens": 4000,
                    "azure_kwargs": {
                        "azure_deployment": chat_deployment,
                        "api_version": api_version,
                        "azure_endpoint": endpoint,
                    },
                },
            },
            "embedder": {
                "provider": "azure_openai",
                "config": {
                    "model": embedding_deployment,
                    "azure_kwargs": {
                        "api_version": api_version,
                        "azure_deployment": embedding_deployment,
                        "azure_endpoint": endpoint,
                    },
                },
            },
            "version": "v1.1",
        }

        return await AsyncMemory.from_config(config)
