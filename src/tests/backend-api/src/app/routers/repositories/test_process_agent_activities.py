# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for ProcessStatusRepository class.
Tests the repository functionality including initialization and process status retrieval.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Any

# Import the class under test
from app.routers.repositories.process_agent_activities import ProcessStatusRepository
from app.routers.models.process_agent_activities import (
    ProcessStatus,
    ProcessStatusSnapshot,
    AgentStatus,
    AgentActivity,
)


class TestProcessStatusRepository:
    """Test cases for ProcessStatusRepository class."""

    @pytest.fixture
    def repository_params(self):
        """Create sample repository parameters."""
        return {
            "account_url": "https://test-cosmos.documents.azure.com:443/",
            "database_name": "test-database",
            "container_name": "process-status-container"
        }

    @pytest.fixture
    def process_status_repository(self, repository_params):
        """Create a ProcessStatusRepository instance."""
        return ProcessStatusRepository(**repository_params)

    @pytest.fixture
    def sample_agent_activity(self):
        """Create a sample AgentActivity for testing."""
        return AgentActivity(
            name="migration-agent",
            current_action="processing",
            last_message_preview="Processing YAML files",
            is_currently_speaking=False,
            participation_status="ready"
        )

    @pytest.fixture
    def sample_process_status(self, sample_agent_activity):
        """Create a sample ProcessStatus object."""
        return ProcessStatus(
            id="test-process-123",
            phase="migration",
            step="file-processing",
            status="running",
            agents={"migration-agent": sample_agent_activity},
            last_update_time="2024-01-01 10:00:00 UTC",
            started_at_time="2024-01-01 09:00:00 UTC"
        )

    @pytest.fixture
    def expected_agent_status(self):
        """Create expected AgentStatus for comparison."""
        return AgentStatus(
            name="migration-agent",
            is_currently_speaking=False,
            is_active=False,
            current_action="processing",
            current_speaking_content="",
            last_message="Processing YAML files",
            participating_status="ready",
            last_reasoning="",
            last_activity_summary="",
            current_reasoning="",
            thinking_about="",
            reasoning_steps=[]
        )

    @pytest.fixture
    def expected_process_snapshot(self, expected_agent_status):
        """Create expected ProcessStatusSnapshot for comparison."""
        return ProcessStatusSnapshot(
            process_id="test-process-123",
            step="file-processing",
            phase="migration",
            status="running",
            agents=[expected_agent_status],
            last_update_time="",
            started_at_time=""
        )


class TestProcessStatusRepositoryInit(TestProcessStatusRepository):
    """Test cases for ProcessStatusRepository initialization."""

    def test_init_with_valid_parameters(self, repository_params):
        """Test that ProcessStatusRepository initializes correctly with valid parameters."""
        repo = ProcessStatusRepository(**repository_params)
        
        # The actual attributes are set by the parent class, so we verify the object is created
        assert isinstance(repo, ProcessStatusRepository)
        assert hasattr(repo, 'find_one_async')  # Inherited from RepositoryBase

    def test_init_stores_parameters_via_super(self, repository_params):
        """Test that initialization passes parameters to parent class."""
        with patch('app.routers.repositories.process_agent_activities.RepositoryBase.__init__') as mock_super_init:
            ProcessStatusRepository(**repository_params)
            mock_super_init.assert_called_once_with(**repository_params)

    def test_init_with_different_parameters(self):
        """Test initialization with different parameter values."""
        params = {
            "account_url": "https://different-cosmos.documents.azure.com:443/",
            "database_name": "different-database", 
            "container_name": "different-container"
        }
        
        repo = ProcessStatusRepository(**params)
        assert isinstance(repo, ProcessStatusRepository)

    def test_init_inheritance_from_repository_base(self, repository_params):
        """Test that ProcessStatusRepository properly inherits from RepositoryBase."""
        repo = ProcessStatusRepository(**repository_params)
        
        # Check that it has the generic typing
        assert hasattr(repo, '__class_getitem__')  # Generic class capability
        # Check that it has expected parent class methods
        assert hasattr(repo, 'find_one_async')
        assert callable(getattr(repo, 'find_one_async'))


class TestGetProcessStatusByProcessId(TestProcessStatusRepository):
    """Test cases for get_process_status_by_process_id method."""

    @pytest.mark.asyncio
    async def test_get_process_status_by_process_id_success(
        self, process_status_repository, sample_process_status
    ):
        """Test successful retrieval of process status."""
        process_id = "test-process-123"
        
        # Mock the find_one_async method
        process_status_repository.find_one_async = AsyncMock(return_value=sample_process_status)
        
        result = await process_status_repository.get_process_status_by_process_id(process_id)
        
        # Verify the method was called with correct parameters
        process_status_repository.find_one_async.assert_called_once_with(predicate={"id": process_id})
        
        # Verify the result structure
        assert result is not None
        assert result.process_id == "test-process-123"
        assert result.step == "file-processing"
        assert result.phase == "migration"
        assert result.status == "running"
        assert len(result.agents) == 1

    @pytest.mark.asyncio
    async def test_get_process_status_by_process_id_not_found(self, process_status_repository):
        """Test behavior when process status is not found."""
        process_id = "non-existent-process"
        
        # Mock find_one_async to return None (not found)
        process_status_repository.find_one_async = AsyncMock(return_value=None)
        
        result = await process_status_repository.get_process_status_by_process_id(process_id)
        
        # Verify the method was called with correct parameters
        process_status_repository.find_one_async.assert_called_once_with(predicate={"id": process_id})
        
        # Verify None is returned
        assert result is None

    @pytest.mark.asyncio
    async def test_get_process_status_by_process_id_agent_mapping(
        self, process_status_repository, sample_agent_activity
    ):
        """Test that agent data is correctly mapped to AgentStatus objects."""
        # Create process status with specific agent data
        sample_agent_activity.name = "test-agent"
        sample_agent_activity.current_action = "analyzing"
        sample_agent_activity.last_message_preview = "Analyzing configuration files"
        sample_agent_activity.is_currently_speaking = True
        sample_agent_activity.participation_status = "thinking"
        
        process_status = ProcessStatus(
            id="test-process-456",
            phase="analysis", 
            step="configuration-check",
            status="running",
            agents={"test-agent": sample_agent_activity}
        )
        
        process_status_repository.find_one_async = AsyncMock(return_value=process_status)
        
        result = await process_status_repository.get_process_status_by_process_id("test-process-456")
        
        # Verify agent mapping
        assert len(result.agents) == 1
        agent = result.agents[0]
        assert agent.name == "test-agent"
        assert agent.current_action == "analyzing"
        assert agent.last_message == "Analyzing configuration files"
        assert agent.is_currently_speaking is True
        assert agent.participating_status == "thinking"

    @pytest.mark.asyncio
    async def test_get_process_status_by_process_id_multiple_agents(
        self, process_status_repository
    ):
        """Test handling of multiple agents in process status."""
        # Create multiple agent activities
        agent1 = AgentActivity(
            name="migration-agent",
            current_action="migrating",
            last_message_preview="Migrating resources",
            is_currently_speaking=False,
            participation_status="ready"
        )
        
        agent2 = AgentActivity(
            name="validation-agent", 
            current_action="validating",
            last_message_preview="Validating configurations",
            is_currently_speaking=True,
            participation_status="speaking"
        )
        
        process_status = ProcessStatus(
            id="multi-agent-process",
            phase="deployment",
            step="validation",
            status="running",
            agents={
                "migration-agent": agent1,
                "validation-agent": agent2
            }
        )
        
        process_status_repository.find_one_async = AsyncMock(return_value=process_status)
        
        result = await process_status_repository.get_process_status_by_process_id("multi-agent-process")
        
        # Verify multiple agents are handled correctly
        assert len(result.agents) == 2
        
        agent_names = [agent.name for agent in result.agents]
        assert "migration-agent" in agent_names
        assert "validation-agent" in agent_names
        
        # Check specific agent properties
        for agent in result.agents:
            if agent.name == "migration-agent":
                assert agent.current_action == "migrating"
                assert agent.last_message == "Migrating resources"
                assert agent.is_currently_speaking is False
                assert agent.participating_status == "ready"
            elif agent.name == "validation-agent":
                assert agent.current_action == "validating"
                assert agent.last_message == "Validating configurations"
                assert agent.is_currently_speaking is True
                assert agent.participating_status == "speaking"

    @pytest.mark.asyncio
    async def test_get_process_status_by_process_id_no_agents(self, process_status_repository):
        """Test handling of process status with no agents."""
        process_status = ProcessStatus(
            id="no-agents-process",
            phase="initialization",
            step="setup",
            status="starting",
            agents={}  # Empty agents dictionary
        )
        
        process_status_repository.find_one_async = AsyncMock(return_value=process_status)
        
        result = await process_status_repository.get_process_status_by_process_id("no-agents-process")
        
        # Verify empty agents list is handled correctly
        assert result is not None
        assert result.process_id == "no-agents-process"
        assert len(result.agents) == 0
        assert result.agents == []

    @pytest.mark.asyncio
    async def test_get_process_status_by_process_id_all_fields(self, process_status_repository):
        """Test that all fields from ProcessStatus are correctly mapped to ProcessStatusSnapshot."""
        sample_agent = AgentActivity(
            name="complete-agent",
            current_action="complete-action",
            last_message_preview="Complete message",
            is_currently_speaking=False,
            participation_status="completed"
        )
        
        process_status = ProcessStatus(
            id="complete-process",
            phase="complete-phase",
            step="complete-step", 
            status="completed",
            agents={"complete-agent": sample_agent}
        )
        
        process_status_repository.find_one_async = AsyncMock(return_value=process_status)
        
        result = await process_status_repository.get_process_status_by_process_id("complete-process")
        
        # Verify all main fields are mapped correctly
        assert result.process_id == "complete-process"
        assert result.phase == "complete-phase"
        assert result.step == "complete-step"
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_get_process_status_by_process_id_predicate_format(self, process_status_repository):
        """Test that the correct predicate format is used for database query."""
        process_id = "predicate-test-process"
        
        process_status_repository.find_one_async = AsyncMock(return_value=None)
        
        await process_status_repository.get_process_status_by_process_id(process_id)
        
        # Verify the exact predicate format used
        expected_predicate = {"id": process_id}
        process_status_repository.find_one_async.assert_called_once_with(predicate=expected_predicate)

    @pytest.mark.asyncio 
    async def test_get_process_status_by_process_id_agent_status_defaults(
        self, process_status_repository
    ):
        """Test that AgentStatus objects have correct default values for fields not in AgentActivity."""
        agent_activity = AgentActivity(
            name="minimal-agent",
            # Only setting required fields, others will use defaults
        )
        
        process_status = ProcessStatus(
            id="minimal-test",
            agents={"minimal-agent": agent_activity}
        )
        
        process_status_repository.find_one_async = AsyncMock(return_value=process_status)
        
        result = await process_status_repository.get_process_status_by_process_id("minimal-test")
        
        agent = result.agents[0]
        # Test AgentStatus fields that come from AgentActivity
        assert agent.name == "minimal-agent"
        assert agent.current_action == "idle"  # AgentActivity default
        assert agent.last_message == ""  # From last_message_preview default
        assert agent.is_currently_speaking is False  # AgentActivity default
        assert agent.participating_status == "ready"  # AgentActivity default
        
        # Test AgentStatus fields that have their own defaults (not from AgentActivity)
        assert agent.is_active is False  # AgentStatus default
        assert agent.current_speaking_content == ""  # AgentStatus default
        assert agent.last_reasoning == ""  # AgentStatus default
        assert agent.last_activity_summary == ""  # AgentStatus default
        assert agent.current_reasoning == ""  # AgentStatus default
        assert agent.thinking_about == ""  # AgentStatus default
        assert agent.reasoning_steps == []  # AgentStatus default


class TestProcessStatusRepositoryIntegration(TestProcessStatusRepository):
    """Integration test cases for ProcessStatusRepository."""

    @pytest.mark.asyncio
    async def test_repository_method_signature_compatibility(self, process_status_repository):
        """Test that the method signatures are compatible with expected usage."""
        # Test that method exists and has correct signature
        method = getattr(process_status_repository, 'get_process_status_by_process_id')
        assert callable(method)
        
        # Test with mock to avoid database dependency
        process_status_repository.find_one_async = AsyncMock(return_value=None)
        
        # Should not raise any exceptions with string input
        result = await method("test-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_exception_handling_in_find_one_async(self, process_status_repository):
        """Test that exceptions from find_one_async are properly propagated."""
        # Mock find_one_async to raise an exception
        process_status_repository.find_one_async = AsyncMock(side_effect=Exception("Database connection error"))
        
        # Verify that the exception is propagated
        with pytest.raises(Exception, match="Database connection error"):
            await process_status_repository.get_process_status_by_process_id("test-process")

    def test_class_inheritance_and_typing(self, process_status_repository):
        """Test the class inheritance and generic typing."""
        # Test that it has expected parent class methods
        assert hasattr(process_status_repository, 'find_one_async')
        assert callable(getattr(process_status_repository, 'find_one_async'))
        
        # Verify typing (ProcessStatus, str)
        # This tests that the generic parameters are correctly set
        assert hasattr(process_status_repository, '__class_getitem__')

    @pytest.mark.asyncio
    async def test_edge_case_empty_string_process_id(self, process_status_repository):
        """Test behavior with empty string process ID."""
        process_status_repository.find_one_async = AsyncMock(return_value=None)
        
        result = await process_status_repository.get_process_status_by_process_id("")
        
        # Should handle empty string gracefully
        process_status_repository.find_one_async.assert_called_once_with(predicate={"id": ""})
        assert result is None

    @pytest.mark.asyncio
    async def test_edge_case_very_long_process_id(self, process_status_repository):
        """Test behavior with very long process ID."""
        long_process_id = "a" * 1000  # Very long process ID
        
        process_status_repository.find_one_async = AsyncMock(return_value=None)
        
        result = await process_status_repository.get_process_status_by_process_id(long_process_id)
        
        # Should handle long string gracefully
        process_status_repository.find_one_async.assert_called_once_with(predicate={"id": long_process_id})
        assert result is None

    def test_repository_has_expected_methods(self, process_status_repository):
        """Test that repository has all expected public methods."""
        expected_methods = [
            'get_process_status_by_process_id',
            'find_one_async'  # Inherited from parent
        ]
        
        for method_name in expected_methods:
            assert hasattr(process_status_repository, method_name)
            assert callable(getattr(process_status_repository, method_name))

    @pytest.mark.asyncio
    async def test_concurrent_calls_independence(self, process_status_repository):
        """Test that concurrent calls to the method are independent."""
        # Setup different return values for different calls
        call_count = 0
        async def mock_find_one_side_effect(predicate):
            nonlocal call_count
            call_count += 1
            if predicate["id"] == "process-1":
                return ProcessStatus(
                    id="process-1", 
                    status="running",
                    last_update_time="2024-01-01 10:00:00 UTC",
                    started_at_time="2024-01-01 09:00:00 UTC"
                )
            elif predicate["id"] == "process-2": 
                return ProcessStatus(
                    id="process-2", 
                    status="completed",
                    last_update_time="2024-01-01 11:00:00 UTC",
                    started_at_time="2024-01-01 09:00:00 UTC"
                )
            return None
        
        process_status_repository.find_one_async = AsyncMock(side_effect=mock_find_one_side_effect)
        
        # Make concurrent calls
        import asyncio
        results = await asyncio.gather(
            process_status_repository.get_process_status_by_process_id("process-1"),
            process_status_repository.get_process_status_by_process_id("process-2"),
            process_status_repository.get_process_status_by_process_id("process-3")
        )
        
        # Verify independent results
        assert results[0] is not None
        assert results[0].process_id == "process-1"
        assert results[0].status == "running"
        
        assert results[1] is not None
        assert results[1].process_id == "process-2"
        assert results[1].status == "completed"
        
        assert results[2] is None
        
        # Verify all calls were made
        assert call_count == 3


class TestProcessStatusRepositoryErrorCases(TestProcessStatusRepository):
    """Test cases for error handling in ProcessStatusRepository."""

    @pytest.mark.asyncio
    async def test_invalid_agent_data_handling(self, process_status_repository):
        """Test handling of potentially invalid agent data."""
        # Create an agent with minimal data that might cause issues
        minimal_agent = AgentActivity(name="minimal")  # Only name provided
        
        process_status = ProcessStatus(
            id="minimal-agent-test",
            agents={"minimal": minimal_agent}
        )
        
        process_status_repository.find_one_async = AsyncMock(return_value=process_status)
        
        # Should not raise exceptions
        result = await process_status_repository.get_process_status_by_process_id("minimal-agent-test")
        
        assert result is not None
        assert len(result.agents) == 1
        assert result.agents[0].name == "minimal"

    @pytest.mark.asyncio
    async def test_none_agent_values_handling(self, process_status_repository):
        """Test that the method handles potential None values in agent data gracefully."""
        # This test ensures robustness against potential data issues
        # Test with valid data but edge cases (empty strings)
        agent = AgentActivity(
            name="edge-case-agent",
            current_action="",  # Empty string
            last_message_preview="",  # Empty string
            participation_status=""  # Empty string
        )
        
        process_status = ProcessStatus(
            id="edge-case-test",
            agents={"edge-case-agent": agent}
        )
        
        process_status_repository.find_one_async = AsyncMock(return_value=process_status)
        
        result = await process_status_repository.get_process_status_by_process_id("edge-case-test")
        
        assert result is not None
        assert len(result.agents) == 1
        agent_result = result.agents[0]
        assert agent_result.name == "edge-case-agent"
        assert agent_result.current_action == ""
        assert agent_result.last_message == ""
        assert agent_result.participating_status == ""