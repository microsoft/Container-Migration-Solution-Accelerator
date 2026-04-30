# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for Cosmos DB-backed workflow checkpoint storage."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from libs.agent_framework.cosmos_checkpoint_storage import (
    CosmosCheckpointStorage,
    CosmosWorkflowCheckpoint,
    CosmosWorkflowCheckpointRepository,
)


def test_checkpoint_id_is_propagated_to_id_field() -> None:
    cp = CosmosWorkflowCheckpoint(checkpoint_id="cp-001", workflow_id="wf-1")
    assert cp.checkpoint_id == "cp-001"
    assert cp.id == "cp-001"
    assert cp.workflow_id == "wf-1"


def test_checkpoint_explicit_id_overrides_default() -> None:
    cp = CosmosWorkflowCheckpoint(checkpoint_id="cp-001", id="explicit-id")
    assert cp.id == "explicit-id"


def _make_repository_without_init() -> CosmosWorkflowCheckpointRepository:
    """Bypass parent RepositoryBase.__init__ which requires Cosmos credentials."""
    with patch.object(
        CosmosWorkflowCheckpointRepository,
        "__init__",
        lambda self, *a, **k: None,
    ):
        repo = CosmosWorkflowCheckpointRepository(
            account_url="x", database_name="y", container_name="z"
        )
    return repo


def test_repository_save_checkpoint_delegates_to_add_async() -> None:
    repo = _make_repository_without_init()
    repo.add_async = AsyncMock()
    cp = CosmosWorkflowCheckpoint(checkpoint_id="cp-1")

    asyncio.run(repo.save_checkpoint(cp))

    repo.add_async.assert_awaited_once_with(cp)


def test_repository_load_checkpoint_returns_get_async_value() -> None:
    repo = _make_repository_without_init()
    sentinel = SimpleNamespace(checkpoint_id="cp-1")
    repo.get_async = AsyncMock(return_value=sentinel)

    result = asyncio.run(repo.load_checkpoint("cp-1"))

    assert result is sentinel
    repo.get_async.assert_awaited_once_with("cp-1")


def test_repository_list_checkpoint_ids_without_filter_uses_all_async() -> None:
    repo = _make_repository_without_init()
    repo.all_async = AsyncMock(return_value=[{"id": "a"}, {"id": "b"}])

    ids = asyncio.run(repo.list_checkpoint_ids())

    assert ids == ["a", "b"]
    repo.all_async.assert_awaited_once()


def test_repository_list_checkpoint_ids_with_workflow_id_uses_find_one_async() -> None:
    repo = _make_repository_without_init()
    repo.find_one_async = AsyncMock(return_value=[{"id": "x"}])

    ids = asyncio.run(repo.list_checkpoint_ids(workflow_id="wf-42"))

    assert ids == ["x"]
    repo.find_one_async.assert_awaited_once_with({"workflow_id": "wf-42"})


def test_repository_list_checkpoints_without_filter_uses_all_async() -> None:
    repo = _make_repository_without_init()
    items = [SimpleNamespace(checkpoint_id="a"), SimpleNamespace(checkpoint_id="b")]
    repo.all_async = AsyncMock(return_value=items)

    result = asyncio.run(repo.list_checkpoints())

    assert result == items


def test_repository_list_checkpoints_with_workflow_id_uses_find_one_async() -> None:
    repo = _make_repository_without_init()
    items = [SimpleNamespace(checkpoint_id="z")]
    repo.find_one_async = AsyncMock(return_value=items)

    result = asyncio.run(repo.list_checkpoints(workflow_id="wf"))

    assert result == items
    repo.find_one_async.assert_awaited_once_with({"workflow_id": "wf"})


def test_repository_delete_checkpoint_delegates_to_delete_async() -> None:
    repo = _make_repository_without_init()
    repo.delete_async = AsyncMock()

    asyncio.run(repo.delete_checkpoint("cp-9"))

    repo.delete_async.assert_awaited_once_with(key="cp-9")


def test_storage_save_checkpoint_converts_and_delegates() -> None:
    repo = _make_repository_without_init()
    repo.save_checkpoint = AsyncMock()
    storage = CosmosCheckpointStorage(repository=repo)

    fake_checkpoint = SimpleNamespace(
        to_dict=lambda: {"checkpoint_id": "cp-11", "workflow_id": "wf-1"}
    )

    asyncio.run(storage.save_checkpoint(fake_checkpoint))

    repo.save_checkpoint.assert_awaited_once()
    saved = repo.save_checkpoint.await_args.args[0]
    assert isinstance(saved, CosmosWorkflowCheckpoint)
    assert saved.checkpoint_id == "cp-11"
    assert saved.id == "cp-11"


def test_storage_load_checkpoint_returns_repository_value() -> None:
    repo = _make_repository_without_init()
    sentinel = SimpleNamespace(id="cp-2")
    repo.load_checkpoint = AsyncMock(return_value=sentinel)
    storage = CosmosCheckpointStorage(repository=repo)

    result = asyncio.run(storage.load_checkpoint("cp-2"))

    assert result is sentinel
    repo.load_checkpoint.assert_awaited_once_with("cp-2")


def test_storage_list_checkpoint_ids_delegates() -> None:
    repo = _make_repository_without_init()
    repo.list_checkpoint_ids = AsyncMock(return_value=["a"])
    storage = CosmosCheckpointStorage(repository=repo)

    assert asyncio.run(storage.list_checkpoint_ids("wf")) == ["a"]
    repo.list_checkpoint_ids.assert_awaited_once_with("wf")


def test_storage_list_checkpoints_delegates() -> None:
    repo = _make_repository_without_init()
    repo.list_checkpoints = AsyncMock(return_value=[1, 2])
    storage = CosmosCheckpointStorage(repository=repo)

    assert asyncio.run(storage.list_checkpoints(None)) == [1, 2]
    repo.list_checkpoints.assert_awaited_once_with(None)


def test_storage_delete_checkpoint_delegates() -> None:
    repo = _make_repository_without_init()
    repo.delete_checkpoint = AsyncMock()
    storage = CosmosCheckpointStorage(repository=repo)

    asyncio.run(storage.delete_checkpoint("cp-x"))
    repo.delete_checkpoint.assert_awaited_once_with("cp-x")
