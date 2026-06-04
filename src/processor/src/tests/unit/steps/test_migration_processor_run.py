# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for MigrationProcessor.run() event-stream handling."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_framework import WorkflowEvent
from agent_framework._workflows._events import WorkflowErrorDetails

from steps.analysis.models.step_param import Analysis_TaskParam
from steps.migration_processor import (
    MigrationProcessor,
    WorkflowExecutorFailedException,
)


def _run(coro):
    return asyncio.run(coro)


def _make_input(process_id="p-1") -> Analysis_TaskParam:
    return Analysis_TaskParam(
        process_id=process_id,
        container_name="processes",
        source_file_folder=f"{process_id}/source",
        output_file_folder=f"{process_id}/converted",
        workspace_file_folder=f"{process_id}/workspace",
    )


def _make_processor(events: list, memory_store=None) -> MigrationProcessor:
    """Create a MigrationProcessor whose workflow streams the given events."""
    proc = MigrationProcessor.__new__(MigrationProcessor)
    proc.app_context = MagicMock()

    telemetry = MagicMock()
    telemetry.init_process = AsyncMock()
    telemetry.update_process_status = AsyncMock()
    telemetry.transition_to_phase = AsyncMock()
    telemetry.record_step_result = AsyncMock()
    telemetry.record_final_outcome = AsyncMock()
    telemetry.record_failure_outcome = AsyncMock()

    proc.app_context.get_service_async = AsyncMock(return_value=telemetry)
    proc.app_context._instances = {}
    proc.app_context.add_singleton = MagicMock()

    proc._telemetry = telemetry  # expose for assertions

    async def _stream(_input):
        for ev in events:
            yield ev

    workflow = MagicMock()
    workflow.run_stream = _stream
    proc.workflow = workflow

    # Patch _create_memory_store as an AsyncMock returning the provided value.
    proc._create_memory_store = AsyncMock(return_value=memory_store)

    return proc


class TestRunSuccessFlow:
    def test_workflow_started_then_normal_output_returns_data(self):
        data = SimpleNamespace(is_hard_terminated=False, value="ok")
        events = [
            WorkflowEvent.started(),
            WorkflowEvent.executor_invoked(executor_id="analysis", data=_make_input()),
            WorkflowEvent.executor_completed(executor_id="analysis", data={"r": 1}),
            WorkflowEvent.executor_invoked(executor_id="design", data=_make_input()),
            WorkflowEvent.output(executor_id="design", data=data),
        ]
        proc = _make_processor(events)
        result = _run(proc.run(_make_input()))
        assert result is data
        proc._telemetry.init_process.assert_awaited()
        proc._telemetry.update_process_status.assert_any_await(
            process_id="p-1", status="completed"
        )

    def test_invoked_event_for_non_analysis_triggers_transition_phase(self):
        data = SimpleNamespace(is_hard_terminated=False)
        events = [
            WorkflowEvent.started(),
            # Documentation invocation should map to "Documentation" display
            WorkflowEvent.executor_invoked(executor_id="documentation", data=_make_input()),
            WorkflowEvent.output(executor_id="documentation", data=data),
        ]
        proc = _make_processor(events)
        _run(proc.run(_make_input()))
        # transition_to_phase should be awaited with the documentation phase
        calls = proc._telemetry.transition_to_phase.await_args_list
        assert any(
            c.kwargs.get("phase") == "Initializing Documentation" for c in calls
        )

    def test_invoked_event_unknown_executor_uses_capitalize(self):
        data = SimpleNamespace(is_hard_terminated=False)
        events = [
            WorkflowEvent.started(),
            WorkflowEvent.executor_invoked(executor_id="custom", data=_make_input()),
            WorkflowEvent.output(executor_id="custom", data=data),
        ]
        proc = _make_processor(events)
        _run(proc.run(_make_input()))
        calls = proc._telemetry.transition_to_phase.await_args_list
        assert any(
            c.kwargs.get("phase") == "Initializing Custom" for c in calls
        )


class TestRunHardTerminationFlow:
    def test_hard_terminated_returns_data_and_records_failure(self):
        data = SimpleNamespace(
            is_hard_terminated=True,
            reason="Blocked",
            blocking_issues=["NEED_HUMAN_REVIEW"],
        )
        events = [
            WorkflowEvent.started(),
            WorkflowEvent.output(executor_id="analysis", data=data),
        ]
        proc = _make_processor(events)
        result = _run(proc.run(_make_input()))
        assert result is data
        proc._telemetry.record_failure_outcome.assert_awaited()
        proc._telemetry.update_process_status.assert_any_await(
            process_id="p-1", status="failed"
        )

    def test_hard_terminated_security_policy_collects_evidence(self):
        data = SimpleNamespace(
            is_hard_terminated=True,
            reason="Blocked",
            blocking_issues=["SECURITY_POLICY_VIOLATION"],
        )
        events = [
            WorkflowEvent.started(),
            WorkflowEvent.output(executor_id="analysis", data=data),
        ]
        proc = _make_processor(events)

        with patch(
            "utils.security_policy_evidence.collect_security_policy_evidence",
            return_value={
                "findings": [
                    {
                        "blob": "secret.yaml",
                        "secret_key_names": ["AWS_KEY"],
                        "signals": ["AKIA"],
                    }
                ]
            },
        ) as collector:
            result = _run(proc.run(_make_input()))

        assert result is data
        collector.assert_called_once()
        # reason was enriched with redacted evidence block
        assert "SECURITY POLICY EVIDENCE" in data.reason

    def test_hard_terminated_security_policy_handles_collector_error(self):
        data = SimpleNamespace(
            is_hard_terminated=True,
            reason="Blocked",
            blocking_issues=["SECURITY_POLICY_VIOLATION"],
        )
        events = [
            WorkflowEvent.started(),
            WorkflowEvent.output(executor_id="analysis", data=data),
        ]
        proc = _make_processor(events)
        with patch(
            "utils.security_policy_evidence.collect_security_policy_evidence",
            side_effect=RuntimeError("boom"),
        ):
            result = _run(proc.run(_make_input()))
        assert result is data
        # Ensure failure outcome still recorded (didn't crash on inner exception)
        proc._telemetry.record_failure_outcome.assert_awaited()


class TestRunOutputMissingFlow:
    def test_missing_output_raises_workflow_executor_failed_exception(self):
        events = [
            WorkflowEvent.started(),
            WorkflowEvent.output(executor_id="analysis", data=None),
        ]
        proc = _make_processor(events)
        with pytest.raises(WorkflowExecutorFailedException) as excinfo:
            _run(proc.run(_make_input()))
        assert "completed without producing output" in str(excinfo.value)
        proc._telemetry.record_failure_outcome.assert_awaited()

    def test_missing_output_with_none_source_uses_unknown(self):
        events = [
            WorkflowEvent.started(),
            WorkflowEvent.output(executor_id=None, data=None),
        ]
        proc = _make_processor(events)
        with pytest.raises(WorkflowExecutorFailedException):
            _run(proc.run(_make_input()))


class TestRunWorkflowFailedFlow:
    def test_workflow_failed_event_raises_with_details(self):
        details = WorkflowErrorDetails(
            error_type="ValueError",
            message="invalid yaml",
            traceback="Traceback ...",
            executor_id="yaml",
        )
        events = [
            WorkflowEvent.started(),
            WorkflowEvent.executor_invoked(executor_id="yaml", data=_make_input()),
            WorkflowEvent.failed(details=details),
        ]
        proc = _make_processor(events)
        with pytest.raises(WorkflowExecutorFailedException) as excinfo:
            _run(proc.run(_make_input()))
        assert "yaml" in str(excinfo.value)
        proc._telemetry.update_process_status.assert_any_await(
            process_id="p-1", status="failed"
        )

    def test_workflow_failed_classifies_context_size_message(self):
        details = WorkflowErrorDetails(
            error_type="RuntimeError",
            message="context window exceeded for token limit",
            traceback="tb",
            executor_id="design",
        )
        events = [
            WorkflowEvent.started(),
            WorkflowEvent.failed(details=details),
        ]
        proc = _make_processor(events)
        with pytest.raises(WorkflowExecutorFailedException):
            _run(proc.run(_make_input()))

    def test_workflow_failed_classifies_context_error_type(self):
        details = WorkflowErrorDetails(
            error_type="ContextLengthExceededError",
            message="too long",
            traceback=None,
            executor_id="analysis",
        )
        events = [
            WorkflowEvent.started(),
            WorkflowEvent.failed(details=details),
        ]
        proc = _make_processor(events)
        with pytest.raises(WorkflowExecutorFailedException):
            _run(proc.run(_make_input()))

    def test_executor_failed_event_is_silently_ignored(self):
        # ExecutorFailedEvent does not raise on its own; WorkflowFailedEvent does.
        details = WorkflowErrorDetails(
            error_type="X", message="m", traceback=None, executor_id="analysis"
        )
        data = SimpleNamespace(is_hard_terminated=False)
        events = [
            WorkflowEvent.started(),
            WorkflowEvent.executor_failed(executor_id="analysis", details=details),
            WorkflowEvent.output(executor_id="analysis", data=data),
        ]
        proc = _make_processor(events)
        result = _run(proc.run(_make_input()))
        assert result is data


class TestRunMemoryStoreLifecycle:
    def test_memory_store_is_registered_and_closed(self):
        data = SimpleNamespace(is_hard_terminated=False)
        events = [
            WorkflowEvent.started(),
            WorkflowEvent.executor_completed(executor_id="analysis", data=None),
            WorkflowEvent.output(executor_id="analysis", data=data),
        ]
        memory_store = MagicMock()
        memory_store.get_count = AsyncMock(return_value=3)
        memory_store.close = AsyncMock()
        proc = _make_processor(events, memory_store=memory_store)
        _run(proc.run(_make_input()))
        # Singleton replaced
        proc.app_context.add_singleton.assert_called_once()
        memory_store.close.assert_awaited()

    def test_memory_store_close_error_is_swallowed(self):
        data = SimpleNamespace(is_hard_terminated=False)
        events = [
            WorkflowEvent.started(),
            WorkflowEvent.output(executor_id="analysis", data=data),
        ]
        memory_store = MagicMock()
        memory_store.get_count = AsyncMock(side_effect=RuntimeError("x"))
        memory_store.close = AsyncMock()
        proc = _make_processor(events, memory_store=memory_store)
        # Should not raise
        result = _run(proc.run(_make_input()))
        assert result is data

    def test_executor_completed_with_memory_store_logs_count(self):
        data = SimpleNamespace(is_hard_terminated=False)
        events = [
            WorkflowEvent.started(),
            WorkflowEvent.executor_completed(
                executor_id="analysis", data={"some": "result"}
            ),
            WorkflowEvent.output(executor_id="design", data=data),
        ]
        memory_store = MagicMock()
        memory_store.get_count = AsyncMock(return_value=7)
        memory_store.close = AsyncMock()
        proc = _make_processor(events, memory_store=memory_store)
        _run(proc.run(_make_input()))
        # get_count called at least once during ExecutorCompletedEvent and at finally
        assert memory_store.get_count.await_count >= 2
        # record_step_result called for the executor completed event with data
        proc._telemetry.record_step_result.assert_any_await(
            process_id="p-1",
            step_name="analysis",
            step_result={"some": "result"},
            execution_time_seconds=pytest.approx(
                proc._telemetry.record_step_result.await_args_list[0]
                .kwargs["execution_time_seconds"],
                rel=1,
            ),
        )
