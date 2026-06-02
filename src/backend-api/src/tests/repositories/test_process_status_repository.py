"""Tests for libs/repositories/process_status_repository.py."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from libs.repositories import process_status_repository as psr_module
from libs.repositories.process_status_repository import (
    ProcessStatusRepository,
    analyze_agent_velocity,
    calculate_activity_duration,
    get_agent_relationship_status,
)


class TestCalculateActivityDuration:
    def test_returns_zero_for_empty_input(self):
        assert calculate_activity_duration("") == (0, "0s")
        assert calculate_activity_duration(None) == (0, "0s")

    def test_returns_seconds_for_under_minute(self):
        ts = (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
        secs, formatted = calculate_activity_duration(ts)
        assert 4 <= secs <= 7
        assert formatted.endswith("s")

    def test_returns_minutes_for_under_hour(self):
        ts = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        secs, formatted = calculate_activity_duration(ts)
        assert 290 <= secs <= 320
        assert "m" in formatted and "s" in formatted

    def test_returns_hours_for_long_durations(self):
        ts = (datetime.now(UTC) - timedelta(hours=2, minutes=15)).isoformat()
        secs, formatted = calculate_activity_duration(ts)
        assert secs >= 2 * 3600
        assert "h" in formatted and "m" in formatted

    def test_handles_utc_suffix(self):
        ts = (datetime.now(UTC) - timedelta(seconds=10)).strftime(
            "%Y-%m-%dT%H:%M:%S UTC"
        )
        secs, _ = calculate_activity_duration(ts)
        assert secs >= 9

    def test_returns_zero_on_parse_error(self):
        assert calculate_activity_duration("not-a-date") == (0, "0s")


class TestAnalyzeAgentVelocity:
    def test_idle_when_no_history(self):
        assert analyze_agent_velocity([]) == "idle"

    def test_slow_when_no_recent_activity(self):
        old = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        history = [{"timestamp": old}]
        assert analyze_agent_velocity(history) == "slow"

    @pytest.mark.parametrize(
        "count,expected",
        [(1, "normal"), (3, "fast"), (5, "very_fast"), (7, "very_fast")],
    )
    def test_velocity_thresholds(self, count, expected):
        ts = datetime.now(UTC).isoformat()
        history = [{"timestamp": ts} for _ in range(count)]
        assert analyze_agent_velocity(history) == expected

    def test_skips_invalid_timestamps(self):
        history = [{"timestamp": "broken"}, {"timestamp": "broken"}]
        assert analyze_agent_velocity(history) == "slow"


class TestGetAgentRelationshipStatus:
    def test_empty_relationships_for_unknown(self):
        rels = get_agent_relationship_status({"name": "x"}, {})
        assert rels == {
            "waiting_for": [],
            "blocking": [],
            "collaborating_with": [],
            "dependency_chain": [],
        }

    def test_standby_agent_waits_for_active_ready(self):
        agent = {"name": "me", "participation_status": "standby"}
        all_agents = {
            "other": {
                "name": "other",
                "is_active": True,
                "participation_status": "ready",
            }
        }
        rels = get_agent_relationship_status(agent, all_agents)
        assert "other" in rels["waiting_for"]

    def test_active_agent_blocks_standby(self):
        agent = {"name": "me", "is_active": True}
        all_agents = {
            "other": {"name": "other", "participation_status": "standby"},
            "me": {"name": "me", "is_active": True},
        }
        rels = get_agent_relationship_status(agent, all_agents)
        assert "other" in rels["blocking"]
        assert "me" not in rels["blocking"]


class _NoOpRepoBase:
    def __init__(self, *a, **kw):
        pass


@pytest.fixture
def repo():
    with patch.object(
        psr_module.RepositoryBase, "__init__", _NoOpRepoBase.__init__
    ):
        r = ProcessStatusRepository("u", "db", "c")
    r.get_async = AsyncMock()
    return r


def _agent_obj(**overrides):
    base = {
        "name": "alpha",
        "is_currently_speaking": False,
        "is_active": True,
        "current_action": "thinking",
        "current_speaking_content": "",
        "last_message_preview": "hello",
        "participation_status": "ready",
        "current_reasoning": "",
        "last_reasoning": "",
        "thinking_about": "",
        "reasoning_steps": [],
        "last_activity_summary": "",
        "is_currently_thinking": False,
        "last_update_time": "",
        "last_full_message": "",
        "activity_history": [],
        "message_word_count": 0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _process_status(agents=None, **overrides):
    base = {
        "id": "proc-1",
        "step": "Analysis",
        "phase": "Analysis",
        "status": "running",
        "last_update_time": "",
        "started_at_time": "",
        "failure_agent": "",
        "failure_reason": "",
        "failure_details": "",
        "failure_step": "",
        "failure_timestamp": "",
        "stack_trace": "",
        "agents": agents if agents is not None else {},
        "step_timings": {},
        "step_results": {},
        "generated_files": [],
        "conversion_metrics": {},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestRepositoryGetters:
    @pytest.mark.asyncio
    async def test_get_process_agent_activities_returns_status(self, repo):
        ps = _process_status()
        repo.get_async.return_value = ps
        result = await repo.get_process_agent_activities_by_process_id("proc-1")
        assert result is ps

    @pytest.mark.asyncio
    async def test_get_process_agent_activities_returns_none(self, repo):
        repo.get_async.return_value = None
        assert (
            await repo.get_process_agent_activities_by_process_id("proc-1") is None
        )

    @pytest.mark.asyncio
    async def test_get_process_status_by_process_id_returns_none(self, repo):
        repo.get_async.return_value = None
        assert await repo.get_process_status_by_process_id("p") is None

    @pytest.mark.asyncio
    async def test_get_process_status_by_process_id_builds_snapshot(self, repo):
        agent = _agent_obj()
        ps = _process_status(agents={"alpha": agent})
        repo.get_async.return_value = ps
        snap = await repo.get_process_status_by_process_id("proc-1")
        assert snap is not None
        assert snap.process_id == "proc-1"
        assert len(snap.agents) == 1
        assert snap.agents[0].name == "alpha"


class TestRenderAgentStatus:
    @pytest.mark.asyncio
    async def test_returns_not_found_when_no_process(self, repo):
        repo.get_async.return_value = None
        result = await repo.render_agent_status("missing")
        assert result["status"] == "not_found"
        assert result["agents"] == []

    @pytest.mark.asyncio
    async def test_renders_with_full_data(self, repo):
        agent = _agent_obj(
            name="Chief_Architect",
            participation_status="ready",
            current_action="reviewing",
        )
        ps = _process_status(agents={"Chief_Architect": agent})
        repo.get_async.return_value = ps
        result = await repo.render_agent_status("proc-1")
        assert result["process_id"] == "proc-1"
        assert result["total_agents"] == 1
        assert "agents" in result
        assert isinstance(result["agents"], list)
        assert result["health_status"].startswith("🟢") or result[
            "health_status"
        ].startswith("🟡")

    @pytest.mark.asyncio
    async def test_renders_failed_process(self, repo):
        agent = _agent_obj(name="system", is_active=True)
        ps = _process_status(agents={"system": agent}, status="failed")
        repo.get_async.return_value = ps
        result = await repo.render_agent_status("proc-1")
        assert "system" in result["failed_agents"]
        assert result["health_status"] == "🔴 CRITICAL"

    @pytest.mark.asyncio
    async def test_renders_speaking_agent(self, repo):
        agent = _agent_obj(
            is_currently_speaking=True,
            current_speaking_content="hello world",
            message_word_count=2,
        )
        ps = _process_status(agents={"alpha": agent})
        repo.get_async.return_value = ps
        result = await repo.render_agent_status("proc-1")
        assert any("hello world" in line for line in result["agents"])

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_agents_data(self, repo):
        ps = _process_status(agents={})
        repo.get_async.return_value = ps
        result = await repo.render_agent_status("proc-1")
        assert result["agents"] == []


class TestRenderAgentStatusOld:
    @pytest.mark.asyncio
    async def test_returns_not_found_when_no_snapshot(self, repo):
        repo.get_async.return_value = None
        result = await repo.render_agent_status_old("nope")
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_renders_old_with_snapshot(self, repo):
        agent = _agent_obj(name="system")
        ps = _process_status(agents={"system": agent})
        repo.get_async.return_value = ps
        result = await repo.render_agent_status_old("proc-1")
        assert result["process_id"] == "proc-1"
        assert isinstance(result["agents"], list)


class TestReadyStatusMessage:
    @pytest.fixture
    def r(self, repo):
        return repo

    @pytest.mark.parametrize(
        "agent,step,expected_substring",
        [
            ("Chief_Architect", "Analysis", "analyze architecture"),
            ("EKS_Expert", "Design", "EKS"),
            ("GKS_Expert", "YAML", "AKS"),
            ("Azure_Expert", "Documentation", "document Azure"),
            ("Technical_Writer", "Analysis", "document"),
            ("QA_Engineer", "YAML", "validate YAML"),
        ],
    )
    def test_known_agent_messages(self, r, agent, step, expected_substring):
        msg = r._get_ready_status_message(agent, step, "Analysis", "ready")
        assert expected_substring.lower() in msg.lower()

    def test_unknown_agent_default(self, r):
        msg = r._get_ready_status_message(
            "Chief_Architect", "UnknownStep", "Analysis", "ready"
        )
        assert "Ready" in msg

    @pytest.mark.parametrize(
        "status,expected",
        [
            ("standby", "Standing by"),
            ("waiting", "Waiting"),
            ("completed", "Completed"),
            ("other", "Ready for"),
        ],
    )
    def test_unknown_agent_status_messages(self, r, status, expected):
        msg = r._get_ready_status_message("Unknown", "Analysis", "Analysis", status)
        assert expected in msg
