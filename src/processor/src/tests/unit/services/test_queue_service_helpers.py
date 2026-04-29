# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.core.exceptions import AzureError, ResourceNotFoundError

from services.queue_service import (
    MigrationQueueMessage,
    QueueMigrationService,
    QueueServiceConfig,
    create_default_migration_request,
    is_base64_encoded,
)
from steps.analysis.models.step_param import Analysis_TaskParam


def _run(coro):
    return asyncio.run(coro)


def _service(account: str = "myacct", queue: str = "q") -> QueueMigrationService:
    """Bypass __init__ to avoid creating real Azure clients."""
    s = QueueMigrationService.__new__(QueueMigrationService)
    s.config = QueueServiceConfig(storage_account_name=account, queue_name=queue)
    s.is_running = False
    s.app_context = None
    s.main_queue = MagicMock()
    s.queue_service = MagicMock()
    s.active_workers = set()
    s._worker_tasks = {}
    s._worker_inflight = {}
    s._worker_inflight_message = {}
    s._worker_inflight_task_param = {}
    s._worker_inflight_task = {}
    s._control_watcher_task = None
    s.instance_id = 99
    s.debug_mode = False
    return s


class TestModuleHelpers:
    def test_is_base64_encoded_true(self):
        s = base64.b64encode(b"hello").decode("utf-8")
        assert is_base64_encoded(s) is True

    def test_is_base64_encoded_false(self):
        assert is_base64_encoded("not_base64!@#") is False

    def test_create_default_migration_request_keys(self):
        req = create_default_migration_request(process_id="p1", user_id="u1")
        assert req["process_id"] == "p1"
        assert req["user_id"] == "u1"
        assert req["container_name"] == "processes"
        assert req["source_file_folder"] == "p1/source"
        assert req["workspace_file_folder"] == "p1/workspace"
        assert req["output_file_folder"] == "p1/converted"


class TestMigrationQueueMessage:
    def _payload(self) -> dict:
        return {
            "process_id": "p1",
            "user_id": "u1",
            "migration_request": {
                "process_id": "p1",
                "user_id": "u1",
                "container_name": "c",
                "source_file_folder": "p1/source",
                "workspace_file_folder": "p1/workspace",
                "output_file_folder": "p1/converted",
            },
        }

    def test_post_init_validates_required_fields(self):
        with pytest.raises(ValueError, match="missing mandatory fields"):
            MigrationQueueMessage(
                process_id="p1",
                migration_request={"process_id": "p1"},
            )

    def test_from_queue_message_b64(self):
        data = self._payload()
        encoded = base64.b64encode(json.dumps(data).encode("utf-8")).decode("utf-8")
        qm = SimpleNamespace(content=encoded)
        out = MigrationQueueMessage.from_queue_message(qm)
        assert out.process_id == "p1"
        assert out.migration_request["container_name"] == "c"

    def test_from_queue_message_plain_json(self):
        data = self._payload()
        qm = SimpleNamespace(content=json.dumps(data))
        out = MigrationQueueMessage.from_queue_message(qm)
        assert out.process_id == "p1"

    def test_from_queue_message_bytes(self):
        data = self._payload()
        qm = SimpleNamespace(content=json.dumps(data).encode("utf-8"))
        out = MigrationQueueMessage.from_queue_message(qm)
        assert out.process_id == "p1"

    def test_from_queue_message_auto_completes(self):
        # Only process_id given → migration_request is auto-built
        data = {"process_id": "p9", "user_id": "u9"}
        qm = SimpleNamespace(content=json.dumps(data))
        out = MigrationQueueMessage.from_queue_message(qm)
        assert out.migration_request["process_id"] == "p9"
        assert out.retry_count == 0
        assert out.priority == "normal"

    def test_from_queue_message_invalid_json_raises(self):
        qm = SimpleNamespace(content="not json{")
        with pytest.raises(ValueError, match="Invalid queue message format"):
            MigrationQueueMessage.from_queue_message(qm)

    def test_from_queue_message_unexpected_content_type(self):
        qm = SimpleNamespace(content=12345)
        with pytest.raises(ValueError, match="Invalid queue message format"):
            MigrationQueueMessage.from_queue_message(qm)

    def test_from_queue_message_filters_unexpected_fields(self):
        data = self._payload()
        data["junk"] = "drop-me"
        qm = SimpleNamespace(content=json.dumps(data))
        out = MigrationQueueMessage.from_queue_message(qm)
        assert not hasattr(out, "junk")


class TestStorageAccountName:
    def test_empty(self):
        s = _service(account="")
        assert s._storage_account_name() == ""

    def test_https_url(self):
        s = _service(account="https://mystorage.queue.core.windows.net")
        assert s._storage_account_name() == "mystorage"

    def test_http_url(self):
        s = _service(account="http://mystorage.dfs.core.windows.net")
        assert s._storage_account_name() == "mystorage"

    def test_hostname(self):
        s = _service(account="mystorage.queue.core.windows.net")
        assert s._storage_account_name() == "mystorage"

    def test_plain_name(self):
        s = _service(account="myacct")
        assert s._storage_account_name() == "myacct"


class TestStatusAndQueueInfo:
    def test_get_service_status(self):
        s = _service()
        s.is_running = True
        s.active_workers = {1, 3}
        s._worker_inflight = {1: "p1"}
        out = s.get_service_status()
        assert out["is_running"] is True
        assert out["active_workers"] == 2
        assert out["active_worker_ids"] == [1, 3]
        assert out["inflight"] == {1: "p1"}
        assert out["queue_name"] == "q"

    def test_get_queue_info_success(self):
        s = _service()
        props = MagicMock()
        props.approximate_message_count = 5
        props.metadata = {"k": "v"}
        s.main_queue.get_queue_properties.return_value = props
        out = _run(s.get_queue_info())
        assert out["main_queue"]["approximate_message_count"] == 5
        assert out["main_queue"]["metadata"] == {"k": "v"}

    def test_get_queue_info_error(self):
        s = _service()
        s.main_queue.get_queue_properties.side_effect = RuntimeError("nope")
        out = _run(s.get_queue_info())
        assert "error" in out


class TestEnsureQueuesExist:
    def test_swallows_already_exists(self):
        s = _service()
        s.main_queue.create_queue.side_effect = Exception("already exists")
        # Should not raise
        _run(s._ensure_queues_exist())

    def test_creates_queue(self):
        s = _service()
        s.debug_mode = True
        s.main_queue.create_queue.return_value = None
        _run(s._ensure_queues_exist())
        s.main_queue.create_queue.assert_called_once()


class TestDeleteInflightMessage:
    def test_no_message_logs_and_returns(self):
        s = _service()
        _run(s._delete_inflight_queue_message(1))
        s.main_queue.delete_message.assert_not_called()

    def test_deletes_when_message_present(self):
        s = _service()
        s._worker_inflight_message[1] = ("mid", "popr")
        _run(s._delete_inflight_queue_message(1))
        s.main_queue.delete_message.assert_called_once_with("mid", "popr")

    def test_resource_not_found_swallowed(self):
        s = _service()
        s._worker_inflight_message[1] = ("mid", "popr")
        s.main_queue.delete_message.side_effect = ResourceNotFoundError("gone")
        _run(s._delete_inflight_queue_message(1))

    def test_azure_error_swallowed(self):
        s = _service()
        s._worker_inflight_message[1] = ("mid", "popr")
        s.main_queue.delete_message.side_effect = AzureError("boom")
        _run(s._delete_inflight_queue_message(1))


class TestBuildTaskParam:
    def test_builds_task_param_from_queue_message(self):
        s = _service()
        data = {
            "process_id": "p1",
            "user_id": "u1",
            "migration_request": {
                "process_id": "p1",
                "user_id": "u1",
                "container_name": "c",
                "source_file_folder": "p1/source",
                "workspace_file_folder": "p1/workspace",
                "output_file_folder": "p1/converted",
            },
        }
        qm = SimpleNamespace(content=json.dumps(data))
        tp = s._build_task_param(qm)
        assert isinstance(tp, Analysis_TaskParam)
        assert tp.process_id == "p1"
        assert tp.container_name == "c"


class TestCleanupTelemetry:
    def test_no_app_context(self):
        s = _service()
        s.app_context = None
        # Should silently skip
        _run(s._cleanup_process_telemetry("p1"))

    def test_calls_delete_via_app_context(self):
        s = _service()
        tm = MagicMock()
        tm.delete_process = AsyncMock()
        ctx = MagicMock()
        ctx.get_service_async = AsyncMock(return_value=tm)
        s.app_context = ctx
        _run(s._cleanup_process_telemetry("p1"))
        tm.delete_process.assert_awaited_once_with("p1")

    def test_falls_back_when_get_service_async_fails(self):
        s = _service()
        ctx = MagicMock()
        ctx.get_service_async = AsyncMock(side_effect=RuntimeError("boom"))
        s.app_context = ctx
        with patch("services.queue_service.TelemetryManager") as MockTM:
            instance = MockTM.return_value
            instance.delete_process = AsyncMock()
            _run(s._cleanup_process_telemetry("p1"))
            MockTM.assert_called_once_with(ctx)
            instance.delete_process.assert_awaited_once_with("p1")

    def test_swallows_telemetry_delete_failures(self):
        s = _service()
        tm = MagicMock()
        tm.delete_process = AsyncMock(side_effect=RuntimeError("delete failed"))
        ctx = MagicMock()
        ctx.get_service_async = AsyncMock(return_value=tm)
        s.app_context = ctx
        # Should not raise
        _run(s._cleanup_process_telemetry("p1"))


class TestStopProcess:
    def test_returns_false_when_not_inflight(self):
        s = _service()
        result = _run(s.stop_process("nope"))
        assert result is False

    def test_kills_and_returns_true(self):
        s = _service()
        s._worker_inflight[7] = "p1"
        s._worker_inflight_message[7] = ("m", "r")
        s._worker_inflight_task_param[7] = Analysis_TaskParam(
            process_id="p1",
            container_name="c",
            source_file_folder="p1/source",
            workspace_file_folder="p1/workspace",
            output_file_folder="p1/converted",
        )
        # No app_context → telemetry cleanup is a no-op
        s.app_context = None

        cleaned: list[str] = []

        async def _cleanup_blobs(tp):
            cleaned.append(tp.process_id)

        s._cleanup_process_blobs = _cleanup_blobs  # type: ignore[assignment]

        result = _run(s.stop_process("p1", timeout_seconds=0.1))
        assert result is True
        assert cleaned == ["p1"]
        s.main_queue.delete_message.assert_called_once_with("m", "r")

    def test_kills_without_task_param_skips_blob_cleanup(self):
        s = _service()
        s._worker_inflight[1] = "p1"
        s._worker_inflight_message[1] = ("m", "r")
        s.app_context = None
        called = []

        async def _cleanup_blobs(tp):
            called.append(tp)

        s._cleanup_process_blobs = _cleanup_blobs  # type: ignore[assignment]

        result = _run(s.stop_process("p1", timeout_seconds=0.1))
        assert result is True
        assert called == []
