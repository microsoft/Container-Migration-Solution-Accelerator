# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from libs.agent_framework import cosmos_checkpoint_storage as ccs
from libs.agent_framework.cosmos_checkpoint_storage import (
    CosmosCheckpointStorage,
    CosmosWorkflowCheckpoint,
)


class TestCosmosWorkflowCheckpoint:
    def test_init_uses_checkpoint_id_as_id(self):
        cp = CosmosWorkflowCheckpoint(checkpoint_id="abc-123", workflow_id="wf-1")
        assert cp.checkpoint_id == "abc-123"
        assert cp.workflow_id == "wf-1"
        assert getattr(cp, "id", None) == "abc-123"

    def test_init_keeps_explicit_id(self):
        cp = CosmosWorkflowCheckpoint(checkpoint_id="x", id="custom-id")
        assert cp.id == "custom-id"

    def test_defaults_populated(self):
        cp = CosmosWorkflowCheckpoint(checkpoint_id="x")
        assert cp.iteration_count == 0
        assert cp.version == "1.0"
        assert cp.messages == {}


class TestCosmosCheckpointStorage:
    def _make(self):
        repo = MagicMock()
        repo.save_checkpoint = AsyncMock()
        repo.load_checkpoint = AsyncMock()
        repo.list_checkpoint_ids = AsyncMock()
        repo.list_checkpoints = AsyncMock()
        repo.delete_checkpoint = AsyncMock()
        return CosmosCheckpointStorage(repository=repo), repo

    def test_save_converts_workflow_to_cosmos(self):
        storage, repo = self._make()
        wf = MagicMock()
        wf.to_dict.return_value = {"checkpoint_id": "cp1", "workflow_id": "wf1"}
        asyncio.run(storage.save_checkpoint(wf))
        repo.save_checkpoint.assert_awaited_once()
        passed = repo.save_checkpoint.await_args.args[0]
        assert isinstance(passed, CosmosWorkflowCheckpoint)
        assert passed.checkpoint_id == "cp1"

    def test_load_delegates_to_repository(self):
        storage, repo = self._make()
        repo.load_checkpoint.return_value = "loaded"
        result = asyncio.run(storage.load_checkpoint("id-1"))
        assert result == "loaded"
        repo.load_checkpoint.assert_awaited_once_with("id-1")

    def test_list_ids_delegates(self):
        storage, repo = self._make()
        repo.list_checkpoint_ids.return_value = ["a", "b"]
        result = asyncio.run(storage.list_checkpoint_ids("wf"))
        assert result == ["a", "b"]
        repo.list_checkpoint_ids.assert_awaited_once_with("wf")

    def test_list_checkpoints_delegates(self):
        storage, repo = self._make()
        repo.list_checkpoints.return_value = []
        asyncio.run(storage.list_checkpoints())
        repo.list_checkpoints.assert_awaited_once_with(None)

    def test_delete_delegates(self):
        storage, repo = self._make()
        asyncio.run(storage.delete_checkpoint("id-9"))
        repo.delete_checkpoint.assert_awaited_once_with("id-9")
