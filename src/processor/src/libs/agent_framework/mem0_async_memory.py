# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

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
                    "model": "gpt-5.1",
                    "temperature": 0.1,
                    "max_tokens": 100000,
                    "azure_kwargs": {
                        "azure_deployment": "gpt-5.1",
                        "api_version": "2024-12-01-preview",
                        "azure_endpoint": "https://aifappframework.cognitiveservices.azure.com/",
                    },
                },
            },
            "embedder": {
                "provider": "azure_openai",
                "config": {
                    "model": "text-embedding-3-large",
                    "azure_kwargs": {
                        "api_version": "2024-02-01",
                        "azure_deployment": "text-embedding-3-large",
                        "azure_endpoint": "https://aifappframework.openai.azure.com/",
                        "default_headers": {
                            "CustomHeader": "container migration",
                        },
                    },
                },
            },
            "version": "v1.1",
        }

        return await AsyncMemory.from_config(config)
