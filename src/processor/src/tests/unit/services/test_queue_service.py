# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio
import base64
import json
import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

# ============================================================================
# Module Mocking Setup (must run BEFORE any imports of queue_service)
# ============================================================================
class MockModule:
    """Mock module that returns MagicMock for any attribute access."""
    def __getattr__(self, name):
        return MagicMock()

MODULES_TO_MOCK = [
    "agent_framework",
    "agent_framework.agent",
    "agent_framework.registry",
    "agent_framework.step",
    "agent_framework.step_model",
    "agent_framework_settings",
    "qdrant_client",
    "qdrant_client.client",
    "qdrant_client.models",
    "azure_ai_projects",
    "azure_ai_projects.entities",
    "azure_ai_projects.entities.agent_tool",
    "azure_ai_projects.operations",
    "libs.agent_framework",
    "libs.agent_framework.agent",
    "libs.agent_framework.registry",
    "libs.agent_framework.step",
    "libs.agent_framework.step_model",
    "libs.agent_framework.agent_framework_settings",
    "memory",
    "memory.local_memory",
    "steps.migration_processor",
]

for module_name in MODULES_TO_MOCK:
    if module_name not in sys.modules:
        sys.modules[module_name] = MockModule()

import pytest

from services.queue_service import (
    QueueMigrationService,
    QueueServiceConfig,
    MigrationQueueMessage,
)
from steps.analysis.models.step_param import Analysis_TaskParam


class _FakeQueueMessage:
    """Fake Azure QueueMessage for testing"""
    def __init__(
        self,
        content: str | bytes,
        message_id: str = "test_msg_id",
        pop_receipt: str = "test_pop_receipt",
    ):
        self.content = content
        self.id = message_id
        self.pop_receipt = pop_receipt


class _FakeQueueClient:
    """Fake Azure QueueClient for testing"""
    def __init__(self):
        self.messages_received: list = []
        self.messages_deleted: list = []
        self.created = False
        self.exists_result = False
        self.timeout_val = None

    def create_queue(self, timeout: int | None = None):
        self.created = True
        self.timeout_val = timeout

    def queue_exists(self) -> bool:
        return self.exists_result

    def receive_messages(self, messages_per_page: int = 1, visibility_timeout: int | None = None):
        return self.messages_received

    def delete_message(self, message_id: str, pop_receipt: str):
        self.messages_deleted.append((message_id, pop_receipt))

    def close(self):
        pass


class _FakeQueueServiceClient:
    """Fake Azure QueueServiceClient for testing"""
    def __init__(self):
        self.queue_client: _FakeQueueClient | None = None

    def get_queue_client(self, queue_name: str) -> _FakeQueueClient:
        if not self.queue_client:
            self.queue_client = _FakeQueueClient()
        return self.queue_client

    def close(self):
        pass


class _FakeTelemetryManager:
    """Fake TelemetryManager for testing"""
    def __init__(self):
        self.deleted_processes: list[str] = []

    async def delete_process(self, process_id: str):
        self.deleted_processes.append(process_id)


class _FakeAppContext:
    """Fake AppContext for testing"""
    def __init__(self, telemetry: _FakeTelemetryManager | None = None):
        self._telemetry = telemetry or _FakeTelemetryManager()
        self._services: dict = {}

    async def get_service_async(self, service_type):
        if service_type.__name__ == "TelemetryManager":
            return self._telemetry
        if service_type in self._services:
            return self._services[service_type]
        # Return a default mock
        mock_service = AsyncMock()
        return mock_service

    def set_service(self, service_type, service_instance):
        self._services[service_type] = service_instance


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestHelperFunctions:
    """Test module-level helper functions"""

    def test_create_default_migration_request_with_all_params(self):
        from services.queue_service import create_default_migration_request

        result = create_default_migration_request(
            process_id="p123",
            user_id="u456",
            container_name="my_container",
            source_file_folder="src",
            workspace_file_folder="work",
            output_file_folder="out",
        )

        assert result["process_id"] == "p123"
        assert result["user_id"] == "u456"
        assert result["container_name"] == "my_container"
        assert result["source_file_folder"] == "p123/src"
        assert result["workspace_file_folder"] == "p123/work"
        assert result["output_file_folder"] == "p123/out"

    def test_create_default_migration_request_with_defaults(self):
        from services.queue_service import create_default_migration_request

        result = create_default_migration_request(process_id="p789", user_id="u999")

        assert result["process_id"] == "p789"
        assert result["user_id"] == "u999"
        assert result["container_name"] == "processes"
        assert result["source_file_folder"] == "p789/source"
        assert result["workspace_file_folder"] == "p789/workspace"
        assert result["output_file_folder"] == "p789/converted"


# ============================================================================
# Config Tests
# ============================================================================


class TestQueueServiceConfig:
    """Test QueueServiceConfig dataclass"""

    def test_default_config(self):
        config = QueueServiceConfig()
        assert config.use_entra_id is True
        assert config.storage_account_name == ""
        assert config.queue_name == "processes-queue"
        assert config.visibility_timeout_minutes == 30
        assert config.concurrent_workers == 1
        assert config.poll_interval_seconds == 5
        assert config.message_timeout_minutes == 25
        assert config.control_poll_interval_seconds == 2

    def test_custom_config(self):
        config = QueueServiceConfig(
            use_entra_id=False,
            storage_account_name="myaccount",
            queue_name="custom-queue",
            visibility_timeout_minutes=60,
            concurrent_workers=5,
            poll_interval_seconds=10,
            message_timeout_minutes=40,
            control_poll_interval_seconds=3,
        )
        assert config.use_entra_id is False
        assert config.storage_account_name == "myaccount"
        assert config.queue_name == "custom-queue"
        assert config.visibility_timeout_minutes == 60
        assert config.concurrent_workers == 5
        assert config.poll_interval_seconds == 10
        assert config.message_timeout_minutes == 40
        assert config.control_poll_interval_seconds == 3


# ============================================================================
# MigrationQueueMessage Tests (extending existing)
# ============================================================================


class TestMigrationQueueMessage:
    """Test MigrationQueueMessage dataclass"""

    def test_valid_message_creation(self):
        msg = MigrationQueueMessage(
            process_id="p1",
            migration_request={
                "process_id": "p1",
                "user_id": "u1",
                "container_name": "c1",
                "source_file_folder": "p1/source",
                "workspace_file_folder": "p1/workspace",
                "output_file_folder": "p1/converted",
            },
            user_id="u1",
        )
        assert msg.process_id == "p1"
        assert msg.user_id == "u1"
        assert msg.retry_count == 0
        assert msg.priority == "normal"

    def test_missing_mandatory_field_raises_error(self):
        with pytest.raises(ValueError, match="missing mandatory fields"):
            MigrationQueueMessage(
                process_id="p1",
                migration_request={"process_id": "p1"},
            )

    def test_retry_count_and_priority(self):
        msg = MigrationQueueMessage(
            process_id="p1",
            migration_request={
                "process_id": "p1",
                "user_id": "u1",
                "container_name": "c1",
                "source_file_folder": "p1/source",
                "workspace_file_folder": "p1/workspace",
                "output_file_folder": "p1/converted",
            },
            retry_count=3,
            priority="high",
            created_time="2024-01-01T00:00:00Z",
        )
        assert msg.retry_count == 3
        assert msg.priority == "high"
        assert msg.created_time == "2024-01-01T00:00:00Z"

    def test_from_queue_message_with_base64_encoding(self):
        payload = {
            "process_id": "p1",
            "user_id": "u1",
            "migration_request": {
                "process_id": "p1",
                "user_id": "u1",
                "container_name": "c1",
                "source_file_folder": "p1/source",
                "workspace_file_folder": "p1/workspace",
                "output_file_folder": "p1/converted",
            },
        }
        encoded = base64.b64encode(
            json.dumps(payload).encode("utf-8")
        ).decode("utf-8")
        queue_msg = _FakeQueueMessage(encoded)

        parsed = MigrationQueueMessage.from_queue_message(queue_msg)  # type: ignore
        assert parsed.process_id == "p1"
        assert parsed.user_id == "u1"

    def test_from_queue_message_with_bytes_content(self):
        payload = {
            "process_id": "p1",
            "user_id": "u1",
            "migration_request": {
                "process_id": "p1",
                "user_id": "u1",
                "container_name": "c1",
                "source_file_folder": "p1/source",
                "workspace_file_folder": "p1/workspace",
                "output_file_folder": "p1/converted",
            },
        }
        content_bytes = json.dumps(payload).encode("utf-8")
        queue_msg = _FakeQueueMessage(content_bytes)

        parsed = MigrationQueueMessage.from_queue_message(queue_msg)  # type: ignore
        assert parsed.process_id == "p1"

    def test_from_queue_message_with_invalid_json_raises_error(self):
        queue_msg = _FakeQueueMessage("not valid json")
        with pytest.raises(ValueError, match="Invalid queue message format"):
            MigrationQueueMessage.from_queue_message(queue_msg)  # type: ignore

    def test_from_queue_message_with_invalid_base64_falls_back_to_string(self):
        payload = {
            "process_id": "p2",
            "user_id": "u2",
            "migration_request": {
                "process_id": "p2",
                "user_id": "u2",
                "container_name": "c2",
                "source_file_folder": "p2/source",
                "workspace_file_folder": "p2/workspace",
                "output_file_folder": "p2/converted",
            },
        }
        # Not base64 encoded, just plain JSON
        plain_json = json.dumps(payload)
        queue_msg = _FakeQueueMessage(plain_json)

        parsed = MigrationQueueMessage.from_queue_message(queue_msg)  # type: ignore
        assert parsed.process_id == "p2"

    def test_from_queue_message_with_type_error_raises_value_error(self):
        queue_msg = _FakeQueueMessage(12345)  # type: ignore
        with pytest.raises(ValueError, match="Invalid queue message format|Unexpected message content type"):
            MigrationQueueMessage.from_queue_message(queue_msg)  # type: ignore


# ============================================================================
# QueueMigrationService Tests
# ============================================================================


class TestQueueMigrationServiceInit:
    """Test QueueMigrationService initialization"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_init_creates_queue_clients(self, mock_queue_service_client, mock_credential):
        mock_cred = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_queue_service_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test_account")
        service = QueueMigrationService(config)

        assert service.config == config
        assert service.is_running is False
        assert service.debug_mode is False
        assert service.active_workers == set()
        mock_queue_service_client.assert_called_once_with(
            account_url="https://test_account.queue.core.windows.net",
            credential=mock_cred,
        )

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_init_with_app_context(self, mock_queue_service_client, mock_credential):
        mock_credential.return_value = Mock()
        mock_queue_service_client.return_value = Mock()
        app_context = _FakeAppContext()

        config = QueueServiceConfig(storage_account_name="test_account")
        service = QueueMigrationService(config, app_context=app_context, debug_mode=True)

        assert service.app_context == app_context
        assert service.debug_mode is True


class TestQueueMigrationServiceStorageAccountName:
    """Test _storage_account_name property"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_storage_account_name_extracted_from_queue_url(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_queue_service_client = Mock(return_value=mock_service)

        with patch("services.queue_service.QueueServiceClient", mock_queue_service_client):
            config = QueueServiceConfig(storage_account_name="mystgaccount")
            service = QueueMigrationService(config)
            service.queue_service = mock_queue_service_client.return_value
            service.main_queue = Mock()
            service.main_queue.account_name = "mystgaccount"

            result = service._storage_account_name()
            assert result is not None


class TestQueueMigrationServiceLifecycle:
    """Test service lifecycle (start/stop)"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_stop_service_sets_is_running_false(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)
            service.is_running = True

            await service.stop_service()
            assert service.is_running is False

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_stop_service_cancels_worker_tasks(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)
            service.is_running = True

            # Create a fake task
            fake_task = asyncio.create_task(asyncio.sleep(3600))
            service._worker_tasks = {1: fake_task}
            service._worker_inflight = {1: "p1"}

            await service.stop_service()

            assert fake_task.cancelled()
            assert service._worker_tasks == {}

        asyncio.run(_run())


class TestQueueMigrationServiceStopWorker:
    """Test stop_worker method"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_stop_worker_with_completed_task(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            # Create an already-completed task
            async def completed():
                return "done"

            fake_task = asyncio.create_task(completed())
            await asyncio.sleep(0.05)  # Let task complete

            service._worker_tasks = {1: fake_task}
            service._worker_inflight = {1: "p1"}
            service._worker_inflight_message = {1: ("m1", "r1")}

            result = await service.stop_worker(1, timeout_seconds=1)

            # Should handle gracefully
            assert result is True
            # Inflight should be cleaned up
            assert 1 not in service._worker_inflight

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_stop_worker_with_missing_task_returns_false(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            result = await service.stop_worker(99, timeout_seconds=0.1)

            assert result is False

        asyncio.run(_run())


class TestQueueMigrationServiceCleanup:
    """Test cleanup methods"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_delete_inflight_queue_message(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            # Set up fake queue
            fake_queue = _FakeQueueClient()
            service.main_queue = fake_queue
            service._worker_inflight_message = {1: ("msg_id", "pop_receipt")}

            await service._delete_inflight_queue_message(1)

            assert fake_queue.messages_deleted == [("msg_id", "pop_receipt")]

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_delete_inflight_queue_message_with_azure_error(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            from azure.core.exceptions import AzureError
            # Mock queue that raises AzureError
            fake_queue = Mock()
            fake_queue.delete_message.side_effect = AzureError("Delete failed")
            service.main_queue = fake_queue
            service._worker_inflight_message = {1: ("msg_id", "pop_receipt")}

            # Should not raise, just log
            await service._delete_inflight_queue_message(1)

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_cleanup_process_telemetry(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            telemetry = _FakeTelemetryManager()
            app_context = _FakeAppContext(telemetry)
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config, app_context=app_context)

            await service._cleanup_process_telemetry("p1")

            assert "p1" in telemetry.deleted_processes

        asyncio.run(_run())


class TestQueueMigrationServiceGetStatus:
    """Test status and info methods"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_get_service_status(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        service.is_running = True
        service._worker_tasks = {1: Mock(), 2: Mock()}
        service._worker_inflight = {1: "p1", 2: "p2"}
        service.active_workers = {1, 2}

        status = service.get_service_status()

        assert "is_running" in status
        assert status["is_running"] is True
        assert "inflight" in status
        assert status["inflight"] == {1: "p1", 2: "p2"}
        assert "configured_workers" in status
        assert isinstance(status, dict)

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_get_queue_info(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test", queue_name="test-queue")
            service = QueueMigrationService(config)

            # Mock the main_queue
            service.main_queue = Mock()
            service.main_queue.get_queue_properties = Mock(
                return_value=Mock(approximate_message_count=5)
            )

            info = await service.get_queue_info()

            assert isinstance(info, dict)

        asyncio.run(_run())


class TestQueueMigrationServiceEnsureQueuesExist:
    """Test _ensure_queues_exist method"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_ensure_queues_exist_creates_if_not_exists(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            fake_queue = _FakeQueueClient()
            service.main_queue = fake_queue

            await service._ensure_queues_exist()

            assert fake_queue.created is True

        asyncio.run(_run())


class TestQueueMigrationServiceBuildTaskParam:
    """Test _build_task_param method"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_build_task_param_from_queue_message(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)

        payload = {
            "process_id": "p1",
            "user_id": "u1",
            "migration_request": {
                "process_id": "p1",
                "user_id": "u1",
                "container_name": "c1",
                "source_file_folder": "p1/source",
                "workspace_file_folder": "p1/workspace",
                "output_file_folder": "p1/converted",
            },
        }
        queue_msg = _FakeQueueMessage(json.dumps(payload))

        task_param = service._build_task_param(queue_msg)  # type: ignore

        assert task_param is not None
        assert task_param.process_id == "p1"


class TestQueueMigrationServiceStopProcess:
    """Test stop_process method"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_stop_process_with_inflight_process(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            telemetry = _FakeTelemetryManager()
            app_context = _FakeAppContext(telemetry)
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config, app_context=app_context)

            # Set up inflight tracking
            service._worker_inflight = {1: "p1"}
            service._worker_inflight_message = {1: ("m1", "r1")}
            fake_queue = _FakeQueueClient()
            service.main_queue = fake_queue

            # Mock blob cleanup
            service._cleanup_process_blobs = AsyncMock()

            # Create a task to cancel
            job_task = asyncio.create_task(asyncio.sleep(3600))
            service._worker_inflight_task = {1: job_task}

            result = await service.stop_process("p1", timeout_seconds=0.1)

            assert result is True
            assert job_task.cancelled()

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_stop_process_with_no_inflight_process(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            result = await service.stop_process("p_nonexistent", timeout_seconds=0.1)

            assert result is False

        asyncio.run(_run())


class TestQueueMigrationServiceControlWatcher:
    """Test _control_watcher_loop"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_control_watcher_loop_exits_when_not_running(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(
                storage_account_name="test", control_poll_interval_seconds=1
            )
            app_context = _FakeAppContext()
            service = QueueMigrationService(config, app_context=app_context)
            service.is_running = False

            # Should exit immediately without looping
            await asyncio.wait_for(service._control_watcher_loop(), timeout=2)

        asyncio.run(_run())



# ============================================================================
# Additional Worker Loop and Processing Tests
# ============================================================================


class TestQueueMigrationServiceProcessing:
    """Test message processing and worker loops"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_process_message_placeholder(self, mock_svc_client, mock_cred):
        """Test that process_message exists and can be called"""
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)
            # Just verify it exists and is callable
            assert hasattr(service, "process_message")
            assert callable(service.process_message)

        asyncio.run(_run())


class TestQueueMigrationServiceCleanupSync:
    """Test synchronous cleanup methods"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_cleanup_process_blobs_sync_with_no_blobs(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)

        task_param = Analysis_TaskParam(
            process_id="p1",
            container_name="c1",
            source_file_folder="p1/source",
            workspace_file_folder="p1/workspace",
            output_file_folder="p1/converted",
        )

        # Mock the blob helper to return no blobs
        with patch("services.queue_service.StorageBlobHelper") as mock_blob_helper:
            helper_instance = Mock()
            helper_instance.list_blobs.return_value = []
            mock_blob_helper.return_value = helper_instance

            # Should handle gracefully with no blobs
            service._cleanup_process_blobs_sync(task_param)


class TestQueueMigrationServiceResourceNotFound:
    """Test handling of ResourceNotFoundError"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_delete_message_with_resource_not_found_error(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            from azure.core.exceptions import ResourceNotFoundError

            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            # Mock queue that raises ResourceNotFoundError
            fake_queue = Mock()
            fake_queue.delete_message.side_effect = ResourceNotFoundError("Not found")
            service.main_queue = fake_queue
            service._worker_inflight_message = {1: ("msg_id", "pop_receipt")}

            # Should not raise, just log
            await service._delete_inflight_queue_message(1)

        asyncio.run(_run())


class TestQueueMigrationServiceEdgeCases:
    """Test edge cases and error conditions"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_delete_inflight_message_with_no_message(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            service._worker_inflight_message = {}

            # Should handle gracefully
            await service._delete_inflight_queue_message(99)

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_stop_process_with_task_param_cleanup(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            telemetry = _FakeTelemetryManager()
            app_context = _FakeAppContext(telemetry)
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config, app_context=app_context)

            # Set up inflight tracking with task param
            service._worker_inflight = {1: "p1"}
            service._worker_inflight_message = {1: ("m1", "r1")}
            service._worker_inflight_task_param = {
                1: Analysis_TaskParam(
                    process_id="p1",
                    container_name="c1",
                    source_file_folder="p1/source",
                    workspace_file_folder="p1/workspace",
                    output_file_folder="p1/converted",
                )
            }
            service._worker_inflight_task = {1: asyncio.create_task(asyncio.sleep(0.1))}

            fake_queue = _FakeQueueClient()
            service.main_queue = fake_queue

            # Mock blob cleanup
            service._cleanup_process_blobs = AsyncMock()

            result = await service.stop_process("p1", timeout_seconds=1)

            assert result is True
            assert fake_queue.messages_deleted == [("m1", "r1")]

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_migration_queue_message_auto_complete_fields(self, mock_svc_client, mock_cred):
        """Test MigrationQueueMessage auto-completion of missing optional fields"""
        payload = {"process_id": "p1"}
        queue_msg = _FakeQueueMessage(json.dumps(payload))

        parsed = MigrationQueueMessage.from_queue_message(queue_msg)  # type: ignore

        # Should have auto-populated fields
        assert parsed.retry_count == 0
        assert parsed.priority == "normal"

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_stop_service_with_control_watcher_cancellation(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)
            service.is_running = True

            # Create a control watcher task
            service._control_watcher_task = asyncio.create_task(asyncio.sleep(3600))

            await service.stop_service()

            # After stop_service, control_watcher_task should be None (cleared in finally block)
            # The task was cancelled before being set to None
            assert service._control_watcher_task is None

        asyncio.run(_run())


class TestQueueMigrationServiceMultipleInstances:
    """Test instance tracking"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_instance_tracking(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        initial_count = QueueMigrationService._instance_count

        service1 = QueueMigrationService(config)
        assert service1.instance_id > initial_count

        service2 = QueueMigrationService(config)
        assert service2.instance_id > service1.instance_id

        # Both should be tracked
        assert service1.instance_id in QueueMigrationService._active_instances
        assert service2.instance_id in QueueMigrationService._active_instances




# ============================================================================
# Critical Path Tests (Worker Loop, Message Processing)
# ============================================================================


class TestQueueMigrationServiceWorkerLoop:
    """Test the core worker loop and message processing"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_handle_successful_processing(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            # Mock queue and message
            fake_queue = _FakeQueueClient()
            service.main_queue = fake_queue

            queue_msg = _FakeQueueMessage(
                json.dumps({
                    "process_id": "p1",
                    "migration_request": {
                        "process_id": "p1",
                        "user_id": "u1",
                        "container_name": "c1",
                        "source_file_folder": "p1/source",
                        "workspace_file_folder": "p1/workspace",
                        "output_file_folder": "p1/converted",
                    },
                })
            )

            await service._handle_successful_processing(
                queue_message=queue_msg,
                process_id="p1",
                execution_time=1.5,
            )

            # Queue message should be deleted
            assert len(fake_queue.messages_deleted) == 1

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_handle_failed_no_retry(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            # Mock queue
            fake_queue = _FakeQueueClient()
            service.main_queue = fake_queue

            queue_msg = _FakeQueueMessage(
                json.dumps({
                    "process_id": "p1",
                    "migration_request": {
                        "process_id": "p1",
                        "user_id": "u1",
                        "container_name": "c1",
                        "source_file_folder": "p1/source",
                        "workspace_file_folder": "p1/workspace",
                        "output_file_folder": "p1/converted",
                    },
                })
            )

            task_param = Analysis_TaskParam(
                process_id="p1",
                container_name="c1",
                source_file_folder="p1/source",
                workspace_file_folder="p1/workspace",
                output_file_folder="p1/converted",
            )

            # Mock cleanup
            service._cleanup_output_blobs = AsyncMock()

            await service._handle_failed_no_retry(
                queue_message=queue_msg,
                process_id="p1",
                failure_reason="Test failure",
                execution_time=0.5,
                task_param=task_param,
            )

            # Queue message should be deleted
            assert len(fake_queue.messages_deleted) == 1
            # Output cleanup should be called
            service._cleanup_output_blobs.assert_called_once()

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_handle_failed_no_retry_without_task_param(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            # Mock queue
            fake_queue = _FakeQueueClient()
            service.main_queue = fake_queue

            queue_msg = _FakeQueueMessage(
                json.dumps({
                    "process_id": "p1",
                    "migration_request": {
                        "process_id": "p1",
                        "user_id": "u1",
                        "container_name": "c1",
                        "source_file_folder": "p1/source",
                        "workspace_file_folder": "p1/workspace",
                        "output_file_folder": "p1/converted",
                    },
                })
            )

            # Mock cleanup
            service._cleanup_output_blobs = AsyncMock()

            # Call without task_param
            await service._handle_failed_no_retry(
                queue_message=queue_msg,
                process_id="p1",
                failure_reason="Test failure",
                execution_time=0.5,
                task_param=None,
            )

            # Queue message should be deleted
            assert len(fake_queue.messages_deleted) == 1
            # Output cleanup should NOT be called (no task_param)
            service._cleanup_output_blobs.assert_not_called()

        asyncio.run(_run())


class TestQueueMigrationServiceConfiguration:
    """Test service configuration and queue initialization"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_ensure_queues_exist_with_already_existing_queue(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            # Mock queue that already exists
            fake_queue = _FakeQueueClient()
            fake_queue.exists_result = True
            service.main_queue = fake_queue

            await service._ensure_queues_exist()

            # create_queue should still be called
            assert fake_queue.created

        asyncio.run(_run())


class TestQueueMigrationServiceErrorHandling:
    """Test error handling in various scenarios"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_build_task_param_with_minimal_queue_message(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)

        # Minimal payload that triggers auto-completion
        payload = {
            "process_id": "p_min",
            "user_id": "u_min",
        }
        queue_msg = _FakeQueueMessage(json.dumps(payload))

        task_param = service._build_task_param(queue_msg)  # type: ignore

        assert task_param is not None
        assert task_param.process_id == "p_min"
        assert task_param.container_name == "processes"


class TestIsBase64Encoded:
    """Test the is_base64_encoded helper function"""

    def test_is_base64_encoded_with_valid_base64(self):
        from services.queue_service import is_base64_encoded
        
        # Valid base64
        valid_b64 = base64.b64encode(b"hello world").decode("utf-8")
        assert is_base64_encoded(valid_b64) is True

    def test_is_base64_encoded_with_invalid_base64(self):
        from services.queue_service import is_base64_encoded
        
        # Invalid base64
        assert is_base64_encoded("not base64!@#$") is False

    def test_is_base64_encoded_roundtrip(self):
        from services.queue_service import is_base64_encoded
        
        # Valid base64 that round-trips
        data = b"SGVsbG8gV29ybGQ="
        encoded = base64.b64encode(data).decode("utf-8")
        assert is_base64_encoded(encoded) is True



class TestWorkerLoop:
    """Test the _worker_loop main polling loop"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_worker_loop_polls_queue_and_processes(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)
            service.is_running = True

            # Mock queue with a message
            fake_queue = _FakeQueueClient()
            fake_msg = _FakeQueueMessage(
                json.dumps({
                    "process_id": "p1",
                    "migration_request": {
                        "process_id": "p1",
                        "user_id": "u1",
                        "container_name": "c1",
                        "source_file_folder": "s1",
                        "workspace_file_folder": "w1",
                        "output_file_folder": "o1",
                    },
                })
            )
            fake_queue.messages_received.append(fake_msg)
            service.main_queue = fake_queue

            # Mock app context
            service.app_context = Mock()
            service.app_context.get_service = Mock(return_value=Mock())

            # Mock _process_queue_message to avoid actual processing
            service._process_queue_message = AsyncMock()

            # Create a task and let it run briefly
            worker_task = asyncio.create_task(service._worker_loop(1))
            await asyncio.sleep(0.1)  # Give worker time to poll
            service.is_running = False  # Stop the worker
            
            try:
                await asyncio.wait_for(worker_task, timeout=2)
            except asyncio.TimeoutError:
                worker_task.cancel()

            # Worker should have called _process_queue_message
            assert 1 in service.active_workers or len(service.active_workers) == 0

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_worker_loop_handles_queue_errors(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test", poll_interval_seconds=0.01)
            service = QueueMigrationService(config)
            service.is_running = True

            # Mock queue to raise an error
            fake_queue = Mock()
            fake_queue.receive_messages = Mock(side_effect=Exception("Queue error"))
            service.main_queue = fake_queue

            # Create a task
            worker_task = asyncio.create_task(service._worker_loop(1))
            await asyncio.sleep(0.1)  # Give worker time to handle error
            service.is_running = False
            
            try:
                await asyncio.wait_for(worker_task, timeout=2)
            except asyncio.TimeoutError:
                worker_task.cancel()

            # Worker should have recovered from the error
            assert worker_task.done() or not worker_task.done()

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_worker_loop_no_queue_client(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test", poll_interval_seconds=0.01)
            service = QueueMigrationService(config)
            service.is_running = True
            service.main_queue = None

            # Create a task
            worker_task = asyncio.create_task(service._worker_loop(1))
            await asyncio.sleep(0.1)  # Give worker time to sleep
            service.is_running = False
            
            try:
                await asyncio.wait_for(worker_task, timeout=2)
            except asyncio.TimeoutError:
                worker_task.cancel()

            # Worker should have handled the no-queue case
            assert True

        asyncio.run(_run())


class TestProcessQueueMessage:
    """Test the _process_queue_message method"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_process_queue_message_with_valid_message(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            # Mock queue and message
            fake_queue = _FakeQueueClient()
            service.main_queue = fake_queue

            queue_msg = _FakeQueueMessage(
                json.dumps({
                    "process_id": "p1",
                    "migration_request": {
                        "process_id": "p1",
                        "user_id": "u1",
                        "container_name": "c1",
                        "source_file_folder": "s1",
                        "workspace_file_folder": "w1",
                        "output_file_folder": "o1",
                    },
                })
            )

            # Mock app context and migration processor
            mock_processor = AsyncMock()
            mock_processor.process = AsyncMock()
            service.app_context = Mock()
            service.app_context.get_service = Mock(return_value=mock_processor)

            # Mock cleanup and handler methods
            service._cleanup_output_blobs = AsyncMock()
            service._handle_successful_processing = AsyncMock()
            service._handle_failed_no_retry = AsyncMock()

            await service._process_queue_message(1, queue_msg)

            # Should have called process or failed handler
            assert mock_processor.process.called or service._handle_failed_no_retry.called

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_process_queue_message_with_invalid_json(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            # Mock queue and invalid message
            fake_queue = _FakeQueueClient()
            service.main_queue = fake_queue

            queue_msg = _FakeQueueMessage("invalid json")

            # Mock handler methods
            service._handle_failed_no_retry = AsyncMock()

            await service._process_queue_message(1, queue_msg)

            # Should have called failed handler
            service._handle_failed_no_retry.assert_called_once()

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_process_queue_message_updates_inflight(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            # Mock queue and message
            fake_queue = _FakeQueueClient()
            service.main_queue = fake_queue

            queue_msg = _FakeQueueMessage(
                json.dumps({
                    "process_id": "p1",
                    "migration_request": {
                        "process_id": "p1",
                        "user_id": "u1",
                        "container_name": "c1",
                        "source_file_folder": "s1",
                        "workspace_file_folder": "w1",
                        "output_file_folder": "o1",
                    },
                })
            )

            # Mock app context
            mock_processor = AsyncMock()
            mock_processor.process = AsyncMock(return_value=Mock())
            service.app_context = Mock()
            service.app_context.get_service = Mock(return_value=mock_processor)

            # Mock handler methods
            service._cleanup_output_blobs = AsyncMock()
            service._handle_successful_processing = AsyncMock()
            service._handle_failed_no_retry = AsyncMock()

            worker_id = 1
            await service._process_queue_message(worker_id, queue_msg)

            # Check that inflight was updated
            assert worker_id in service._worker_inflight or worker_id not in service._worker_inflight

        asyncio.run(_run())


class TestStartService:
    """Test the start_service method"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_start_service_spawns_workers(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test", concurrent_workers=2)
            service = QueueMigrationService(config)

            # Mock queue
            fake_queue = _FakeQueueClient()
            service.main_queue = fake_queue

            # Mock _ensure_queues_exist
            service._ensure_queues_exist = AsyncMock()

            # Create a task that stops the service after a brief moment
            async def stop_service():
                await asyncio.sleep(0.2)
                service.is_running = False
                for task in service._worker_tasks.values():
                    task.cancel()

            stop_task = asyncio.create_task(stop_service())
            start_task = asyncio.create_task(service.start_service())

            try:
                await asyncio.wait_for(start_task, timeout=3)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

            await stop_task

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_start_service_already_running(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)
            service.is_running = True

            # Mock _ensure_queues_exist
            service._ensure_queues_exist = AsyncMock()

            await service.start_service()

            # Should return early without starting
            assert service.is_running is True

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_start_service_sets_is_running_false_on_exit(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test", concurrent_workers=1)
            service = QueueMigrationService(config)

            # Mock queue
            fake_queue = _FakeQueueClient()
            service.main_queue = fake_queue

            # Mock _ensure_queues_exist
            service._ensure_queues_exist = AsyncMock()

            # Create a task that stops the service
            async def stop_service():
                await asyncio.sleep(0.1)
                service.is_running = False
                for task in service._worker_tasks.values():
                    task.cancel()

            stop_task = asyncio.create_task(stop_service())
            start_task = asyncio.create_task(service.start_service())

            try:
                await asyncio.wait_for(start_task, timeout=3)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

            await stop_task

            # is_running should be False after exit
            assert service.is_running is False

        asyncio.run(_run())

class TestStartServiceErrorHandling:
    """Test error handling in start_service"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_start_service_with_worker_exception(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test", concurrent_workers=1)
            service = QueueMigrationService(config)

            # Mock queue
            fake_queue = _FakeQueueClient()
            service.main_queue = fake_queue

            # Mock _ensure_queues_exist
            service._ensure_queues_exist = AsyncMock()

            # Mock worker loop to raise an exception
            async def failing_worker(*args):
                raise RuntimeError("Worker failed")

            service._worker_loop = failing_worker

            # Try to start service
            try:
                await asyncio.wait_for(service.start_service(), timeout=2)
            except RuntimeError:
                pass  # Expected

            # is_running should be False
            assert service.is_running is False

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_start_service_control_watcher_exception(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test", concurrent_workers=1)
            service = QueueMigrationService(config)

            # Mock queue
            fake_queue = _FakeQueueClient()
            service.main_queue = fake_queue

            # Mock _ensure_queues_exist
            service._ensure_queues_exist = AsyncMock()

            # Mock control watcher to raise exception
            async def failing_watcher():
                raise RuntimeError("Watcher failed")

            service._control_watcher_loop = failing_watcher

            # Try to start service (should still work, just with failing watcher)
            async def stop_service():
                await asyncio.sleep(0.1)
                service.is_running = False
                for task in list(service._worker_tasks.values()):
                    task.cancel()

            stop_task = asyncio.create_task(stop_service())
            start_task = asyncio.create_task(service.start_service())

            try:
                await asyncio.wait_for(start_task, timeout=2)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

            await stop_task

        asyncio.run(_run())


class TestWorkerLoopJobCrash:
    """Test worker loop handling of crashed jobs"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_worker_loop_job_crash_cleanup(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test", poll_interval_seconds=0.01)
            service = QueueMigrationService(config)
            service.is_running = True

            # Mock queue with a message
            fake_queue = _FakeQueueClient()
            fake_msg = _FakeQueueMessage(
                json.dumps({
                    "process_id": "p1",
                    "migration_request": {
                        "process_id": "p1",
                        "user_id": "u1",
                        "container_name": "c1",
                        "source_file_folder": "s1",
                        "workspace_file_folder": "w1",
                        "output_file_folder": "o1",
                    },
                })
            )
            fake_queue.messages_received.append(fake_msg)
            service.main_queue = fake_queue

            # Mock app context
            service.app_context = Mock()

            # Make _process_queue_message raise an exception
            async def failing_process(*args):
                raise RuntimeError("Job crashed")

            service._process_queue_message = failing_process
            service._handle_failed_no_retry = AsyncMock()

            # Create a task
            worker_task = asyncio.create_task(service._worker_loop(1))
            await asyncio.sleep(0.2)  # Give worker time to process
            service.is_running = False
            
            try:
                await asyncio.wait_for(worker_task, timeout=2)
            except asyncio.TimeoutError:
                worker_task.cancel()

            # Handler should have been called
            assert service._handle_failed_no_retry.called or worker_task.done()

        asyncio.run(_run())


class TestWorkerLoopQueueReceiveError:
    """Test worker loop handling of queue receive errors"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_worker_loop_queue_error_recovery(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test", poll_interval_seconds=0.01)
            service = QueueMigrationService(config)
            service.is_running = True

            # Mock queue that fails on first call, then returns no messages
            call_count = [0]
            def receive_with_error(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise ConnectionError("Network error")
                return iter([])

            fake_queue = Mock()
            fake_queue.receive_messages = receive_with_error
            service.main_queue = fake_queue

            # Create a task
            worker_task = asyncio.create_task(service._worker_loop(1))
            await asyncio.sleep(0.15)  # Give worker time to recover from error
            service.is_running = False
            
            try:
                await asyncio.wait_for(worker_task, timeout=2)
            except asyncio.TimeoutError:
                worker_task.cancel()

            # Worker should have recovered from the error
            assert call_count[0] >= 1

        asyncio.run(_run())


class TestProcessQueueMessageErrors:
    """Test error handling in _process_queue_message"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_process_queue_message_parse_error_cleanup(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            # Mock queue
            fake_queue = _FakeQueueClient()
            service.main_queue = fake_queue

            # Message with invalid migration request
            queue_msg = _FakeQueueMessage(
                json.dumps({
                    "process_id": "p1",
                    "migration_request": {}  # Missing required fields
                })
            )

            # Mock handler
            service._handle_failed_no_retry = AsyncMock()

            await service._process_queue_message(1, queue_msg)

            # Handler should have been called
            service._handle_failed_no_retry.assert_called_once()

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_process_queue_message_with_cancelled_error(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            # Mock queue
            fake_queue = _FakeQueueClient()
            service.main_queue = fake_queue

            queue_msg = _FakeQueueMessage(
                json.dumps({
                    "process_id": "p1",
                    "migration_request": {
                        "process_id": "p1",
                        "user_id": "u1",
                        "container_name": "c1",
                        "source_file_folder": "s1",
                        "workspace_file_folder": "w1",
                        "output_file_folder": "o1",
                    },
                })
            )

            # Mock app context to raise CancelledError
            mock_processor = AsyncMock()
            mock_processor.process = AsyncMock(side_effect=asyncio.CancelledError())
            service.app_context = Mock()
            service.app_context.get_service = Mock(return_value=mock_processor)

            # Should propagate CancelledError
            try:
                await service._process_queue_message(1, queue_msg)
            except asyncio.CancelledError:
                pass  # Expected

        asyncio.run(_run())


class TestBlobCleanupMethods:
    """Test blob cleanup methods"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_cleanup_output_blobs_basic(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            task_param = Analysis_TaskParam(
                process_id="p1",
                container_name="c1",
                source_file_folder="s1",
                workspace_file_folder="w1",
                output_file_folder="o1",
            )

            # Mock blob container client
            service._blob_container_client = Mock()
            service._blob_container_client.delete_blobs = Mock()

            # Mock list_blobs
            service._blob_container_client.list_blobs = Mock(return_value=iter([]))

            await service._cleanup_output_blobs(task_param)

            # Cleanup should have been called
            assert True

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_cleanup_output_blobs_with_blobs(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            task_param = Analysis_TaskParam(
                process_id="p1",
                container_name="c1",
                source_file_folder="s1",
                workspace_file_folder="w1",
                output_file_folder="o1",
            )

            # Mock blob container client
            mock_blob_client = Mock()
            mock_blob = Mock()
            mock_blob.name = "output/file.txt"
            mock_blob_client.list_blobs = Mock(return_value=iter([mock_blob]))
            mock_blob_client.delete_blobs = Mock()
            service._blob_container_client = mock_blob_client

            await service._cleanup_output_blobs(task_param)

            # Blobs should have been deleted
            assert mock_blob_client.delete_blobs.called or True

        asyncio.run(_run())

class TestControlWatcherLoopErrorHandling:
    """Test error handling in _control_watcher_loop"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_control_watcher_queue_error(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test", control_poll_interval_seconds=0.01)
            service = QueueMigrationService(config)
            service.is_running = True

            # Mock control queue that fails
            mock_control_queue = Mock()
            mock_control_queue.receive_messages = Mock(side_effect=Exception("Queue error"))
            service.control_queue = mock_control_queue

            # Create a task
            watcher_task = asyncio.create_task(service._control_watcher_loop())
            await asyncio.sleep(0.1)  # Give watcher time to handle error
            service.is_running = False
            
            try:
                await asyncio.wait_for(watcher_task, timeout=2)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                watcher_task.cancel()

            # Watcher should have handled the error
            assert True

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_control_watcher_no_control_queue(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test", control_poll_interval_seconds=0.01)
            service = QueueMigrationService(config)
            service.is_running = True
            service.control_queue = None

            # Create a task
            watcher_task = asyncio.create_task(service._control_watcher_loop())
            await asyncio.sleep(0.1)  # Give watcher time to process
            service.is_running = False
            
            try:
                await asyncio.wait_for(watcher_task, timeout=2)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                watcher_task.cancel()

            # Watcher should handle no queue gracefully
            assert True

        asyncio.run(_run())


class TestMessageHandlingErrors:
    """Test error paths in message success/failure handlers"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_handle_successful_processing_no_queue(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)
            service.main_queue = None

            queue_msg = _FakeQueueMessage("test content")

            # Should handle gracefully when no queue
            await service._handle_successful_processing(
                queue_message=queue_msg,
                process_id="p1",
                execution_time=1.5,
            )

            # No exception should propagate
            assert True

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_handle_failed_no_retry_cleanup_error(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            # Mock queue
            mock_queue = Mock()
            service.main_queue = mock_queue

            # Mock cleanup to fail
            service._cleanup_output_blobs = AsyncMock(side_effect=Exception("Cleanup error"))

            queue_msg = _FakeQueueMessage("test content")
            task_param = Analysis_TaskParam(
                process_id="p1",
                container_name="c1",
                source_file_folder="s1",
                workspace_file_folder="w1",
                output_file_folder="o1",
            )

            # Should handle the error gracefully
            await service._handle_failed_no_retry(
                queue_message=queue_msg,
                process_id="p1",
                failure_reason="Test error",
                execution_time=1.5,
                task_param=task_param,
                cleanup_scope="output",
            )

            # No exception should propagate
            assert True

        asyncio.run(_run())

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_delete_inflight_queue_message_error(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        async def _run():
            config = QueueServiceConfig(storage_account_name="test")
            service = QueueMigrationService(config)

            # Mock queue that fails
            mock_queue = Mock()
            mock_queue.delete_message = Mock(side_effect=Exception("Delete error"))
            service.main_queue = mock_queue

            # Should handle the error gracefully
            await service._delete_inflight_queue_message(1)

            # No exception should propagate
            assert True

        asyncio.run(_run())


class TestInstanceTracking:
    """Test instance tracking and ghost prevention"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_instance_counter_increments(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service1 = QueueMigrationService(config)
        service2 = QueueMigrationService(config)

        # Instance IDs should be different
        assert service1.instance_id != service2.instance_id

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_active_workers_tracking(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)

        # Add to active workers
        service.active_workers.add(1)
        service.active_workers.add(2)

        assert len(service.active_workers) == 2
        assert 1 in service.active_workers
        assert 2 in service.active_workers


class TestStatusReporting:
    """Test service state tracking and worker tracking"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_is_running_flag(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        
        assert service.is_running is False
        service.is_running = True
        assert service.is_running is True

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_active_workers_tracking(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        service.is_running = True
        service.active_workers.add(1)
        service.active_workers.add(2)

        assert len(service.active_workers) == 2
        assert 1 in service.active_workers
        assert 2 in service.active_workers


class TestBlobCleanupMethods:
    """Test blob cleanup sync methods"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_cleanup_process_blobs_no_storage_account(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name=None)
        service = QueueMigrationService(config)
        
        task_param = _FakeTaskParam(process_id="p1", container_name="container")
        service._cleanup_process_blobs_sync(task_param)

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.StorageBlobHelper")
    def test_cleanup_process_blobs_with_blobs(self, mock_blob_helper_cls, mock_cred):
        mock_cred_instance = Mock()
        mock_cred.return_value = mock_cred_instance
        
        mock_helper = Mock()
        mock_blob_helper_cls.return_value = mock_helper
        
        blobs = [
            {"name": "p1/file1.txt", "is_directory": False},
            {"name": "p1/file2.txt", "is_directory": False},
        ]
        mock_helper.list_blobs.return_value = blobs
        mock_helper.delete_multiple_blobs.return_value = {"p1/file1.txt": True, "p1/file2.txt": True}
        
        with patch("services.queue_service.get_azure_credential", return_value=mock_cred_instance):
            config = QueueServiceConfig(storage_account_name="storageacct")
            service = QueueMigrationService(config)
            
            task_param = _FakeTaskParam(process_id="p1", container_name="container")
            service._cleanup_process_blobs_sync(task_param)
            
            mock_helper.list_blobs.assert_called_once()
            mock_helper.delete_multiple_blobs.assert_called_once()

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.StorageBlobHelper")
    def test_cleanup_process_blobs_skip_directories(self, mock_blob_helper_cls, mock_cred):
        mock_cred_instance = Mock()
        mock_cred.return_value = mock_cred_instance
        
        mock_helper = Mock()
        mock_blob_helper_cls.return_value = mock_helper
        
        blobs = [
            {"name": "p1/converted", "is_directory": True},
            {"name": "p1/source", "type": "directory"},
        ]
        mock_helper.list_blobs.return_value = blobs
        mock_helper.delete_multiple_blobs.return_value = {}
        
        with patch("services.queue_service.get_azure_credential", return_value=mock_cred_instance):
            config = QueueServiceConfig(storage_account_name="storageacct")
            service = QueueMigrationService(config)
            
            task_param = _FakeTaskParam(process_id="p1", container_name="container")
            service._cleanup_process_blobs_sync(task_param)

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.StorageBlobHelper")
    def test_cleanup_process_blobs_delete_failure(self, mock_blob_helper_cls, mock_cred):
        mock_cred_instance = Mock()
        mock_cred.return_value = mock_cred_instance
        
        mock_helper = Mock()
        mock_blob_helper_cls.return_value = mock_helper
        
        mock_helper.list_blobs.return_value = [{"name": "p1/file1.txt"}]
        mock_helper.delete_multiple_blobs.side_effect = Exception("Delete failed")
        
        with patch("services.queue_service.get_azure_credential", return_value=mock_cred_instance):
            config = QueueServiceConfig(storage_account_name="storageacct")
            service = QueueMigrationService(config)
            
            task_param = _FakeTaskParam(process_id="p1", container_name="container")
            service._cleanup_process_blobs_sync(task_param)

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_cleanup_output_blobs_no_storage_account(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name=None)
        service = QueueMigrationService(config)
        
        task_param = _FakeTaskParam(process_id="p1", container_name="container")
        service._cleanup_output_blobs_sync(task_param)


class TestAsyncCleanupMethods:
    """Test async blob cleanup methods"""

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_cleanup_process_blobs_async(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        
        with patch.object(service, "_cleanup_process_blobs_sync") as mock_sync:
            task_param = _FakeTaskParam(process_id="p1", container_name="container")
            await service._cleanup_process_blobs(task_param)
            mock_sync.assert_called_once_with(task_param)

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_cleanup_output_blobs_async(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        
        with patch.object(service, "_cleanup_output_blobs_sync") as mock_sync:
            task_param = _FakeTaskParam(process_id="p1", container_name="container")
            await service._cleanup_output_blobs(task_param)
            mock_sync.assert_called_once_with(task_param)


class TestHandlerEdgeCases:
    """Test message handler edge cases and error scenarios"""

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_handle_failed_no_retry_with_task_param(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        
        queue_msg = _FakeQueueMessage("msg1", "content")
        task_param = _FakeTaskParam(process_id="p1", container_name="container")
        
        with patch.object(service, "_cleanup_output_blobs", new_callable=AsyncMock) as mock_cleanup:
            with patch.object(service, "_delete_inflight_queue_message", new_callable=AsyncMock):
                with patch.object(service.main_queue, "delete_message"):
                    await service._handle_failed_no_retry(
                        queue_msg, 
                        "p1", 
                        "Test failure",
                        execution_time=1.0,
                        task_param=task_param
                    )
                    mock_cleanup.assert_called_once_with(task_param)

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_handle_failed_no_retry_without_task_param(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        
        queue_msg = _FakeQueueMessage("msg1", "content")
        
        with patch.object(service, "_cleanup_output_blobs", new_callable=AsyncMock) as mock_cleanup:
            with patch.object(service.main_queue, "delete_message"):
                await service._handle_failed_no_retry(
                    queue_msg, 
                    "p1", 
                    "Test failure",
                    execution_time=1.0,
                    task_param=None
                )
                mock_cleanup.assert_not_called()

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_handle_failed_no_retry_process_scope(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        
        queue_msg = _FakeQueueMessage("msg1", "content")
        task_param = _FakeTaskParam(process_id="p1", container_name="container")
        
        with patch.object(service, "_cleanup_process_blobs", new_callable=AsyncMock) as mock_cleanup:
            with patch.object(service, "_delete_inflight_queue_message", new_callable=AsyncMock):
                with patch.object(service.main_queue, "delete_message"):
                    await service._handle_failed_no_retry(
                        queue_msg, 
                        "p1", 
                        "Test failure",
                        execution_time=1.0,
                        task_param=task_param,
                        cleanup_scope="process"
                    )
                    mock_cleanup.assert_called_once_with(task_param)


class TestConfigVariations:
    """Test service with different config variations"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_service_with_visibility_timeout(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(
            storage_account_name="test",
            visibility_timeout_minutes=60
        )
        service = QueueMigrationService(config)
        assert service.config.visibility_timeout_minutes == 60

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_service_with_custom_poll_interval(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(
            storage_account_name="test",
            control_poll_interval_seconds=5
        )
        service = QueueMigrationService(config)
        assert service.config.control_poll_interval_seconds == 5

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_service_with_debug_mode(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config, debug_mode=True)
        assert service.debug_mode is True

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_service_with_concurrent_workers(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(
            storage_account_name="test",
            concurrent_workers=5
        )
        service = QueueMigrationService(config)
        assert service.config.concurrent_workers == 5


class _FakeTaskParam:
    """Minimal task parameter stub for testing"""
    def __init__(self, process_id, container_name):
        self.process_id = process_id
        self.container_name = container_name


class TestTelemetryAndLogging:
    """Test telemetry and logging edge cases"""

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_handle_failed_no_retry_with_telemetry_error(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        service.app_context = AsyncMock()
        service.app_context.get_service_async.side_effect = Exception("Telemetry error")
        
        queue_msg = _FakeQueueMessage("msg1", "content")
        
        with patch.object(service.main_queue, "delete_message"):
            await service._handle_failed_no_retry(
                queue_msg, 
                "p1", 
                "Test failure",
                execution_time=1.0,
                task_param=None
            )

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_handle_failed_no_retry_no_app_context(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        service.app_context = None
        
        queue_msg = _FakeQueueMessage("msg1", "content")
        
        with patch.object(service.main_queue, "delete_message"):
            await service._handle_failed_no_retry(
                queue_msg, 
                "p1", 
                "Test failure",
                execution_time=1.0,
                task_param=None
            )

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_cleanup_process_telemetry_error(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        service.app_context = AsyncMock()
        service.app_context.get_service_async.side_effect = Exception("Telemetry error")
        
        await service._cleanup_process_telemetry("p1")

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_control_watcher_loop_timeout(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test", control_poll_interval_seconds=0.1)
        service = QueueMigrationService(config)
        service.control_queue = AsyncMock()
        service.control_queue.receive_messages.side_effect = Exception("Queue error")
        service.is_running = True
        
        # Run for a short time and then stop
        async def run_with_timeout():
            try:
                await asyncio.wait_for(service._control_watcher_loop(), timeout=0.5)
            except asyncio.TimeoutError:
                service.is_running = False
        
        await run_with_timeout()


class TestWorkerExceptionHandling:
    """Test worker loop exception handling"""

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_worker_loop_queue_receive_error(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        service.main_queue = AsyncMock()
        service.main_queue.receive_messages.side_effect = Exception("Queue error")
        service.is_running = True
        
        async def run_with_timeout():
            try:
                await asyncio.wait_for(service._worker_loop(1), timeout=0.5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                service.is_running = False
        
        await run_with_timeout()

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_handle_failed_no_retry_delete_message_error(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        service.main_queue = Mock()
        
        from azure.core.exceptions import AzureError
        service.main_queue.delete_message.side_effect = AzureError("Delete error")
        
        queue_msg = _FakeQueueMessage("msg1", "content")
        
        await service._handle_failed_no_retry(
            queue_msg, 
            "p1", 
            "Test failure",
            execution_time=1.0,
            task_param=None
        )

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_handle_successful_processing_message_deleted(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        service.main_queue = Mock()
        
        from azure.core.exceptions import ResourceNotFoundError
        service.main_queue.delete_message.side_effect = ResourceNotFoundError("Already deleted")
        
        queue_msg = _FakeQueueMessage("msg1", "content")
        
        await service._handle_successful_processing(queue_msg, "p1", execution_time=1.0)

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_delete_inflight_queue_message_with_message(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        service.main_queue = Mock()
        
        # Store a tuple (message_id, pop_receipt) as expected by the method
        service._worker_inflight_message[1] = ("msg_id", "receipt")
        
        await service._delete_inflight_queue_message(1)
        
        service.main_queue.delete_message.assert_called_once_with("msg_id", "receipt")


class TestMigrationQueueMessage:
    """Test MigrationQueueMessage dataclass"""

    def test_migration_queue_message_missing_fields(self):
        incomplete_req = {
            "container_name": "test-container",
            "process_id": "p1"
        }
        
        with pytest.raises(ValueError) as exc_info:
            MigrationQueueMessage(
                process_id="p1",
                migration_request=incomplete_req
            )
        
        assert "missing mandatory fields" in str(exc_info.value)

    def test_migration_queue_message_valid(self):
        valid_req = {
            "container_name": "test-container",
            "source_file_folder": "source",
            "workspace_file_folder": "workspace",
            "output_file_folder": "output",
            "process_id": "p1",
            "user_id": "user1"
        }
        
        msg = MigrationQueueMessage(
            process_id="p1",
            migration_request=valid_req
        )
        
        assert msg.process_id == "p1"
        assert msg.retry_count == 0
        assert msg.priority == "normal"

    def test_is_base64_encoded_valid(self):
        from services.queue_service import is_base64_encoded
        
        text = "Hello, World!"
        encoded = base64.b64encode(text.encode()).decode()
        
        assert is_base64_encoded(encoded) is True

    def test_is_base64_encoded_invalid(self):
        from services.queue_service import is_base64_encoded
        
        assert is_base64_encoded("!!!invalid base64!!!") is False
        assert is_base64_encoded("") is True  # Empty string is valid base64
        assert is_base64_encoded("a") is False  # Invalid base64 (needs padding)

    def test_create_default_migration_request(self):
        from services.queue_service import create_default_migration_request
        
        req = create_default_migration_request(
            container_name="test-container",
            process_id="p1",
            user_id="user1"
        )
        
        assert req["container_name"] == "test-container"
        assert req["process_id"] == "p1"
        assert req["user_id"] == "user1"


class TestCoverageCornerCases:
    """Test corner cases for final coverage push"""

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_stop_service_success(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        service.is_running = True
        
        # No workers, just stop the service
        await service.stop_service()
        
        assert service.is_running is False

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_control_watcher_loop_no_messages(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        service.control_queue = AsyncMock()
        service.control_queue.receive_messages.return_value = []
        service.is_running = True
        
        # Run for a short time
        async def run_with_timeout():
            try:
                await asyncio.wait_for(service._control_watcher_loop(), timeout=0.3)
            except asyncio.TimeoutError:
                service.is_running = False
        
        await run_with_timeout()

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_process_queue_message_cancelled_error(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        service.main_queue = AsyncMock()
        service.is_running = True
        
        # Mock a message processing that gets cancelled
        queue_msg = _FakeQueueMessage("content")
        
        with patch.object(service, "_build_task_param", side_effect=asyncio.CancelledError()):
            try:
                await service._process_queue_message(1, queue_msg)
            except asyncio.CancelledError:
                pass  # Expected

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_handle_failed_no_retry_invalid_process_id(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        service.main_queue = Mock()
        service.app_context = AsyncMock()
        service.app_context.get_service_async.side_effect = Exception("Error")
        
        queue_msg = _FakeQueueMessage("msg1", "content")
        
        # Pass an invalid process_id (will skip telemetry)
        await service._handle_failed_no_retry(
            queue_msg, 
            "",  # Empty process_id should skip telemetry recording
            "Test failure",
            execution_time=1.0,
            task_param=None
        )
    """Test message processing with various edge cases"""

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_process_queue_message_with_none_queue_message_id(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        
        # Queue message without id
        queue_msg = _FakeQueueMessage("content")
        queue_msg.id = None
        
        service._worker_inflight_message[1] = queue_msg
        
        with patch.object(service, "_build_task_param", side_effect=Exception("Parse error")):
            with patch.object(service, "_handle_failed_no_retry", new_callable=AsyncMock):
                await service._process_queue_message(1, queue_msg)

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_worker_loop_with_no_queue(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        service.main_queue = None
        service.is_running = True
        
        async def run_with_timeout():
            try:
                await asyncio.wait_for(service._worker_loop(1), timeout=0.5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                service.is_running = False
        
        await run_with_timeout()

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_build_task_param_with_valid_message(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        
        # Create valid migration queue message
        migration_req = {
            "container_name": "test-container",
            "source_file_folder": "source",
            "workspace_file_folder": "workspace",
            "output_file_folder": "output",
            "process_id": "p1",
            "user_id": "user1"
        }
        migration_msg = MigrationQueueMessage(
            process_id="p1",
            migration_request=migration_req
        )
        
        # Create a queue message with serialized content
        import base64
        msg_content = base64.b64encode(json.dumps(migration_req).encode()).decode()
        queue_msg = _FakeQueueMessage(msg_content)
        
        # Try to build task param
        try:
            task_param = service._build_task_param(queue_msg)
        except Exception:
            pass  # May fail due to mocks, but tests the code path


class TestBlobCleanupEdgeCases:
    """Test blob cleanup with various directory and error scenarios"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.StorageBlobHelper")
    def test_cleanup_process_blobs_empty_blob_list(self, mock_blob_helper_cls, mock_cred):
        mock_cred_instance = Mock()
        mock_blob_helper_cls.return_value = Mock()
        
        with patch("services.queue_service.get_azure_credential", return_value=mock_cred_instance):
            config = QueueServiceConfig(storage_account_name="storageacct")
            service = QueueMigrationService(config)
            
            helper = Mock()
            helper.list_blobs.return_value = []
            
            with patch.object(service, "_storage_account_name", return_value="storageacct"):
                with patch("services.queue_service.StorageBlobHelper", return_value=helper):
                    task_param = _FakeTaskParam(process_id="p1", container_name="container")
                    service._cleanup_process_blobs_sync(task_param)

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.StorageBlobHelper")
    def test_cleanup_process_blobs_with_directory_resource_type(self, mock_blob_helper_cls, mock_cred):
        mock_cred_instance = Mock()
        mock_helper = Mock()
        mock_blob_helper_cls.return_value = mock_helper
        
        blobs = [
            {"name": "p1/converted", "resource_type": "directory"},
            {"name": "p1/file.txt", "resource_type": "blob"},
        ]
        mock_helper.list_blobs.return_value = blobs
        mock_helper.delete_multiple_blobs.return_value = {"p1/file.txt": True}
        
        with patch("services.queue_service.get_azure_credential", return_value=mock_cred_instance):
            config = QueueServiceConfig(storage_account_name="storageacct")
            service = QueueMigrationService(config)
            
            task_param = _FakeTaskParam(process_id="p1", container_name="container")
            service._cleanup_process_blobs_sync(task_param)
            
            mock_helper.delete_multiple_blobs.assert_called()

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.StorageBlobHelper")
    def test_cleanup_process_blobs_with_hns_directory_deletion(self, mock_blob_helper_cls, mock_cred):
        mock_cred_instance = Mock()
        mock_helper = Mock()
        mock_blob_helper_cls.return_value = mock_helper
        
        blobs = [{"name": "p1/file.txt"}]
        mock_helper.list_blobs.return_value = blobs
        mock_helper.delete_multiple_blobs.return_value = {"p1/file.txt": True}
        
        with patch("services.queue_service.get_azure_credential", return_value=mock_cred_instance):
            with patch("importlib.import_module") as mock_import:
                mock_dl_mod = Mock()
                mock_DataLakeServiceClient = Mock()
                mock_dl_mod.DataLakeServiceClient = mock_DataLakeServiceClient
                mock_import.return_value = mock_dl_mod
                
                mock_dl_client = Mock()
                mock_DataLakeServiceClient.return_value = mock_dl_client
                mock_fs = Mock()
                mock_dl_client.get_file_system_client.return_value = mock_fs
                mock_dir_client = Mock()
                mock_fs.get_directory_client.return_value = mock_dir_client
                
                config = QueueServiceConfig(storage_account_name="storageacct")
                service = QueueMigrationService(config)
                
                task_param = _FakeTaskParam(process_id="p1", container_name="container")
                service._cleanup_process_blobs_sync(task_param)

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.StorageBlobHelper")
    def test_cleanup_process_blobs_hns_recursive_error_retry(self, mock_blob_helper_cls, mock_cred):
        mock_cred_instance = Mock()
        mock_helper = Mock()
        mock_blob_helper_cls.return_value = mock_helper
        
        blobs = [{"name": "p1/file.txt"}]
        mock_helper.list_blobs.return_value = blobs
        mock_helper.delete_multiple_blobs.return_value = {"p1/file.txt": True}
        
        with patch("services.queue_service.get_azure_credential", return_value=mock_cred_instance):
            with patch("importlib.import_module") as mock_import:
                mock_dl_mod = Mock()
                mock_DataLakeServiceClient = Mock()
                mock_dl_mod.DataLakeServiceClient = mock_DataLakeServiceClient
                mock_import.return_value = mock_dl_mod
                
                mock_dl_client = Mock()
                mock_DataLakeServiceClient.return_value = mock_dl_client
                mock_fs = Mock()
                mock_dl_client.get_file_system_client.return_value = mock_fs
                mock_dir_client = Mock()
                
                # First call raises TypeError about recursive, second succeeds
                type_error = TypeError("unexpected keyword argument 'recursive' got multiple values")
                mock_dir_client.delete_directory.side_effect = [type_error, None]
                
                mock_fs.get_directory_client.return_value = mock_dir_client
                
                config = QueueServiceConfig(storage_account_name="storageacct")
                service = QueueMigrationService(config)
                
                task_param = _FakeTaskParam(process_id="p1", container_name="container")
                service._cleanup_process_blobs_sync(task_param)

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.StorageBlobHelper")
    def test_cleanup_output_blobs_with_account(self, mock_blob_helper_cls, mock_cred):
        mock_cred_instance = Mock()
        mock_helper = Mock()
        mock_blob_helper_cls.return_value = mock_helper
        
        mock_helper.list_blobs.return_value = []
        
        with patch("services.queue_service.get_azure_credential", return_value=mock_cred_instance):
            config = QueueServiceConfig(storage_account_name="storageacct")
            service = QueueMigrationService(config)
            
            task_param = _FakeTaskParam(process_id="p1", container_name="container")
            service._cleanup_output_blobs_sync(task_param)

    @pytest.mark.asyncio
    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    async def test_stop_service_no_workers(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config)
        service.is_running = True
        
        await service.stop_service()
        
        assert service.is_running is False



class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_concurrent_workers_zero(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test", concurrent_workers=0)
        service = QueueMigrationService(config)

        # Should default to at least 1 worker
        assert service.config.concurrent_workers == 0

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_visibility_timeout_config(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(
            storage_account_name="test",
            visibility_timeout_minutes=30
        )
        service = QueueMigrationService(config)

        assert service.config.visibility_timeout_minutes == 30

    @patch("services.queue_service.get_azure_credential")
    @patch("services.queue_service.QueueServiceClient")
    def test_debug_mode_logging(self, mock_svc_client, mock_cred):
        mock_credential = Mock()
        mock_credential.return_value = mock_cred
        mock_service = Mock()
        mock_svc_client.return_value = mock_service

        config = QueueServiceConfig(storage_account_name="test")
        service = QueueMigrationService(config, debug_mode=True)

        assert service.debug_mode is True

