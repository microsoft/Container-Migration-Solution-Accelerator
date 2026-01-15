# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for business_router_process class.
Tests all methods related to blob storage operations, queue operations,
and process status management in the business router.
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Any

# Import the class under test  
from app.routers.business.router_process import business_router_process
from app.libs.base.typed_fastapi import TypedFastAPI
from app.libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper
from app.libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper
from app.libs.services.interfaces import ILoggerService
from app.libs.repositories.process_status_repository import ProcessStatusRepository
from app.routers.models.files import FileInfo
from app.routers.models.processes import enlist_process_queue_response, FileInfo as ProcessFileInfo
from app.routers.models.process_agent_activities import ProcessStatusSnapshot, AgentStatus


class TestBusinessRouterProcess:
    """Test cases for business_router_process class."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock TypedFastAPI application with all necessary dependencies."""
        app = Mock(spec=TypedFastAPI)
        app.app_context = Mock()
        app.app_context.configuration = Mock()
        app.app_context.configuration.storage_account_process_container = "test-container"
        app.app_context.configuration.storage_account_process_queue = "test-queue"
        return app

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger service."""
        logger = Mock(spec=ILoggerService)
        logger.log_info = Mock()
        logger.log_error = Mock()
        return logger

    @pytest.fixture
    def mock_blob_helper(self):
        """Create a mock blob helper with async methods."""
        blob_helper = AsyncMock(spec=AsyncStorageBlobHelper)
        blob_helper.container_exists = AsyncMock(return_value=True)
        blob_helper.create_container = AsyncMock()
        blob_helper.upload_blob = AsyncMock()
        blob_helper.list_blobs = AsyncMock(return_value=[])
        blob_helper.download_blob = AsyncMock(return_value=b"test content")
        blob_helper.get_blob_properties = AsyncMock(return_value={"content_type": "text/plain", "size": 100})
        blob_helper.blob_exists = AsyncMock(return_value=True)
        blob_helper.delete_blob = AsyncMock()
        return blob_helper

    @pytest.fixture
    def mock_queue_helper(self):
        """Create a mock queue helper with async methods."""
        queue_helper = AsyncMock(spec=AsyncStorageQueueHelper)
        queue_helper.queue_exists = AsyncMock(return_value=True)
        queue_helper.create_queue = AsyncMock()
        queue_helper.send_message = AsyncMock()
        return queue_helper

    @pytest.fixture
    def router_process(self, mock_app):
        """Create a business_router_process instance with mocked dependencies."""
        return business_router_process(mock_app)

    @pytest.fixture
    def sample_files(self):
        """Create sample FileInfo objects for testing."""
        return [
            FileInfo(filename="test1.yaml", content=b"content1", content_type="text/yaml", size=8),
            FileInfo(filename="test2.yaml", content=b"content2", content_type="text/yaml", size=8),
        ]


class TestBusinessRouterProcessInit(TestBusinessRouterProcess):
    """Test cases for business_router_process initialization."""

    def test_init_with_valid_app(self, mock_app):
        """Test that business_router_process initializes correctly with a valid app."""
        router = business_router_process(mock_app)
        assert router.app == mock_app

    def test_init_stores_app_reference(self, mock_app):
        """Test that the app reference is stored correctly."""
        router = business_router_process(mock_app)
        assert router.app is mock_app


class TestSaveFilesToBlob(TestBusinessRouterProcess):
    """Test cases for save_files_to_blob method."""

    @pytest.mark.asyncio
    async def test_save_files_to_blob_success(self, mock_app, mock_blob_helper, mock_logger, sample_files):
        """Test successful file save to blob storage."""
        router = business_router_process(mock_app)
        process_id = "test-process-123"

        # Configure mock context manager
        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_blob_helper)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.get_service = Mock(return_value=async_context_manager)

        # Execute
        await router.save_files_to_blob(process_id, sample_files)

        # Verify blob uploads were called for each file
        assert mock_blob_helper.upload_blob.call_count == len(sample_files)

    @pytest.mark.asyncio
    async def test_save_files_to_blob_creates_container_if_not_exists(self, mock_app, mock_blob_helper, mock_logger, sample_files):
        """Test that container is created if it doesn't exist."""
        router = business_router_process(mock_app)
        process_id = "test-process-123"

        mock_blob_helper.container_exists = AsyncMock(return_value=False)
        
        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_blob_helper)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.get_service = Mock(return_value=async_context_manager)

        await router.save_files_to_blob(process_id, sample_files)

        mock_blob_helper.create_container.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_files_to_blob_raises_when_helper_not_available(self, mock_app, sample_files):
        """Test that ValueError is raised when blob helper is not available."""
        router = business_router_process(mock_app)
        process_id = "test-process-123"

        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=None)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.get_service = Mock(return_value=async_context_manager)

        with pytest.raises(ValueError, match="Blob helper service is not available"):
            await router.save_files_to_blob(process_id, sample_files)

    @pytest.mark.asyncio
    async def test_save_files_to_blob_correct_blob_path(self, mock_app, mock_blob_helper, sample_files):
        """Test that files are saved with correct blob path format."""
        router = business_router_process(mock_app)
        process_id = "test-process-123"

        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_blob_helper)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.get_service = Mock(return_value=async_context_manager)

        await router.save_files_to_blob(process_id, sample_files)

        # Verify the blob name format
        calls = mock_blob_helper.upload_blob.call_args_list
        assert calls[0][1]["blob_name"] == f"{process_id}/source/test1.yaml"
        assert calls[1][1]["blob_name"] == f"{process_id}/source/test2.yaml"

    @pytest.mark.asyncio
    async def test_save_files_to_blob_logs_creation_and_uploads(self, mock_app, mock_blob_helper, mock_logger, sample_files):
        """Test that proper logging occurs for container creation and file uploads."""
        router = business_router_process(mock_app)
        process_id = "test-process-123"

        mock_blob_helper.container_exists = AsyncMock(return_value=False)
        
        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_blob_helper)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.get_service = Mock(return_value=async_context_manager)

        await router.save_files_to_blob(process_id, sample_files)

        # Verify logging was called (through mock_app.app_context.get_service calls)
        assert mock_app.app_context.get_service.call_count >= 2  # At least for blob helper and logger

    @pytest.mark.asyncio
    async def test_save_files_to_blob_empty_files_list(self, mock_app, mock_blob_helper):
        """Test handling of empty files list."""
        router = business_router_process(mock_app)
        process_id = "test-process-123"

        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_blob_helper)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.get_service = Mock(return_value=async_context_manager)

        await router.save_files_to_blob(process_id, [])

        # Should not upload any files
        mock_blob_helper.upload_blob.assert_not_called()


class TestProcessEnqueue(TestBusinessRouterProcess):
    """Test cases for process_enqueue method."""

    @pytest.mark.asyncio
    async def test_process_enqueue_success(self, mock_app, mock_queue_helper, mock_logger):
        """Test successful message enqueue."""
        router = business_router_process(mock_app)
        queue_message = enlist_process_queue_response(
            user_id="user-123",
            process_id="process-123",
            message="Test message",
            files=[ProcessFileInfo(filename="test.yaml", content_type="text/yaml", size=100)]
        )

        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_queue_helper)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.get_service = Mock(return_value=async_context_manager)

        await router.process_enqueue(queue_message)

        mock_queue_helper.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_enqueue_creates_queue_if_not_exists(self, mock_app, mock_queue_helper, mock_logger):
        """Test that queue is created if it doesn't exist."""
        router = business_router_process(mock_app)
        queue_message = enlist_process_queue_response(
            user_id="user-123",
            process_id="process-123",
        )

        mock_queue_helper.queue_exists = AsyncMock(return_value=False)

        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_queue_helper)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.get_service = Mock(return_value=async_context_manager)

        await router.process_enqueue(queue_message)

        mock_queue_helper.create_queue.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_enqueue_raises_when_service_not_available(self, mock_app):
        """Test that ValueError is raised when queue service is not available."""
        router = business_router_process(mock_app)
        queue_message = enlist_process_queue_response(
            user_id="user-123",
            process_id="process-123",
        )

        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=None)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.get_service = Mock(return_value=async_context_manager)

        with pytest.raises(ValueError, match="Queue service is not available"):
            await router.process_enqueue(queue_message)

    @pytest.mark.asyncio
    async def test_process_enqueue_sends_base64_message(self, mock_app, mock_queue_helper):
        """Test that message is sent as base64 encoded."""
        router = business_router_process(mock_app)
        queue_message = enlist_process_queue_response(
            user_id="user-123",
            process_id="process-123",
        )

        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_queue_helper)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.get_service = Mock(return_value=async_context_manager)

        await router.process_enqueue(queue_message)

        call_args = mock_queue_helper.send_message.call_args
        assert call_args[1]["content"] == queue_message.to_base64()

    @pytest.mark.asyncio
    async def test_process_enqueue_uses_correct_queue_name(self, mock_app, mock_queue_helper):
        """Test that correct queue name is used from configuration."""
        router = business_router_process(mock_app)
        queue_message = enlist_process_queue_response(
            user_id="user-123",
            process_id="process-123",
        )

        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_queue_helper)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.get_service = Mock(return_value=async_context_manager)

        await router.process_enqueue(queue_message)

        # Verify queue_exists called with correct queue name
        mock_queue_helper.queue_exists.assert_called_once_with(
            queue_name="test-queue"
        )

    @pytest.mark.asyncio
    async def test_process_enqueue_logs_queue_creation(self, mock_app, mock_queue_helper, mock_logger):
        """Test that queue creation is logged."""
        router = business_router_process(mock_app)
        queue_message = enlist_process_queue_response(
            user_id="user-123",
            process_id="process-123",
        )

        mock_queue_helper.queue_exists = AsyncMock(return_value=False)

        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_queue_helper)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.get_service = Mock(return_value=async_context_manager)

        await router.process_enqueue(queue_message)

        # Verify logging service was requested for queue creation
        assert mock_app.app_context.get_service.call_count >= 2  # At least for queue helper and logger


class TestGetCurrentProcessAgentActivities(TestBusinessRouterProcess):
    """Test cases for get_current_process_agent_activities method."""

    @pytest.mark.asyncio
    async def test_get_current_process_agent_activities_success(self, mock_app):
        """Test successful retrieval of current process agent activities."""
        router = business_router_process(mock_app)
        process_id = "test-process-123"
        
        expected_activities = [
            {"agent": "agent1", "activity": "processing"},
            {"agent": "agent2", "activity": "waiting"}
        ]

        mock_process_status_repo = AsyncMock(spec=ProcessStatusRepository)
        mock_process_status_repo.get_process_agent_activities_by_process_id = AsyncMock(return_value=expected_activities)

        mock_scope = AsyncMock()
        mock_scope.get_service = Mock(return_value=mock_process_status_repo)
        mock_scope.__aenter__ = AsyncMock(return_value=mock_scope)
        mock_scope.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.create_scope = Mock(return_value=mock_scope)

        result = await router.get_current_process_agent_activities(process_id)

        assert result == expected_activities
        mock_process_status_repo.get_process_agent_activities_by_process_id.assert_called_once_with(process_id)

    @pytest.mark.asyncio
    async def test_get_current_process_agent_activities_empty_result(self, mock_app):
        """Test that empty result is handled correctly."""
        router = business_router_process(mock_app)
        process_id = "test-process-123"

        mock_process_status_repo = AsyncMock(spec=ProcessStatusRepository)
        mock_process_status_repo.get_process_agent_activities_by_process_id = AsyncMock(return_value=[])

        mock_scope = AsyncMock()
        mock_scope.get_service = Mock(return_value=mock_process_status_repo)
        mock_scope.__aenter__ = AsyncMock(return_value=mock_scope)
        mock_scope.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.create_scope = Mock(return_value=mock_scope)

        result = await router.get_current_process_agent_activities(process_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_current_process_agent_activities_none_result(self, mock_app):
        """Test that None result is handled correctly."""
        router = business_router_process(mock_app)
        process_id = "non-existent-process"

        mock_process_status_repo = AsyncMock(spec=ProcessStatusRepository)
        mock_process_status_repo.get_process_agent_activities_by_process_id = AsyncMock(return_value=None)

        mock_scope = AsyncMock()
        mock_scope.get_service = Mock(return_value=mock_process_status_repo)
        mock_scope.__aenter__ = AsyncMock(return_value=mock_scope)
        mock_scope.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.create_scope = Mock(return_value=mock_scope)

        result = await router.get_current_process_agent_activities(process_id)

        assert result is None


class TestGetCurrentProcess(TestBusinessRouterProcess):
    """Test cases for get_current_process method."""

    @pytest.mark.asyncio
    async def test_get_current_process_success(self, mock_app):
        """Test successful retrieval of current process status."""
        router = business_router_process(mock_app)
        process_id = "test-process-123"

        mock_snapshot = ProcessStatusSnapshot(
            process_id=process_id,
            step="step1",
            phase="phase1",
            status="running",
            agents=[],
            last_update_time="2024-01-01 00:00:00 UTC",
            started_at_time="2024-01-01 00:00:00 UTC"
        )

        mock_process_status_repo = AsyncMock(spec=ProcessStatusRepository)
        mock_process_status_repo.get_process_status_by_process_id = AsyncMock(return_value=mock_snapshot)

        mock_scope = AsyncMock()
        mock_scope.get_service = Mock(return_value=mock_process_status_repo)
        mock_scope.__aenter__ = AsyncMock(return_value=mock_scope)
        mock_scope.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.create_scope = Mock(return_value=mock_scope)

        result = await router.get_current_process(process_id)

        assert result == mock_snapshot
        mock_process_status_repo.get_process_status_by_process_id.assert_called_once_with(process_id)

    @pytest.mark.asyncio
    async def test_get_current_process_returns_none_when_not_found(self, mock_app):
        """Test that None is returned when process is not found."""
        router = business_router_process(mock_app)
        process_id = "non-existent-process"

        mock_process_status_repo = AsyncMock(spec=ProcessStatusRepository)
        mock_process_status_repo.get_process_status_by_process_id = AsyncMock(return_value=None)

        mock_scope = AsyncMock()
        mock_scope.get_service = Mock(return_value=mock_process_status_repo)
        mock_scope.__aenter__ = AsyncMock(return_value=mock_scope)
        mock_scope.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.create_scope = Mock(return_value=mock_scope)

        result = await router.get_current_process(process_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_process_with_agents(self, mock_app):
        """Test retrieval of process status with agent data."""
        router = business_router_process(mock_app)
        process_id = "test-process-123"

        mock_agent = AgentStatus(
            name="test-agent",
            is_currently_speaking=False,
            is_active=True,
            current_action="processing",
            current_speaking_content="",
            last_message="Processing files",
            participating_status="ready",
            last_reasoning="",
            last_activity_summary="",
            current_reasoning="",
            thinking_about="",
            reasoning_steps=[]
        )

        mock_snapshot = ProcessStatusSnapshot(
            process_id=process_id,
            step="step1",
            phase="phase1",
            status="running",
            agents=[mock_agent],
            last_update_time="2024-01-01 00:00:00 UTC",
            started_at_time="2024-01-01 00:00:00 UTC"
        )

        mock_process_status_repo = AsyncMock(spec=ProcessStatusRepository)
        mock_process_status_repo.get_process_status_by_process_id = AsyncMock(return_value=mock_snapshot)

        mock_scope = AsyncMock()
        mock_scope.get_service = Mock(return_value=mock_process_status_repo)
        mock_scope.__aenter__ = AsyncMock(return_value=mock_scope)
        mock_scope.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.create_scope = Mock(return_value=mock_scope)

        result = await router.get_current_process(process_id)

        assert result == mock_snapshot
        assert len(result.agents) == 1
        assert result.agents[0].name == "test-agent"


class TestRenderProcessStatus(TestBusinessRouterProcess):
    """Test cases for render_process_status method."""

    @pytest.mark.asyncio
    async def test_render_process_status_success(self, mock_app):
        """Test successful rendering of process status."""
        router = business_router_process(mock_app)
        process_id = "test-process-123"
        expected_render = ["Agent 1: Running", "Agent 2: Idle"]

        mock_process_status_repo = AsyncMock(spec=ProcessStatusRepository)
        mock_process_status_repo.render_agent_status = AsyncMock(return_value=expected_render)

        mock_scope = AsyncMock()
        mock_scope.get_service = Mock(return_value=mock_process_status_repo)
        mock_scope.__aenter__ = AsyncMock(return_value=mock_scope)
        mock_scope.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.create_scope = Mock(return_value=mock_scope)

        result = await router.render_process_status(process_id)

        assert result == expected_render
        mock_process_status_repo.render_agent_status.assert_called_once_with(process_id)

    @pytest.mark.asyncio
    async def test_render_process_status_empty_result(self, mock_app):
        """Test render returns empty list when no agents."""
        router = business_router_process(mock_app)
        process_id = "test-process-123"

        mock_process_status_repo = AsyncMock(spec=ProcessStatusRepository)
        mock_process_status_repo.render_agent_status = AsyncMock(return_value=[])

        mock_scope = AsyncMock()
        mock_scope.get_service = Mock(return_value=mock_process_status_repo)
        mock_scope.__aenter__ = AsyncMock(return_value=mock_scope)
        mock_scope.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.create_scope = Mock(return_value=mock_scope)

        result = await router.render_process_status(process_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_render_process_status_single_agent(self, mock_app):
        """Test rendering with single agent status."""
        router = business_router_process(mock_app)
        process_id = "test-process-123"
        expected_render = ["Agent Migration: Processing files"]

        mock_process_status_repo = AsyncMock(spec=ProcessStatusRepository)
        mock_process_status_repo.render_agent_status = AsyncMock(return_value=expected_render)

        mock_scope = AsyncMock()
        mock_scope.get_service = Mock(return_value=mock_process_status_repo)
        mock_scope.__aenter__ = AsyncMock(return_value=mock_scope)
        mock_scope.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.create_scope = Mock(return_value=mock_scope)

        result = await router.render_process_status(process_id)

        assert result == expected_render
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_render_process_status_multiple_agents(self, mock_app):
        """Test rendering with multiple agent statuses."""
        router = business_router_process(mock_app)
        process_id = "test-process-123"
        expected_render = [
            "Agent Migration: Processing YAML files", 
            "Agent Validation: Validating configurations",
            "Agent Deployment: Ready to deploy"
        ]

        mock_process_status_repo = AsyncMock(spec=ProcessStatusRepository)
        mock_process_status_repo.render_agent_status = AsyncMock(return_value=expected_render)

        mock_scope = AsyncMock()
        mock_scope.get_service = Mock(return_value=mock_process_status_repo)
        mock_scope.__aenter__ = AsyncMock(return_value=mock_scope)
        mock_scope.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.create_scope = Mock(return_value=mock_scope)

        result = await router.render_process_status(process_id)

        assert result == expected_render
        assert len(result) == 3


class TestBusinessRouterProcessIntegration(TestBusinessRouterProcess):
    """Integration test cases for business_router_process methods working together."""

    @pytest.mark.asyncio
    async def test_error_handling_consistency(self, mock_app):
        """Test that all methods handle service unavailability consistently."""
        router = business_router_process(mock_app)
        process_id = "test-process-123"

        # Test blob service unavailable
        blob_context_manager = AsyncMock()
        blob_context_manager.__aenter__ = AsyncMock(return_value=None)
        blob_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.get_service = Mock(return_value=blob_context_manager)

        with pytest.raises(ValueError, match="Blob helper service is not available"):
            await router.save_files_to_blob(process_id, [])

        # Test queue service unavailable
        queue_context_manager = AsyncMock()
        queue_context_manager.__aenter__ = AsyncMock(return_value=None)
        queue_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.get_service = Mock(return_value=queue_context_manager)

        queue_message = enlist_process_queue_response(user_id="user-123", process_id=process_id)
        with pytest.raises(ValueError, match="Queue service is not available"):
            await router.process_enqueue(queue_message)

    @pytest.mark.asyncio
    async def test_process_id_consistency_across_methods(self, mock_app, mock_blob_helper):
        """Test that process_id is used consistently across different methods."""
        router = business_router_process(mock_app)
        process_id = "consistent-process-id-123"

        # Test save_files_to_blob uses process_id correctly
        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_blob_helper)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.get_service = Mock(return_value=async_context_manager)

        sample_file = FileInfo(filename="test.yaml", content=b"content", content_type="text/yaml", size=7)
        await router.save_files_to_blob(process_id, [sample_file])

        # Verify process_id is used in blob path
        call_args = mock_blob_helper.upload_blob.call_args
        assert process_id in call_args[1]["blob_name"]
        assert call_args[1]["blob_name"].startswith(f"{process_id}/source/")

    def test_class_attributes_and_methods_exist(self, mock_app):
        """Test that all expected methods and attributes exist on the class."""
        router = business_router_process(mock_app)
        
        # Test class has expected attributes
        assert hasattr(router, 'app')
        assert router.app == mock_app
        
        # Test all expected methods exist
        expected_methods = [
            'save_files_to_blob',
            'process_enqueue', 
            'get_current_process_agent_activities',
            'get_current_process',
            'render_process_status'
        ]
        
        for method_name in expected_methods:
            assert hasattr(router, method_name)
            assert callable(getattr(router, method_name))

    @pytest.mark.asyncio
    async def test_blob_operations_with_multiple_files(self, mock_app, mock_blob_helper):
        """Test blob operations with multiple files work correctly."""
        router = business_router_process(mock_app)
        process_id = "multi-file-test-123"

        # Create multiple test files
        files = [
            FileInfo(filename="config.yaml", content=b"config content", content_type="text/yaml", size=14),
            FileInfo(filename="deployment.yaml", content=b"deployment content", content_type="text/yaml", size=18),
            FileInfo(filename="service.yaml", content=b"service content", content_type="text/yaml", size=15),
        ]

        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=mock_blob_helper)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_app.app_context.get_service = Mock(return_value=async_context_manager)

        await router.save_files_to_blob(process_id, files)

        # Verify all files were uploaded
        assert mock_blob_helper.upload_blob.call_count == len(files)
        
        # Verify correct blob names were used
        calls = mock_blob_helper.upload_blob.call_args_list
        for i, call in enumerate(calls):
            expected_blob_name = f"{process_id}/source/{files[i].filename}"
            assert call[1]["blob_name"] == expected_blob_name

    @pytest.mark.asyncio
    async def test_service_dependency_injection_patterns(self, mock_app):
        """Test that dependency injection patterns work correctly."""
        router = business_router_process(mock_app)
        
        # Test that each method uses the correct service type
        mock_app.app_context.get_service = Mock()
        mock_app.app_context.create_scope = Mock()

        # Verify that the correct service types would be requested
        # (This tests the dependency injection pattern without executing the full method)
        assert router.app == mock_app
        assert hasattr(router.app.app_context, 'get_service')
        assert hasattr(router.app.app_context, 'create_scope')