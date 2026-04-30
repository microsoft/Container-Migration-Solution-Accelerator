# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Tests for libs.reporting.migration_report_generator."""

import asyncio

import pytest

from libs.reporting.migration_report_generator import (
    MigrationReportCollector,
    MigrationReportGenerator,
)
from libs.reporting.models.failure_context import (
    FailureSeverity,
    FailureType,
)
from libs.reporting.models.migration_report import ReportStatus


# ---------- MigrationReportCollector ----------


class TestCollectorContextManagement:
    def test_set_current_step_creates_step_context(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis", step_phase="initialization")
        assert "analysis" in c._step_contexts
        assert c._step_contexts["analysis"].step_phase == "initialization"
        assert c._current_step == "analysis"

    def test_set_current_step_updates_phase_when_already_present(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("design")
        c.set_current_step("design", step_phase="orchestration")
        assert c._step_contexts["design"].step_phase == "orchestration"

    def test_set_current_step_normalizes_blank_name(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("   ")
        assert c._current_step == "unknown"
        assert "unknown" in c._step_contexts

    def test_set_current_step_normalizes_non_string(self):
        c = MigrationReportCollector("p1")
        c.set_current_step(None)  # type: ignore[arg-type]
        assert c._current_step == "unknown"

    def test_set_current_file_records_size_when_path_exists(self, tmp_path):
        path = tmp_path / "a.yaml"
        path.write_text("hello")
        c = MigrationReportCollector("p1")
        c.set_current_file("a.yaml", str(path), yaml_kind="Deployment")
        ctx = c._file_contexts["a.yaml"]
        assert ctx.file_size_bytes == len("hello")
        assert ctx.yaml_kind == "Deployment"

    def test_set_current_file_swallows_size_lookup_error(self, monkeypatch):
        monkeypatch.setattr(
            "libs.reporting.migration_report_generator.os.path.exists",
            lambda _: True,
        )
        monkeypatch.setattr(
            "libs.reporting.migration_report_generator.os.path.getsize",
            lambda _: (_ for _ in ()).throw(OSError("no")),
        )
        c = MigrationReportCollector("p1")
        c.set_current_file("z.yaml", "/nonexistent/z.yaml")
        assert c._file_contexts["z.yaml"].file_size_bytes is None

    def test_set_current_file_skips_size_when_path_missing(self, tmp_path):
        c = MigrationReportCollector("p1")
        c.set_current_file("missing.yaml", str(tmp_path / "missing.yaml"))
        assert c._file_contexts["missing.yaml"].file_size_bytes is None

    def test_set_current_file_does_not_overwrite_existing_context(self, tmp_path):
        path = tmp_path / "x.yaml"
        path.write_text("data")
        c = MigrationReportCollector("p1")
        c.set_current_file("x.yaml", str(path), yaml_kind="Service")
        c.set_current_file("x.yaml", str(path), yaml_kind="ChangedKind")
        assert c._file_contexts["x.yaml"].yaml_kind == "Service"

    def test_set_current_agent_records_activity_with_step_and_file(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis")
        c._current_file = "f.yaml"
        c.set_current_agent("Azure Expert", "azure_expert", activity="reviewing")
        assert c._current_agent == "Azure Expert"
        assert c._agent_activities[0]["step"] == "analysis"
        assert c._agent_activities[0]["file"] == "f.yaml"
        assert c._agent_activities[0]["activity"] == "reviewing"


class TestRecordFailure:
    def test_records_failure_with_default_classification(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis")
        ctx = c.record_failure(ConnectionError("boom: connection refused"))
        assert ctx.failure_type == FailureType.NETWORK_ERROR
        assert ctx.severity == FailureSeverity.LOW
        assert ctx.step_context.step_name == "analysis"
        assert c._failure_contexts == [ctx]

    def test_record_failure_attaches_file_and_agent_context(self, tmp_path):
        c = MigrationReportCollector("p1")
        c.set_current_step("design")
        c.set_current_file("y.yaml", str(tmp_path / "y.yaml"))
        c.set_current_agent("Azure Expert", "azure_expert")
        ctx = c.record_failure(RuntimeError("oops"))
        assert ctx.file_context is not None
        assert ctx.file_context.file_name == "y.yaml"
        assert ctx.agent_context is not None
        assert ctx.agent_context.agent_name == "Azure Expert"
        assert "design" in ctx.agent_context.current_activity

    def test_record_failure_uses_supplied_metadata(self):
        c = MigrationReportCollector("p1")
        ctx = c.record_failure(
            ValueError("config missing"),
            failure_type=FailureType.LLM_API_FAILURE,
            severity=FailureSeverity.HIGH,
            custom_message="custom",
            stack_trace="trace-line",
            exception_type="CustomError",
        )
        assert ctx.failure_type == FailureType.LLM_API_FAILURE
        assert ctx.severity == FailureSeverity.HIGH
        assert ctx.error_message == "custom"
        assert ctx.exception_type == "CustomError"
        assert ctx.stack_trace == "trace-line"

    def test_record_failure_truncates_long_stack_trace(self):
        c = MigrationReportCollector("p1")
        big = "A" * 25_000
        ctx = c.record_failure(RuntimeError("x"), stack_trace=big)
        assert "[stack trace truncated]" in ctx.stack_trace
        assert len(ctx.stack_trace) < 25_000


class TestClassification:
    @pytest.mark.parametrize(
        "exc,expected",
        [
            (ConnectionError("no route"), FailureType.NETWORK_ERROR),
            (OSError("disk error"), FailureType.NETWORK_ERROR),
            (RuntimeError("operation timeout exceeded"), FailureType.TIMEOUT),
            (RuntimeError("auth denied"), FailureType.AUTHENTICATION_FAILURE),
            (RuntimeError("permission denied"), FailureType.AUTHENTICATION_FAILURE),
            (ValueError("bad config"), FailureType.CONFIGURATION_ERROR),
            (TypeError("boom"), FailureType.CONFIGURATION_ERROR),
            (RuntimeError("yaml broken"), FailureType.YAML_PARSING_ERROR),
            (RuntimeError("orchestrator state corrupted"), FailureType.ORCHESTRATOR_ERROR),
            (RuntimeError("manager broken"), FailureType.ORCHESTRATOR_ERROR),
            (Exception("totally novel"), FailureType.UNKNOWN_ERROR),
        ],
    )
    def test_classify_failure_type(self, exc, expected):
        c = MigrationReportCollector("p1")
        assert c._classify_failure_type(exc) is expected

    @pytest.mark.parametrize(
        "ftype,expected",
        [
            (FailureType.AUTHENTICATION_FAILURE, FailureSeverity.CRITICAL),
            (FailureType.CONFIGURATION_ERROR, FailureSeverity.CRITICAL),
            (FailureType.TIMEOUT, FailureSeverity.HIGH),
            (FailureType.ORCHESTRATOR_ERROR, FailureSeverity.HIGH),
            (FailureType.YAML_PARSING_ERROR, FailureSeverity.MEDIUM),
            (FailureType.UNSUPPORTED_API_VERSION, FailureSeverity.MEDIUM),
            (FailureType.NETWORK_ERROR, FailureSeverity.LOW),
        ],
    )
    def test_classify_failure_severity(self, ftype, expected):
        c = MigrationReportCollector("p1")
        assert c._classify_failure_severity(Exception("x"), ftype) is expected


class TestEnvironmentCollection:
    def test_environment_context_when_psutil_missing(self, monkeypatch):
        # Cause `import psutil` to raise.
        import builtins

        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "psutil":
                raise ImportError("absent")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        c = MigrationReportCollector("p1")
        env = c._environment_context
        assert env.available_memory_mb is None
        assert env.cpu_usage_percent is None

    def test_mark_step_completed_sets_execution_time(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis")
        c.mark_step_completed("analysis", execution_time=1.25)
        assert c._step_contexts["analysis"].execution_time_seconds == 1.25

    def test_mark_step_completed_is_noop_for_unknown_step(self):
        c = MigrationReportCollector("p1")
        c.mark_step_completed("never-set", execution_time=0.5)
        assert "never-set" not in c._step_contexts


# ---------- MigrationReportGenerator ----------


def _run(coro):
    return asyncio.run(coro)


class TestGenerator:
    def test_generate_failure_report_no_failures_yields_no_analysis(self, tmp_path):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis")
        c.set_current_file("a.yaml", str(tmp_path / "a.yaml"), yaml_kind="Deployment")
        c.set_current_file("b.yaml", str(tmp_path / "b.yaml"))
        c.mark_step_completed("analysis", execution_time=0.5)

        report = _run(MigrationReportGenerator(c).generate_failure_report(
            overall_status=ReportStatus.SUCCESS
        ))
        assert report.failure_analysis is None
        assert report.remediation_guide is None
        assert report.input_analysis.file_breakdown == {"Deployment": 1, "Unknown": 1}
        assert report.executive_summary.completion_percentage == 100.0
        assert report.step_details[0].status == "completed"

    def test_generate_failure_report_with_failures_sets_root_cause(self, tmp_path):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis")
        c.set_current_file("a.yaml", str(tmp_path / "a.yaml"))
        c.record_failure(RuntimeError("auth missing"))  # critical: AUTH
        c.record_failure(RuntimeError("yaml broke"))  # medium

        report = _run(MigrationReportGenerator(c).generate_failure_report())
        assert report.failure_analysis is not None
        assert report.failure_analysis.root_cause == "auth missing"
        assert report.failure_analysis.failure_pattern == "authentication_failure"
        assert report.failure_analysis.recurrence_likelihood == "MEDIUM"
        assert report.remediation_guide is not None
        # AUTH suggestion is "immediate"; it should be in priority_actions.
        assert any(
            a.title == "Verify Azure Authentication"
            for a in report.remediation_guide.priority_actions
        )
        assert report.step_details[0].status == "failed"
        # Critical+High count ≥ 1
        assert report.executive_summary.critical_issues_count >= 1

    def test_generate_failure_report_partial_status_when_no_exec_time(self, tmp_path):
        c = MigrationReportCollector("p1")
        c.set_current_step("design")
        report = _run(MigrationReportGenerator(c).generate_failure_report())
        assert report.step_details[0].status == "partial"

    def test_generate_failure_report_uses_first_failure_when_no_critical(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis")
        # Use a NETWORK error - severity LOW; not critical.
        c.record_failure(ConnectionError("first"))
        c.record_failure(ConnectionError("second"))
        report = _run(MigrationReportGenerator(c).generate_failure_report())
        assert report.failure_analysis.root_cause == "first"
        assert report.failure_analysis.contributing_factors == ["second"]

    def test_remediation_for_timeout_yields_configuration_recommendation(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis")
        c.record_failure(RuntimeError("operation timeout exceeded"))
        report = _run(MigrationReportGenerator(c).generate_failure_report())
        assert any(
            r.title == "Increase Timeout Settings"
            for r in report.remediation_guide.configuration_recommendations
        )

    def test_remediation_for_orchestrator_yields_priority_action(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis")
        c.record_failure(RuntimeError("orchestrator failed"))
        report = _run(MigrationReportGenerator(c).generate_failure_report())
        assert any(
            r.title == "Debug Orchestrator State"
            for r in report.remediation_guide.priority_actions
        )

    def test_supporting_data_includes_recent_failures(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis")
        for i in range(5):
            c.record_failure(ConnectionError(f"err-{i}"))
        report = _run(MigrationReportGenerator(c).generate_failure_report())
        # Last 3 failures captured.
        msgs = [le["message"] for le in report.supporting_data.log_excerpts]
        assert msgs == ["err-2", "err-3", "err-4"]
        for le in report.supporting_data.log_excerpts:
            assert le["source"] == "analysis"
            assert le["level"] == "ERROR"

    def test_supporting_data_records_unknown_source_when_no_step_context(self):
        c = MigrationReportCollector("p1")
        c.record_failure(ConnectionError("orphan"))  # no step set
        report = _run(MigrationReportGenerator(c).generate_failure_report())
        assert report.supporting_data.log_excerpts[0]["source"] == "unknown"

    def test_recurrence_high_when_retry_count_set(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis")
        ctx = c.record_failure(RuntimeError("auth fail"))
        ctx.add_retry_attempt("second try")
        report = _run(MigrationReportGenerator(c).generate_failure_report())
        assert report.failure_analysis.recurrence_likelihood == "HIGH"
