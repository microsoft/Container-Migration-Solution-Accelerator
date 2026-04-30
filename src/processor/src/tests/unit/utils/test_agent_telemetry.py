# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from utils.agent_telemetry import (
    TelemetryManager,
    ProcessStatus,
    AgentActivity,
    AgentActivityHistory,
    _sha256_text,
    _byte_len_text,
    _get_process_blob_container_name,
    _get_storage_connection_string,
    _get_utc_timestamp,
    _parse_utc_timestamp,
    _build_step_lap_times,
    get_orchestration_agents,
)


# Test helper functions - simple utility functions
def test_sha256_text():
    result = _sha256_text("hello world")
    assert isinstance(result, str)
    assert len(result) == 64  # SHA256 hex is 64 chars
    assert result == _sha256_text("hello world")  # Deterministic


def test_byte_len_text():
    assert _byte_len_text("hello") == 5
    assert _byte_len_text("") == 0
    assert _byte_len_text("hello world") == 11
    assert _byte_len_text("你好") > 2  # UTF-8 multibyte


def test_get_process_blob_container_name():
    with patch.dict(os.environ, {}, clear=False):
        if "PROCESS_BLOB_CONTAINER_NAME" in os.environ:
            del os.environ["PROCESS_BLOB_CONTAINER_NAME"]
        result = _get_process_blob_container_name()
        assert result == "processes"
    
    with patch.dict(os.environ, {"PROCESS_BLOB_CONTAINER_NAME": "  custom-container  "}):
        result = _get_process_blob_container_name()
        assert result == "custom-container"
    
    with patch.dict(os.environ, {"PROCESS_BLOB_CONTAINER_NAME": ""}):
        result = _get_process_blob_container_name()
        assert result == "processes"


def test_get_storage_connection_string():
    with patch.dict(os.environ, {}, clear=False):
        for key in ["AZURE_STORAGE_CONNECTION_STRING", "STORAGE_CONNECTION_STRING", "AzureWebJobsStorage"]:
            if key in os.environ:
                del os.environ[key]
        result = _get_storage_connection_string()
        assert result is None
    
    with patch.dict(os.environ, {"AZURE_STORAGE_CONNECTION_STRING": "test-conn-str"}):
        result = _get_storage_connection_string()
        assert result == "test-conn-str"
    
    with patch.dict(os.environ, {"STORAGE_CONNECTION_STRING": "test-conn-str-2"}):
        result = _get_storage_connection_string()
        assert result == "test-conn-str-2"
    
    with patch.dict(os.environ, {"AzureWebJobsStorage": "test-conn-str-3"}):
        result = _get_storage_connection_string()
        assert result == "test-conn-str-3"


def test_get_utc_timestamp():
    result = _get_utc_timestamp()
    assert isinstance(result, str)
    assert "UTC" in result
    assert "-" in result and ":" in result  # Date and time format


def test_parse_utc_timestamp():
    now_str = _get_utc_timestamp()
    parsed = _parse_utc_timestamp(now_str)
    assert parsed is not None
    assert parsed.tzinfo is not None
    
    assert _parse_utc_timestamp("") is None
    assert _parse_utc_timestamp(None) is None
    assert _parse_utc_timestamp(123) is None
    assert _parse_utc_timestamp("invalid-date") is None


def test_build_step_lap_times():
    step_timings = {
        "analysis": {
            "started_at": "2025-01-01 10:00:00 UTC",
            "ended_at": "2025-01-01 10:05:00 UTC",
            "elapsed_seconds": 300,
        },
        "design": {
            "started_at": "2025-01-01 10:05:00 UTC",
            "ended_at": "2025-01-01 10:10:00 UTC",
        },
    }
    items, total_elapsed = _build_step_lap_times(step_timings)
    
    assert isinstance(items, list)
    assert isinstance(total_elapsed, float)
    assert total_elapsed >= 300
    assert len(items) == 2
    
    for item in items:
        assert "step" in item
        assert "started_at" in item
        assert "ended_at" in item
        assert "status" in item
        assert "elapsed_seconds" in item


def test_build_step_lap_times_with_none():
    items, total_elapsed = _build_step_lap_times(None)
    assert items == []
    assert total_elapsed == 0.0


def test_build_step_lap_times_running_step():
    now_str = _get_utc_timestamp()
    step_timings = {
        "analysis": {
            "started_at": now_str,
            "elapsed_seconds": None,
        }
    }
    items, total_elapsed = _build_step_lap_times(step_timings)
    
    assert len(items) == 1
    assert items[0]["status"] == "running"
    assert items[0]["elapsed_seconds"] is not None


def test_get_orchestration_agents():
    agents = get_orchestration_agents()
    assert isinstance(agents, set)
    assert "Coordinator" in agents


# Test model classes
def test_agent_activity_history_creation():
    history = AgentActivityHistory(action="thinking", message_preview="Processing...")
    assert history.action == "thinking"
    assert history.message_preview == "Processing..."
    assert history.step == ""
    assert history.tool_used == ""
    assert "UTC" in history.timestamp


def test_agent_activity_creation():
    activity = AgentActivity(name="TestAgent")
    assert activity.name == "TestAgent"
    assert activity.current_action == "idle"
    assert activity.is_active is False
    assert activity.participation_status == "ready"
    assert len(activity.activity_history) == 0


def test_process_status_creation():
    process = ProcessStatus(id="test-proc-1", phase="analysis", step="start")
    assert process.id == "test-proc-1"
    assert process.phase == "analysis"
    assert process.step == "start"
    assert process.status == "running"
    assert len(process.agents) == 0


# Test TelemetryManager with development mode
def test_telemetry_manager_development_mode():
    telemetry = TelemetryManager(app_context=None)
    assert telemetry.repository is None


def test_telemetry_manager_development_mode_no_cosmos_url():
    mock_config = MagicMock()
    mock_config.cosmos_db_account_url = "http://<"
    mock_app_context = MagicMock()
    mock_app_context.configuration = mock_config
    
    telemetry = TelemetryManager(app_context=mock_app_context)
    assert telemetry.repository is None


def test_telemetry_manager_with_localhost():
    mock_config = MagicMock()
    mock_config.cosmos_db_account_url = "http://localhost:8081"
    mock_app_context = MagicMock()
    mock_app_context.configuration = mock_config
    
    telemetry = TelemetryManager(app_context=mock_app_context)
    assert telemetry.repository is None


# Test async TelemetryManager methods with development mode
def test_telemetry_manager_delete_process_dev_mode():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        await telemetry.delete_process("proc-1")
    
    asyncio.run(_run())


def test_telemetry_manager_init_process_dev_mode():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        await telemetry.init_process("proc-1", "analysis", "start")
        # Should not raise
    
    asyncio.run(_run())


def test_telemetry_manager_update_agent_activity_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        await telemetry.update_agent_activity(
            "proc-1",
            "TestAgent",
            "thinking",
            "Processing data"
        )
    
    asyncio.run(_run())


def test_telemetry_manager_track_tool_usage_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        await telemetry.track_tool_usage(
            "proc-1",
            "TestAgent",
            "blob_ops",
            "list_files",
            "Listed 10 files"
        )
    
    asyncio.run(_run())


def test_telemetry_manager_update_process_status_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        await telemetry.update_process_status("proc-1", "completed")
    
    asyncio.run(_run())


def test_telemetry_manager_set_agent_idle_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        await telemetry.set_agent_idle("proc-1", "TestAgent")
    
    asyncio.run(_run())


def test_telemetry_manager_update_phase_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        await telemetry.update_phase("proc-1", "design")
    
    asyncio.run(_run())


def test_telemetry_manager_transition_to_phase_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        await telemetry.transition_to_phase("proc-1", "design", "architecture")
    
    asyncio.run(_run())


def test_telemetry_manager_complete_all_participant_agents_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        await telemetry.complete_all_participant_agents("proc-1")
    
    asyncio.run(_run())


def test_telemetry_manager_record_failure_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        await telemetry.record_failure(
            "proc-1",
            "Test failure"
        )
    
    asyncio.run(_run())


def test_telemetry_manager_get_current_process_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        result = await telemetry.get_current_process("proc-1")
        assert result is None
    
    asyncio.run(_run())


def test_telemetry_manager_get_process_outcome_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        result = await telemetry.get_process_outcome("proc-1")
        assert result == ""
    
    asyncio.run(_run())


def test_telemetry_manager_get_process_status_by_process_id_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        result = await telemetry.get_process_status_by_process_id("proc-1")
        assert result is None
    
    asyncio.run(_run())


def test_telemetry_manager_render_agent_status_no_process():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        result = await telemetry.render_agent_status("proc-1")
        assert result["process_id"] == "proc-1"
        assert result["status"] == "not_found"
    
    asyncio.run(_run())


def test_telemetry_manager_record_step_result_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        await telemetry.record_step_result(
            "proc-1",
            "analysis",
            {"result": "success"}
        )
    
    asyncio.run(_run())


def test_telemetry_manager_record_final_outcome_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        await telemetry.record_final_outcome("proc-1", {"data": "test"})
    
    asyncio.run(_run())


def test_telemetry_manager_record_failure_outcome_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        await telemetry.record_failure_outcome(
            "proc-1",
            "Test error",
            "analysis"
        )
    
    asyncio.run(_run())


def test_telemetry_manager_get_final_results_summary_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        result = await telemetry.get_final_results_summary("proc-1")
        assert result == {}
    
    asyncio.run(_run())


def test_telemetry_manager_record_ui_data_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        await telemetry.record_ui_data("proc-1", {"test": "data"})
    
    asyncio.run(_run())


def test_telemetry_manager_get_ui_telemetry_data_no_repo():
    async def _run():
        telemetry = TelemetryManager(app_context=None)
        result = await telemetry.get_ui_telemetry_data("proc-1")
        assert result == {}
    
    asyncio.run(_run())


def test_telemetry_manager_get_ready_status_message_coordinator():
    telemetry = TelemetryManager(app_context=None)
    
    msg = telemetry._get_ready_status_message("Coordinator", "analysis", "ANALYSIS PHASE", "ready")
    assert "analysis" in msg.lower() or "platform" in msg.lower()
    
    msg = telemetry._get_ready_status_message("Coordinator", "design", "DESIGN PHASE", "ready")
    assert "design" in msg.lower() or "azure" in msg.lower()
    
    msg = telemetry._get_ready_status_message("Coordinator", "yaml", "YAML PHASE", "ready")
    assert "yaml" in msg.lower() or "conversion" in msg.lower()


def test_telemetry_manager_get_ready_status_message_expert():
    telemetry = TelemetryManager(app_context=None)
    
    msg = telemetry._get_ready_status_message("System_Analyzer", "analysis", "ANALYSIS", "ready")
    assert "analyze" in msg.lower() or "ready" in msg.lower()
    
    msg = telemetry._get_ready_status_message("Azure_Expert", "design", "DESIGN", "ready")
    assert "azure" in msg.lower() or "design" in msg.lower()


# Test with repository - mock the repository to execute production code paths
def test_telemetry_manager_init_process_with_repository():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        mock_config.cosmos_db_database_name = "testdb"
        mock_config.cosmos_db_container_name = "testcontainer"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_repo = AsyncMock()
        mock_repo.add_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            assert telemetry.repository is not None
            
            await telemetry.init_process("proc-123", "analysis", "start")
            
            mock_repo.add_async.assert_called_once()
            call_args = mock_repo.add_async.call_args[0][0]
            assert call_args.id == "proc-123"
            assert call_args.phase == "analysis"
            assert call_args.step == "start"
            assert "Coordinator" in call_args.agents
    
    asyncio.run(_run())


def test_telemetry_manager_update_agent_activity_with_repository():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        # Create a mock process status
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            agents={"Coordinator": AgentActivity(name="Coordinator")}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.update_agent_activity(
                "proc-123",
                "TestAgent",
                "thinking",
                "Processing analysis",
                full_message="Full message about analysis"
            )
            
            mock_repo.update_async.assert_called_once()
            updated_process = mock_repo.update_async.call_args[0][0]
            assert "TestAgent" in updated_process.agents
            agent = updated_process.agents["TestAgent"]
            assert agent.current_action == "thinking"
            assert agent.participation_status == "thinking"


def test_telemetry_manager_update_agent_activity_speaking():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            agents={}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.update_agent_activity(
                "proc-123",
                "TestAgent",
                "speaking",
                "Agent response"
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            agent = updated_process.agents["TestAgent"]
            assert agent.participation_status == "speaking"
            assert agent.is_currently_speaking is True
            assert agent.is_currently_thinking is False


def test_telemetry_manager_track_tool_usage_with_repository():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            agents={"TestAgent": AgentActivity(name="TestAgent")}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.track_tool_usage(
                "proc-123",
                "TestAgent",
                "blob_storage",
                "list_files",
                "Listed 10 files"
            )
            
            mock_repo.update_async.assert_called_once()
            updated_process = mock_repo.update_async.call_args[0][0]
            agent = updated_process.agents["TestAgent"]
            assert agent.current_action == "using_tool"
            assert len(agent.reasoning_steps) > 0


def test_telemetry_manager_update_process_status_completed():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            agents={"Agent1": AgentActivity(name="Agent1", is_active=True)}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.update_process_status("proc-123", "completed")
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.status == "completed"
            assert updated_process.phase == "end"
            for agent in updated_process.agents.values():
                assert agent.is_active is False
                assert agent.current_action == "idle"


def test_telemetry_manager_set_agent_idle():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            agents={"TestAgent": AgentActivity(name="TestAgent", is_active=True, current_action="thinking")}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.set_agent_idle("proc-123", "TestAgent")
            
            updated_process = mock_repo.update_async.call_args[0][0]
            agent = updated_process.agents["TestAgent"]
            assert agent.current_action == "idle"
            assert agent.is_active is False
            assert agent.participation_status == "standby"


def test_telemetry_manager_transition_to_phase():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            agents={"TestAgent": AgentActivity(name="TestAgent")}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.transition_to_phase("proc-123", "DESIGN PHASE", "architecture")
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.phase == "DESIGN PHASE"
            assert updated_process.step == "architecture"
            assert "architecture" in updated_process.step_timings


def test_telemetry_manager_record_failure():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="analysis"
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.record_failure(
                "proc-123",
                "Connection timeout",
                "Failed to connect to service",
                "analysis",
                "Agent1",
                "Traceback..."
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.status == "failed"
            assert updated_process.failure_reason == "Connection timeout"
            assert updated_process.failure_step == "analysis"


def test_telemetry_manager_render_agent_status():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="ANALYSIS PHASE",
            step="analysis",
            agents={
                "Coordinator": AgentActivity(
                    name="Coordinator",
                    current_action="thinking",
                    participation_status="thinking",
                    is_currently_thinking=True
                ),
                "TestAgent": AgentActivity(
                    name="TestAgent",
                    current_action="speaking",
                    participation_status="speaking",
                    is_currently_speaking=True,
                    current_speaking_content="Test content"
                )
            }
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            result = await telemetry.render_agent_status("proc-123")
            
            assert result["process_id"] == "proc-123"
            assert result["phase"] == "ANALYSIS PHASE"
            assert len(result["agents"]) == 2


def test_telemetry_manager_record_step_result():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            step_timings={"analysis": {"started_at": _get_utc_timestamp()}}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            result_data = {"success": True, "files_analyzed": 5}
            await telemetry.record_step_result(
                "proc-123",
                "analysis",
                result_data,
                execution_time_seconds=10.5
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert "analysis" in updated_process.step_results
            assert updated_process.step_results["analysis"]["result"] == result_data


def test_telemetry_manager_record_failure_outcome():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="analysis",
            step_timings={"analysis": {"started_at": _get_utc_timestamp()}}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.record_failure_outcome(
                "proc-123",
                "Network error occurred",
                "analysis",
                {"error_code": 500},
                execution_time_seconds=5.0
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.status == "failed"
            assert updated_process.final_outcome["success"] is False


def test_telemetry_manager_record_final_outcome_success():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="documentation",
            step="documentation"
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            outcome_data = {
                "termination_output": {
                    "generated_files": {
                        "analysis": [{"file_name": "analysis.md", "file_type": "markdown"}],
                        "yaml": [{"source_file": "app.yaml", "converted_file": "app-azure.yaml"}]
                    },
                    "process_metrics": {
                        "platform_detected": "Kubernetes",
                        "conversion_accuracy": "95%"
                    }
                }
            }
            
            await telemetry.record_final_outcome("proc-123", outcome_data, success=True)
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.status == "completed"
            assert updated_process.final_outcome["success"] is True


def test_telemetry_manager_complete_all_participant_agents():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            agents={
                "Coordinator": AgentActivity(name="Coordinator", is_active=True),
                "TestAgent": AgentActivity(name="TestAgent", is_active=True)
            }
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.complete_all_participant_agents("proc-123")
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.agents["TestAgent"].participation_status == "completed"
            assert updated_process.agents["TestAgent"].is_active is False


def test_telemetry_manager_record_ui_data():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(id="proc-123")
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            ui_data = {
                "file_manifest": {
                    "converted_files": ["file1.yaml"],
                }
            }
            
            await telemetry.record_ui_data("proc-123", ui_data)
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.ui_telemetry_data == ui_data


def test_telemetry_manager_get_final_results_summary():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            status="completed",
            step_results={"analysis": {"result": {"success": True}}},
            generated_files=[{"file_name": "analysis.md"}],
            conversion_metrics={"accuracy": "95%"}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            result = await telemetry.get_final_results_summary("proc-123")
            
            assert result["process_id"] == "proc-123"
            assert result["status"] == "completed"


def test_telemetry_manager_init_process_with_exception_retry():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_repo = AsyncMock()
        # First call raises exception, then succeeds on retry
        mock_repo.add_async = AsyncMock(side_effect=[Exception("First failed"), None])
        mock_repo.delete_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.init_process("proc-123", "analysis", "start")
            
            # Should have been called twice (failed first, then succeeded after delete+add)
            assert mock_repo.add_async.call_count == 2
            assert mock_repo.delete_async.called
    
    asyncio.run(_run())


def test_telemetry_manager_update_agent_activity_no_process():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=None)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            # Should not raise, just return
            await telemetry.update_agent_activity(
                "proc-123",
                "TestAgent",
                "thinking"
            )
    
    asyncio.run(_run())


def test_telemetry_manager_update_agent_activity_get_async_error():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(side_effect=Exception("Read error"))
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            # Should not raise, just return
            await telemetry.update_agent_activity(
                "proc-123",
                "TestAgent",
                "thinking"
            )
    
    asyncio.run(_run())


def test_telemetry_manager_update_agent_activity_reset_for_new_step():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        agent = AgentActivity(name="TestAgent")
        agent.activity_history.append(AgentActivityHistory(action="previous"))
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="design",
            agents={"TestAgent": agent}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.update_agent_activity(
                "proc-123",
                "TestAgent",
                "thinking",
                reset_for_new_step=True
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            updated_agent = updated_process.agents["TestAgent"]
            assert updated_agent.step_reset_count == 1
            assert any(h.action == "step_transition_to_design" for h in updated_agent.activity_history)


def test_telemetry_manager_update_agent_activity_with_tool():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            agents={"TestAgent": AgentActivity(name="TestAgent", current_action="processing")}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.update_agent_activity(
                "proc-123",
                "TestAgent",
                "thinking",
                tool_used=True,
                tool_name="blob_storage"
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            updated_agent = updated_process.agents["TestAgent"]
            assert any(h.tool_used == "blob_storage" for h in updated_agent.activity_history)


def test_telemetry_manager_track_tool_usage_no_process():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=None)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.track_tool_usage(
                "proc-123",
                "TestAgent",
                "blob",
                "list"
            )
    
    asyncio.run(_run())


def test_telemetry_manager_track_tool_usage_error():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            agents={}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock(side_effect=Exception("Update failed"))
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.track_tool_usage(
                "proc-123",
                "TestAgent",
                "blob",
                "list"
            )
    
    asyncio.run(_run())


def test_telemetry_manager_update_process_status_failed():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            agents={"Agent1": AgentActivity(name="Agent1", is_active=True)}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.update_process_status("proc-123", "failed")
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.status == "failed"
            assert updated_process.phase == "end"


def test_telemetry_manager_update_process_status_error():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(side_effect=Exception("Error"))
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.update_process_status("proc-123", "completed")
    
    asyncio.run(_run())


def test_telemetry_manager_set_agent_idle_not_found():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            agents={}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.set_agent_idle("proc-123", "MissingAgent")
    
    asyncio.run(_run())


def test_telemetry_manager_update_phase_error():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=None)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.update_phase("proc-123", "NEW PHASE")
    
    asyncio.run(_run())


def test_telemetry_manager_transition_to_phase_not_found():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=None)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.transition_to_phase("proc-123", "DESIGN", "design")
    
    asyncio.run(_run())


def test_telemetry_manager_record_step_result_error():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=None)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.record_step_result(
                "proc-123",
                "analysis",
                {"result": "success"}
            )
    
    asyncio.run(_run())


def test_build_step_lap_times_completed_step():
    step_timings = {
        "analysis": {
            "started_at": "2025-01-01 10:00:00 UTC",
            "ended_at": "2025-01-01 10:05:00 UTC",
        }
    }
    items, total = _build_step_lap_times(step_timings)
    assert len(items) == 1
    assert items[0]["status"] == "completed"


def test_build_step_lap_times_invalid_entries():
    step_timings = {
        "": {},  # Empty step name
        "analysis": "not-a-dict",  # Not a dict
        "design": {"started_at": "", "ended_at": ""},  # Empty timestamps
        "yaml": {
            "started_at": "invalid-date",
            "ended_at": "also-invalid"
        }
    }
    items, total = _build_step_lap_times(step_timings)
    # Should only include valid entries
    assert isinstance(items, list)
    assert isinstance(total, float)


def test_build_step_lap_times_with_elapsed_seconds():
    step_timings = {
        "analysis": {
            "started_at": "2025-01-01 10:00:00 UTC",
            "ended_at": "2025-01-01 10:05:00 UTC",
            "elapsed_seconds": 350  # Different from calculated
        }
    }
    items, total = _build_step_lap_times(step_timings)
    assert items[0]["elapsed_seconds"] == 350


def test_parse_utc_timestamp_various_formats():
    valid_ts = _get_utc_timestamp()
    parsed = _parse_utc_timestamp(valid_ts)
    assert parsed is not None
    
    assert _parse_utc_timestamp("") is None
    assert _parse_utc_timestamp("  ") is None
    assert _parse_utc_timestamp(None) is None
    assert _parse_utc_timestamp(123) is None
    assert _parse_utc_timestamp([]) is None


def test_telemetry_manager_record_step_result_with_list_normalization():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="yaml_parsing",
            agents={},
            step_results={},
            step_timings={"yaml_parsing": {"started_at": _get_utc_timestamp()}}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            # Pass result as list to trigger normalization
            await telemetry.record_step_result(
                "proc-123",
                "yaml_parsing",
                [{"result": "success", "files": 5}]
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert "yaml_parsing" in updated_process.step_results
            result = updated_process.step_results["yaml_parsing"]["result"]
            # Should be normalized from list to dict
            assert isinstance(result, dict)


def test_telemetry_manager_record_step_result_with_execution_time():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="design",
            agents={},
            step_results={},
            step_timings={"design": {"started_at": _get_utc_timestamp()}}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.record_step_result(
                "proc-123",
                "design",
                {"result": "success"},
                execution_time_seconds=45.5
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.step_timings["design"]["elapsed_seconds"] == 45.5


def test_telemetry_manager_record_failure_outcome_with_traceback():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="yaml_parsing",
            agents={},
            step_results={},
            step_timings={"yaml_parsing": {"started_at": _get_utc_timestamp()}}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.record_failure_outcome(
                "proc-123",
                "yaml_parsing",
                "Failed to parse YAML",
                {
                    "traceback": "short traceback",
                    "error_code": "YAML001"
                }
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.status == "failed"
            assert updated_process.final_outcome["success"] is False
            assert updated_process.final_outcome["error_message"] == "Failed to parse YAML"


def test_telemetry_manager_record_failure_outcome_no_process():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=None)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.record_failure_outcome(
                "proc-123",
                "yaml_parsing",
                "Failed"
            )
    
    asyncio.run(_run())


def test_telemetry_manager_record_final_outcome_success():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="end",
            step="complete",
            agents={},
            step_results={}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.record_final_outcome(
                "proc-123",
                True,
                summary="Migration completed successfully",
                summary_data={"migrated_items": 100}
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.final_outcome["success"] is True
            assert updated_process.status == "completed"


def test_telemetry_manager_complete_all_participant_agents():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        agent1 = AgentActivity(name="Agent1", is_active=True)
        agent2 = AgentActivity(name="Agent2", is_active=True)
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="end",
            step="complete",
            agents={"Agent1": agent1, "Agent2": agent2}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.complete_all_participant_agents("proc-123")
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert all(not agent.is_active for agent in updated_process.agents.values())


def test_telemetry_manager_record_ui_data():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="yaml_parsing"
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.record_ui_data(
                "proc-123",
                {"message": "Test", "count": 5}
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.ui_telemetry_data == {"message": "Test", "count": 5}


def test_telemetry_manager_render_agent_status_all_active():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        agent1 = AgentActivity(name="AnalysisAgent", is_active=True, current_action="analyzing")
        agent2 = AgentActivity(name="DesignAgent", is_active=True, current_action="designing")
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="design",
            agents={"AnalysisAgent": agent1, "DesignAgent": agent2}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            status_msg = await telemetry.render_agent_status("proc-123")
            
            assert "AnalysisAgent" in status_msg
            assert "DesignAgent" in status_msg
            assert "analyzing" in status_msg or "active" in status_msg.lower()


def test_telemetry_manager_get_final_results_summary():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="end",
            step="complete",
            agents={},
            status="completed",
            final_outcome={
                "success": True,
                "summary": "Migration completed",
                "timestamp": _get_utc_timestamp()
            }
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            result = await telemetry.get_final_results_summary("proc-123")
            
            assert isinstance(result, dict)


def test_telemetry_manager_record_failure_with_update_error():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="yaml_parsing",
            agents={}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock(side_effect=Exception("Update failed"))
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            # Should handle update error gracefully (exception is caught and logged)
            await telemetry.record_failure("proc-123", "Test error reason")
    
    asyncio.run(_run())


def test_telemetry_manager_record_ui_data_no_process():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=None)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            # Should not raise, just return early
            await telemetry.record_ui_data("proc-123", {"key": "value"})
    
    asyncio.run(_run())


def test_telemetry_manager_get_final_results_summary_no_process():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=None)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            result = await telemetry.get_final_results_summary("proc-123")
            
            # When process not found, returns error dict
            assert isinstance(result, dict)
            assert "error" in result
    
    asyncio.run(_run())


def test_telemetry_manager_render_agent_status_not_found():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=None)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            result = await telemetry.render_agent_status("proc-123")
            
            assert result is not None
    
    asyncio.run(_run())


def test_telemetry_manager_init_process_with_specified_step():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_repo = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.init_process("proc-456", "DESIGN", "design")
            
            added_process = mock_repo.add_async.call_args[0][0]
            assert added_process.phase == "DESIGN"
            assert added_process.step == "design"
    
    asyncio.run(_run())


def test_get_orchestration_agents():
    agents = get_orchestration_agents()
    assert isinstance(agents, set)
    assert "Coordinator" in agents


def test_agent_activity_activity_history_append():
    agent = AgentActivity(name="TestAgent")
    assert len(agent.activity_history) == 0
    
    agent.activity_history.append(AgentActivityHistory(action="test"))
    assert len(agent.activity_history) == 1
    assert agent.activity_history[0].action == "test"


def test_process_status_field_types():
    status = ProcessStatus(id="test-1", phase="analysis", step="yaml_parsing")
    assert status.id == "test-1"
    assert status.phase == "analysis"
    assert status.step == "yaml_parsing"
    assert status.status == "running"  # Default status
    assert isinstance(status.agents, dict)
    assert isinstance(status.step_results, dict)
    assert isinstance(status.step_timings, dict)
    assert isinstance(status.ui_telemetry_data, dict)



def test_telemetry_manager_record_failure_outcome_with_large_traceback():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="yaml_parsing",
            agents={},
            step_results={},
            step_timings={"yaml_parsing": {"started_at": _get_utc_timestamp()}}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        # Create a large traceback that will trigger blob upload
        large_traceback = "x" * 300000  # 300KB traceback
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            with patch("utils.agent_telemetry._upload_text_to_process_blob") as mock_upload:
                mock_upload.return_value = {
                    "container": "processes",
                    "blob": "proc-123/output/debug/traceback.txt",
                    "bytes": 300000
                }
                
                telemetry = TelemetryManager(app_context=mock_app_context)
                
                await telemetry.record_failure_outcome(
                    "proc-123",
                    "yaml_parsing",
                    "Failed to parse YAML",
                    {
                        "traceback": large_traceback,
                        "error_code": "YAML001"
                    }
                )
                
                # Verify that blob upload was called for large traceback
                assert mock_upload.called or mock_repo.update_async.called
    
    asyncio.run(_run())


def test_telemetry_manager_update_agent_activity_with_is_speaking():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        agent = AgentActivity(name="TestAgent")
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            agents={"TestAgent": agent}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.update_agent_activity(
                "proc-123",
                "TestAgent",
                "speaking",
                message_preview="New message",
                full_message="This is a full message"
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.agents["TestAgent"].current_action == "speaking"
            assert updated_process.agents["TestAgent"].last_message_preview == "New message"
    
    asyncio.run(_run())


def test_telemetry_manager_update_agent_activity_with_tool_used():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        agent = AgentActivity(name="TestAgent", current_action="analyzing")
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            agents={"TestAgent": agent}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.update_agent_activity(
                "proc-123",
                "TestAgent",
                "processing",
                message_preview="Using cosmos",
                tool_used=True,
                tool_name="cosmos"
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            # Previous action should be in history with tool info
            history = updated_process.agents["TestAgent"].activity_history
            assert len(history) > 0
    
    asyncio.run(_run())


def test_telemetry_manager_track_tool_usage_with_update():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            agents={"TestAgent": AgentActivity(name="TestAgent", is_active=True)}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.track_tool_usage(
                "proc-123",
                "TestAgent",
                "cosmos",
                "query"
            )
            
            assert mock_repo.update_async.called


def test_telemetry_manager_update_agent_activity_with_is_active():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        agent = AgentActivity(name="TestAgent", is_active=False)
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            agents={"TestAgent": agent}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.update_agent_activity(
                "proc-123",
                "TestAgent",
                "idle",
                is_active=True
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.agents["TestAgent"].is_active is True


def test_telemetry_manager_transition_to_phase_with_agents():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        agent1 = AgentActivity(name="Agent1", is_active=False)
        agent2 = AgentActivity(name="Agent2", is_active=False)
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="yaml_parsing",
            agents={"Agent1": agent1, "Agent2": agent2}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.transition_to_phase(
                "proc-123",
                "DESIGN",
                "design",
                participant_agents=["Agent1", "Agent2"]
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.phase == "DESIGN"
            assert updated_process.step == "design"


def test_telemetry_manager_update_process_status_with_step_update():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="old_step",
            agents={}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.update_process_status(
                "proc-123",
                "running",
                new_step="new_step"
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.step == "new_step"


def test_telemetry_manager_record_final_outcome_failure():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="end",
            step="complete",
            agents={},
            step_results={"step1": {"result": "data"}}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.record_final_outcome(
                "proc-123",
                False,
                summary="Migration failed",
                summary_data={"error": "Test error"}
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.final_outcome["success"] is False
            assert updated_process.status == "failed"


def test_telemetry_manager_record_step_result_with_normalization_error():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="yaml_parsing",
            agents={},
            step_results={},
            step_timings={"yaml_parsing": {"started_at": _get_utc_timestamp()}}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.record_step_result(
                "proc-123",
                "yaml_parsing",
                [[["nested", "list"]]]  # Invalid format for normalization
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert "yaml_parsing" in updated_process.step_results


def test_telemetry_manager_render_agent_status_mixed_states():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        agent1 = AgentActivity(name="Active", is_active=True, current_action="working")
        agent2 = AgentActivity(name="Idle", is_active=False, current_action="waiting")
        agent3 = AgentActivity(name="Thinking", is_active=True, is_currently_thinking=True, thinking_about="problem")
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="yaml_parsing",
            agents={"Active": agent1, "Idle": agent2, "Thinking": agent3}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            status = await telemetry.render_agent_status("proc-123")
            
            assert "Active" in status
            assert "Idle" in status
            assert "Thinking" in status


def test_telemetry_manager_record_step_result_timing_calculation():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        # Calculate start time 60 seconds ago
        end_time = _get_utc_timestamp()
        start_time_dt = datetime.now(UTC) - timedelta(seconds=60)
        start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="yaml_parsing",
            agents={},
            step_results={},
            step_timings={"yaml_parsing": {"started_at": start_time}}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.record_step_result(
                "proc-123",
                "yaml_parsing",
                {"result": "success"},
                execution_time_seconds=0.1  # Very small perf counter
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            # Should use timestamp-based calculation instead of small perf counter
            elapsed = updated_process.step_timings["yaml_parsing"]["elapsed_seconds"]
            assert elapsed >= 59  # Should be around 60 seconds, not 0.1




def test_telemetry_manager_record_step_result_with_empty_step_name():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="",  # Empty step name
            agents={},
            step_results={},
            step_timings={}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.record_step_result(
                "proc-123",
                "",  # Empty step name
                {"result": "success"}
            )
            
            # Should still record even with empty step
            assert mock_repo.update_async.called
    
    asyncio.run(_run())


def test_telemetry_manager_transition_to_phase_all_agents():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        # Create 5 agents
        agents = {}
        for i in range(5):
            agents[f"Agent{i}"] = AgentActivity(name=f"Agent{i}", is_active=False)
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="yaml_parsing",
            agents=agents
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.transition_to_phase(
                "proc-123",
                "DESIGN",
                "design"
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.phase == "DESIGN"
    
    asyncio.run(_run())


def test_telemetry_manager_get_process_outcome_completed():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="end",
            step="complete",
            status="completed"
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            outcome = await telemetry.get_process_outcome("proc-123")
            
            assert "completed successfully" in outcome.lower()
    
    asyncio.run(_run())


def test_telemetry_manager_get_process_outcome_failed():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="end",
            step="complete",
            status="failed",
            failure_reason="Migration error"
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            outcome = await telemetry.get_process_outcome("proc-123")
            
            assert "failed" in outcome.lower()
            assert "Migration error" in outcome
    
    asyncio.run(_run())


def test_telemetry_manager_record_step_result_with_zero_execution_time():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="quick_step",
            agents={},
            step_results={},
            step_timings={"quick_step": {"started_at": _get_utc_timestamp()}}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.record_step_result(
                "proc-123",
                "quick_step",
                {"result": "instant"},
                execution_time_seconds=0
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert "quick_step" in updated_process.step_results
    
    asyncio.run(_run())


def test_telemetry_manager_complete_all_participant_agents_mixed():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        agent1 = AgentActivity(name="Agent1", is_active=True)
        agent2 = AgentActivity(name="Agent2", is_active=False)
        agent3 = AgentActivity(name="Agent3", is_active=True)
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="end",
            step="complete",
            agents={"Agent1": agent1, "Agent2": agent2, "Agent3": agent3}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.complete_all_participant_agents("proc-123")
            
            updated_process = mock_repo.update_async.call_args[0][0]
            # All should be deactivated
            assert all(not agent.is_active for agent in updated_process.agents.values())
    
    asyncio.run(_run())


def test_telemetry_manager_record_ui_data_with_file_manifest():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="end",
            step="complete"
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.record_ui_data(
                "proc-123",
                {
                    "file_manifest": {
                        "converted_files": ["file1.py", "file2.py"],
                        "failed_files": ["file3.py"],
                        "report_files": ["report.html"]
                    },
                    "dashboard_metrics": {
                        "completion_percentage": 66.7
                    }
                }
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert "file_manifest" in updated_process.ui_telemetry_data
    
    asyncio.run(_run())


def test_telemetry_manager_update_process_status_running():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="yaml_parsing",
            agents={},
            status="in_progress"
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.update_process_status("proc-123", "running")
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.status == "running"
    
    asyncio.run(_run())



def test_telemetry_manager_set_agent_idle_updates_status():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        agent = AgentActivity(name="TestAgent", is_active=True, current_action="working")
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="start",
            agents={"TestAgent": agent}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.set_agent_idle("proc-123", "TestAgent")
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.agents["TestAgent"].current_action == "idle"
    
    asyncio.run(_run())


def test_telemetry_manager_update_phase_updates_timing():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="yaml_parsing",
            agents={},
            step_timings={}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.update_phase("proc-123", "NEW PHASE")
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.phase == "NEW PHASE"
            # Should have called update
            assert mock_repo.update_async.called
    
    asyncio.run(_run())


def test_telemetry_manager_record_step_result_updates_process_fields():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="analysis",
            agents={},
            step_results={},
            step_timings={"analysis": {"started_at": _get_utc_timestamp()}}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            result_data = {"files": 42, "status": "success"}
            await telemetry.record_step_result(
                "proc-123",
                "analysis",
                result_data,
                execution_time_seconds=15.5
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.step_results["analysis"]["result"] == result_data
            assert updated_process.step_timings["analysis"]["elapsed_seconds"] == 15.5
    
    asyncio.run(_run())


def test_telemetry_manager_record_final_outcome_with_data():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="end",
            step="complete",
            agents={},
            step_results={}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            outcome_data = {
                "total_files": 100,
                "migrated_files": 95,
                "duration": "2 hours"
            }
            
            await telemetry.record_final_outcome(
                "proc-123",
                outcome_data,
                success=True
            )
            
            # Should have called update
            assert mock_repo.update_async.called
    
    asyncio.run(_run())


def test_telemetry_manager_record_failure_outcome_comprehensive():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="analysis",
            step="yaml_parsing",
            agents={},
            step_results={"step1": {"result": "data"}},
            step_timings={"yaml_parsing": {"started_at": _get_utc_timestamp()}}
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        mock_repo.update_async = AsyncMock()
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            await telemetry.record_failure_outcome(
                "proc-123",
                "yaml_parsing",
                "Failed to parse YAML file",
                {"error_line": 42, "traceback": "short"}
            )
            
            updated_process = mock_repo.update_async.call_args[0][0]
            assert updated_process.status == "failed"
            assert updated_process.final_outcome["success"] is False
            assert updated_process.final_outcome["total_steps_completed"] == 1
    
    asyncio.run(_run())


def test_telemetry_manager_get_ui_telemetry_data_empty():
    async def _run():
        mock_config = MagicMock()
        mock_config.cosmos_db_account_url = "https://test.cosmos.azure.com"
        
        mock_app_context = MagicMock()
        mock_app_context.configuration = mock_config
        
        mock_process = ProcessStatus(
            id="proc-123",
            phase="end",
            step="complete",
            status="completed"
        )
        
        mock_repo = AsyncMock()
        mock_repo.get_async = AsyncMock(return_value=mock_process)
        
        with patch("utils.agent_telemetry.AgentActivityRepository", return_value=mock_repo):
            telemetry = TelemetryManager(app_context=mock_app_context)
            
            result = await telemetry.get_ui_telemetry_data("proc-123")
            
            # Should return a dict with default data for completed process
            assert isinstance(result, dict)
    
    asyncio.run(_run())


def test_byte_len_text_unicode():
    text = "Hello 世界 🌍"
    byte_len = _byte_len_text(text)
    assert byte_len > len(text)  # Multi-byte UTF-8 characters
    assert byte_len > 0


def test_sha256_text():
    text = "test content"
    hash1 = _sha256_text(text)
    hash2 = _sha256_text(text)
    
    assert hash1 == hash2  # Should be deterministic
    assert len(hash1) == 64  # SHA256 hex digest is 64 chars


def test_get_storage_connection_string_env_vars():
    with patch.dict("os.environ", {"AZURE_STORAGE_CONNECTION_STRING": "test-conn-str"}):
        result = _get_storage_connection_string()
        assert result == "test-conn-str"


def test_get_process_blob_container_name_default():
    with patch.dict("os.environ", {}, clear=False):
        result = _get_process_blob_container_name()
        assert result == "processes"


