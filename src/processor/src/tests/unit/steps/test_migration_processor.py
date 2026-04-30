# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Tests for steps.migration_processor (MigrationProcessor + helpers)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from steps.analysis.models.step_param import Analysis_TaskParam
from steps import migration_processor as mp_module
from steps.migration_processor import (
    MigrationProcessor,
    WorkflowExecutorFailedException,
    WorkflowOutputMissingException,
)


# Real classes used to replace mocked agent_framework event types so that
# `isinstance(event, EventClass)` works inside production code under test.
class _FakeWorkflowStartedEvent:
    pass


class _FakeWorkflowOutputEvent:
    pass


class _FakeWorkflowFailedEvent:
    pass


class _FakeExecutorInvokedEvent:
    pass


class _FakeExecutorCompletedEvent:
    pass


class _FakeExecutorFailedEvent:
    pass


@pytest.fixture(autouse=False)
def _patch_event_classes(monkeypatch):
    """Swap mocked agent_framework event types with real classes."""
    monkeypatch.setattr(mp_module, "WorkflowStartedEvent", _FakeWorkflowStartedEvent)
    monkeypatch.setattr(mp_module, "WorkflowOutputEvent", _FakeWorkflowOutputEvent)
    monkeypatch.setattr(mp_module, "WorkflowFailedEvent", _FakeWorkflowFailedEvent)
    monkeypatch.setattr(mp_module, "ExecutorInvokedEvent", _FakeExecutorInvokedEvent)
    monkeypatch.setattr(
        mp_module, "ExecutorCompletedEvent", _FakeExecutorCompletedEvent
    )
    monkeypatch.setattr(mp_module, "ExecutorFailedEvent", _FakeExecutorFailedEvent)
    yield


def _run(coro):
    return asyncio.run(coro)


# ---------- exception class helpers ----------


class _DetailsAttrsOnly:
    def __init__(self, executor_id="x", error_type="E", message="m"):
        self.executor_id = executor_id
        self.error_type = error_type
        self.message = message


def test_details_to_dict_handles_none_and_repr_fallback():
    assert WorkflowExecutorFailedException._details_to_dict(None) == {"details": None}

    class _Bad:
        @property
        def __dict__(self):  # vars() raises
            raise RuntimeError("no")

        def __repr__(self):
            return "<bad>"

    out = WorkflowExecutorFailedException._details_to_dict(_Bad())
    assert out == {"details": "<bad>"}


def test_details_to_dict_swallows_model_dump_errors():
    obj = MagicMock()
    obj.model_dump.side_effect = RuntimeError("dump failed")
    obj.dict.side_effect = RuntimeError("dict failed")
    out = WorkflowExecutorFailedException._details_to_dict(obj)
    # Falls back to vars(MagicMock()) which is a dict.
    assert isinstance(out, dict)


def test_workflow_output_missing_exception_carries_executor_id():
    exc = WorkflowOutputMissingException("design")
    assert exc.source_executor_id == "design"
    assert "design" in str(exc)


# ---------- MigrationProcessor: construction ----------


@pytest.fixture
def processor_factory():
    """Build a MigrationProcessor that skips real workflow construction."""

    def _make(app_context=None):
        app_context = app_context or MagicMock()
        with patch.object(
            MigrationProcessor, "_init_workflow", return_value=MagicMock()
        ):
            return MigrationProcessor(app_context=app_context)

    return _make


def test_init_workflow_builds_via_workflow_builder():
    """Verify the chained WorkflowBuilder calls happen during _init_workflow."""
    fake_builder_instance = MagicMock()
    # Chain methods all return self.
    for method_name in [
        "register_executor",
        "set_start_executor",
        "add_edge",
    ]:
        getattr(fake_builder_instance, method_name).return_value = (
            fake_builder_instance
        )
    sentinel_workflow = MagicMock(name="workflow")
    fake_builder_instance.build.return_value = sentinel_workflow

    with (
        patch(
            "steps.migration_processor.WorkflowBuilder",
            return_value=fake_builder_instance,
        ),
        patch("steps.migration_processor.AnalysisExecutor"),
        patch("steps.migration_processor.DesignExecutor"),
        patch("steps.migration_processor.YamlConvertExecutor"),
        patch("steps.migration_processor.DocumentationExecutor"),
    ):
        proc = MigrationProcessor(app_context=MagicMock())
    assert proc.workflow is sentinel_workflow
    fake_builder_instance.build.assert_called_once()
    fake_builder_instance.set_start_executor.assert_called_once_with("analysis")


# ---------- _create_memory_store ----------


def test_create_memory_store_disabled_via_env(monkeypatch, processor_factory):
    monkeypatch.setenv("SHARED_MEMORY_ENABLED", "false")
    proc = processor_factory()
    out = _run(proc._create_memory_store("p1"))
    assert out is None


def test_create_memory_store_returns_none_when_no_default_service_config(
    monkeypatch, processor_factory
):
    monkeypatch.setenv("SHARED_MEMORY_ENABLED", "true")
    helper = MagicMock()
    helper.settings.get_service_config.return_value = None
    app_context = MagicMock()
    app_context.get_service.return_value = helper

    proc = processor_factory(app_context=app_context)
    out = _run(proc._create_memory_store("p1"))
    assert out is None


def test_create_memory_store_returns_none_when_no_embedding_deployment(
    monkeypatch, processor_factory
):
    monkeypatch.setenv("SHARED_MEMORY_ENABLED", "true")
    helper = MagicMock()
    helper.settings.get_service_config.return_value = SimpleNamespace(
        embedding_deployment_name=None,
        endpoint="https://e",
        api_version="2024",
    )
    app_context = MagicMock()
    app_context.get_service.return_value = helper

    proc = processor_factory(app_context=app_context)
    out = _run(proc._create_memory_store("p1"))
    assert out is None


def test_create_memory_store_swallows_exceptions(monkeypatch, processor_factory):
    monkeypatch.setenv("SHARED_MEMORY_ENABLED", "true")
    app_context = MagicMock()
    app_context.get_service.side_effect = RuntimeError("no helper")

    proc = processor_factory(app_context=app_context)
    out = _run(proc._create_memory_store("p1"))
    assert out is None


def test_create_memory_store_returns_initialized_store(monkeypatch, processor_factory):
    monkeypatch.setenv("SHARED_MEMORY_ENABLED", "true")
    helper = MagicMock()
    helper.settings.get_service_config.return_value = SimpleNamespace(
        embedding_deployment_name="text-embed",
        endpoint="https://e",
        api_version="2024",
    )
    app_context = MagicMock()
    app_context.get_service.return_value = helper

    proc = processor_factory(app_context=app_context)

    fake_store = MagicMock()
    fake_store.initialize = AsyncMock()
    with (
        patch(
            "steps.migration_processor.QdrantMemoryStore", return_value=fake_store
        ),
        patch(
            "steps.migration_processor.AsyncAzureOpenAI", return_value=MagicMock()
        ),
        patch(
            "steps.migration_processor.get_bearer_token_provider",
            return_value=MagicMock(),
        ),
    ):
        out = _run(proc._create_memory_store("p1"))
    assert out is fake_store
    fake_store.initialize.assert_awaited_once()


# ---------- run() helpers and event flows ----------


def _make_task_param() -> Analysis_TaskParam:
    return Analysis_TaskParam(
        process_id="p1",
        container_name="c1",
        source_file_folder="src/folder",
        workspace_file_folder="ws",
        output_file_folder="out",
    )


def _telemetry_mock():
    t = MagicMock()
    t.init_process = AsyncMock()
    t.transition_to_phase = AsyncMock()
    t.record_step_result = AsyncMock()
    t.record_failure_outcome = AsyncMock()
    t.record_final_outcome = AsyncMock()
    t.update_process_status = AsyncMock()
    return t


def _app_context_with(telemetry, helper=None):
    app = MagicMock()
    app._instances = {}
    app.add_singleton = MagicMock()
    app.get_service_async = AsyncMock(return_value=telemetry)
    if helper is not None:
        app.get_service.return_value = helper
    return app


def _stream(events):
    """Build an async iterator returning the given events."""

    async def _it(_input):
        for ev in events:
            yield ev

    return _it


def _patch_no_memory_store(processor):
    processor._create_memory_store = AsyncMock(return_value=None)


def _make_started_event():
    ev = _FakeWorkflowStartedEvent()
    ev.origin = SimpleNamespace(value="origin")
    return ev


def _make_invoked_event(executor_id, process_id="p1"):
    ev = _FakeExecutorInvokedEvent()
    ev.executor_id = executor_id
    ev.data = SimpleNamespace(process_id=process_id)
    return ev


def _make_completed_event(executor_id, data=None):
    ev = _FakeExecutorCompletedEvent()
    ev.executor_id = executor_id
    ev.data = data
    return ev


def _make_output_event(data, source="analysis"):
    ev = _FakeWorkflowOutputEvent()
    ev.data = data
    ev.source_executor_id = source
    ev.origin = SimpleNamespace(value="origin")
    return ev


def _make_failed_event(executor_id="analysis", message="boom",
                       error_type="ValueError", traceback="trace"):
    ev = _FakeWorkflowFailedEvent()
    ev.origin = SimpleNamespace(value="origin")
    ev.details = SimpleNamespace(
        executor_id=executor_id,
        message=message,
        error_type=error_type,
        traceback=traceback,
    )
    return ev


@pytest.mark.usefixtures("_patch_event_classes")
class TestRun:
    def test_normal_completion_records_final_outcome(self, processor_factory):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)
        _patch_no_memory_store(proc)

        success_data = SimpleNamespace(
            is_hard_terminated=False,
            model_dump=lambda: {"k": "v"},
        )
        events = [
            _make_started_event(),
            _make_invoked_event("analysis"),
            _make_completed_event("analysis", data=success_data),
            _make_output_event(success_data, source="documentation"),
        ]
        proc.workflow.run_stream = _stream(events)

        out = _run(proc.run(_make_task_param()))
        assert out is success_data
        telemetry.init_process.assert_awaited_once()
        telemetry.update_process_status.assert_any_await(
            process_id="p1", status="completed"
        )
        telemetry.record_final_outcome.assert_awaited()

    def test_invoked_event_for_non_analysis_triggers_transition(
        self, processor_factory
    ):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)
        _patch_no_memory_store(proc)

        events = [
            _make_started_event(),
            _make_invoked_event("design"),
            _make_invoked_event("yaml"),
            _make_invoked_event("documentation"),
            _make_invoked_event("custom_step"),
            _make_completed_event(
                "custom_step",
                data=SimpleNamespace(model_dump=lambda: {}),
            ),
            _make_output_event(
                SimpleNamespace(is_hard_terminated=False, model_dump=lambda: {}),
                source="custom_step",
            ),
        ]
        proc.workflow.run_stream = _stream(events)

        _run(proc.run(_make_task_param()))
        # transition_to_phase called for design, yaml, documentation, custom_step
        phases = [c.kwargs.get("phase") for c in telemetry.transition_to_phase.await_args_list]
        assert any("Initializing Design" in p for p in phases)
        assert any("Initializing YAML" in p for p in phases)
        assert any("Initializing Documentation" in p for p in phases)
        assert any("Initializing Custom_step" in p for p in phases)

    def test_workflow_output_none_raises_executor_failed(self, processor_factory):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)
        _patch_no_memory_store(proc)

        events = [
            _make_started_event(),
            _make_invoked_event("analysis"),
            _make_output_event(None, source="analysis"),
        ]
        proc.workflow.run_stream = _stream(events)

        with pytest.raises(WorkflowExecutorFailedException) as excinfo:
            _run(proc.run(_make_task_param()))
        assert "completed without producing output" in str(excinfo.value)
        telemetry.update_process_status.assert_any_await(
            process_id="p1", status="failed"
        )

    def test_workflow_output_none_unknown_source(self, processor_factory):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)
        _patch_no_memory_store(proc)

        ev = _make_output_event(None, source=None)
        events = [_make_started_event(), ev]
        proc.workflow.run_stream = _stream(events)

        with pytest.raises(WorkflowExecutorFailedException):
            _run(proc.run(_make_task_param()))

    def test_hard_terminated_returns_payload(self, processor_factory):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)
        _patch_no_memory_store(proc)

        terminated = SimpleNamespace(
            is_hard_terminated=True,
            blocking_issues=["MISSING_FILES"],
            reason="user reason",
            model_dump=lambda: {},
        )
        events = [
            _make_started_event(),
            _make_invoked_event("design"),
            _make_output_event(terminated, source="design"),
        ]
        proc.workflow.run_stream = _stream(events)

        out = _run(proc.run(_make_task_param()))
        assert out is terminated
        telemetry.record_failure_outcome.assert_awaited()
        telemetry.update_process_status.assert_any_await(
            process_id="p1", status="failed"
        )

    def test_hard_terminated_security_policy_collects_evidence(
        self, processor_factory
    ):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)
        _patch_no_memory_store(proc)

        terminated = SimpleNamespace(
            is_hard_terminated=True,
            blocking_issues=["SECURITY_POLICY_VIOLATION"],
            reason="blocked",
            model_dump=lambda: {},
        )
        events = [
            _make_started_event(),
            _make_invoked_event("analysis"),
            _make_output_event(terminated, source="analysis"),
        ]
        proc.workflow.run_stream = _stream(events)

        with patch(
            "utils.security_policy_evidence.collect_security_policy_evidence",
            return_value={
                "findings": [
                    {
                        "blob": "secret.yaml",
                        "secret_key_names": ["api_key"],
                        "signals": ["k8s_kind_secret"],
                    }
                ]
            },
        ) as ev_collect:
            _run(proc.run(_make_task_param()))
        ev_collect.assert_called_once()
        assert "SECURITY POLICY EVIDENCE" in terminated.reason

    def test_hard_terminated_security_policy_collection_error(self, processor_factory):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)
        _patch_no_memory_store(proc)

        terminated = SimpleNamespace(
            is_hard_terminated=True,
            blocking_issues=["SECURITY_POLICY_VIOLATION"],
            reason=None,
            model_dump=lambda: {},
        )
        events = [
            _make_started_event(),
            _make_invoked_event("analysis"),
            _make_output_event(terminated, source="analysis"),
        ]
        proc.workflow.run_stream = _stream(events)

        with patch(
            "utils.security_policy_evidence.collect_security_policy_evidence",
            side_effect=RuntimeError("scan died"),
        ):
            out = _run(proc.run(_make_task_param()))
        assert out is terminated

    def test_workflow_failed_event_raises_and_classifies_context_error(
        self, processor_factory
    ):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)
        _patch_no_memory_store(proc)

        ev = _make_failed_event(
            executor_id="design",
            message="The context window was exceeded",
            error_type="ContextLengthExceeded",
        )
        events = [_make_started_event(), _make_invoked_event("design"), ev]
        proc.workflow.run_stream = _stream(events)

        with pytest.raises(WorkflowExecutorFailedException):
            _run(proc.run(_make_task_param()))
        telemetry.record_failure_outcome.assert_awaited()

    def test_workflow_failed_event_with_no_step_perf_set(self, processor_factory):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)
        _patch_no_memory_store(proc)

        # WorkflowFailedEvent without preceding Invoked: ensures perf fallback path.
        ev = _make_failed_event(
            executor_id="yaml", message="generic", error_type="X", traceback=None
        )
        events = [_make_started_event(), ev]
        proc.workflow.run_stream = _stream(events)
        with pytest.raises(WorkflowExecutorFailedException):
            _run(proc.run(_make_task_param()))

    def test_executor_failed_event_is_ignored(self, processor_factory):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)
        _patch_no_memory_store(proc)

        ef = _FakeExecutorFailedEvent()
        success = SimpleNamespace(
            is_hard_terminated=False, model_dump=lambda: {}
        )
        events = [
            _make_started_event(),
            _make_invoked_event("analysis"),
            ef,
            _make_output_event(success, source="analysis"),
        ]
        proc.workflow.run_stream = _stream(events)
        out = _run(proc.run(_make_task_param()))
        assert out is success

    def test_unknown_event_type_is_ignored(self, processor_factory):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)
        _patch_no_memory_store(proc)

        success = SimpleNamespace(
            is_hard_terminated=False, model_dump=lambda: {}
        )
        events = [
            _make_started_event(),
            _make_invoked_event("analysis"),
            object(),
            _make_output_event(success, source="analysis"),
        ]
        proc.workflow.run_stream = _stream(events)
        _run(proc.run(_make_task_param()))

    def test_completed_event_with_no_data_skips_record(self, processor_factory):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)
        _patch_no_memory_store(proc)

        success = SimpleNamespace(
            is_hard_terminated=False, model_dump=lambda: {}
        )
        events = [
            _make_started_event(),
            _make_invoked_event("analysis"),
            _make_completed_event("analysis", data=None),
            _make_output_event(success, source="analysis"),
        ]
        proc.workflow.run_stream = _stream(events)
        _run(proc.run(_make_task_param()))
        # record_step_result called once (from output event), not from completed.
        assert telemetry.record_step_result.await_count == 1

    def test_run_uses_memory_store_when_provided(self, processor_factory):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)

        memory = MagicMock()
        memory.get_count = AsyncMock(return_value=42)
        memory.close = AsyncMock()
        proc._create_memory_store = AsyncMock(return_value=memory)

        success = SimpleNamespace(
            is_hard_terminated=False, model_dump=lambda: {}
        )
        events = [
            _make_started_event(),
            _make_invoked_event("analysis"),
            _make_completed_event("analysis", data=success),
            _make_output_event(success, source="analysis"),
        ]
        proc.workflow.run_stream = _stream(events)

        _run(proc.run(_make_task_param()))
        memory.close.assert_awaited()
        # Memory was injected via add_singleton.
        app.add_singleton.assert_called()

    def test_run_memory_store_close_swallows_errors(self, processor_factory):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)

        memory = MagicMock()
        memory.get_count = AsyncMock(side_effect=RuntimeError("boom"))
        memory.close = AsyncMock()
        proc._create_memory_store = AsyncMock(return_value=memory)

        success = SimpleNamespace(
            is_hard_terminated=False, model_dump=lambda: {}
        )
        events = [
            _make_started_event(),
            _make_invoked_event("analysis"),
            _make_output_event(success, source="analysis"),
        ]
        proc.workflow.run_stream = _stream(events)
        _run(proc.run(_make_task_param()))

    def test_completed_event_logs_memory_count(self, processor_factory):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)

        memory = MagicMock()
        memory.get_count = AsyncMock(return_value=7)
        memory.close = AsyncMock()
        proc._create_memory_store = AsyncMock(return_value=memory)

        success = SimpleNamespace(
            is_hard_terminated=False, model_dump=lambda: {}
        )
        events = [
            _make_started_event(),
            _make_invoked_event("analysis"),
            _make_completed_event("analysis", data=success),
            _make_output_event(success, source="analysis"),
        ]
        proc.workflow.run_stream = _stream(events)
        _run(proc.run(_make_task_param()))
        # get_count called at least once during ExecutorCompleted + once during cleanup
        assert memory.get_count.await_count >= 1

    def test_completed_event_memory_count_error_ignored(self, processor_factory):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)

        memory = MagicMock()
        memory.get_count = AsyncMock(side_effect=RuntimeError("boom"))
        memory.close = AsyncMock()
        proc._create_memory_store = AsyncMock(return_value=memory)

        success = SimpleNamespace(
            is_hard_terminated=False, model_dump=lambda: {}
        )
        events = [
            _make_started_event(),
            _make_invoked_event("analysis"),
            _make_completed_event("analysis", data=success),
            _make_output_event(success, source="analysis"),
        ]
        proc.workflow.run_stream = _stream(events)
        _run(proc.run(_make_task_param()))


# ---------- _to_jsonable behaviour (covered via run paths) ----------


@pytest.mark.usefixtures("_patch_event_classes")
class TestToJsonable:
    """_to_jsonable is defined inside run(); cover its branches via the success path."""

    def test_supporting_data_serialization_handles_complex_types(
        self, processor_factory
    ):
        telemetry = _telemetry_mock()
        app = _app_context_with(telemetry)
        proc = processor_factory(app_context=app)
        _patch_no_memory_store(proc)

        # Build a model_dump that returns a payload exercising list/dict/primitive branches.
        class _Sub:
            def model_dump(self):
                return {"sub": True}

        class _Custom:
            def __init__(self):
                self.attr = "val"

        complex_payload = SimpleNamespace(
            is_hard_terminated=False,
            model_dump=lambda: {
                "primitive": 1,
                "string": "s",
                "bool": True,
                "list": [1, "two", _Sub(), {"nested": "v"}],
                "nested": {"k": _Custom()},
            },
        )

        events = [
            _make_started_event(),
            _make_invoked_event("analysis"),
            _make_output_event(complex_payload, source="analysis"),
        ]
        proc.workflow.run_stream = _stream(events)
        _run(proc.run(_make_task_param()))
        telemetry.record_final_outcome.assert_awaited()
