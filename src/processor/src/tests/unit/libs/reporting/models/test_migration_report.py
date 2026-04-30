# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Unit tests for `libs.reporting.models.migration_report`."""

from __future__ import annotations

from libs.reporting.models.failure_context import (
    FailureContext,
    FailureSeverity,
    FailureType,
    RemediationSuggestion,
)
from libs.reporting.models.migration_report import (
    ExecutiveSummary,
    FailureAnalysis,
    InputAnalysis,
    MigrationReport,
    RemediationGuide,
    ReportStatus,
    StepDetail,
    SupportingData,
)


def _make_failure(severity=FailureSeverity.HIGH, fid="f1") -> FailureContext:
    return FailureContext(
        failure_id=fid,
        failure_type=FailureType.TIMEOUT,
        severity=severity,
        error_message="boom",
    )


def _make_report(**overrides) -> MigrationReport:
    defaults = dict(
        report_id="r1",
        process_id="p1",
        overall_status=ReportStatus.SUCCESS,
        executive_summary=ExecutiveSummary(completion_percentage=0.0),
        input_analysis=InputAnalysis(source_platform="EKS", total_files=0),
    )
    defaults.update(overrides)
    return MigrationReport(**defaults)


def test_report_status_enum_values():
    assert ReportStatus.SUCCESS.value == "success"
    assert ReportStatus.PARTIAL_SUCCESS.value == "partial_success"
    assert ReportStatus.FAILED.value == "failed"
    assert ReportStatus.TIMEOUT.value == "timeout"
    assert ReportStatus.CANCELLED.value == "cancelled"


def test_executive_summary_defaults():
    summary = ExecutiveSummary(completion_percentage=0.0)
    assert summary.completed_steps == []
    assert summary.failed_step is None
    assert summary.total_files == 0
    assert summary.files_processed == 0
    assert summary.files_failed == 0
    assert summary.critical_issues_count == 0


def test_input_analysis_defaults():
    inp = InputAnalysis(source_platform="GKE", total_files=5)
    assert inp.file_breakdown == {}
    assert inp.complexity_score is None
    assert inp.supported_features == []
    assert inp.unsupported_features == []


def test_step_detail_defaults():
    sd = StepDetail(step_name="analysis", status="completed")
    assert sd.execution_time_seconds is None
    assert sd.files_processed == []
    assert sd.failure_contexts == []


def test_failure_analysis_and_remediation_guide_defaults():
    fa = FailureAnalysis()
    assert fa.root_cause is None
    assert fa.contributing_factors == []
    rg = RemediationGuide()
    assert rg.priority_actions == []
    assert rg.when_to_retry is None


def test_supporting_data_defaults():
    sd = SupportingData()
    assert sd.log_excerpts == []
    assert sd.environment_info == {}
    assert sd.dependency_versions == {}


def test_migration_report_minimum_construction_and_defaults():
    rep = _make_report()
    assert rep.report_id == "r1"
    assert rep.process_id == "p1"
    assert rep.report_version == "1.0"
    assert isinstance(rep.timestamp, float) and rep.timestamp > 0
    assert rep.failure_analysis is None
    assert rep.remediation_guide is None
    assert rep.api_calls_made == 0
    assert rep.tokens_consumed == 0


def test_timestamp_iso_property_returns_iso8601_string():
    rep = _make_report(timestamp=1700000000.0)
    iso = rep.timestamp_iso
    assert isinstance(iso, str)
    assert "T" in iso  # ISO format includes 'T' as date/time separator


def test_is_success_true_for_success_and_partial():
    assert _make_report(overall_status=ReportStatus.SUCCESS).is_success is True
    assert (
        _make_report(overall_status=ReportStatus.PARTIAL_SUCCESS).is_success is True
    )


def test_is_success_false_for_other_statuses():
    for s in (ReportStatus.FAILED, ReportStatus.TIMEOUT, ReportStatus.CANCELLED):
        assert _make_report(overall_status=s).is_success is False


def test_has_failures_false_when_no_failure_contexts():
    rep = _make_report()
    rep.add_step_detail(StepDetail(step_name="analysis", status="completed"))
    assert rep.has_failures is False


def test_has_failures_true_when_step_has_failures():
    rep = _make_report()
    sd = StepDetail(
        step_name="analysis",
        status="failed",
        failure_contexts=[_make_failure()],
    )
    rep.add_step_detail(sd)
    assert rep.has_failures is True


def test_get_failed_steps_returns_only_failing_ones():
    rep = _make_report()
    rep.add_step_detail(StepDetail(step_name="ok", status="completed"))
    rep.add_step_detail(
        StepDetail(
            step_name="bad",
            status="failed",
            failure_contexts=[_make_failure()],
        )
    )
    failed = rep.get_failed_steps()
    assert len(failed) == 1
    assert failed[0].step_name == "bad"


def test_get_all_failures_aggregates_across_steps():
    rep = _make_report()
    rep.add_step_detail(
        StepDetail(
            step_name="a",
            status="failed",
            failure_contexts=[_make_failure(fid="f1"), _make_failure(fid="f2")],
        )
    )
    rep.add_step_detail(
        StepDetail(
            step_name="b",
            status="failed",
            failure_contexts=[_make_failure(fid="f3")],
        )
    )
    fids = [f.failure_id for f in rep.get_all_failures()]
    assert sorted(fids) == ["f1", "f2", "f3"]


def test_add_step_detail_replaces_existing_with_same_name():
    rep = _make_report()
    rep.add_step_detail(StepDetail(step_name="x", status="completed"))
    rep.add_step_detail(StepDetail(step_name="x", status="failed"))
    assert len(rep.step_details) == 1
    assert rep.step_details[0].status == "failed"


def test_update_executive_summary_with_completed_and_failed_and_files():
    rep = _make_report()
    rep.add_step_detail(
        StepDetail(
            step_name="a",
            status="completed",
            files_processed=["x.yaml", "y.yaml"],
        )
    )
    rep.add_step_detail(
        StepDetail(
            step_name="b",
            status="failed",
            files_failed=["z.yaml"],
            failure_contexts=[
                _make_failure(severity=FailureSeverity.CRITICAL, fid="c1"),
                _make_failure(severity=FailureSeverity.LOW, fid="c2"),
            ],
        )
    )
    rep.remediation_guide = RemediationGuide(
        priority_actions=[
            RemediationSuggestion(
                action_type="immediate", priority=1, title="t", description="d"
            )
        ],
        configuration_recommendations=[
            RemediationSuggestion(
                action_type="configuration", priority=2, title="t", description="d"
            )
        ],
        code_fixes_suggested=[
            RemediationSuggestion(
                action_type="code_fix", priority=3, title="t", description="d"
            )
        ],
    )

    rep.update_executive_summary()

    assert rep.executive_summary.completion_percentage == 50.0
    assert rep.executive_summary.completed_steps == ["a"]
    assert rep.executive_summary.failed_step == "b"
    assert rep.executive_summary.files_processed == 2
    assert rep.executive_summary.files_failed == 1
    # only CRITICAL counts as critical/high (high+critical), LOW does not
    assert rep.executive_summary.critical_issues_count == 1
    assert rep.executive_summary.actionable_recommendations_count == 3


def test_update_executive_summary_no_steps_zero_percent():
    rep = _make_report()
    rep.executive_summary.completion_percentage = 99.0
    rep.update_executive_summary()
    assert rep.executive_summary.completion_percentage == 0


def test_update_executive_summary_without_remediation_guide():
    rep = _make_report()
    rep.add_step_detail(StepDetail(step_name="a", status="completed"))
    # no remediation_guide set
    rep.update_executive_summary()
    # The recommendations count should remain at its default (0)
    assert rep.executive_summary.actionable_recommendations_count == 0
