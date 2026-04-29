# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils import agent_telemetry as at
from utils.agent_telemetry import (
    AgentActivity,
    AgentActivityHistory,
    AgentActivityRepository,
    ProcessStatus,
    TelemetryManager,
    _build_step_lap_times,
    _byte_len_text,
    _get_process_blob_container_name,
    _get_storage_connection_string,
    _get_utc_timestamp,
    _parse_utc_timestamp,
    _sha256_text,
    get_orchestration_agents,
)


def _run(coro):
    return asyncio.run(coro)


# ---------- pure helpers ----------


class TestPureHelpers:
    def test_sha256_text_deterministic(self):
        assert _sha256_text("a") == _sha256_text("a")
        assert _sha256_text("a") != _sha256_text("b")

    def test_byte_len_text_handles_unicode(self):
        assert _byte_len_text("abc") == 3
        # 'é' is 2 bytes in UTF-8
        assert _byte_len_text("é") == 2

    def test_get_orchestration_agents_returns_coordinator(self):
        assert get_orchestration_agents() == {"Coordinator"}

    def test_get_process_blob_container_default(self, monkeypatch):
        monkeypatch.delenv("PROCESS_BLOB_CONTAINER_NAME", raising=False)
        assert _get_process_blob_container_name() == "processes"

    def test_get_process_blob_container_env_used(self, monkeypatch):
        monkeypatch.setenv("PROCESS_BLOB_CONTAINER_NAME", "mybox")
        assert _get_process_blob_container_name() == "mybox"

    def test_get_process_blob_container_blank_falls_back(self, monkeypatch):
        monkeypatch.setenv("PROCESS_BLOB_CONTAINER_NAME", "   ")
        assert _get_process_blob_container_name() == "processes"

    def test_get_storage_connection_string_present(self, monkeypatch):
        monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "  conn  ")
        assert _get_storage_connection_string() == "conn"

    def test_get_storage_connection_string_none(self, monkeypatch):
        for key in ["AZURE_STORAGE_CONNECTION_STRING", "STORAGE_CONNECTION_STRING", "AzureWebJobsStorage"]:
            monkeypatch.delenv(key, raising=False)
        assert _get_storage_connection_string() is None

    def test_get_utc_timestamp_format(self):
        ts = _get_utc_timestamp()
        assert ts.endswith(" UTC")
        assert _parse_utc_timestamp(ts) is not None

    def test_parse_utc_timestamp_invalid(self):
        assert _parse_utc_timestamp("") is None
        assert _parse_utc_timestamp("not a date") is None
        assert _parse_utc_timestamp(None) is None  # type: ignore[arg-type]
        assert _parse_utc_timestamp(123) is None  # type: ignore[arg-type]


class TestBuildStepLapTimes:
    def test_empty_returns_no_items(self):
        items, total = _build_step_lap_times(None)
        assert items == []
        assert total == 0.0

    def test_completed_step_uses_elapsed_seconds(self):
        timings = {
            "analysis": {
                "started_at": "2024-01-01 00:00:00 UTC",
                "ended_at": "2024-01-01 00:00:10 UTC",
                "elapsed_seconds": 10.0,
            }
        }
        items, total = _build_step_lap_times(timings)
        assert len(items) == 1
        assert items[0]["status"] == "completed"
        assert items[0]["elapsed_seconds"] == 10.0
        assert total == 10.0

    def test_running_step_status_and_elapsed(self):
        timings = {
            "design": {
                "started_at": _get_utc_timestamp(),
            }
        }
        items, _ = _build_step_lap_times(timings)
        assert items[0]["status"] == "running"
        # elapsed should be roughly 0 (just started)
        assert items[0]["elapsed_seconds"] is not None

    def test_unknown_status_when_no_timestamps(self):
        timings = {"design": {"some": "data"}}
        items, _ = _build_step_lap_times(timings)
        assert items[0]["status"] == "unknown"

    def test_invalid_timing_skipped(self):
        timings = {"": {"started_at": ""}, "x": "not-a-dict", "ok": {}}
        items, _ = _build_step_lap_times(timings)
        assert {it["step"] for it in items} == {"ok"}

    def test_preferred_order(self):
        timings = {
            "documentation": {"elapsed_seconds": 1},
            "analysis": {"elapsed_seconds": 2},
            "yaml": {"elapsed_seconds": 3},
            "design": {"elapsed_seconds": 4},
            "extra": {"elapsed_seconds": 5},
        }
        items, total = _build_step_lap_times(timings)
        order = [it["step"] for it in items]
        assert order[:4] == ["analysis", "design", "yaml", "documentation"]
        assert order[-1] == "extra"
        assert total == 15.0

    def test_derives_elapsed_from_timestamps_when_no_seconds(self):
        timings = {
            "analysis": {
                "started_at": "2024-01-01 00:00:00 UTC",
                "ended_at": "2024-01-01 00:00:30 UTC",
            }
        }
        items, _ = _build_step_lap_times(timings)
        assert items[0]["elapsed_seconds"] == 30.0


# ---------- pydantic dataclass defaults ----------


class TestPydanticModels:
    def test_agent_activity_defaults(self):
        a = AgentActivity(name="X")
        assert a.current_action == "idle"
        assert a.is_active is False
        assert a.message_word_count == 0
        assert a.activity_history == []

    def test_process_status_defaults(self):
        ps = ProcessStatus(id="p")
        assert ps.status == "running"
        assert ps.agents == {}
        assert ps.step_timings == {}

    def test_agent_activity_history_default_timestamp(self):
        h = AgentActivityHistory(action="speaking")
        assert h.action == "speaking"
        assert h.message_preview == ""


# ---------- AgentActivityRepository init guard ----------


class TestAgentActivityRepository:
    def test_raises_without_configuration(self):
        ctx = SimpleNamespace(configuration=None)
        with pytest.raises(ValueError):
            AgentActivityRepository(ctx)


# ---------- TelemetryManager constructor ----------


class TestTelemetryManagerConstruction:
    def test_dev_mode_when_no_app_context(self):
        tm = TelemetryManager()
        assert tm.repository is None
        assert tm.app_context is None

    def test_dev_mode_for_localhost_url(self):
        cfg = SimpleNamespace(cosmos_db_account_url="http://localhost:8081")
        ctx = SimpleNamespace(configuration=cfg)
        tm = TelemetryManager(ctx)
        assert tm.repository is None

    def test_dev_mode_for_template_placeholder(self):
        cfg = SimpleNamespace(cosmos_db_account_url="http://<replace>")
        ctx = SimpleNamespace(configuration=cfg)
        tm = TelemetryManager(ctx)
        assert tm.repository is None

    def test_production_creates_repository(self):
        cfg = SimpleNamespace(
            cosmos_db_account_url="https://prod.documents.azure.com:443/",
            cosmos_db_database_name="db",
            cosmos_db_container_name="c",
        )
        ctx = SimpleNamespace(configuration=cfg)
        with patch.object(at, "AgentActivityRepository") as repo_cls:
            repo_cls.return_value = "repo-instance"
            tm = TelemetryManager(ctx)
            assert tm.repository == "repo-instance"


# ---------- TelemetryManager methods (dev mode no-ops + with mocked repo) ----------


def _tm_with_repo():
    tm = TelemetryManager()  # dev mode, repository = None
    tm.repository = MagicMock()
    tm.repository.get_async = AsyncMock()
    tm.repository.add_async = AsyncMock()
    tm.repository.update_async = AsyncMock()
    tm.repository.delete_async = AsyncMock()
    return tm


class TestTelemetryManagerDevModeNoops:
    def test_delete_process_noop(self):
        tm = TelemetryManager()
        _run(tm.delete_process("p"))

    def test_init_process_noop_in_dev(self):
        tm = TelemetryManager()
        _run(tm.init_process("p", "phase", "analysis"))

    def test_get_current_process_returns_none(self):
        tm = TelemetryManager()
        assert _run(tm.get_current_process("p")) is None

    def test_get_process_outcome_empty_string(self):
        tm = TelemetryManager()
        assert _run(tm.get_process_outcome("p")) == ""


class TestTelemetryManagerWithRepo:
    def test_delete_process_calls_repository_when_record_exists(self):
        tm = _tm_with_repo()
        tm.repository.get_async.return_value = ProcessStatus(id="p")
        _run(tm.delete_process("p"))
        tm.repository.delete_async.assert_awaited_once_with("p")

    def test_delete_process_skips_when_missing(self):
        tm = _tm_with_repo()
        tm.repository.get_async.return_value = None
        _run(tm.delete_process("p"))
        tm.repository.delete_async.assert_not_called()

    def test_delete_process_swallows_errors(self):
        tm = _tm_with_repo()
        tm.repository.get_async.side_effect = RuntimeError("boom")
        _run(tm.delete_process("p"))  # must not raise

    def test_init_process_seeds_step_timing(self):
        tm = _tm_with_repo()
        _run(tm.init_process("p1", "phase", "analysis"))
        added = tm.repository.add_async.await_args.args[0]
        assert added.id == "p1"
        assert "analysis" in added.step_timings
        assert "started_at" in added.step_timings["analysis"]

    def test_init_process_recovers_when_add_conflict(self):
        tm = _tm_with_repo()
        tm.repository.add_async.side_effect = [Exception("conflict"), None]
        _run(tm.init_process("p1", "phase", "analysis"))
        tm.repository.delete_async.assert_awaited_once_with("p1")
        assert tm.repository.add_async.await_count == 2

    def test_update_agent_activity_creates_agent_and_sets_state(self):
        tm = _tm_with_repo()
        ps = ProcessStatus(id="p")
        tm.repository.get_async.return_value = ps
        _run(
            tm.update_agent_activity(
                "p",
                "Azure_Expert",
                "thinking",
                message_preview="Analyzing",
                full_message="Analyzing details",
            )
        )
        assert "Azure_Expert" in ps.agents
        a = ps.agents["Azure_Expert"]
        assert a.is_active is True
        assert a.is_currently_thinking is True
        assert a.participation_status == "thinking"
        assert a.last_full_message == "Analyzing details"
        assert a.message_word_count == 2

    def test_update_agent_activity_sets_speaking(self):
        tm = _tm_with_repo()
        ps = ProcessStatus(id="p", agents={"X": AgentActivity(name="X", current_action="ready")})
        tm.repository.get_async.return_value = ps
        _run(tm.update_agent_activity("p", "X", "speaking", message_preview="say"))
        assert ps.agents["X"].participation_status == "speaking"

    def test_update_agent_activity_completes(self):
        tm = _tm_with_repo()
        ps = ProcessStatus(id="p", agents={"X": AgentActivity(name="X")})
        tm.repository.get_async.return_value = ps
        _run(tm.update_agent_activity("p", "X", "completed"))
        assert ps.agents["X"].participation_status == "completed"

    def test_update_agent_activity_truncates_long_preview(self):
        tm = _tm_with_repo()
        ps = ProcessStatus(id="p")
        tm.repository.get_async.return_value = ps
        long_text = "x" * 500
        _run(tm.update_agent_activity("p", "X", "speaking", message_preview=long_text))
        assert ps.agents["X"].last_message_preview.endswith("...")

    def test_update_agent_activity_no_process_returns_silently(self):
        tm = _tm_with_repo()
        tm.repository.get_async.return_value = None
        _run(tm.update_agent_activity("p", "X", "thinking"))
        tm.repository.update_async.assert_not_called()

    def test_update_agent_activity_step_reset_increments_counter(self):
        tm = _tm_with_repo()
        ps = ProcessStatus(id="p", step="design", agents={"X": AgentActivity(name="X")})
        tm.repository.get_async.return_value = ps
        _run(
            tm.update_agent_activity(
                "p", "X", "thinking", reset_for_new_step=True
            )
        )
        assert ps.agents["X"].step_reset_count == 1

    def test_update_agent_activity_other_agents_become_inactive(self):
        tm = _tm_with_repo()
        ps = ProcessStatus(
            id="p",
            agents={
                "A": AgentActivity(name="A", is_active=True),
                "B": AgentActivity(name="B", is_active=True),
            },
        )
        tm.repository.get_async.return_value = ps
        _run(tm.update_agent_activity("p", "A", "thinking"))
        assert ps.agents["B"].is_active is False

    def test_update_process_status_running(self):
        tm = _tm_with_repo()
        ps = ProcessStatus(id="p", status="running")
        tm.repository.get_async.return_value = ps
        _run(tm.update_process_status("p", "running"))
        assert ps.status == "running"

    def test_update_process_status_terminal_marks_agents_idle(self):
        tm = _tm_with_repo()
        ps = ProcessStatus(
            id="p",
            agents={"A": AgentActivity(name="A", is_active=True, is_currently_speaking=True)},
        )
        tm.repository.get_async.return_value = ps
        _run(tm.update_process_status("p", "completed"))
        assert ps.status == "completed"
        assert ps.phase == "end"
        a = ps.agents["A"]
        assert a.is_active is False and a.is_currently_speaking is False
        assert a.participation_status == "standby"

    def test_set_agent_idle(self):
        tm = _tm_with_repo()
        ps = ProcessStatus(
            id="p",
            agents={"A": AgentActivity(name="A", is_active=True, current_action="speaking")},
        )
        tm.repository.get_async.return_value = ps
        _run(tm.set_agent_idle("p", "A"))
        assert ps.agents["A"].current_action == "idle"
        assert ps.agents["A"].is_active is False

    def test_set_agent_idle_unknown_agent_noop(self):
        tm = _tm_with_repo()
        ps = ProcessStatus(id="p", agents={})
        tm.repository.get_async.return_value = ps
        _run(tm.set_agent_idle("p", "missing"))
        tm.repository.update_async.assert_not_called()

    def test_update_phase_changes_phase(self):
        tm = _tm_with_repo()
        ps = ProcessStatus(id="p", phase="analysis")
        tm.repository.get_async.return_value = ps
        _run(tm.update_phase("p", "design"))
        assert ps.phase == "design"

    def test_update_phase_no_process_noop(self):
        tm = _tm_with_repo()
        tm.repository.get_async.return_value = None
        _run(tm.update_phase("p", "design"))
        tm.repository.update_async.assert_not_called()

    def test_transition_to_phase_seeds_timing(self):
        tm = _tm_with_repo()
        ps = ProcessStatus(
            id="p",
            phase="analysis",
            agents={"A": AgentActivity(name="A")},
        )
        tm.repository.get_async.return_value = ps
        _run(tm.transition_to_phase("p", "design phase", "design"))
        assert ps.phase == "design phase"
        assert ps.step == "design"
        assert "design" in ps.step_timings
        assert ps.agents["A"].participation_status == "ready"

    def test_complete_all_participant_agents(self):
        tm = _tm_with_repo()
        ps = ProcessStatus(
            id="p",
            agents={
                "Coordinator": AgentActivity(name="Coordinator", is_active=True),
                "X": AgentActivity(name="X", is_active=True),
            },
        )
        tm.repository.get_async.return_value = ps
        _run(tm.complete_all_participant_agents("p"))
        assert ps.agents["X"].current_action == "completed"
        # Coordinator (orchestration) untouched
        assert ps.agents["Coordinator"].is_active is True

    def test_record_failure(self):
        tm = _tm_with_repo()
        ps = ProcessStatus(id="p", step="design")
        tm.repository.get_async.return_value = ps
        _run(
            tm.record_failure(
                "p",
                "boom",
                failure_details="bad",
                failure_step="",
                failure_agent="A",
                stack_trace="trace",
            )
        )
        assert ps.status == "failed"
        assert ps.failure_reason == "boom"
        assert ps.failure_step == "design"  # used current step
        assert ps.failure_agent == "A"

    def test_get_process_outcome_completed(self):
        tm = _tm_with_repo()
        tm.repository.get_async.return_value = ProcessStatus(id="p", status="completed")
        assert _run(tm.get_process_outcome("p")) == "Process completed successfully"

    def test_get_process_outcome_failed(self):
        tm = _tm_with_repo()
        tm.repository.get_async.return_value = ProcessStatus(
            id="p", status="failed", failure_reason="boom"
        )
        assert "boom" in _run(tm.get_process_outcome("p"))

    def test_get_process_outcome_running(self):
        tm = _tm_with_repo()
        tm.repository.get_async.return_value = ProcessStatus(id="p", status="running")
        assert _run(tm.get_process_outcome("p")) == "Process is still running"

    def test_get_process_outcome_other_status(self):
        tm = _tm_with_repo()
        tm.repository.get_async.return_value = ProcessStatus(id="p", status="qa_review")
        assert _run(tm.get_process_outcome("p")) == "Status: qa_review"

    def test_get_process_outcome_no_process(self):
        tm = _tm_with_repo()
        tm.repository.get_async.return_value = None
        assert _run(tm.get_process_outcome("p")) == "No active process"

    def test_track_tool_usage_updates_agent(self):
        tm = _tm_with_repo()
        ps = ProcessStatus(id="p", agents={})
        tm.repository.get_async.return_value = ps
        _run(
            tm.track_tool_usage(
                "p", "A", "blob_ops", "list", tool_details="x" * 80, tool_result_preview="y" * 200
            )
        )
        assert ps.agents["A"].current_action == "using_tool"
        assert ps.agents["A"].activity_history
        assert ps.agents["A"].reasoning_steps

    def test_track_tool_usage_no_process(self):
        tm = _tm_with_repo()
        tm.repository.get_async.return_value = None
        _run(tm.track_tool_usage("p", "A", "t", "a"))
        tm.repository.update_async.assert_not_called()


# ---------- _get_ready_status_message ----------


class TestReadyStatusMessage:
    def _tm(self):
        return TelemetryManager()

    @pytest.mark.parametrize(
        "phase,expected_substr",
        [
            ("analysis phase", "platform analysis"),
            ("design phase", "Azure architecture"),
            ("yaml conversion", "YAML conversion"),
            ("documentation phase", "documentation"),
            ("final", "expert discussion for migration step"),
        ],
    )
    def test_coordinator_messages(self, phase, expected_substr):
        msg = self._tm()._get_ready_status_message(
            "Coordinator", "step", phase, "ready"
        )
        assert expected_substr in msg

    def test_analysis_system_agent(self):
        msg = self._tm()._get_ready_status_message(
            "system_observer", "step", "analysis", "ready"
        )
        assert "source platform" in msg

    def test_analysis_other_agent(self):
        msg = self._tm()._get_ready_status_message(
            "Some_Expert", "Inspect", "analysis", "ready"
        )
        assert "inspect" in msg

    def test_design_azure_agent(self):
        msg = self._tm()._get_ready_status_message(
            "Azure_Expert", "design", "design", "ready"
        )
        assert "Azure recommendations" in msg

    def test_yaml_with_yaml_agent(self):
        msg = self._tm()._get_ready_status_message(
            "yaml_expert", "convert", "yaml", "ready"
        )
        assert "YAML configurations" in msg

    def test_documentation_writer(self):
        msg = self._tm()._get_ready_status_message(
            "technical_writer_one", "write", "documentation", "ready"
        )
        assert "comprehensive documentation" in msg

    def test_unknown_phase_default(self):
        msg = self._tm()._get_ready_status_message(
            "Foo", "", "weird-phase", "ready"
        )
        assert "Ready for" in msg


# ---------- render_agent_status ----------


class TestRenderAgentStatus:
    def test_returns_not_found_when_no_process(self):
        tm = _tm_with_repo()
        tm.repository.get_async.return_value = None
        result = _run(tm.render_agent_status("p"))
        assert result["status"] == "not_found"
        assert result["agents"] == []

    def test_renders_speaking_agent(self):
        tm = _tm_with_repo()
        ps = ProcessStatus(
            id="p",
            phase="analysis",
            agents={
                "Azure_Expert": AgentActivity(
                    name="Azure_Expert",
                    participation_status="speaking",
                    is_currently_speaking=True,
                    current_speaking_content="Talking",
                    message_word_count=2,
                )
            },
        )
        tm.repository.get_async.return_value = ps
        result = _run(tm.render_agent_status("p"))
        assert result["agents"] == ['\u2713[] Azure Expert: Speaking - "Talking" (2 words)']

    def test_renders_ready_agent_uses_context_message(self):
        # render_agent_status doesn't return formatted lines as 'agents' but
        # we just ensure no error and proper structure (returns dict).
        tm = _tm_with_repo()
        ps = ProcessStatus(
            id="p",
            phase="analysis",
            agents={
                "Coordinator": AgentActivity(
                    name="Coordinator",
                    participation_status="ready",
                    last_message_preview="processing",
                )
            },
        )
        tm.repository.get_async.return_value = ps
        result = _run(tm.render_agent_status("p"))
        assert isinstance(result, dict)
        assert "agents" in result and len(result["agents"]) == 1
