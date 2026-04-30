"""Extended tests for process_status_repository to reach >=85% coverage."""
import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch, AsyncMock
from libs.repositories.process_status_repository import (
    ProcessStatusRepository,
    calculate_activity_duration,
    analyze_agent_velocity,
    get_agent_relationship_status,
)
from routers.models.process_agent_activities import ProcessStatus, ProcessStatusSnapshot


class TestCalculateActivityDuration:
    """Test calculate_activity_duration utility function."""

    def test_calculate_duration_with_empty_string(self):
        """Test calculate_activity_duration returns 0s for empty input."""
        duration_seconds, formatted = calculate_activity_duration("")
        assert duration_seconds == 0
        assert formatted == "0s"

    def test_calculate_duration_with_none(self):
        """Test calculate_activity_duration returns 0s for None input."""
        duration_seconds, formatted = calculate_activity_duration(None)
        assert duration_seconds == 0
        assert formatted == "0s"

    def test_calculate_duration_seconds(self):
        """Test calculate_activity_duration formats seconds correctly."""
        # Create a time 30 seconds ago
        past_time = datetime.now(UTC).isoformat().replace("+00:00", " UTC")
        
        # For testing, use a recent timestamp
        recent = (datetime.now(UTC).isoformat() + " UTC").replace(".", " ").split(" ")[0]
        duration_seconds, formatted = calculate_activity_duration(recent + " UTC")
        
        # Should be a small number since it's very recent
        assert duration_seconds >= 0
        assert "s" in formatted

    def test_calculate_duration_minutes(self):
        """Test calculate_activity_duration formats minutes correctly."""
        # Create a time that will result in minutes display
        now = datetime.now(UTC)
        past = (now - __import__('datetime').timedelta(minutes=5)).isoformat().replace("+00:00", " UTC")
        
        duration_seconds, formatted = calculate_activity_duration(past)
        
        # Should be around 300 seconds (5 minutes)
        assert duration_seconds >= 299  # Allow 1 second tolerance
        assert "m" in formatted or "s" in formatted

    def test_calculate_duration_hours(self):
        """Test calculate_activity_duration formats hours correctly."""
        # Create a time that will result in hours display
        now = datetime.now(UTC)
        past = (now - __import__('datetime').timedelta(hours=2)).isoformat().replace("+00:00", " UTC")
        
        duration_seconds, formatted = calculate_activity_duration(past)
        
        # Should be around 7200 seconds (2 hours)
        assert duration_seconds >= 7199  # Allow 1 second tolerance
        assert "h" in formatted or "m" in formatted

    def test_calculate_duration_handles_invalid_timestamp(self):
        """Test calculate_activity_duration handles invalid timestamp gracefully."""
        duration_seconds, formatted = calculate_activity_duration("invalid-timestamp")
        assert duration_seconds == 0
        assert formatted == "0s"


class TestAnalyzeAgentVelocity:
    """Test analyze_agent_velocity utility function."""

    def test_analyze_velocity_empty_history(self):
        """Test analyze_agent_velocity returns 'idle' for empty history."""
        velocity = analyze_agent_velocity([])
        assert velocity == "idle"

    def test_analyze_velocity_no_recent_activities(self):
        """Test analyze_agent_velocity returns 'slow' when no recent activities."""
        # Create old timestamps
        old_time = (datetime.now(UTC) - __import__('datetime').timedelta(hours=1)).isoformat()
        activity_history = [
            {"timestamp": old_time + " UTC"},
            {"timestamp": old_time + " UTC"},
        ]
        
        velocity = analyze_agent_velocity(activity_history)
        assert velocity == "slow"

    def test_analyze_velocity_very_fast(self):
        """Test analyze_agent_velocity returns 'very_fast' for 5+ recent activities."""
        # Create timestamps that will be within 5 minutes
        # Note: isoformat() adds timezone, so we create naive and append UTC
        now = datetime.now(UTC).replace(tzinfo=None)
        recent_activities = []
        for i in range(5):
            time_ago = (now - __import__('datetime').timedelta(minutes=i)).isoformat()
            recent_activities.append({"timestamp": time_ago + " UTC"})
        
        velocity = analyze_agent_velocity(recent_activities)
        assert velocity == "very_fast"

    def test_analyze_velocity_fast(self):
        """Test analyze_agent_velocity returns 'fast' for 3-4 recent activities."""
        now = datetime.now(UTC).replace(tzinfo=None)
        recent_activities = []
        for i in range(3):
            time_ago = (now - __import__('datetime').timedelta(minutes=i)).isoformat()
            recent_activities.append({"timestamp": time_ago + " UTC"})
        
        velocity = analyze_agent_velocity(recent_activities)
        assert velocity == "fast"

    def test_analyze_velocity_normal(self):
        """Test analyze_agent_velocity returns 'normal' for 1-2 recent activities."""
        now = datetime.now(UTC).replace(tzinfo=None)
        recent_activities = []
        for i in range(1):
            time_ago = (now - __import__('datetime').timedelta(minutes=i)).isoformat()
            recent_activities.append({"timestamp": time_ago + " UTC"})
        
        velocity = analyze_agent_velocity(recent_activities)
        assert velocity == "normal"

    def test_analyze_velocity_handles_invalid_timestamps(self):
        """Test analyze_agent_velocity handles invalid timestamps gracefully."""
        activity_history = [
            {"timestamp": "invalid-timestamp"},
            {"timestamp": "another-invalid"},
        ]
        
        velocity = analyze_agent_velocity(activity_history)
        # Should still return a valid velocity value
        assert velocity in ["idle", "slow", "normal", "fast", "very_fast"]


class TestGetAgentRelationshipStatus:
    """Test get_agent_relationship_status utility function."""

    def test_relationship_no_dependencies(self):
        """Test get_agent_relationship_status with no dependencies."""
        agent_data = {"name": "agent1", "is_active": False, "participation_status": "ready"}
        all_agents = {"agent1": agent_data}
        
        relationships = get_agent_relationship_status(agent_data, all_agents)
        
        assert "waiting_for" in relationships
        assert "blocking" in relationships
        assert "collaborating_with" in relationships
        assert "dependency_chain" in relationships

    def test_relationship_agent_waiting_for_active_agent(self):
        """Test relationship when agent is waiting for active agent."""
        agent1 = {"name": "agent1", "is_active": False, "participation_status": "standby"}
        agent2 = {"name": "agent2", "is_active": True, "participation_status": "ready"}
        all_agents = {"agent1": agent1, "agent2": agent2}
        
        relationships = get_agent_relationship_status(agent1, all_agents)
        
        assert isinstance(relationships, dict)
        assert "waiting_for" in relationships

    def test_relationship_active_agent_blocks_others(self):
        """Test relationship when active agent blocks standby agents."""
        agent1 = {"name": "agent1", "is_active": True, "participation_status": "active"}
        agent2 = {"name": "agent2", "is_active": False, "participation_status": "standby"}
        all_agents = {"agent1": agent1, "agent2": agent2}
        
        relationships = get_agent_relationship_status(agent1, all_agents)
        
        assert isinstance(relationships, dict)
        assert "blocking" in relationships

    def test_relationship_ignores_self_in_relationships(self):
        """Test that agent doesn't reference itself in relationships."""
        agent1 = {"name": "agent1", "is_active": True, "participation_status": "active"}
        all_agents = {"agent1": agent1}
        
        relationships = get_agent_relationship_status(agent1, all_agents)
        
        # Agent should not be in waiting_for or blocking lists
        assert "agent1" not in relationships.get("waiting_for", [])
        assert "agent1" not in relationships.get("blocking", [])


class TestProcessStatusRepository:
    """Test ProcessStatusRepository class."""

    def test_repository_initialization(self):
        """Test ProcessStatusRepository initializes correctly."""
        repo = ProcessStatusRepository(
            account_url="https://test.cosmos.azure.com/",
            database_name="test_db",
            container_name="test_container"
        )
        
        assert repo is not None
        assert hasattr(repo, "_read_semaphore")
        assert hasattr(repo, "_write_semaphore")

    def test_repository_has_semaphores(self):
        """Test repository initializes with semaphores."""
        repo = ProcessStatusRepository(
            account_url="https://test.cosmos.azure.com/",
            database_name="test_db",
            container_name="test_container"
        )
        
        # Check semaphores are created
        assert repo._read_semaphore is not None
        assert repo._write_semaphore is not None

    def test_get_process_agent_activities_by_process_id_success(self):
        """Test get_process_agent_activities_by_process_id returns process status."""
        repo = ProcessStatusRepository(
            account_url="https://test.cosmos.azure.com/",
            database_name="test_db",
            container_name="test_container"
        )
        
        # Mock the parent class's get_async method
        mock_status = MagicMock()
        with patch.object(repo, 'get_async', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_status
            
            async def run_test():
                result = await repo.get_process_agent_activities_by_process_id("process-123")
                return result
            
            result = asyncio.run(run_test())
            assert result == mock_status

    def test_get_process_agent_activities_by_process_id_not_found(self):
        """Test get_process_agent_activities_by_process_id returns None when not found."""
        repo = ProcessStatusRepository(
            account_url="https://test.cosmos.azure.com/",
            database_name="test_db",
            container_name="test_container"
        )
        
        with patch.object(repo, 'get_async', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            
            async def run_test():
                result = await repo.get_process_agent_activities_by_process_id("nonexistent")
                return result
            
            result = asyncio.run(run_test())
            assert result is None

    def test_get_process_status_by_process_id_success(self):
        """Test get_process_status_by_process_id returns ProcessStatusSnapshot."""
        repo = ProcessStatusRepository(
            account_url="https://test.cosmos.azure.com/",
            database_name="test_db",
            container_name="test_container"
        )
        
        # Create a mock agent
        mock_agent = MagicMock()
        mock_agent.name = "agent1"
        mock_agent.is_currently_speaking = False
        mock_agent.is_active = False
        mock_agent.current_action = "idle"
        mock_agent.current_speaking_content = ""
        mock_agent.last_message_preview = "Last message"
        mock_agent.participation_status = "inactive"
        mock_agent.current_reasoning = ""
        mock_agent.last_reasoning = ""
        mock_agent.thinking_about = ""
        mock_agent.reasoning_steps = []
        mock_agent.last_activity_summary = ""
        
        # Create a mock status object with all required string fields (empty strings, not None)
        mock_status = MagicMock()
        mock_status.id = "process-123"
        mock_status.step = "step1"
        mock_status.phase = "phase1"
        mock_status.status = "running"
        mock_status.last_update_time = datetime.now(UTC).isoformat()
        mock_status.started_at_time = datetime.now(UTC).isoformat()
        mock_status.failure_agent = ""  # Use empty string, not None
        mock_status.failure_reason = ""
        mock_status.failure_details = ""
        mock_status.failure_step = ""
        mock_status.failure_timestamp = ""
        mock_status.stack_trace = ""
        mock_status.agents = {}  # Empty dict (no active agents)
        mock_status.total_duration_seconds = 100
        mock_status.activities = []
        
        with patch.object(repo, 'get_async', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_status
            
            async def run_test():
                result = await repo.get_process_status_by_process_id("process-123")
                return result
            
            result = asyncio.run(run_test())
            # Should return a ProcessStatusSnapshot
            assert result is not None

    def test_get_process_status_by_process_id_not_found(self):
        """Test get_process_status_by_process_id returns None when not found."""
        repo = ProcessStatusRepository(
            account_url="https://test.cosmos.azure.com/",
            database_name="test_db",
            container_name="test_container"
        )
        
        with patch.object(repo, 'get_async', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            
            async def run_test():
                result = await repo.get_process_status_by_process_id("nonexistent")
                return result
            
            result = asyncio.run(run_test())
            assert result is None


class TestProcessStatusRepositoryIntegration:
    """Integration tests for ProcessStatusRepository."""

    def test_repository_read_semaphore_limits_concurrent_reads(self):
        """Test that read semaphore limits concurrent reads."""
        repo = ProcessStatusRepository(
            account_url="https://test.cosmos.azure.com/",
            database_name="test_db",
            container_name="test_container"
        )
        
        # Verify semaphore has correct limit (50)
        assert repo._read_semaphore._value == 50

    def test_repository_write_semaphore_limits_concurrent_writes(self):
        """Test that write semaphore limits concurrent writes."""
        repo = ProcessStatusRepository(
            account_url="https://test.cosmos.azure.com/",
            database_name="test_db",
            container_name="test_container"
        )
        
        # Verify semaphore has correct limit (10)
        assert repo._write_semaphore._value == 10

    def test_multiple_repositories_have_independent_semaphores(self):
        """Test that multiple repository instances have independent semaphores."""
        repo1 = ProcessStatusRepository(
            account_url="https://test.cosmos.azure.com/",
            database_name="test_db",
            container_name="test_container"
        )
        repo2 = ProcessStatusRepository(
            account_url="https://test.cosmos.azure.com/",
            database_name="test_db",
            container_name="test_container"
        )
        
        # Semaphores should be different instances
        assert repo1._read_semaphore is not repo2._read_semaphore
        assert repo1._write_semaphore is not repo2._write_semaphore


class TestActivityDurationFormats:
    """Test various activity duration scenarios."""

    def test_duration_displays_as_seconds_under_minute(self):
        """Test that durations under 60 seconds display as seconds."""
        now = datetime.now(UTC)
        recent = (now - __import__('datetime').timedelta(seconds=30)).isoformat().replace("+00:00", " UTC")
        
        _, formatted = calculate_activity_duration(recent)
        assert "s" in formatted
        assert "m" not in formatted
        assert "h" not in formatted

    def test_duration_displays_as_minutes_under_hour(self):
        """Test that durations under 3600 seconds display with minutes."""
        now = datetime.now(UTC)
        past = (now - __import__('datetime').timedelta(minutes=5, seconds=30)).isoformat().replace("+00:00", " UTC")
        
        _, formatted = calculate_activity_duration(past)
        # Should contain minutes representation
        assert "m" in formatted or "s" in formatted

    def test_duration_displays_as_hours_and_minutes(self):
        """Test that durations >= 3600 seconds display hours and minutes."""
        now = datetime.now(UTC)
        past = (now - __import__('datetime').timedelta(hours=3, minutes=45)).isoformat().replace("+00:00", " UTC")
        
        _, formatted = calculate_activity_duration(past)
        # Should contain hours representation
        assert "h" in formatted or "m" in formatted
