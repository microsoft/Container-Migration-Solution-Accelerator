# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

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


def _run(coro):
    return asyncio.run(coro)


class TestMigrationReportCollectorBasics:
    def test_init_seeds_environment_and_ids(self):
        c = MigrationReportCollector("p1")
        assert c.process_id == "p1"
        assert isinstance(c.report_id, str) and len(c.report_id) > 0
        assert c.start_time > 0
        assert c._environment_context is not None
        assert c._environment_context.python_version

    def test_set_current_step_creates_and_updates_phase(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis", step_phase="phase-a")
        assert c._current_step == "analysis"
        assert c._step_contexts["analysis"].step_phase == "phase-a"
        c.set_current_step("analysis", step_phase="phase-b")
        assert c._step_contexts["analysis"].step_phase == "phase-b"

    def test_set_current_step_handles_invalid(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("", step_phase=None)
        assert c._current_step == "unknown"

    def test_set_current_file_records_size(self, tmp_path):
        c = MigrationReportCollector("p1")
        f = tmp_path / "deploy.yaml"
        f.write_text("kind: Deployment\n")
        c.set_current_file("deploy.yaml", str(f), yaml_kind="Deployment")
        assert c._file_contexts["deploy.yaml"].yaml_kind == "Deployment"
        assert c._file_contexts["deploy.yaml"].file_size_bytes is not None
        c.set_current_file("deploy.yaml", str(f))
        assert c._file_contexts["deploy.yaml"].yaml_kind == "Deployment"

    def test_set_current_file_missing_path_no_size(self):
        c = MigrationReportCollector("p1")
        c.set_current_file("ghost.yaml", "/no/such/path.yaml")
        assert c._file_contexts["ghost.yaml"].file_size_bytes is None

    def test_set_current_agent_appends_activity(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis")
        c.set_current_file("a.yaml", "/no/a.yaml")
        c.set_current_agent("Azure_Expert", "expert", activity="reviewing")
        assert c._current_agent == "Azure_Expert"
        assert len(c._agent_activities) == 1
        rec = c._agent_activities[0]
        assert rec["agent_name"] == "Azure_Expert"
        assert rec["step"] == "analysis"
        assert rec["file"] == "a.yaml"

    def test_mark_step_completed_sets_time_when_known(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis")
        c.mark_step_completed("analysis", execution_time=1.5)
        assert c._step_contexts["analysis"].execution_time_seconds == 1.5

    def test_mark_step_completed_unknown_step_noop(self):
        c = MigrationReportCollector("p1")
        c.mark_step_completed("not-a-step", execution_time=1.0)
        assert "not-a-step" not in c._step_contexts


class TestRecordFailure:
    def test_record_failure_auto_classifies(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis")
        c.set_current_agent("AzureExpert", "expert")
        ctx = c.record_failure(ConnectionError("network connection lost"))
        assert ctx.failure_type == FailureType.NETWORK_ERROR
        assert ctx.severity == FailureSeverity.LOW
        assert ctx.agent_context is not None
        assert ctx.step_context is not None
        assert c._failure_contexts == [ctx]

    def test_record_failure_truncates_long_stack(self):
        c = MigrationReportCollector("p1")
        long_stack = "x" * 25000
        ctx = c.record_failure(RuntimeError("boom"), stack_trace=long_stack)
        assert "[stack trace truncated]" in (ctx.stack_trace or "")

    def test_record_failure_custom_overrides(self):
        c = MigrationReportCollector("p1")
        ctx = c.record_failure(
            Exception("orig"),
            failure_type=FailureType.YAML_PARSING_ERROR,
            severity=FailureSeverity.MEDIUM,
            custom_message="custom",
            stack_trace="short trace",
            exception_type="MyError",
        )
        assert ctx.error_message == "custom"
        assert ctx.exception_type == "MyError"
        assert ctx.stack_trace == "short trace"
        assert ctx.failure_type == FailureType.YAML_PARSING_ERROR
        assert ctx.severity == FailureSeverity.MEDIUM


class TestClassifiers:
    @pytest.mark.parametrize(
        "exc,expected",
        [
            (ConnectionError("x"), FailureType.NETWORK_ERROR),
            (Exception("network connection refused"), FailureType.NETWORK_ERROR),
            (Exception("operation timeout"), FailureType.TIMEOUT),
            (Exception("auth failed"), FailureType.AUTHENTICATION_FAILURE),
            (Exception("credential missing"), FailureType.AUTHENTICATION_FAILURE),
            (Exception("permission denied"), FailureType.AUTHENTICATION_FAILURE),
            (ValueError("bad value"), FailureType.CONFIGURATION_ERROR),
            (TypeError("nope"), FailureType.CONFIGURATION_ERROR),
            (Exception("config error"), FailureType.CONFIGURATION_ERROR),
            (Exception("yaml parse boom"), FailureType.YAML_PARSING_ERROR),
            (Exception("orchestrator failed"), FailureType.ORCHESTRATOR_ERROR),
            (Exception("manager crashed"), FailureType.ORCHESTRATOR_ERROR),
            (Exception("totally random"), FailureType.UNKNOWN_ERROR),
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


class TestGenerator:
    def test_generate_with_no_failures(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis")
        c.mark_step_completed("analysis", execution_time=2.0)
        c.set_current_file("a.yaml", "/no/a.yaml", yaml_kind="Deployment")
        gen = MigrationReportGenerator(c)
        report = _run(gen.generate_failure_report(overall_status=ReportStatus.SUCCESS))
        assert report.process_id == "p1"
        assert report.failure_analysis is None
        assert report.remediation_guide is None
        assert report.input_analysis.total_files == 1
        assert any(s.step_name == "analysis" for s in report.step_details)

    def test_generate_with_failures(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis")
        c.record_failure(Exception("auth failed"))  # CRITICAL
        c.record_failure(asyncio.TimeoutError())  # HIGH
        c.record_failure(Exception("yaml parse error"))  # MEDIUM
        c.record_failure(Exception("orchestrator boom"))  # HIGH
        c.set_current_file("a.yaml", "/no/a.yaml", yaml_kind=None)
        gen = MigrationReportGenerator(c)
        report = _run(gen.generate_failure_report())
        assert report.failure_analysis is not None
        assert report.remediation_guide is not None
        assert len(report.failure_analysis.contributing_factors) == 3
        assert len(report.remediation_guide.priority_actions) >= 1
        assert report.input_analysis.file_breakdown.get("Unknown") == 1

    def test_step_status_partial_when_no_failure_no_completion(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("design")
        gen = MigrationReportGenerator(c)
        details = gen._create_step_details()
        assert details[0].status == "partial"

    def test_step_status_failed_when_failure_attached(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("design")
        c.record_failure(Exception("bad"))
        gen = MigrationReportGenerator(c)
        details = gen._create_step_details()
        assert details[0].status == "failed"

    def test_supporting_data_includes_recent_failures(self):
        c = MigrationReportCollector("p1")
        c.set_current_step("analysis")
        for i in range(5):
            c.record_failure(Exception(f"err{i}"))
        gen = MigrationReportGenerator(c)
        sd = gen._create_supporting_data()
        assert len(sd.log_excerpts) == 3
        assert sd.environment_info.get("python_version")
