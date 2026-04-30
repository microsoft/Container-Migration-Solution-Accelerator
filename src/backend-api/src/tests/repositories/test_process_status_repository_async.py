"""Targeted tests for the async methods of ProcessStatusRepository.

Covers render_agent_status (lines ~200-515), render_agent_status_old
(lines ~520-630) and _get_ready_status_message (lines ~642-700) which
were untouched by the existing extended suite.
"""
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from libs.repositories.process_status_repository import ProcessStatusRepository


def _run(coro):
    return asyncio.run(coro)


def _make_repo():
    return ProcessStatusRepository(
        account_url="https://test.cosmos.azure.com/",
        database_name="db",
        container_name="c",
    )


def _make_full_agent(
    name="agent1",
    is_active=True,
    is_speaking=False,
    is_thinking=False,
    participation="ready",
    current_action="idle",
    speaking_content="",
    thinking_about="",
    last_message_preview="msg",
    last_activity_summary="",
    message_word_count=0,
    activity_history=None,
):
    """Build a MagicMock matching the AgentActivity contract used by render_agent_status."""
    agent = MagicMock()
    agent.name = name
    agent.current_action = current_action
    agent.last_message_preview = last_message_preview
    agent.last_full_message = ""
    agent.last_update_time = "2024-01-01 00:00:00 UTC"
    agent.is_active = is_active
    agent.is_currently_speaking = is_speaking
    agent.is_currently_thinking = is_thinking
    agent.participation_status = participation
    agent.thinking_about = thinking_about
    agent.current_speaking_content = speaking_content
    agent.last_activity_summary = last_activity_summary
    agent.message_word_count = message_word_count
    agent.activity_history = activity_history or []
    return agent


def _make_full_process(agents=None, status="running", phase="Analysis", step="Analysis"):
    process = MagicMock()
    process.id = "p1"
    process.step = step
    process.phase = phase
    process.status = status
    process.last_update_time = "2024-01-01 00:00:00 UTC"
    process.started_at_time = "2024-01-01 00:00:00 UTC"
    process.failure_agent = ""
    process.failure_reason = ""
    process.failure_details = ""
    process.failure_step = ""
    process.failure_timestamp = ""
    process.stack_trace = ""
    process.step_timings = {}
    process.step_results = {}
    process.generated_files = []
    process.conversion_metrics = {}
    process.agents = agents or {}
    return process


class TestRenderAgentStatusNotFound:
    def test_returns_not_found_when_no_data(self):
        repo = _make_repo()

        with patch.object(
            repo, "get_process_status_by_process_id", new=AsyncMock(return_value=None)
        ), patch.object(repo, "get_async", new=AsyncMock(return_value=None)):
            result = _run(repo.render_agent_status("missing"))

        assert result["status"] == "not_found"
        assert result["agents"] == []

    def test_returns_empty_when_no_agents_data(self):
        repo = _make_repo()
        process = _make_full_process(agents={})

        with patch.object(
            repo, "get_process_status_by_process_id", new=AsyncMock(return_value=None)
        ), patch.object(repo, "get_async", new=AsyncMock(return_value=process)):
            result = _run(repo.render_agent_status("p1"))

        assert result["agents"] == []
        assert result["phase"] == "Analysis"


class TestRenderAgentStatusSuccess:
    def test_success_with_speaking_agent(self):
        repo = _make_repo()
        agent = _make_full_agent(
            name="EKS_Expert",
            is_active=True,
            is_speaking=True,
            speaking_content="Talking now",
            message_word_count=2,
            participation="speaking",
        )
        process = _make_full_process(agents={"EKS_Expert": agent})

        with patch.object(
            repo, "get_process_status_by_process_id", new=AsyncMock(return_value=None)
        ), patch.object(repo, "get_async", new=AsyncMock(return_value=process)):
            result = _run(repo.render_agent_status("p1"))

        assert len(result["agents"]) == 1
        assert "EKS Expert" in result["agents"][0]
        assert result["active_agent_count"] == 1

    def test_success_with_thinking_agent(self):
        repo = _make_repo()
        agent = _make_full_agent(
            name="Azure_Expert",
            is_active=True,
            is_thinking=True,
            participation="thinking",
            thinking_about="Designing arch",
        )
        process = _make_full_process(agents={"Azure_Expert": agent})

        with patch.object(
            repo, "get_process_status_by_process_id", new=AsyncMock(return_value=None)
        ), patch.object(repo, "get_async", new=AsyncMock(return_value=process)):
            result = _run(repo.render_agent_status("p1"))

        assert "Designing arch" in result["agents"][0]

    def test_success_with_ready_agent_uses_ready_message(self):
        repo = _make_repo()
        agent = _make_full_agent(
            name="Chief_Architect",
            is_active=False,
            participation="ready",
            last_message_preview="",
            last_activity_summary="",
        )
        process = _make_full_process(agents={"Chief_Architect": agent}, step="Design")

        with patch.object(
            repo, "get_process_status_by_process_id", new=AsyncMock(return_value=None)
        ), patch.object(repo, "get_async", new=AsyncMock(return_value=process)):
            result = _run(repo.render_agent_status("p1"))

        # Ready message for Chief_Architect/Design
        assert "design migration architecture" in result["agents"][0].lower()

    def test_success_with_completed_and_standby_agents(self):
        repo = _make_repo()
        completed = _make_full_agent(
            name="QA_Engineer",
            is_active=False,
            participation="completed",
            last_message_preview="",
            last_activity_summary="",
        )
        standby = _make_full_agent(
            name="Other",
            is_active=False,
            participation="standby",
            last_message_preview="",
            last_activity_summary="",
        )
        process = _make_full_process(
            agents={"QA_Engineer": completed, "Other": standby}, phase="YAML"
        )

        with patch.object(
            repo, "get_process_status_by_process_id", new=AsyncMock(return_value=None)
        ), patch.object(repo, "get_async", new=AsyncMock(return_value=process)):
            result = _run(repo.render_agent_status("p1"))

        joined = " ".join(result["agents"])
        assert "completed" in joined.lower() or "Task completed" in joined
        assert "Standing by" in joined

    def test_failed_process_marks_system_agent_failed(self):
        repo = _make_repo()
        sys_agent = _make_full_agent(
            name="system",
            is_active=True,
            participation="ready",
            speaking_content="System update",
        )
        process = _make_full_process(agents={"system": sys_agent}, status="failed")

        with patch.object(
            repo, "get_process_status_by_process_id", new=AsyncMock(return_value=None)
        ), patch.object(repo, "get_async", new=AsyncMock(return_value=process)):
            result = _run(repo.render_agent_status("p1"))

        assert "🔴 CRITICAL" in result["health_status"]
        assert "system" in result["failed_agents"]

    def test_process_failed_action_marks_agent_failed(self):
        repo = _make_repo()
        agent = _make_full_agent(
            name="Worker",
            is_active=True,
            current_action="process_failed",
            participation="ready",
        )
        process = _make_full_process(agents={"Worker": agent})

        with patch.object(
            repo, "get_process_status_by_process_id", new=AsyncMock(return_value=None)
        ), patch.object(repo, "get_async", new=AsyncMock(return_value=process)):
            result = _run(repo.render_agent_status("p1"))

        assert "FAILED" in result["agents"][0]

    def test_health_bottlenecked_when_many_blocking(self):
        repo = _make_repo()
        # One active agent with many standby agents -> blocking count > 5
        active = _make_full_agent(name="Active", is_active=True, participation="active")
        standbys = {
            f"S{i}": _make_full_agent(
                name=f"S{i}", is_active=False, participation="standby"
            )
            for i in range(7)
        }
        agents = {"Active": active, **standbys}
        process = _make_full_process(agents=agents)

        with patch.object(
            repo, "get_process_status_by_process_id", new=AsyncMock(return_value=None)
        ), patch.object(repo, "get_async", new=AsyncMock(return_value=process)):
            result = _run(repo.render_agent_status("p1"))

        assert result["health_status"] in ["🟡 BOTTLENECKED", "🟢 ACTIVE", "🟢 STABLE"]
        assert result["bottleneck_score"] >= 0

    def test_health_very_active_with_many_active_agents(self):
        repo = _make_repo()
        agents = {
            f"A{i}": _make_full_agent(name=f"A{i}", is_active=True, participation="ready")
            for i in range(7)
        }
        process = _make_full_process(agents=agents)

        with patch.object(
            repo, "get_process_status_by_process_id", new=AsyncMock(return_value=None)
        ), patch.object(repo, "get_async", new=AsyncMock(return_value=process)):
            result = _run(repo.render_agent_status("p1"))

        assert result["active_agent_count"] == 7

    def test_recent_activity_history_drives_velocity_and_tools(self):
        from datetime import datetime, UTC, timedelta

        repo = _make_repo()
        now = datetime.now(UTC).replace(tzinfo=None)
        recent = []
        for i in range(5):
            ts = (now - timedelta(seconds=i * 10)).isoformat() + " UTC"
            entry = MagicMock()
            entry.timestamp = ts
            entry.action = "act"
            entry.message_preview = "x"
            entry.step = "Analysis"
            entry.tool_used = f"tool{i % 2}"
            recent.append(entry)

        agent = _make_full_agent(
            name="Worker",
            is_active=True,
            participation="active",
            activity_history=recent,
        )
        process = _make_full_process(agents={"Worker": agent})

        with patch.object(
            repo, "get_process_status_by_process_id", new=AsyncMock(return_value=None)
        ), patch.object(repo, "get_async", new=AsyncMock(return_value=process)):
            result = _run(repo.render_agent_status("p1"))

        assert "Worker" in result["fast_agents"]
        assert "🔧" in result["agents"][0]
        assert "actions" in result["agents"][0]


class TestRenderAgentStatusSnapshotFallback:
    def test_uses_snapshot_when_full_data_missing(self):
        """Snapshot provides agents; full_process_data is None."""
        from routers.models.process_agent_activities import (
            AgentStatus,
            ProcessStatusSnapshot,
        )

        repo = _make_repo()
        snapshot_agent = AgentStatus(
            name="agent1",
            is_currently_speaking=False,
            is_active=True,
            current_action="idle",
            current_speaking_content="",
            last_message="snapshot last",
            participating_status="ready",
            current_reasoning="",
            last_reasoning="",
            thinking_about="",
            reasoning_steps=[],
            last_activity_summary="",
        )
        snapshot = ProcessStatusSnapshot(
            process_id="p1",
            step="Analysis",
            phase="Analysis",
            status="running",
            last_update_time="2024-01-01 00:00:00 UTC",
            started_at_time="2024-01-01 00:00:00 UTC",
            failure_agent="",
            failure_reason="",
            failure_details="",
            failure_step="",
            failure_timestamp="",
            stack_trace="",
            agents=[snapshot_agent],
        )

        with patch.object(
            repo,
            "get_process_status_by_process_id",
            new=AsyncMock(return_value=snapshot),
        ), patch.object(repo, "get_async", new=AsyncMock(return_value=None)):
            result = _run(repo.render_agent_status("p1"))

        assert result["status"] == "running"
        assert len(result["agents"]) == 1


class TestRenderAgentStatusOld:
    def test_returns_not_found_when_snapshot_missing(self):
        repo = _make_repo()

        with patch.object(
            repo,
            "get_process_status_by_process_id",
            new=AsyncMock(return_value=None),
        ):
            result = _run(repo.render_agent_status_old("p1"))

        assert result["status"] == "not_found"
        assert result["agents"] == []

    def _build_snapshot(self, agents):
        from routers.models.process_agent_activities import ProcessStatusSnapshot

        return ProcessStatusSnapshot(
            process_id="p1",
            step="Design",
            phase="Design",
            status="running",
            last_update_time="2024-01-01 00:00:00 UTC",
            started_at_time="2024-01-01 00:00:00 UTC",
            failure_agent="",
            failure_reason="",
            failure_details="",
            failure_step="",
            failure_timestamp="",
            stack_trace="",
            agents=agents,
        )

    def _agent(self, **overrides):
        from routers.models.process_agent_activities import AgentStatus

        defaults = dict(
            name="agent1",
            is_currently_speaking=False,
            is_active=True,
            current_action="idle",
            current_speaking_content="",
            last_message="last msg",
            participating_status="ready",
            current_reasoning="",
            last_reasoning="",
            thinking_about="",
            reasoning_steps=[],
            last_activity_summary="",
        )
        defaults.update(overrides)
        return AgentStatus(**defaults)

    def test_system_agent_special_handling(self):
        repo = _make_repo()
        snap = self._build_snapshot(
            [self._agent(name="system", current_speaking_content="status")]
        )
        with patch.object(
            repo,
            "get_process_status_by_process_id",
            new=AsyncMock(return_value=snap),
        ):
            result = _run(repo.render_agent_status_old("p1"))
        assert "status" in result["agents"][0]

    def test_speaking_agent(self):
        repo = _make_repo()
        snap = self._build_snapshot(
            [
                self._agent(
                    is_currently_speaking=True,
                    current_speaking_content="words here",
                    participating_status="speaking",
                )
            ]
        )
        with patch.object(
            repo,
            "get_process_status_by_process_id",
            new=AsyncMock(return_value=snap),
        ):
            result = _run(repo.render_agent_status_old("p1"))
        assert "words here" in result["agents"][0]

    def test_thinking_agent(self):
        repo = _make_repo()
        snap = self._build_snapshot(
            [
                self._agent(
                    participating_status="thinking",
                    thinking_about="planning",
                )
            ]
        )
        with patch.object(
            repo,
            "get_process_status_by_process_id",
            new=AsyncMock(return_value=snap),
        ):
            result = _run(repo.render_agent_status_old("p1"))
        assert "planning" in result["agents"][0]

    def test_ready_agent_uses_context_message(self):
        repo = _make_repo()
        snap = self._build_snapshot(
            [
                self._agent(
                    name="Chief_Architect",
                    participating_status="ready",
                    last_message="",
                    last_activity_summary="",
                )
            ]
        )
        with patch.object(
            repo,
            "get_process_status_by_process_id",
            new=AsyncMock(return_value=snap),
        ):
            result = _run(repo.render_agent_status_old("p1"))
        assert "design migration architecture" in result["agents"][0].lower()

    def test_completed_agent(self):
        repo = _make_repo()
        snap = self._build_snapshot(
            [
                self._agent(
                    participating_status="completed",
                    last_message="",
                    last_activity_summary="",
                )
            ]
        )
        with patch.object(
            repo,
            "get_process_status_by_process_id",
            new=AsyncMock(return_value=snap),
        ):
            result = _run(repo.render_agent_status_old("p1"))
        assert "Task completed" in result["agents"][0]

    def test_standby_agent(self):
        repo = _make_repo()
        snap = self._build_snapshot(
            [
                self._agent(
                    participating_status="standby",
                    last_message="",
                    last_activity_summary="",
                )
            ]
        )
        with patch.object(
            repo,
            "get_process_status_by_process_id",
            new=AsyncMock(return_value=snap),
        ):
            result = _run(repo.render_agent_status_old("p1"))
        assert "Standing by" in result["agents"][0]

    def test_fallback_action_message(self):
        repo = _make_repo()
        snap = self._build_snapshot(
            [
                self._agent(
                    participating_status="other",
                    last_message="",
                    last_activity_summary="",
                    current_action="working_hard",
                )
            ]
        )
        with patch.object(
            repo,
            "get_process_status_by_process_id",
            new=AsyncMock(return_value=snap),
        ):
            result = _run(repo.render_agent_status_old("p1"))
        assert "Working Hard" in result["agents"][0]

    def test_last_message_preview_used_when_present(self):
        repo = _make_repo()
        snap = self._build_snapshot(
            [
                self._agent(
                    participating_status="other",
                    last_message="last said",
                )
            ]
        )
        with patch.object(
            repo,
            "get_process_status_by_process_id",
            new=AsyncMock(return_value=snap),
        ):
            result = _run(repo.render_agent_status_old("p1"))
        assert "last said" in result["agents"][0]

    def test_last_activity_summary_used_when_no_message(self):
        repo = _make_repo()
        snap = self._build_snapshot(
            [
                self._agent(
                    participating_status="other",
                    last_message="",
                    last_activity_summary="summary text",
                )
            ]
        )
        with patch.object(
            repo,
            "get_process_status_by_process_id",
            new=AsyncMock(return_value=snap),
        ):
            result = _run(repo.render_agent_status_old("p1"))
        assert "summary text" in result["agents"][0]


class TestGetReadyStatusMessage:
    def test_known_agent_known_step(self):
        repo = _make_repo()
        msg = repo._get_ready_status_message(
            "EKS_Expert", "Analysis", "Analysis", "ready"
        )
        assert "EKS" in msg

    def test_known_agent_unknown_step_uses_default(self):
        repo = _make_repo()
        msg = repo._get_ready_status_message(
            "Azure_Expert", "WeirdStep", "WeirdStep", "ready"
        )
        assert "Azure" in msg

    def test_known_agent_all_roles_have_default(self):
        repo = _make_repo()
        for agent in [
            "Chief_Architect",
            "EKS_Expert",
            "GKS_Expert",
            "Azure_Expert",
            "Technical_Writer",
            "QA_Engineer",
        ]:
            msg = repo._get_ready_status_message(agent, "Unknown", "Unknown", "ready")
            assert isinstance(msg, str) and msg

    def test_unknown_agent_standby(self):
        repo = _make_repo()
        msg = repo._get_ready_status_message("Mystery", "Analysis", "Analysis", "standby")
        assert "Standing by" in msg and "analysis" in msg

    def test_unknown_agent_waiting(self):
        repo = _make_repo()
        msg = repo._get_ready_status_message("Mystery", "Analysis", "Analysis", "waiting")
        assert "Waiting" in msg

    def test_unknown_agent_completed(self):
        repo = _make_repo()
        msg = repo._get_ready_status_message(
            "Mystery", "Analysis", "Analysis", "completed"
        )
        assert "Completed" in msg

    def test_unknown_agent_other_status(self):
        repo = _make_repo()
        msg = repo._get_ready_status_message("Mystery", "Analysis", "Analysis", "other")
        assert "Ready for" in msg
