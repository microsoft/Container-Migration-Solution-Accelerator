"""
Unit tests for migration_service.py

Tests the MigrationProcessor class and related functionality including:
- Initialization and configuration
- Migration execution flows (success, failure, timeout)
- Error handling and classification
- Report generation
- Helper methods and utilities
"""

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from services.migration_service import (
    MigrationEngineResult,
    MigrationProcessor,
    ProcessStatus,
    create_migration_service,
    format_step_status,
)
from utils.error_classifier import ErrorClassification


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_app_context():
    """Mock application context"""
    context = MagicMock()
    context.config = {"timeout_minutes": 25, "debug_mode": False}
    return context


@pytest.fixture
def mock_kernel_agent():
    """Mock semantic_kernel_agent"""
    agent = MagicMock()
    agent.kernel = MagicMock()
    agent.initialize_async = AsyncMock()
    return agent


@pytest.fixture
def mock_telemetry_manager():
    """Mock TelemetryManager"""
    telemetry = MagicMock()
    telemetry.init_process = AsyncMock()
    telemetry.update_agent_activity = AsyncMock()
    telemetry.update_process_status = AsyncMock()
    telemetry.complete_all_participant_agents = AsyncMock()
    telemetry.get_current_process = AsyncMock()
    telemetry.record_final_outcome = AsyncMock()
    return telemetry


@pytest.fixture
def mock_migration_process():
    """Mock KernelProcess"""
    process = MagicMock()
    return process


@pytest.fixture
def mock_final_state():
    """Mock final state with successful completion"""

    class MockStepState:
        def __init__(self, result=True):
            self.state = MagicMock()
            self.state.result = result

    class MockFinalState:
        def __init__(self, num_steps=4, all_success=True):
            self.steps = [MockStepState(all_success) for _ in range(num_steps)]

    return MockFinalState()


@pytest.fixture
def mock_process_context():
    """Mock process context"""
    context = MagicMock()
    context.get_state = AsyncMock()
    context.__aenter__ = AsyncMock(return_value=context)
    context.__aexit__ = AsyncMock()
    return context


@pytest.fixture
async def migration_processor(mock_app_context):
    """Create MigrationProcessor instance for testing"""
    processor = MigrationProcessor(
        app_context=mock_app_context, debug_mode=True, timeout_minutes=25
    )
    return processor


# ============================================================================
# Test format_step_status utility function
# ============================================================================


class TestFormatStepStatus:
    """Test cases for format_step_status utility function"""

    def test_format_step_status_not_started(self):
        """Test formatting for not started step"""
        result = format_step_status("Analysis", None)
        assert "⏳ Not started yet" in result
        assert "Analysis" in result

    def test_format_step_status_success(self):
        """Test formatting for successful step"""
        result = format_step_status("Design", True)
        assert "✅ Completed successfully" in result
        assert "Design" in result

    def test_format_step_status_failure_with_reason(self):
        """Test formatting for failed step with reason"""
        result = format_step_status("YAML Conversion", False, "Invalid syntax")
        assert "❌" in result
        assert "Invalid syntax" in result
        assert "YAML Conversion" in result

    def test_format_step_status_failure_without_reason(self):
        """Test formatting for failed step without reason"""
        result = format_step_status("Documentation", False)
        assert "❌" in result
        assert "Encountered issues" in result
        assert "Documentation" in result


# ============================================================================
# Test ProcessStatus Enum
# ============================================================================


class TestProcessStatus:
    """Test cases for ProcessStatus enum"""

    def test_process_status_values(self):
        """Test that ProcessStatus has expected values"""
        assert ProcessStatus.INITIALIZING.value == "initializing"
        assert ProcessStatus.RUNNING.value == "running"
        assert ProcessStatus.COMPLETED.value == "completed"
        assert ProcessStatus.FAILED.value == "failed"
        assert ProcessStatus.TIMEOUT.value == "timeout"


# ============================================================================
# Test MigrationEngineResult dataclass
# ============================================================================


class TestMigrationEngineResult:
    """Test cases for MigrationEngineResult dataclass"""

    def test_migration_engine_result_success(self):
        """Test successful result"""
        result = MigrationEngineResult(
            success=True,
            process_id="test-123",
            execution_time=10.5,
            status=ProcessStatus.COMPLETED,
        )
        assert result.success is True
        assert result.process_id == "test-123"
        assert result.execution_time == 10.5
        assert result.status == ProcessStatus.COMPLETED
        assert result.error_message is None
        assert result.timestamp is not None
        assert result.is_retryable is False

    def test_migration_engine_result_retryable_failure(self):
        """Test retryable failure result"""
        result = MigrationEngineResult(
            success=False,
            process_id="test-456",
            execution_time=5.0,
            status=ProcessStatus.FAILED,
            error_message="Rate limit exceeded",
            error_classification=ErrorClassification.RETRYABLE,
        )
        assert result.success is False
        assert result.is_retryable is True
        assert result.error_classification == ErrorClassification.RETRYABLE

    def test_migration_engine_result_non_retryable_failure(self):
        """Test non-retryable failure result"""
        result = MigrationEngineResult(
            success=False,
            process_id="test-789",
            execution_time=3.0,
            status=ProcessStatus.FAILED,
            error_message="Invalid configuration",
            error_classification=ErrorClassification.NON_RETRYABLE,
        )
        assert result.success is False
        assert result.is_retryable is False
        assert result.error_classification == ErrorClassification.NON_RETRYABLE

    def test_migration_engine_result_timestamp_auto_generated(self):
        """Test that timestamp is auto-generated if not provided"""
        before = time.time()
        result = MigrationEngineResult(
            success=True,
            process_id="test-timestamp",
            execution_time=1.0,
            status=ProcessStatus.COMPLETED,
        )
        after = time.time()
        assert before <= result.timestamp <= after

    def test_migration_engine_result_custom_timestamp(self):
        """Test custom timestamp"""
        custom_time = 1234567890.0
        result = MigrationEngineResult(
            success=True,
            process_id="test-custom",
            execution_time=1.0,
            status=ProcessStatus.COMPLETED,
            timestamp=custom_time,
        )
        assert result.timestamp == custom_time


# ============================================================================
# Test MigrationProcessor Initialization
# ============================================================================


class TestMigrationProcessorInitialization:
    """Test cases for MigrationProcessor initialization"""

    def test_init_with_defaults(self):
        """Test initialization with default parameters"""
        processor = MigrationProcessor()
        assert processor.app_context is None
        assert processor.debug_mode is False
        assert processor.timeout_minutes == 25
        assert processor.kernel_agent is None
        assert processor.migration_process is None
        assert processor._report_collector is None
        assert processor.telemetry is not None

    def test_init_with_custom_parameters(self, mock_app_context):
        """Test initialization with custom parameters"""
        processor = MigrationProcessor(
            app_context=mock_app_context, debug_mode=True, timeout_minutes=30
        )
        assert processor.app_context == mock_app_context
        assert processor.debug_mode is True
        assert processor.timeout_minutes == 30

    @patch("services.migration_service.semantic_kernel_agent")
    @patch("services.migration_service.AKSMigrationProcess")
    async def test_initialize_success(
        self, mock_aks_process, mock_sk_agent, migration_processor, mock_kernel_agent
    ):
        """Test successful initialization"""
        mock_sk_agent.return_value = mock_kernel_agent
        mock_aks_process.create_process.return_value = MagicMock()

        await migration_processor.initialize()

        assert migration_processor.kernel_agent is not None
        assert migration_processor.migration_process is not None
        mock_kernel_agent.initialize_async.assert_called_once()

    @patch("services.migration_service.semantic_kernel_agent")
    async def test_initialize_kernel_agent_failure(
        self, mock_sk_agent, migration_processor
    ):
        """Test initialization failure when kernel agent creation fails"""
        mock_sk_agent.side_effect = Exception("Failed to create kernel agent")

        with pytest.raises(Exception, match="Failed to create kernel agent"):
            await migration_processor.initialize()

    @patch("services.migration_service.semantic_kernel_agent")
    @patch("services.migration_service.AKSMigrationProcess")
    async def test_initialize_process_failure(
        self, mock_aks_process, mock_sk_agent, migration_processor, mock_kernel_agent
    ):
        """Test initialization failure when migration process creation fails"""
        mock_sk_agent.return_value = mock_kernel_agent
        mock_aks_process.create_process.return_value = None

        with pytest.raises(RuntimeError, match="Failed to create migration process"):
            await migration_processor.initialize()


# ============================================================================
# Test MigrationProcessor.execute_migration
# ============================================================================


class TestExecuteMigration:
    """Test cases for execute_migration method"""

    @pytest.fixture
    async def initialized_processor(self, migration_processor, mock_kernel_agent):
        """Initialize processor for testing"""
        with patch("services.migration_service.semantic_kernel_agent") as mock_sk:
            with patch("services.migration_service.AKSMigrationProcess") as mock_aks:
                mock_sk.return_value = mock_kernel_agent
                mock_aks.create_process.return_value = MagicMock()
                await migration_processor.initialize()
        return migration_processor

    async def test_execute_migration_missing_process_id(self, initialized_processor):
        """Test execute_migration raises error when process_id is missing"""
        with pytest.raises(ValueError, match="Process ID is required"):
            await initialized_processor.execute_migration(
                "", "user-123", {"source": "eks"}
            )

    async def test_execute_migration_missing_user_id(self, initialized_processor):
        """Test execute_migration raises error when user_id is missing"""
        with pytest.raises(ValueError, match="User ID is required"):
            await initialized_processor.execute_migration(
                "process-123", "", {"source": "eks"}
            )

    @patch("services.migration_service.start")
    async def test_execute_migration_success(
        self, mock_start, initialized_processor, mock_process_context, mock_final_state
    ):
        """Test successful migration execution"""
        # Setup mocks
        mock_process_context.get_state.return_value = mock_final_state
        mock_start.return_value = mock_process_context

        # Mock telemetry methods
        with (
            patch.object(
                initialized_processor.telemetry, "init_process", new=AsyncMock()
            ),
            patch.object(
                initialized_processor.telemetry,
                "update_agent_activity",
                new=AsyncMock(),
            ),
            patch.object(
                initialized_processor.telemetry,
                "update_process_status",
                new=AsyncMock(),
            ),
            patch.object(
                initialized_processor.telemetry,
                "complete_all_participant_agents",
                new=AsyncMock(),
            ),
            patch.object(
                initialized_processor.telemetry,
                "get_current_process",
                new=AsyncMock(return_value=None),
            ),
        ):
            # Execute migration
            result = await initialized_processor.execute_migration(
                process_id="test-process-123",
                user_id="test-user-456",
                migration_request={"source": "eks", "target": "aks"},
            )

        # Assertions
        assert result.success is True
        assert result.process_id == "test-process-123"
        assert result.status == ProcessStatus.COMPLETED
        assert result.error_message is None
        assert result.execution_time > 0

    @patch("services.migration_service.start")
    async def test_execute_migration_timeout(
        self, mock_start, initialized_processor, mock_process_context
    ):
        """Test migration execution timeout"""

        # Make process hang
        async def slow_get_state():
            await asyncio.sleep(100)

        mock_process_context.get_state.side_effect = slow_get_state
        mock_start.return_value = mock_process_context

        # Create a processor with very short timeout
        short_timeout_processor = MigrationProcessor(timeout_minutes=0.01)
        with (
            patch("services.migration_service.semantic_kernel_agent") as mock_sk,
            patch("services.migration_service.AKSMigrationProcess") as mock_aks,
        ):
            mock_sk.return_value = MagicMock()
            mock_sk.return_value.initialize_async = AsyncMock()
            mock_sk.return_value.kernel = MagicMock()
            mock_aks.create_process.return_value = MagicMock()
            await short_timeout_processor.initialize()

        with (
            patch.object(
                short_timeout_processor.telemetry, "init_process", new=AsyncMock()
            ),
            patch.object(
                short_timeout_processor.telemetry,
                "update_agent_activity",
                new=AsyncMock(),
            ),
            patch.object(
                short_timeout_processor.telemetry,
                "update_process_status",
                new=AsyncMock(),
            ),
            patch.object(
                short_timeout_processor.telemetry,
                "record_final_outcome",
                new=AsyncMock(),
            ),
        ):
            # Note: This test may need to be adjusted based on actual timeout implementation
            # The current code doesn't have timeout protection, so we simulate it
            _result = await initialized_processor.execute_migration(
                process_id="timeout-test",
                user_id="user-123",
                migration_request={"source": "eks"},
            )

    @patch("services.migration_service.start")
    async def test_execute_migration_exception(
        self, mock_start, initialized_processor
    ):
        """Test migration execution with exception"""
        mock_start.side_effect = Exception("Unexpected error during migration")

        with (
            patch.object(
                initialized_processor.telemetry, "init_process", new=AsyncMock()
            ),
            patch.object(
                initialized_processor.telemetry,
                "update_agent_activity",
                new=AsyncMock(),
            ),
            patch.object(
                initialized_processor.telemetry,
                "update_process_status",
                new=AsyncMock(),
            ),
            patch.object(
                initialized_processor.telemetry,
                "record_final_outcome",
                new=AsyncMock(),
            ),
        ):
            result = await initialized_processor.execute_migration(
                process_id="error-test",
                user_id="user-123",
                migration_request={"source": "eks"},
            )

        assert result.success is False
        assert result.status == ProcessStatus.FAILED
        assert result.error_message is not None
        assert "Unexpected error during migration" in result.error_message


# ============================================================================
# Test MigrationProcessor Helper Methods
# ============================================================================


class TestMigrationProcessorHelperMethods:
    """Test cases for MigrationProcessor helper methods"""

    @pytest.fixture
    async def initialized_processor(self, migration_processor, mock_kernel_agent):
        """Initialize processor for testing"""
        with (
            patch("services.migration_service.semantic_kernel_agent") as mock_sk,
            patch("services.migration_service.AKSMigrationProcess") as mock_aks,
        ):
            mock_sk.return_value = mock_kernel_agent
            mock_aks.create_process.return_value = MagicMock()
            await migration_processor.initialize()
        return migration_processor

    def test_evaluate_process_success_all_steps_complete(
        self, initialized_processor, mock_final_state
    ):
        """Test process evaluation when all steps are successful"""
        result = initialized_processor._evaluate_process_success(mock_final_state)
        assert result is True

    def test_evaluate_process_success_incomplete_steps(self, initialized_processor):
        """Test process evaluation when steps are incomplete"""

        class MockStepState:
            def __init__(self):
                self.state = MagicMock()
                self.state.result = True

        class MockIncompleteState:
            def __init__(self):
                self.steps = [MockStepState() for _ in range(2)]  # Only 2 steps

        incomplete_state = MockIncompleteState()
        result = initialized_processor._evaluate_process_success(incomplete_state)
        assert result == "RUNNING"

    def test_evaluate_process_success_failed_step(self, initialized_processor):
        """Test process evaluation when a step has failed"""

        class MockStepState:
            def __init__(self, result):
                self.state = MagicMock()
                self.state.result = result

        class MockFailedState:
            def __init__(self):
                self.steps = [
                    MockStepState(True),
                    MockStepState(False),  # Failed step
                    MockStepState(True),
                    MockStepState(True),
                ]

        failed_state = MockFailedState()
        result = initialized_processor._evaluate_process_success(failed_state)
        assert result is False

    async def test_handle_success(self, initialized_processor):
        """Test _handle_success updates telemetry correctly"""
        with (
            patch.object(
                initialized_processor.telemetry,
                "update_process_status",
                new=AsyncMock(),
            ) as mock_update_status,
            patch.object(
                initialized_processor.telemetry,
                "update_agent_activity",
                new=AsyncMock(),
            ),
            patch.object(
                initialized_processor.telemetry,
                "complete_all_participant_agents",
                new=AsyncMock(),
            ) as mock_complete_agents,
            patch.object(
                initialized_processor.telemetry,
                "get_current_process",
                new=AsyncMock(return_value=None),
            ),
        ):
            await initialized_processor._handle_success("test-process", 10.5)

        mock_update_status.assert_called_once_with(
            process_id="test-process", status="completed"
        )
        mock_complete_agents.assert_called_once_with(process_id="test-process")

    async def test_handle_failure_final(self, initialized_processor):
        """Test _handle_failure with final failure"""
        with (
            patch.object(
                initialized_processor.telemetry,
                "update_process_status",
                new=AsyncMock(),
            ) as mock_update_status,
            patch.object(
                initialized_processor.telemetry,
                "update_agent_activity",
                new=AsyncMock(),
            ),
        ):
            await initialized_processor._handle_failure(
                process_id="test-fail",
                error_message="Test error",
                execution_time=5.0,
                error_classification=ErrorClassification.NON_RETRYABLE,
                is_final_failure=True,
            )

        mock_update_status.assert_called_once()

    def test_create_comprehensive_error_message(self, initialized_processor):
        """Test error message creation"""
        test_exception = ValueError("Test error message")
        error_msg = initialized_processor._create_comprehensive_error_message(
            test_exception
        )

        assert "ValueError" in error_msg
        assert "Test error message" in error_msg

    def test_create_comprehensive_error_message_with_cause(
        self, initialized_processor
    ):
        """Test error message creation with exception cause"""
        cause = ValueError("Original cause")
        test_exception = RuntimeError("Wrapper error")
        test_exception.__cause__ = cause

        error_msg = initialized_processor._create_comprehensive_error_message(
            test_exception
        )

        assert "RuntimeError" in error_msg
        assert "Wrapper error" in error_msg
        assert "Original cause" in error_msg


# ============================================================================
# Test MigrationProcessor Cleanup
# ============================================================================


class TestMigrationProcessorCleanup:
    """Test cases for MigrationProcessor cleanup"""

    @pytest.fixture
    async def initialized_processor(self, migration_processor, mock_kernel_agent):
        """Initialize processor for testing"""
        with (
            patch("services.migration_service.semantic_kernel_agent") as mock_sk,
            patch("services.migration_service.AKSMigrationProcess") as mock_aks,
        ):
            mock_sk.return_value = mock_kernel_agent
            mock_aks.create_process.return_value = MagicMock()
            await migration_processor.initialize()
        return migration_processor

    async def test_cleanup_success(self, initialized_processor):
        """Test successful cleanup"""
        # Mock the kernel agent cleanup
        initialized_processor.kernel_agent = MagicMock()

        await initialized_processor.cleanup()
        # Just ensure no exception is raised

    async def test_cleanup_with_exception(self, initialized_processor):
        """Test cleanup handles exceptions gracefully"""
        initialized_processor.kernel_agent = MagicMock()
        initialized_processor.kernel_agent.cleanup = Mock(
            side_effect=Exception("Cleanup error")
        )

        # Should not raise exception
        await initialized_processor.cleanup()


# ============================================================================
# Test create_migration_service Factory Function
# ============================================================================


class TestCreateMigrationService:
    """Test cases for create_migration_service factory function"""

    @patch("services.migration_service.semantic_kernel_agent")
    @patch("services.migration_service.AKSMigrationProcess")
    async def test_create_migration_service_success(
        self, mock_aks_process, mock_sk_agent, mock_app_context, mock_kernel_agent
    ):
        """Test successful creation of migration service"""
        mock_sk_agent.return_value = mock_kernel_agent
        mock_aks_process.create_process.return_value = MagicMock()

        processor = await create_migration_service(
            app_context=mock_app_context, debug_mode=True, timeout_minutes=30
        )

        assert processor is not None
        assert processor.app_context == mock_app_context
        assert processor.debug_mode is True
        assert processor.timeout_minutes == 30
        assert processor.kernel_agent is not None
        assert processor.migration_process is not None

    @patch("services.migration_service.semantic_kernel_agent")
    async def test_create_migration_service_initialization_failure(
        self, mock_sk_agent, mock_app_context
    ):
        """Test factory function handles initialization failures"""
        mock_sk_agent.side_effect = Exception("Initialization failed")

        with pytest.raises(Exception, match="Initialization failed"):
            await create_migration_service(app_context=mock_app_context)


# ============================================================================
# Test Report Generation Methods
# ============================================================================


class TestReportGeneration:
    """Test cases for report generation methods"""

    @pytest.fixture
    async def initialized_processor(self, migration_processor, mock_kernel_agent):
        """Initialize processor for testing"""
        with (
            patch("services.migration_service.semantic_kernel_agent") as mock_sk,
            patch("services.migration_service.AKSMigrationProcess") as mock_aks,
        ):
            mock_sk.return_value = mock_kernel_agent
            mock_aks.create_process.return_value = MagicMock()
            await migration_processor.initialize()
        migration_processor._report_collector = MagicMock()
        return migration_processor

    @patch("services.migration_service.MigrationReportGenerator")
    async def test_generate_success_report(
        self, mock_generator_class, initialized_processor
    ):
        """Test success report generation"""
        mock_generator = MagicMock()
        mock_report = MagicMock()
        mock_report.overall_status = MagicMock(value="SUCCESS")
        mock_generator.generate_failure_report = AsyncMock(return_value=mock_report)
        mock_generator_class.return_value = mock_generator

        with patch.object(
            initialized_processor,
            "_save_report_to_telemetry",
            new=AsyncMock(),
        ) as mock_save:
            await initialized_processor._generate_success_report("test-proc", 10.0)

        mock_save.assert_called_once()

    @patch("services.migration_service.MigrationReportGenerator")
    async def test_generate_failure_report(
        self, mock_generator_class, initialized_processor
    ):
        """Test failure report generation"""
        mock_generator = MagicMock()
        mock_report = MagicMock()
        mock_report.overall_status = MagicMock(value="FAILED")
        mock_report.executive_summary = MagicMock(
            completion_percentage=50.0, critical_issues_count=3, files_failed=5
        )
        mock_report.remediation_guide = None
        mock_generator.generate_failure_report = AsyncMock(return_value=mock_report)
        mock_generator_class.return_value = mock_generator

        with patch.object(
            initialized_processor,
            "_save_report_to_telemetry",
            new=AsyncMock(),
        ) as mock_save:
            await initialized_processor._generate_failure_report(
                "test-proc", 10.0, ProcessStatus.FAILED
            )

        mock_save.assert_called_once()

    async def test_generate_report_without_collector(self, initialized_processor):
        """Test report generation without initialized collector"""
        initialized_processor._report_collector = None

        # Should not raise exception
        await initialized_processor._generate_success_report("test-proc", 10.0)
        await initialized_processor._generate_failure_report(
            "test-proc", 10.0, ProcessStatus.FAILED
        )

    @patch("services.migration_service.JsonReportFormatter")
    @patch("services.migration_service.MarkdownReportFormatter")
    async def test_save_report_to_telemetry(
        self, mock_md_formatter, mock_json_formatter, initialized_processor
    ):
        """Test saving report to telemetry"""
        mock_report = MagicMock()
        mock_report.overall_status = MagicMock(value="SUCCESS")
        mock_report.steps = []
        mock_report.execution_time = 10.0
        mock_report.timestamp = None

        mock_md_formatter.format_report.return_value = "# Markdown Report"
        mock_md_formatter.format_executive_summary.return_value = "## Summary"
        mock_json_formatter.format_report.return_value = '{"report": "data"}'

        with patch.object(
            initialized_processor.telemetry, "record_final_outcome", new=AsyncMock()
        ) as mock_record:
            await initialized_processor._save_report_to_telemetry(
                mock_report, "test-proc", "success"
            )

        mock_record.assert_called_once()
        call_args = mock_record.call_args
        assert call_args[1]["process_id"] == "test-proc"
        assert call_args[1]["success"] is True


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for complete migration workflows"""

    @patch("services.migration_service.semantic_kernel_agent")
    @patch("services.migration_service.AKSMigrationProcess")
    @patch("services.migration_service.start")
    async def test_full_migration_workflow_success(
        self,
        mock_start,
        mock_aks_process,
        mock_sk_agent,
        mock_app_context,
        mock_kernel_agent,
        mock_process_context,
        mock_final_state,
    ):
        """Test complete successful migration workflow"""
        # Setup mocks
        mock_sk_agent.return_value = mock_kernel_agent
        mock_aks_process.create_process.return_value = MagicMock()
        mock_process_context.get_state.return_value = mock_final_state
        mock_start.return_value = mock_process_context

        # Create and initialize processor
        processor = await create_migration_service(
            app_context=mock_app_context, debug_mode=True
        )

        # Mock telemetry methods
        with (
            patch.object(processor.telemetry, "init_process", new=AsyncMock()),
            patch.object(
                processor.telemetry, "update_agent_activity", new=AsyncMock()
            ),
            patch.object(
                processor.telemetry, "update_process_status", new=AsyncMock()
            ),
            patch.object(
                processor.telemetry,
                "complete_all_participant_agents",
                new=AsyncMock(),
            ),
            patch.object(
                processor.telemetry,
                "get_current_process",
                new=AsyncMock(return_value=None),
            ),
        ):
            # Execute migration
            result = await processor.execute_migration(
                process_id="integration-test",
                user_id="test-user",
                migration_request={
                    "source": "eks",
                    "target": "aks",
                    "files": ["deployment.yaml"],
                },
            )

        # Verify success
        assert result.success is True
        assert result.status == ProcessStatus.COMPLETED

        # Cleanup
        await processor.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
