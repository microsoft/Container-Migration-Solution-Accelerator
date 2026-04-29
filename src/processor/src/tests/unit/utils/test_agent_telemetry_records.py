# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Coverage for record_step_result / record_final_outcome / record_failure_outcome."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import utils.agent_telemetry as at
from utils.agent_telemetry import ProcessStatus, TelemetryManager


def _run(coro):
    return asyncio.run(coro)


def _tm_with_repo(record: ProcessStatus | None = None) -> TelemetryManager:
    tm = TelemetryManager()
    tm.repository = MagicMock()
    tm.repository.get_async = AsyncMock(return_value=record)
    tm.repository.update_async = AsyncMock()
    tm.repository.add_async = AsyncMock()
    tm.repository.delete_async = AsyncMock()
    return tm


class TestRecordStepResult:
    def test_no_repo_returns_silently(self):
        tm = TelemetryManager()
        _run(tm.record_step_result("p", "analysis", {"x": 1}))

    def test_missing_record_warns_and_returns(self):
        tm = _tm_with_repo(None)
        _run(tm.record_step_result("p", "analysis", {"x": 1}))
        tm.repository.update_async.assert_not_awaited()

    def test_records_and_normalizes_singleton_list(self):
        rec = ProcessStatus(id="p")
        rec.step_timings = {"analysis": {"started_at": "2025-01-01T00:00:00Z"}}
        tm = _tm_with_repo(rec)
        _run(
            tm.record_step_result(
                "p", "analysis", [{"foo": "bar"}], execution_time_seconds=2.5
            )
        )
        assert rec.step_results["analysis"]["result"] == {"foo": "bar"}
        assert rec.step_timings["analysis"]["elapsed_seconds"] == 2.5
        tm.repository.update_async.assert_awaited()

    def test_uses_timestamp_elapsed_when_perf_too_small(self):
        # candidate < 0.5 and timestamps show >5s -> use ts_elapsed
        rec = ProcessStatus(id="p")
        rec.step_timings = {
            "design": {"started_at": "2025-01-01T00:00:00Z"}
        }
        tm = _tm_with_repo(rec)
        with patch.object(at, "_get_utc_timestamp", return_value="2025-01-01T00:00:30Z"):
            _run(
                tm.record_step_result(
                    "p", "design", {"r": 1}, execution_time_seconds=0.001
                )
            )
        assert rec.step_timings["design"]["elapsed_seconds"] == 30.0

    def test_only_timestamp_elapsed_when_no_perf(self):
        rec = ProcessStatus(id="p")
        rec.step_timings = {
            "yaml": {"started_at": "2025-01-01T00:00:00Z"}
        }
        tm = _tm_with_repo(rec)
        with patch.object(at, "_get_utc_timestamp", return_value="2025-01-01T00:00:10Z"):
            _run(tm.record_step_result("p", "yaml", {"r": 1}))
        assert rec.step_timings["yaml"]["elapsed_seconds"] == 10.0

    def test_swallows_update_exception(self):
        rec = ProcessStatus(id="p")
        tm = _tm_with_repo(rec)
        tm.repository.update_async.side_effect = RuntimeError("boom")
        # Should not raise
        _run(tm.record_step_result("p", "analysis", {"r": 1}))


class TestRecordFinalOutcome:
    def test_no_repo_returns(self):
        tm = TelemetryManager()
        _run(tm.record_final_outcome("p", {}, success=True))

    def test_missing_record_warns_and_returns(self):
        tm = _tm_with_repo(None)
        _run(tm.record_final_outcome("p", {"x": 1}))
        tm.repository.update_async.assert_not_awaited()

    def test_records_legacy_generated_files_collection(self):
        rec = ProcessStatus(id="p")
        tm = _tm_with_repo(rec)
        outcome = {
            "GeneratedFilesCollection": {
                "analysis": [{"file_name": "a.md", "file_type": "md", "content_summary": "s"}],
                "yaml": [
                    {
                        "source_file": "src.yaml",
                        "converted_file": "out.yaml",
                        "file_type": "deployment",
                        "conversion_status": "Success",
                        "accuracy_rating": "high",
                    }
                ],
                "total_files_generated": 2,
            },
            "ProcessMetrics": {
                "platform_detected": "EKS",
                "conversion_accuracy": "high",
                "documentation_completeness": "high",
                "enterprise_readiness": "ready",
            },
        }
        _run(tm.record_final_outcome("p", outcome, success=True))
        assert rec.status == "completed"
        assert len(rec.generated_files) == 2
        assert rec.conversion_metrics["platform_detected"] == "EKS"
        assert rec.conversion_metrics["total_files_generated"] == 2
        # finalized_generated includes one artifact for migration_report
        assert (
            rec.final_outcome["finalized_generated"]["artifacts"][0]["type"]
            == "migration_report"
        )

    def test_records_termination_output_and_conversion_report(self):
        rec = ProcessStatus(id="p")
        # The yaml step result has a conversion_report_file pointer.
        rec.step_results = {
            "yaml": {
                "result": {
                    "termination_output": {"conversion_report_file": "p/output/conv.md"}
                }
            }
        }
        tm = _tm_with_repo(rec)
        outcome = {
            "termination_output": {
                "generated_files": {
                    "documentation": [
                        {"file_name": "d.md", "file_type": "md", "content_summary": ""}
                    ],
                    "total_files_generated": 1,
                },
                "process_metrics": {"platform_detected": "GKE"},
            }
        }
        _run(tm.record_final_outcome("p", outcome, success=True))
        artifact_types = [
            a["type"] for a in rec.final_outcome["finalized_generated"]["artifacts"]
        ]
        assert "conversion_report" in artifact_types

    def test_failure_path_sets_failed_status(self):
        rec = ProcessStatus(id="p")
        tm = _tm_with_repo(rec)
        _run(tm.record_final_outcome("p", {}, success=False))
        assert rec.status == "failed"

    def test_extraction_exception_is_swallowed(self):
        rec = ProcessStatus(id="p")
        tm = _tm_with_repo(rec)
        # Pass a truly weird outcome_data shape that triggers the inner exception via
        # a non-iterable for the collection slot.
        outcome = {"GeneratedFilesCollection": "not-a-dict"}
        _run(tm.record_final_outcome("p", outcome, success=True))
        # Did not raise; record still updated
        assert rec.status == "completed"


class TestRecordFailureOutcome:
    def test_no_repo_returns(self):
        tm = TelemetryManager()
        _run(
            tm.record_failure_outcome(
                "p", error_message="x", failed_step="analysis"
            )
        )

    def test_missing_record_warns_and_returns(self):
        tm = _tm_with_repo(None)
        _run(
            tm.record_failure_outcome(
                "p", error_message="x", failed_step="analysis"
            )
        )
        tm.repository.update_async.assert_not_awaited()

    def test_records_failure_with_traceback_inline(self):
        rec = ProcessStatus(id="p")
        rec.step_timings = {"analysis": {"started_at": "2025-01-01T00:00:00Z"}}
        tm = _tm_with_repo(rec)
        _run(
            tm.record_failure_outcome(
                "p",
                error_message="oops",
                failed_step="analysis",
                failure_details={"traceback": "short tb"},
                execution_time_seconds=3.0,
            )
        )
        assert rec.status == "failed"
        assert rec.failure_reason == "oops"
        assert rec.failure_step == "analysis"
        assert rec.step_timings["analysis"]["elapsed_seconds"] == 3.0

    def test_records_failure_offloads_large_traceback(self, monkeypatch):
        rec = ProcessStatus(id="p")
        tm = _tm_with_repo(rec)
        big_tb = "x" * 1000
        monkeypatch.setenv("TELEMETRY_TRACEBACK_INLINE_MAX_BYTES", "100")

        async def _fake_upload(**_kwargs):
            return {"blob": "debug/traceback.txt"}

        with patch.object(at, "_upload_text_to_process_blob", new=_fake_upload):
            _run(
                tm.record_failure_outcome(
                    "p",
                    error_message="big",
                    failed_step="design",
                    failure_details={"traceback": big_tb},
                )
            )
        details = rec.final_outcome["failure_details"]
        assert "traceback" not in details
        assert details["traceback_artifact"] == {"blob": "debug/traceback.txt"}

    def test_swallows_offload_exception(self, monkeypatch):
        rec = ProcessStatus(id="p")
        tm = _tm_with_repo(rec)
        big_tb = "x" * 1000
        monkeypatch.setenv("TELEMETRY_TRACEBACK_INLINE_MAX_BYTES", "100")

        async def _fail(**_kwargs):
            raise RuntimeError("blob fail")

        with patch.object(at, "_upload_text_to_process_blob", new=_fail):
            # Should not raise
            _run(
                tm.record_failure_outcome(
                    "p",
                    error_message="big",
                    failed_step="design",
                    failure_details={"traceback": big_tb},
                )
            )

    def test_swallows_update_exception(self):
        rec = ProcessStatus(id="p")
        tm = _tm_with_repo(rec)
        tm.repository.update_async.side_effect = RuntimeError("boom")
        # Should not raise
        _run(
            tm.record_failure_outcome(
                "p", error_message="x", failed_step="analysis"
            )
        )


class TestGetFinalResultsSummary:
    def test_no_repo_returns_empty(self):
        tm = TelemetryManager()
        assert _run(tm.get_final_results_summary("p")) == {}

    def test_missing_returns_error(self):
        tm = _tm_with_repo(None)
        assert _run(tm.get_final_results_summary("p")) == {"error": "No active process"}

    def test_returns_summary(self):
        rec = ProcessStatus(id="p")
        rec.status = "completed"
        rec.step_results = {"analysis": {"result": {}}}
        rec.generated_files = [{"file_name": "x"}]
        rec.conversion_metrics = {"k": "v"}
        tm = _tm_with_repo(rec)
        out = _run(tm.get_final_results_summary("p"))
        assert out["status"] == "completed"
        assert out["generated_files_count"] == 1
        assert "completed_steps" in out


class TestRecordUiData:
    def test_no_repo_returns(self):
        tm = TelemetryManager()
        _run(tm.record_ui_data("p", {"x": 1}))

    def test_missing_record_warns_and_returns(self):
        tm = _tm_with_repo(None)
        _run(tm.record_ui_data("p", {"x": 1}))
        tm.repository.update_async.assert_not_awaited()

    def test_records_ui_data(self):
        rec = ProcessStatus(id="p")
        tm = _tm_with_repo(rec)
        ui_data = {
            "file_manifest": {
                "converted_files": [{"a": 1}],
                "failed_files": [],
                "report_files": [{"b": 2}],
            },
            "dashboard_metrics": {"completion_percentage": 99.0},
        }
        _run(tm.record_ui_data("p", ui_data))
        assert rec.ui_telemetry_data["file_manifest"]["converted_files"] == [{"a": 1}]
        tm.repository.update_async.assert_awaited()

    def test_swallows_exception(self):
        tm = _tm_with_repo(ProcessStatus(id="p"))
        tm.repository.update_async.side_effect = RuntimeError("x")
        # Should not raise
        _run(tm.record_ui_data("p", {"file_manifest": {}, "dashboard_metrics": {}}))


class TestGetUiTelemetryData:
    def test_no_repo_returns_empty(self):
        tm = TelemetryManager()
        assert _run(tm.get_ui_telemetry_data("p")) == {}

    def test_missing_returns_empty(self):
        tm = _tm_with_repo(None)
        assert _run(tm.get_ui_telemetry_data("p")) == {}

    def test_returns_data_when_present(self):
        rec = ProcessStatus(id="p")
        rec.ui_telemetry_data = {"a": 1}  # type: ignore[attr-defined]
        tm = _tm_with_repo(rec)
        assert _run(tm.get_ui_telemetry_data("p")) == {"a": 1}

    def test_returns_fallback_when_completed_and_empty(self):
        rec = ProcessStatus(id="p")
        rec.status = "completed"
        rec.generated_files = [{"x": 1}, {"y": 2}]
        tm = _tm_with_repo(rec)
        out = _run(tm.get_ui_telemetry_data("p"))
        assert out["dashboard_metrics"]["files_processed"] == 2
