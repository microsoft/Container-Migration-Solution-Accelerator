# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from agent_framework import WorkflowCheckpoint, CheckpointStorage
from sas.cosmosdb.sql import RootEntityBase, RepositoryBase
from typing import Any


class CosmosWorkflowCheckpoint(RootEntityBase[WorkflowCheckpoint, str]):
    """Cosmos DB wrapper for WorkflowCheckpoint with partition key support."""

    checkpoint_id: str
    workflow_id: str = ""
    timestamp: str = ""

    # Core workflow state
    messages: dict[str, list[dict[str, Any]]] = {}
    shared_state: dict[str, Any] = {}
    pending_request_info_events: dict[str, dict[str, Any]] = {}

    # Runtime state
    iteration_count: int = 0

    # Metadata
    metadata: dict[str, Any] = {}
    version: str = "1.0"

    def __init__(self, **data):
        # Add id field from checkpoint_id before passing to parent
        if "id" not in data and "checkpoint_id" in data:
            data["id"] = data["checkpoint_id"]
        super().__init__(**data)


class CosmosWorkflowCheckpointRepository(RepositoryBase[CosmosWorkflowCheckpoint, str]):
    def __init__(self, account_url: str, database_name: str, container_name: str):
        super().__init__(
            account_url=account_url,
            database_name=database_name,
            container_name=container_name,
        )

    async def save_checkpoint(self, checkpoint: CosmosWorkflowCheckpoint):
        await self.add_async(checkpoint)

    async def load_checkpoint(self, checkpoint_id: str) -> CosmosWorkflowCheckpoint:
        cosmos_checkpoint = await self.get_async(checkpoint_id)
        return cosmos_checkpoint

    async def list_checkpoint_ids(self, workflow_id: str | None = None) -> list[str]:
        if workflow_id is None:
            query = await self.all_async()
        else:
            query = await self.find_one_async({"workflow_id": workflow_id})
            # f"SELECT c.id FROM c WHERE c.entity.workflow_id = '{workflow_id}'"

        return [checkpoint_id["id"] for checkpoint_id in query]

    async def list_checkpoints(
        self, workflow_id: str | None = None
    ) -> list[WorkflowCheckpoint]:
        if workflow_id is None:
            query = await self.all_async()
        else:
            query = await self.find_one_async({"workflow_id": workflow_id})

        return [checkpoint for checkpoint in query]

    async def delete_checkpoint(self, checkpoint_id: str):
        await self.delete_async(key=checkpoint_id)


class CosmosCheckpointStorage(CheckpointStorage):
    def __init__(self, repository: CosmosWorkflowCheckpointRepository):
        self.repository = repository

    async def save_checkpoint(self, checkpoint: WorkflowCheckpoint):
        # Convert WorkflowCheckpoint to CosmosWorkflowCheckpoint
        cosmos_checkpoint = CosmosWorkflowCheckpoint(**checkpoint.to_dict())
        await self.repository.save_checkpoint(cosmos_checkpoint)

    async def load_checkpoint(self, checkpoint_id: str) -> WorkflowCheckpoint:
        cosmos_checkpoint = await self.repository.load_checkpoint(checkpoint_id)
        # CosmosWorkflowCheckpoint is already a WorkflowCheckpoint, just return it
        return cosmos_checkpoint

    async def list_checkpoint_ids(self, workflow_id: str | None = None) -> list[str]:
        return await self.repository.list_checkpoint_ids(workflow_id)

    async def list_checkpoints(
        self, workflow_id: str | None = None
    ) -> list[WorkflowCheckpoint]:
        return await self.repository.list_checkpoints(workflow_id)

    async def delete_checkpoint(self, checkpoint_id: str):
        await self.repository.delete_checkpoint(checkpoint_id)
