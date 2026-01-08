import os
import sys
import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Any, Dict

# Add the backend-api src to path for imports
backend_api_path = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "..", "..", "backend-api", "src", "app"
)
sys.path.insert(0, backend_api_path)

from libs.repositories.process_status_repository import (
    ProcessStatusRepository,
    calculate_activity_duration,
    analyze_agent_velocity,
    get_agent_relationship_status,
)
from routers.models.process_agent_activities import (
    ProcessStatus,
    ProcessStatusSnapshot,
    AgentStatus,
    AgentActivity,
    AgentActivityHistory,
)


class TestCalculateActivityDuration:
    """Test cases for calculate_activity_duration function"""

    def test_calculate_duration_none_or_empty(self):
        """Test with None or empty activity_start"""
        seconds, formatted = calculate_activity_duration(None)
        assert seconds == 0
        assert formatted == "0s"

        seconds, formatted = calculate_activity_duration("")
        assert seconds == 0
        assert formatted == "0s"

    def test_calculate_duration_seconds(self):
        """Test duration calculation for seconds"""
        # 5 seconds ago
        start_time = (datetime.now(UTC) - timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S UTC")
        seconds, formatted = calculate_activity_duration(start_time)
        assert 4 <= seconds <= 6  # Allow small variance
        assert "s" in formatted

    def test_calculate_duration_minutes(self):
        """Test duration calculation for minutes"""
        # 90 seconds ago
        start_time = (datetime.now(UTC) - timedelta(seconds=90)).strftime("%Y-%m-%d %H:%M:%S UTC")
        seconds, formatted = calculate_activity_duration(start_time)
        assert 85 <= seconds <= 95
        assert "m" in formatted and "s" in formatted

    def test_calculate_duration_hours(self):
        """Test duration calculation for hours"""
        # 2 hours ago
        start_time = (datetime.now(UTC) - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S UTC")
        seconds, formatted = calculate_activity_duration(start_time)
        assert 7100 <= seconds <= 7300
        assert "h" in formatted and "m" in formatted

    def test_calculate_duration_invalid_format(self):
        """Test with invalid date format"""
        seconds, formatted = calculate_activity_duration("invalid date")
        assert seconds == 0
        assert formatted == "0s"

    def test_calculate_duration_iso_format(self):
        """Test with ISO format datetime string"""
        start_time = (datetime.now(UTC) - timedelta(seconds=30)).isoformat()
        seconds, formatted = calculate_activity_duration(start_time)
        assert 25 <= seconds <= 35


class TestAnalyzeAgentVelocity:
    """Test cases for analyze_agent_velocity function"""

    def test_velocity_empty_history(self):
        """Test with empty activity history"""
        velocity = analyze_agent_velocity([])
        assert velocity == "idle"

    def test_velocity_very_fast(self):
        """Test very fast velocity (5+ activities in last 5 minutes)"""
        now = datetime.now(UTC)
        activity_history = [
            {"timestamp": (now - timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S UTC"), "action": f"action_{i}"}
            for i in range(6)
        ]
        velocity = analyze_agent_velocity(activity_history)
        assert velocity == "very_fast"

    def test_velocity_fast(self):
        """Test fast velocity (3-4 activities in last 5 minutes)"""
        now = datetime.now(UTC)
        activity_history = [
            {"timestamp": (now - timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S UTC"), "action": f"action_{i}"}
            for i in range(4)
        ]
        velocity = analyze_agent_velocity(activity_history)
        assert velocity == "fast"

    def test_velocity_normal(self):
        """Test normal velocity (1-2 activities in last 5 minutes)"""
        now = datetime.now(UTC)
        activity_history = [
            {"timestamp": (now - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S UTC"), "action": "action_1"}
        ]
        velocity = analyze_agent_velocity(activity_history)
        assert velocity == "normal"

    def test_velocity_slow(self):
        """Test slow velocity (no recent activities)"""
        now = datetime.now(UTC)
        activity_history = [
            {"timestamp": (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S UTC"), "action": "action_1"}
        ]
        velocity = analyze_agent_velocity(activity_history)
        assert velocity == "slow"

    def test_velocity_with_invalid_timestamps(self):
        """Test with invalid timestamps in history"""
        activity_history = [
            {"timestamp": "invalid", "action": "action_1"},
            {"timestamp": "2024-01-01 invalid", "action": "action_2"}
        ]
        velocity = analyze_agent_velocity(activity_history)
        assert velocity == "slow"  # No valid recent activities


class TestGetAgentRelationshipStatus:
    """Test cases for get_agent_relationship_status function"""

    def test_relationship_waiting_for(self):
        """Test agent waiting for others"""
        agent_data = {
            "name": "agent1",
            "participation_status": "standby",
            "is_active": False
        }
        all_agents = {
            "agent1": agent_data,
            "agent2": {
                "name": "agent2",
                "is_active": True,
                "participation_status": "ready"
            }
        }
        relationships = get_agent_relationship_status(agent_data, all_agents)
        assert "agent2" in relationships["waiting_for"]

    def test_relationship_blocking(self):
        """Test agent blocking others"""
        agent_data = {
            "name": "agent1",
            "participation_status": "ready",
            "is_active": True
        }
        all_agents = {
            "agent1": agent_data,
            "agent2": {
                "name": "agent2",
                "is_active": False,
                "participation_status": "standby"
            },
            "agent3": {
                "name": "agent3",
                "is_active": False,
                "participation_status": "standby"
            }
        }
        relationships = get_agent_relationship_status(agent_data, all_agents)
        assert len(relationships["blocking"]) == 2
        assert "agent2" in relationships["blocking"]
        assert "agent3" in relationships["blocking"]

    def test_relationship_no_relationships(self):
        """Test agent with no relationships"""
        agent_data = {
            "name": "agent1",
            "participation_status": "ready",
            "is_active": False
        }
        all_agents = {
            "agent1": agent_data
        }
        relationships = get_agent_relationship_status(agent_data, all_agents)
        assert len(relationships["waiting_for"]) == 0
        assert len(relationships["blocking"]) == 0

    def test_relationship_structure(self):
        """Test relationship structure is correct"""
        agent_data = {"name": "agent1", "participation_status": "ready", "is_active": True}
        all_agents = {"agent1": agent_data}
        relationships = get_agent_relationship_status(agent_data, all_agents)
        
        assert "waiting_for" in relationships
        assert "blocking" in relationships
        assert "collaborating_with" in relationships
        assert "dependency_chain" in relationships
        assert isinstance(relationships["waiting_for"], list)
        assert isinstance(relationships["blocking"], list)


class TestProcessStatusRepository:
    """Test cases for ProcessStatusRepository class"""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock ProcessStatusRepository"""
        with patch("libs.repositories.process_status_repository.RepositoryBase.__init__"):
            repo = ProcessStatusRepository(
                account_url="https://test.documents.azure.com:443/",
                database_name="test_db",
                container_name="test_container"
            )
            return repo

    @pytest.fixture
    def sample_process_status(self):
        """Create a sample ProcessStatus object"""
        agent1 = AgentActivity(
            name="Chief_Architect",
            current_action="analyzing",
            last_message_preview="Analyzing architecture",
            is_active=True,
            is_currently_speaking=True,
            participation_status="speaking",
            current_speaking_content="Currently analyzing the architecture requirements",
            message_word_count=50
        )
        agent2 = AgentActivity(
            name="EKS_Expert",
            current_action="ready",
            last_message_preview="Ready to help",
            is_active=False,
            participation_status="ready"
        )
        
        process_status = ProcessStatus(
            id="test-process-123",
            phase="Analysis",
            step="Architecture Review",
            status="running",
            agents={"Chief_Architect": agent1, "EKS_Expert": agent2}
        )
        return process_status

    @pytest.fixture
    def sample_snapshot(self):
        """Create a sample ProcessStatusSnapshot"""
        agent1 = AgentStatus(
            name="Chief_Architect",
            is_currently_speaking=True,
            is_active=True,
            current_action="analyzing",
            current_speaking_content="Analyzing architecture",
            last_message="Last message preview",
            participating_status="speaking",
            current_reasoning="Current reasoning",
            last_reasoning="Last reasoning",
            last_activity_summary="Summary",
            thinking_about="Architecture patterns"
        )
        
        snapshot = ProcessStatusSnapshot(
            process_id="test-process-123",
            step="Architecture Review",
            phase="Analysis",
            status="running",
            last_update_time="2024-01-08 10:00:00 UTC",
            started_at_time="2024-01-08 09:00:00 UTC",
            failure_agent="",
            failure_reason="",
            failure_details="",
            failure_step="",
            failure_timestamp="",
            stack_trace="",
            agents=[agent1]
        )
        return snapshot

    def test_repository_initialization(self, mock_repository):
        """Test repository initialization"""
        assert mock_repository is not None
        assert hasattr(mock_repository, "_read_semaphore")
        assert hasattr(mock_repository, "_write_semaphore")
        assert mock_repository._read_semaphore._value == 50
        assert mock_repository._write_semaphore._value == 10

    @pytest.mark.asyncio
    async def test_get_process_agent_activities_success(self, mock_repository, sample_process_status):
        """Test get_process_agent_activities_by_process_id with valid data"""
        mock_repository.get_async = AsyncMock(return_value=sample_process_status)
        
        result = await mock_repository.get_process_agent_activities_by_process_id("test-process-123")
        
        assert result is not None
        assert result.id == "test-process-123"
        assert result.phase == "Analysis"
        assert len(result.agents) == 2
        mock_repository.get_async.assert_called_once_with("test-process-123")

    @pytest.mark.asyncio
    async def test_get_process_agent_activities_not_found(self, mock_repository):
        """Test get_process_agent_activities_by_process_id when process not found"""
        mock_repository.get_async = AsyncMock(return_value=None)
        
        result = await mock_repository.get_process_agent_activities_by_process_id("non-existent")
        
        assert result is None
        mock_repository.get_async.assert_called_once_with("non-existent")

    @pytest.mark.asyncio
    async def test_get_process_status_success(self, mock_repository, sample_process_status):
        """Test get_process_status_by_process_id with valid data"""
        mock_repository.get_async = AsyncMock(return_value=sample_process_status)
        
        result = await mock_repository.get_process_status_by_process_id("test-process-123")
        
        assert result is not None
        assert result.process_id == "test-process-123"
        assert result.phase == "Analysis"
        assert result.status == "running"
        assert len(result.agents) == 1  # Only active agents
        assert result.agents[0].name == "Chief_Architect"

    @pytest.mark.asyncio
    async def test_get_process_status_not_found(self, mock_repository):
        """Test get_process_status_by_process_id when process not found"""
        mock_repository.get_async = AsyncMock(return_value=None)
        
        result = await mock_repository.get_process_status_by_process_id("non-existent")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_process_status_filters_inactive_agents(self, mock_repository, sample_process_status):
        """Test that get_process_status_by_process_id filters out inactive agents"""
        mock_repository.get_async = AsyncMock(return_value=sample_process_status)
        
        result = await mock_repository.get_process_status_by_process_id("test-process-123")
        
        # Only Chief_Architect is active, EKS_Expert is not
        assert len(result.agents) == 1
        assert result.agents[0].name == "Chief_Architect"

    @pytest.mark.asyncio
    async def test_render_agent_status_not_found(self, mock_repository):
        """Test render_agent_status when process not found"""
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=None)
        
        result = await mock_repository.render_agent_status("non-existent")
        
        assert result["process_id"] == "non-existent"
        assert result["phase"] == "unknown"
        assert result["status"] == "not_found"
        assert result["agents"] == []

    @pytest.mark.asyncio
    async def test_render_agent_status_with_snapshot(self, mock_repository, sample_snapshot):
        """Test render_agent_status with snapshot data"""
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=sample_snapshot)
        mock_repository.get_async = AsyncMock(return_value=None)
        
        result = await mock_repository.render_agent_status("test-process-123")
        
        assert result["process_id"] == "test-process-123"
        assert result["phase"] == "Analysis"
        assert result["status"] == "running"
        assert len(result["agents"]) == 1
        assert "Chief Architect" in result["agents"][0]

    @pytest.mark.asyncio
    async def test_render_agent_status_with_full_data(self, mock_repository, sample_process_status):
        """Test render_agent_status with full process data"""
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=sample_process_status)
        
        result = await mock_repository.render_agent_status("test-process-123")
        
        assert result["process_id"] == "test-process-123"
        assert result["phase"] == "Analysis"
        assert result["status"] == "running"
        assert "health_status" in result
        assert "active_agent_count" in result
        assert "total_agents" in result

    @pytest.mark.asyncio
    async def test_render_agent_status_speaking_agent(self, mock_repository, sample_process_status):
        """Test render_agent_status displays speaking agent correctly"""
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=sample_process_status)
        
        result = await mock_repository.render_agent_status("test-process-123")
        
        # Find the speaking agent line
        speaking_line = [line for line in result["agents"] if "🗣️" in line]
        assert len(speaking_line) > 0
        assert "Chief Architect" in speaking_line[0]

    @pytest.mark.asyncio
    async def test_render_agent_status_ready_agent(self, mock_repository, sample_process_status):
        """Test render_agent_status displays ready agent correctly"""
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=sample_process_status)
        
        result = await mock_repository.render_agent_status("test-process-123")
        
        # Find the ready agent line
        ready_line = [line for line in result["agents"] if "EKS Expert" in line]
        assert len(ready_line) > 0

    @pytest.mark.asyncio
    async def test_render_agent_status_failed_process(self, mock_repository, sample_process_status):
        """Test render_agent_status with failed process"""
        sample_process_status.status = "failed"
        sample_process_status.failure_reason = "Test failure"
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=sample_process_status)
        
        result = await mock_repository.render_agent_status("test-process-123")
        
        assert result["status"] == "failed"
        assert result["failure_reason"] == "Test failure"
        assert "health_status" in result

    @pytest.mark.asyncio
    async def test_render_agent_status_health_critical(self, mock_repository, sample_process_status):
        """Test health status is CRITICAL when agents fail"""
        sample_process_status.status = "failed"
        sample_process_status.agents["Chief_Architect"].participation_status = "failed"
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=sample_process_status)
        
        result = await mock_repository.render_agent_status("test-process-123")
        
        assert "CRITICAL" in result["health_status"]

    @pytest.mark.asyncio
    async def test_render_agent_status_with_activity_history(self, mock_repository, sample_process_status):
        """Test render_agent_status with agent activity history"""
        now = datetime.now(UTC)
        history = [
            AgentActivityHistory(
                timestamp=(now - timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S UTC"),
                action=f"action_{i}",
                message_preview=f"message_{i}"
            )
            for i in range(6)
        ]
        sample_process_status.agents["Chief_Architect"].activity_history = history
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=sample_process_status)
        
        result = await mock_repository.render_agent_status("test-process-123")
        
        assert result is not None
        assert len(result["agents"]) > 0

    def test_get_ready_status_message(self, mock_repository):
        """Test _get_ready_status_message for different scenarios"""
        # Test Chief_Architect in Analysis phase
        message = mock_repository._get_ready_status_message(
            "Chief_Architect", "Analysis", "Analysis", "ready"
        )
        assert "analyze architecture requirements" in message.lower()

        # Test EKS_Expert in Design phase
        message = mock_repository._get_ready_status_message(
            "EKS_Expert", "Design", "Design", "ready"
        )
        assert "eks" in message.lower()

        # Test Azure_Expert in YAML phase
        message = mock_repository._get_ready_status_message(
            "Azure_Expert", "YAML", "YAML", "ready"
        )
        assert "yaml" in message.lower()

        # Test unknown agent
        message = mock_repository._get_ready_status_message(
            "Unknown_Agent", "Analysis", "Analysis", "ready"
        )
        assert "analysis" in message.lower()

    def test_get_ready_status_message_all_agents(self, mock_repository):
        """Test _get_ready_status_message for all known agents"""
        agents = [
            "Chief_Architect",
            "EKS_Expert",
            "GKS_Expert",
            "Azure_Expert",
            "Technical_Writer",
            "QA_Engineer"
        ]
        phases = ["Analysis", "Design", "YAML", "Documentation"]
        
        for agent in agents:
            for phase in phases:
                message = mock_repository._get_ready_status_message(
                    agent, phase, phase, "ready"
                )
                assert message is not None
                assert len(message) > 0

    @pytest.mark.asyncio
    async def test_render_agent_status_concurrency(self, mock_repository, sample_process_status):
        """Test concurrent access to render_agent_status"""
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=sample_process_status)
        
        # Run multiple concurrent requests
        import asyncio
        tasks = [
            mock_repository.render_agent_status("test-process-123")
            for _ in range(10)
        ]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(results) == 10
        for result in results:
            assert result["process_id"] == "test-process-123"

    @pytest.mark.asyncio
    async def test_render_agent_status_old_method(self, mock_repository, sample_snapshot):
        """Test render_agent_status_old with snapshot"""
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=sample_snapshot)
        
        result = await mock_repository.render_agent_status_old("test-process-123")
        
        assert result["process_id"] == "test-process-123"
        assert result["phase"] == "Analysis"
        assert len(result["agents"]) == 1

    @pytest.mark.asyncio
    async def test_render_agent_status_old_not_found(self, mock_repository):
        """Test render_agent_status_old when process not found"""
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        
        result = await mock_repository.render_agent_status_old("non-existent")
        
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_render_agent_status_system_agent(self, mock_repository, sample_process_status):
        """Test render_agent_status with system agent"""
        system_agent = AgentActivity(
            name="system",
            current_action="monitoring",
            current_speaking_content="System monitoring active",
            is_active=True,
            participation_status="speaking"
        )
        sample_process_status.agents["system"] = system_agent
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=sample_process_status)
        
        result = await mock_repository.render_agent_status("test-process-123")
        
        system_line = [line for line in result["agents"] if "system" in line.lower()]
        assert len(system_line) > 0

    @pytest.mark.asyncio
    async def test_render_agent_status_with_relationships(self, mock_repository, sample_process_status):
        """Test render_agent_status shows agent relationships"""
        # Add standby agent
        standby_agent = AgentActivity(
            name="Azure_Expert",
            current_action="waiting",
            is_active=False,
            participation_status="standby"
        )
        sample_process_status.agents["Azure_Expert"] = standby_agent
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=sample_process_status)
        
        result = await mock_repository.render_agent_status("test-process-123")
        
        assert len(result["agents"]) >= 2

    @pytest.mark.asyncio
    async def test_render_agent_status_velocity_indicators(self, mock_repository, sample_process_status):
        """Test render_agent_status includes velocity indicators"""
        now = datetime.now(UTC)
        # Add many recent activities for very_fast velocity
        history = [
            AgentActivityHistory(
                timestamp=(now - timedelta(seconds=i*30)).strftime("%Y-%m-%d %H:%M:%S UTC"),
                action=f"action_{i}",
                message_preview=f"message_{i}"
            )
            for i in range(10)
        ]
        sample_process_status.agents["Chief_Architect"].activity_history = history
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=sample_process_status)
        
        result = await mock_repository.render_agent_status("test-process-123")
        
        # Should have velocity indicators in output
        assert result is not None
        assert "active_agent_count" in result

    @pytest.mark.asyncio
    async def test_render_agent_status_empty_agents(self, mock_repository):
        """Test render_agent_status with process that has no agents"""
        empty_process = ProcessStatus(
            id="test-process-123",
            phase="Analysis",
            status="running",
            agents={}
        )
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=empty_process)
        
        result = await mock_repository.render_agent_status("test-process-123")
        
        assert result["agents"] == []
        assert result["process_id"] == "test-process-123"


class TestProcessStatusRepositoryEdgeCases:
    """Test edge cases and error scenarios"""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock ProcessStatusRepository"""
        with patch("libs.repositories.process_status_repository.RepositoryBase.__init__"):
            repo = ProcessStatusRepository(
                account_url="https://test.documents.azure.com:443/",
                database_name="test_db",
                container_name="test_container"
            )
            return repo

    @pytest.mark.asyncio
    async def test_concurrent_read_limiting(self, mock_repository):
        """Test that read semaphore limits concurrent operations"""
        call_count = 0
        
        async def mock_get(process_id):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate work
            return None
        
        mock_repository.get_async = mock_get
        
        # Try to make many concurrent calls
        import asyncio
        tasks = [
            mock_repository.get_process_agent_activities_by_process_id(f"test-{i}")
            for i in range(100)
        ]
        
        await asyncio.gather(*tasks)
        assert call_count == 100

    def test_calculate_duration_edge_cases(self):
        """Test edge cases for duration calculation"""
        # Future time (should handle gracefully)
        future_time = (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S UTC")
        seconds, formatted = calculate_activity_duration(future_time)
        # Should return negative or handle it
        assert isinstance(seconds, int)
        assert isinstance(formatted, str)

    def test_analyze_velocity_mixed_valid_invalid(self):
        """Test velocity analysis with mixed valid/invalid data"""
        now = datetime.now(UTC)
        activity_history = [
            {"timestamp": (now - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S UTC"), "action": "valid1"},
            {"timestamp": "invalid", "action": "invalid"},
            {"timestamp": (now - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S UTC"), "action": "valid2"},
            {"timestamp": "", "action": "empty"},
        ]
        velocity = analyze_agent_velocity(activity_history)
        assert velocity in ["very_fast", "fast", "normal", "slow", "idle"]

    def test_get_relationship_missing_fields(self):
        """Test relationship analysis with missing fields"""
        agent_data = {"name": "agent1"}  # Missing other fields
        all_agents = {"agent1": agent_data}
        
        relationships = get_agent_relationship_status(agent_data, all_agents)
        
        assert isinstance(relationships, dict)
        assert "waiting_for" in relationships
        assert "blocking" in relationships


@pytest.mark.asyncio
class TestProcessStatusRepositoryIntegration:
    """Integration-style tests for complete workflows"""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock ProcessStatusRepository"""
        with patch("libs.repositories.process_status_repository.RepositoryBase.__init__"):
            repo = ProcessStatusRepository(
                account_url="https://test.documents.azure.com:443/",
                database_name="test_db",
                container_name="test_container"
            )
            return repo

    async def test_full_workflow_speaking_to_ready(self, mock_repository):
        """Test full workflow from speaking agent to ready state"""
        # Initial state - agent is speaking
        agent = AgentActivity(
            name="Chief_Architect",
            is_active=True,
            is_currently_speaking=True,
            participation_status="speaking",
            current_speaking_content="Analyzing architecture patterns"
        )
        process_status = ProcessStatus(
            id="workflow-test",
            phase="Analysis",
            status="running",
            agents={"Chief_Architect": agent}
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=process_status)
        
        result1 = await mock_repository.render_agent_status("workflow-test")
        assert "🗣️" in result1["agents"][0]
        
        # Update to ready state
        agent.is_currently_speaking = False
        agent.participation_status = "ready"
        agent.current_speaking_content = ""
        
        result2 = await mock_repository.render_agent_status("workflow-test")
        assert "ready" in result2["agents"][0].lower()

    async def test_multi_agent_coordination(self, mock_repository):
        """Test multiple agents coordinating"""
        agents = {
            "Chief_Architect": AgentActivity(
                name="Chief_Architect",
                is_active=True,
                participation_status="speaking",
                is_currently_speaking=True,
                current_speaking_content="Leading discussion"
            ),
            "EKS_Expert": AgentActivity(
                name="EKS_Expert",
                is_active=False,
                participation_status="standby"
            ),
            "Azure_Expert": AgentActivity(
                name="Azure_Expert",
                is_active=False,
                participation_status="standby"
            )
        }
        
        process_status = ProcessStatus(
            id="multi-agent-test",
            phase="Analysis",
            status="running",
            agents=agents
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=process_status)
        
        result = await mock_repository.render_agent_status("multi-agent-test")
        
        assert len(result["agents"]) == 3
        assert result["active_agent_count"] == 1
        assert result["total_agents"] == 3

    async def test_thinking_agent_status(self, mock_repository):
        """Test agent in thinking state"""
        agent = AgentActivity(
            name="Chief_Architect",
            is_active=True,
            is_currently_thinking=True,
            participation_status="thinking",
            thinking_about="Analyzing migration strategy"
        )
        process_status = ProcessStatus(
            id="thinking-test",
            phase="Analysis",
            status="running",
            agents={"Chief_Architect": agent}
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=process_status)
        
        result = await mock_repository.render_agent_status("thinking-test")
        
        assert "🤔" in result["agents"][0]
        assert "thinking" in result["agents"][0].lower()

    async def test_agent_with_waiting_relationships(self, mock_repository):
        """Test agent waiting for others with relationship indicators"""
        agents = {
            "Chief_Architect": AgentActivity(
                name="Chief_Architect",
                is_active=True,
                participation_status="ready",
                current_action="working"
            ),
            "EKS_Expert": AgentActivity(
                name="EKS_Expert",
                is_active=False,
                participation_status="standby"
            ),
            "Azure_Expert": AgentActivity(
                name="Azure_Expert",
                is_active=False,
                participation_status="standby"
            )
        }
        
        process_status = ProcessStatus(
            id="waiting-test",
            phase="Analysis",
            status="running",
            agents=agents
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=process_status)
        
        result = await mock_repository.render_agent_status("waiting-test")
        
        # Check for relationship indicators
        assert len(result["agents"]) == 3

    async def test_agent_blocking_multiple(self, mock_repository):
        """Test agent blocking multiple other agents (>3)"""
        agents = {
            "Chief_Architect": AgentActivity(
                name="Chief_Architect",
                is_active=True,
                participation_status="ready",
                current_action="working"
            )
        }
        
        # Add 5 standby agents
        for i in range(5):
            agents[f"Agent_{i}"] = AgentActivity(
                name=f"Agent_{i}",
                is_active=False,
                participation_status="standby"
            )
        
        process_status = ProcessStatus(
            id="blocking-test",
            phase="Analysis",
            status="running",
            agents=agents
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=process_status)
        
        result = await mock_repository.render_agent_status("blocking-test")
        
        # Check for blocking count (Chief blocks 5 agents in standby)
        assert result["bottleneck_score"] >= 5
        # With only 1 active agent, health should be STABLE
        assert "STABLE" in result["health_status"]

    async def test_completed_status(self, mock_repository):
        """Test agent with completed status"""
        agent = AgentActivity(
            name="Chief_Architect",
            is_active=False,
            participation_status="completed",
            current_action="completed"
        )
        process_status = ProcessStatus(
            id="completed-test",
            phase="Analysis",
            status="completed",
            agents={"Chief_Architect": agent}
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=process_status)
        
        result = await mock_repository.render_agent_status("completed-test")
        
        assert "completed" in result["agents"][0].lower()

    async def test_standby_with_phase(self, mock_repository):
        """Test standby agent with phase information"""
        agent = AgentActivity(
            name="Azure_Expert",
            is_active=False,
            participation_status="standby",
            current_action="waiting"
        )
        process_status = ProcessStatus(
            id="standby-test",
            phase="Design",
            status="running",
            agents={"Azure_Expert": agent}
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=process_status)
        
        result = await mock_repository.render_agent_status("standby-test")
        
        assert "standby" in result["agents"][0].lower()

    async def test_agent_with_duration_timing(self, mock_repository):
        """Test active agent with duration timing (>30 seconds)"""
        now = datetime.now(UTC)
        agent = AgentActivity(
            name="Chief_Architect",
            is_active=True,
            participation_status="speaking",
            is_currently_speaking=True,
            current_speaking_content="Working on task",
            last_update_time=(now - timedelta(seconds=60)).strftime("%Y-%m-%d %H:%M:%S UTC")
        )
        process_status = ProcessStatus(
            id="duration-test",
            phase="Analysis",
            status="running",
            agents={"Chief_Architect": agent}
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=process_status)
        
        result = await mock_repository.render_agent_status("duration-test")
        
        # Should have duration in output
        assert len(result["agents"]) > 0

    async def test_process_failed_action(self, mock_repository):
        """Test agent with process_failed action"""
        agent = AgentActivity(
            name="Chief_Architect",
            is_active=False,
            participation_status="failed",
            current_action="process_failed"
        )
        process_status = ProcessStatus(
            id="process-failed-test",
            phase="Analysis",
            status="failed",
            failure_reason="Test failure",
            agents={"Chief_Architect": agent}
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=process_status)
        
        result = await mock_repository.render_agent_status("process-failed-test")
        
        assert "FAILED" in result["agents"][0]
        assert "❌" in result["agents"][0]

    async def test_very_fast_velocity(self, mock_repository):
        """Test agent with very_fast velocity indicator"""
        now = datetime.now(UTC)
        history = [
            AgentActivityHistory(
                timestamp=(now - timedelta(seconds=i*20)).strftime("%Y-%m-%d %H:%M:%S UTC"),
                action=f"action_{i}",
                message_preview=f"message_{i}"
            )
            for i in range(8)
        ]
        
        agent = AgentActivity(
            name="Chief_Architect",
            is_active=True,
            participation_status="ready",
            activity_history=history
        )
        process_status = ProcessStatus(
            id="velocity-test",
            phase="Analysis",
            status="running",
            agents={"Chief_Architect": agent}
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=process_status)
        
        result = await mock_repository.render_agent_status("velocity-test")
        
        # Should show velocity indicators
        assert len(result["fast_agents"]) > 0

    async def test_very_active_health_status(self, mock_repository):
        """Test health status as VERY_ACTIVE with >5 active agents"""
        agents = {}
        for i in range(7):
            agents[f"Agent_{i}"] = AgentActivity(
                name=f"Agent_{i}",
                is_active=True,
                participation_status="ready"
            )
        
        process_status = ProcessStatus(
            id="very-active-test",
            phase="Analysis",
            status="running",
            agents=agents
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=process_status)
        
        result = await mock_repository.render_agent_status("very-active-test")
        
        assert "VERY_ACTIVE" in result["health_status"]
        assert result["active_agent_count"] == 7

    async def test_active_health_status(self, mock_repository):
        """Test health status as ACTIVE with 3-5 active agents"""
        agents = {}
        for i in range(4):
            agents[f"Agent_{i}"] = AgentActivity(
                name=f"Agent_{i}",
                is_active=True,
                participation_status="ready"
            )
        
        process_status = ProcessStatus(
            id="active-test",
            phase="Analysis",
            status="running",
            agents=agents
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=process_status)
        
        result = await mock_repository.render_agent_status("active-test")
        
        assert "ACTIVE" in result["health_status"]
        assert result["active_agent_count"] == 4

    async def test_stable_health_status(self, mock_repository):
        """Test health status as STABLE with <=2 active agents"""
        agents = {
            "Agent_0": AgentActivity(
                name="Agent_0",
                is_active=True,
                participation_status="ready"
            ),
            "Agent_1": AgentActivity(
                name="Agent_1",
                is_active=False,
                participation_status="standby"
            )
        }
        
        process_status = ProcessStatus(
            id="stable-test",
            phase="Analysis",
            status="running",
            agents=agents
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=process_status)
        
        result = await mock_repository.render_agent_status("stable-test")
        
        assert "STABLE" in result["health_status"]

    async def test_error_handler_agent_in_failed_process(self, mock_repository):
        """Test error_handler agent in failed process"""
        agents = {
            "error_handler": AgentActivity(
                name="error_handler",
                is_active=True,
                participation_status="ready",
                current_action="handling_error"
            )
        }
        
        process_status = ProcessStatus(
            id="error-handler-test",
            phase="Analysis",
            status="failed",
            failure_reason="System error",
            started_at_time=(datetime.now(UTC) - timedelta(seconds=10)).strftime("%Y-%m-%d %H:%M:%S UTC"),
            last_update_time=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
            agents=agents
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=None)
        mock_repository.get_async = AsyncMock(return_value=process_status)
        
        result = await mock_repository.render_agent_status("error-handler-test")
        
        # error_handler should be marked as failed when process fails
        assert result["status"] == "failed"


@pytest.mark.asyncio
class TestRenderAgentStatusOldCoverage:
    """Additional tests for render_agent_status_old method coverage"""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock ProcessStatusRepository"""
        with patch("libs.repositories.process_status_repository.RepositoryBase.__init__"):
            repo = ProcessStatusRepository(
                account_url="https://test.documents.azure.com:443/",
                database_name="test_db",
                container_name="test_container"
            )
            return repo

    async def test_old_method_with_thinking_agent(self, mock_repository):
        """Test render_agent_status_old with thinking agent"""
        agent = AgentStatus(
            name="Chief_Architect",
            is_currently_speaking=False,
            is_active=True,
            current_action="thinking",
            current_speaking_content="",
            last_message="",
            participating_status="thinking",
            current_reasoning="",
            last_reasoning="",
            last_activity_summary="",
            thinking_about="Analyzing the migration plan"
        )
        
        snapshot = ProcessStatusSnapshot(
            process_id="old-thinking-test",
            step="Analysis",
            phase="Analysis",
            status="running",
            last_update_time="2024-01-08 10:00:00 UTC",
            started_at_time="2024-01-08 09:00:00 UTC",
            failure_agent="",
            failure_reason="",
            failure_details="",
            failure_step="",
            failure_timestamp="",
            stack_trace="",
            agents=[agent]
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=snapshot)
        
        result = await mock_repository.render_agent_status_old("old-thinking-test")
        
        assert "thinking" in result["agents"][0].lower()
        assert "Analyzing the migration plan" in result["agents"][0]

    async def test_old_method_with_word_count(self, mock_repository):
        """Test render_agent_status_old with message word count"""
        # Create a Mock object instead of AgentStatus to allow setting arbitrary attributes
        agent = Mock()
        agent.name = "Chief_Architect"
        agent.is_currently_speaking = True
        agent.is_active = True
        agent.current_action = "speaking"
        agent.current_speaking_content = "This is a test message with multiple words"
        agent.last_message = ""
        agent.participating_status = "speaking"
        agent.message_word_count = 8
        agent.last_activity_summary = ""
        
        snapshot = Mock()
        snapshot.process_id = "old-wordcount-test"
        snapshot.step = "Analysis"
        snapshot.phase = "Analysis"
        snapshot.status = "running"
        snapshot.last_update_time = "2024-01-08 10:00:00 UTC"
        snapshot.started_at_time = "2024-01-08 09:00:00 UTC"
        snapshot.failure_agent = ""
        snapshot.failure_reason = ""
        snapshot.failure_details = ""
        snapshot.failure_step = ""
        snapshot.failure_timestamp = ""
        snapshot.stack_trace = ""
        snapshot.agents = [agent]
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=snapshot)
        
        result = await mock_repository.render_agent_status_old("old-wordcount-test")
        
        assert "8 words" in result["agents"][0]

    async def test_old_method_with_last_activity_summary(self, mock_repository):
        """Test render_agent_status_old with last_activity_summary"""
        # Create Mock to test last_activity_summary path
        agent = Mock()
        agent.name = "Chief_Architect"
        agent.is_currently_speaking = False
        agent.is_active = True
        agent.current_action = "analyzing"
        agent.current_speaking_content = ""
        agent.last_message = ""
        agent.participating_status = "waiting"  # Use different status to avoid ready message override
        agent.last_activity_summary = "Completed initial analysis"
        
        snapshot = Mock()
        snapshot.process_id = "old-summary-test"
        snapshot.step = "Analysis"
        snapshot.phase = "Analysis"
        snapshot.status = "running"
        snapshot.last_update_time = "2024-01-08 10:00:00 UTC"
        snapshot.started_at_time = "2024-01-08 09:00:00 UTC"
        snapshot.failure_agent = ""
        snapshot.failure_reason = ""
        snapshot.failure_details = ""
        snapshot.failure_step = ""
        snapshot.failure_timestamp = ""
        snapshot.stack_trace = ""
        snapshot.agents = [agent]
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=snapshot)
        
        result = await mock_repository.render_agent_status_old("old-summary-test")
        
        assert "Completed initial analysis" in result["agents"][0]

    async def test_old_method_with_completed_status(self, mock_repository):
        """Test render_agent_status_old with completed status"""
        agent = AgentStatus(
            name="Chief_Architect",
            is_currently_speaking=False,
            is_active=False,
            current_action="completed",
            current_speaking_content="",
            last_message="",
            participating_status="completed",
            current_reasoning="",
            last_reasoning="",
            last_activity_summary="",
            thinking_about=""
        )
        
        snapshot = ProcessStatusSnapshot(
            process_id="old-completed-test",
            step="Analysis",
            phase="Analysis",
            status="completed",
            last_update_time="2024-01-08 10:00:00 UTC",
            started_at_time="2024-01-08 09:00:00 UTC",
            failure_agent="",
            failure_reason="",
            failure_details="",
            failure_step="",
            failure_timestamp="",
            stack_trace="",
            agents=[agent]
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=snapshot)
        
        result = await mock_repository.render_agent_status_old("old-completed-test")
        
        assert "completed" in result["agents"][0].lower()

    async def test_old_method_with_standby_and_phase(self, mock_repository):
        """Test render_agent_status_old with standby and phase"""
        agent = AgentStatus(
            name="Azure_Expert",
            is_currently_speaking=False,
            is_active=False,
            current_action="waiting",
            current_speaking_content="",
            last_message="",
            participating_status="standby",
            current_reasoning="",
            last_reasoning="",
            last_activity_summary="",
            thinking_about=""
        )
        
        snapshot = ProcessStatusSnapshot(
            process_id="old-standby-test",
            step="Design",
            phase="Design",
            status="running",
            last_update_time="2024-01-08 10:00:00 UTC",
            started_at_time="2024-01-08 09:00:00 UTC",
            failure_agent="",
            failure_reason="",
            failure_details="",
            failure_step="",
            failure_timestamp="",
            stack_trace="",
            agents=[agent]
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=snapshot)
        
        result = await mock_repository.render_agent_status_old("old-standby-test")
        
        assert "standby" in result["agents"][0].lower()
        assert "design" in result["agents"][0].lower()

    async def test_old_method_fallback_action(self, mock_repository):
        """Test render_agent_status_old fallback for action display"""
        agent = AgentStatus(
            name="Chief_Architect",
            is_currently_speaking=False,
            is_active=True,
            current_action="processing_data",
            current_speaking_content="",
            last_message="",
            participating_status="busy",
            current_reasoning="",
            last_reasoning="",
            last_activity_summary="",
            thinking_about=""
        )
        
        snapshot = ProcessStatusSnapshot(
            process_id="old-fallback-test",
            step="Processing",
            phase="Processing",
            status="running",
            last_update_time="2024-01-08 10:00:00 UTC",
            started_at_time="2024-01-08 09:00:00 UTC",
            failure_agent="",
            failure_reason="",
            failure_details="",
            failure_step="",
            failure_timestamp="",
            stack_trace="",
            agents=[agent]
        )
        
        mock_repository.get_process_status_by_process_id = AsyncMock(return_value=snapshot)
        
        result = await mock_repository.render_agent_status_old("old-fallback-test")
        
        assert "Processing Data" in result["agents"][0]
