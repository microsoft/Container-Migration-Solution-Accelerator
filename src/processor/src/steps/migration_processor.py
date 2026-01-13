import json
import time
from datetime import datetime
from typing import Any

from agent_framework import (
    ExecutorCompletedEvent,
    ExecutorFailedEvent,
    ExecutorInvokedEvent,
    Workflow,
    WorkflowBuilder,
    WorkflowFailedEvent,
    WorkflowOutputEvent,
    WorkflowStartedEvent,
)
from art import text2art

from libs.application.application_context import AppContext
from libs.reporting import (
    MigrationReportCollector,
    MigrationReportGenerator,
    ReportStatus,
)
from libs.reporting.models.failure_context import FailureType
from utils.agent_telemetry import TelemetryManager

from .analysis.models.step_param import Analysis_TaskParam
from .analysis.workflow.analysis_executor import AnalysisExecutor
from .convert.workflow.yaml_convert_executor import YamlConvertExecutor
from .design.workflow.design_executor import DesignExecutor
from .documentation.workflow.documentation_executor import DocumentationExecutor


class WorkflowExecutorFailedException(Exception):
    """Raised when an executor fails, preserving WorkflowErrorDetails payload."""

    def __init__(self, details: Any):
        self.details = details
        super().__init__(self._format_message(details))

    @staticmethod
    def _details_to_dict(details: Any) -> dict[str, Any]:
        if details is None:
            return {"details": None}

        # Pydantic v2
        model_dump = getattr(details, "model_dump", None)
        if callable(model_dump):
            try:
                return model_dump()
            except Exception:
                pass

        # Pydantic v1
        dict_fn = getattr(details, "dict", None)
        if callable(dict_fn):
            try:
                return dict_fn()
            except Exception:
                pass

        # Generic objects / dataclasses
        try:
            return dict(vars(details))
        except Exception:
            return {"details": repr(details)}

    @classmethod
    def _format_message(cls, details: Any) -> str:
        payload = cls._details_to_dict(details)
        executor_id = payload.get("executor_id", "<unknown>")
        error_type = payload.get("error_type", "<unknown>")
        message = payload.get("message", "<no message>")
        traceback = payload.get("traceback")

        payload_json = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        if traceback:
            return (
                f"Executor {executor_id} failed ({error_type}): {message}\n"
                f"WorkflowErrorDetails:\n{payload_json}\n"
                f"Traceback:\n{traceback}"
            )
        return (
            f"Executor {executor_id} failed ({error_type}): {message}\n"
            f"WorkflowErrorDetails:\n{payload_json}"
        )


class WorkflowOutputMissingException(Exception):
    """Raised when the workflow completes without producing a usable output."""

    def __init__(self, source_executor_id: str | None):
        self.source_executor_id = source_executor_id
        super().__init__(
            f"Workflow output is None (source_executor_id={source_executor_id or '<unknown>'})"
        )


class MigrationProcessor:
    def __init__(self, app_context: AppContext):
        self.app_context = app_context
        self.workflow = self._init_workflow()

    def _init_workflow(self) -> Workflow:
        workflow = (
            WorkflowBuilder()
            .register_executor(
                lambda: AnalysisExecutor(id="analysis", app_context=self.app_context),
                name="analysis",
            )
            .register_executor(
                lambda: DesignExecutor(id="design", app_context=self.app_context),
                name="design",
            )
            .register_executor(
                lambda: YamlConvertExecutor(id="yaml", app_context=self.app_context),
                name="yaml",
            )
            .register_executor(
                lambda: DocumentationExecutor(
                    id="documentation", app_context=self.app_context
                ),
                name="documentation",
            )
            .set_start_executor("analysis")
            .add_edge("analysis", "design")
            .add_edge("design", "yaml")
            .add_edge("yaml", "documentation")
            .build()
        )

        return workflow

    async def run(self, input_data: Analysis_TaskParam):
        start_dt = datetime.now()
        start_perf = time.perf_counter()

        # Structured report capture (small summary persisted to telemetry)
        report_collector = MigrationReportCollector(process_id=input_data.process_id)
        report_generator = MigrationReportGenerator(report_collector)
        step_start_perf: dict[str, float] = {}

        try:
            telemetry: TelemetryManager = await self.app_context.get_service_async(
                TelemetryManager
            )

            def _to_jsonable(val: Any) -> Any:
                if val is None:
                    return None
                if isinstance(val, (str, int, float, bool)):
                    return val
                if isinstance(val, list):
                    return [_to_jsonable(x) for x in val]
                if isinstance(val, dict):
                    return {str(k): _to_jsonable(v) for k, v in val.items()}

                model_dump = getattr(val, "model_dump", None)
                if callable(model_dump):
                    try:
                        return _to_jsonable(model_dump())
                    except Exception:
                        pass
                dict_fn = getattr(val, "dict", None)
                if callable(dict_fn):
                    try:
                        return _to_jsonable(dict_fn())
                    except Exception:
                        pass

                try:
                    return _to_jsonable(vars(val))
                except Exception:
                    return str(val)

            async def _generate_report_summary(
                overall_status: ReportStatus,
            ) -> dict[str, Any]:
                report = await report_generator.generate_failure_report(
                    overall_status=overall_status
                )

                failed_steps = []
                try:
                    failed_steps = [s.step_name for s in report.get_failed_steps()]
                except Exception:
                    failed_steps = []

                remediation_titles: list[str] = []
                if report.remediation_guide:
                    remediation_titles = [
                        s.title
                        for s in (report.remediation_guide.priority_actions or [])
                    ][:5]

                return {
                    "report_id": report.report_id,
                    "process_id": report.process_id,
                    "overall_status": report.overall_status.value,
                    "timestamp": report.timestamp,
                    "executive_summary": _to_jsonable(
                        report.executive_summary.model_dump()
                    ),
                    "failed_steps": failed_steps,
                    "root_cause": report.failure_analysis.root_cause
                    if report.failure_analysis
                    else None,
                    "top_remediations": remediation_titles,
                }

            async for event in self.workflow.run_stream(input_data):
                if isinstance(event, WorkflowStartedEvent):
                    print(f"Workflow started ({event.origin.value})")

                    report_collector.set_current_step("analysis", step_phase="start")
                    step_start_perf["analysis"] = time.perf_counter()

                    await telemetry.init_process(
                        process_id=input_data.process_id, step="analysis", phase="start"
                    )
                elif isinstance(event, WorkflowOutputEvent):
                    # WorkflowOutputEvent carries the step output (success or hard-termination).
                    # Note: a None payload is an error that must be surfaced clearly.
                    if event.data is None:
                        report_collector.set_current_step(
                            event.source_executor_id or "unknown"
                        )
                        report_collector.record_failure(
                            exception=ValueError("Workflow output is None"),
                            custom_message="Workflow output is None",
                        )

                        failure_details: Any = "Workflow output is None"
                        try:
                            failure_details = {
                                "reason": "Workflow output is None",
                                "migration_report_summary": await _generate_report_summary(
                                    ReportStatus.FAILED
                                ),
                            }
                        except Exception:
                            pass

                        await telemetry.record_failure_outcome(
                            process_id=input_data.process_id,
                            failed_step=event.source_executor_id or "unknown",
                            error_message="Workflow output is None",
                            failure_details=failure_details,
                            execution_time_seconds=(
                                time.perf_counter()
                                - step_start_perf[event.source_executor_id]
                                if event.source_executor_id in step_start_perf
                                else None
                            ),
                        )
                        await telemetry.update_process_status(
                            process_id=input_data.process_id, status="failed"
                        )

                        # Raise a rich exception so the queue worker reports a meaningful reason.
                        raise WorkflowExecutorFailedException({
                            "executor_id": event.source_executor_id or "unknown",
                            "error_type": "WorkflowOutputMissing",
                            "message": "Workflow output is None",
                            "traceback": None,
                        })

                    is_hard_terminated = bool(
                        getattr(event.data, "is_hard_terminated", False)
                    )
                    if is_hard_terminated:
                        # Optional: enrich SECURITY_POLICY_VIOLATION with safe (redacted) evidence.
                        security_evidence: Any = None
                        try:
                            if any(
                                (issue or "").strip() == "SECURITY_POLICY_VIOLATION"
                                for issue in (
                                    getattr(event.data, "blocking_issues", None) or []
                                )
                            ):
                                from utils.security_policy_evidence import (
                                    collect_security_policy_evidence,
                                )

                                security_evidence = collect_security_policy_evidence(
                                    container_name=input_data.container_name,
                                    source_folder=input_data.source_file_folder,
                                )

                                findings = (security_evidence or {}).get(
                                    "findings"
                                ) or []
                                if findings:
                                    summarized: list[str] = []
                                    for finding in findings[:10]:
                                        keys = finding.get("secret_key_names") or []
                                        sigs = finding.get("signals") or []
                                        key_part = f" keys={keys[:10]}" if keys else ""
                                        summarized.append(
                                            f"- {finding.get('blob')}{key_part} signals={sigs}"
                                        )
                                    event.data.reason = (
                                        (
                                            getattr(event.data, "reason", None)
                                            or "Hard terminated"
                                        )
                                        + "\n\nSECURITY POLICY EVIDENCE (redacted):\n"
                                        + "\n".join(summarized)
                                    )
                        except Exception as e:
                            security_evidence = {
                                "error": f"security evidence scan failed: {type(e).__name__}: {e}",
                            }

                        report_collector.set_current_step(
                            event.source_executor_id or "unknown"
                        )
                        report_collector.record_failure(
                            exception=ValueError(
                                getattr(event.data, "reason", None)
                                or f"Hard terminated in {event.source_executor_id} step"
                            ),
                            custom_message=getattr(event.data, "reason", None)
                            or f"Hard terminated in {event.source_executor_id} step",
                        )

                        failure_details: Any = (
                            ", ".join(
                                getattr(event.data, "blocking_issues", None) or []
                            )
                            or "No blocking issues provided"
                        )
                        try:
                            failure_details = {
                                "blocking_issues": getattr(
                                    event.data, "blocking_issues", None
                                )
                                or [],
                                "security_policy_evidence": security_evidence,
                                "migration_report_summary": await _generate_report_summary(
                                    ReportStatus.FAILED
                                ),
                            }
                        except Exception:
                            pass

                        await telemetry.record_failure_outcome(
                            process_id=input_data.process_id,
                            failed_step=event.source_executor_id or "unknown",
                            error_message=getattr(event.data, "reason", None)
                            or f"Hard terminated in {event.source_executor_id} step",
                            failure_details=failure_details,
                            execution_time_seconds=(
                                time.perf_counter()
                                - step_start_perf[event.source_executor_id]
                                if event.source_executor_id in step_start_perf
                                else None
                            ),
                        )

                        await telemetry.update_process_status(
                            process_id=input_data.process_id, status="failed"
                        )

                        # Return hard-terminated output so the queue worker can display blockers.
                        return event.data

                    # Normal completion
                    print(f"Workflow output ({event.origin.value}): {event.data}")
                    await telemetry.record_step_result(
                        process_id=input_data.process_id,
                        step_name=event.source_executor_id,
                        step_result=event.data,
                        execution_time_seconds=(
                            time.perf_counter()
                            - step_start_perf[event.source_executor_id]
                            if event.source_executor_id in step_start_perf
                            else None
                        ),
                    )

                    if event.source_executor_id in step_start_perf:
                        report_collector.mark_step_completed(
                            event.source_executor_id,
                            execution_time=time.perf_counter()
                            - step_start_perf[event.source_executor_id],
                        )

                    try:
                        outcome_payload = _to_jsonable(event.data) or {}
                        try:
                            outcome_payload[
                                "migration_report_summary"
                            ] = await _generate_report_summary(ReportStatus.SUCCESS)
                        except Exception:
                            pass

                        await telemetry.record_final_outcome(
                            process_id=input_data.process_id,
                            outcome_data=outcome_payload,
                            success=True,
                        )
                    except Exception:
                        pass

                    await telemetry.update_process_status(
                        process_id=input_data.process_id, status="completed"
                    )

                    return event.data
                elif isinstance(event, ExecutorFailedEvent):
                    pass
                    # will handle in WorkflowFailedEvent
                elif isinstance(event, WorkflowFailedEvent):
                    print(
                        f"Executor failed ({event.origin.value}): "
                        f"{event.details.executor_id} [{event.details.error_type}]: {event.details.message}"
                        f" (traceback: {event.details.traceback})"
                    )

                    report_collector.set_current_step(event.details.executor_id)

                    # Ensure we have a sensible perf start time for elapsed calculation.
                    if (
                        event.details.executor_id
                        and event.details.executor_id not in step_start_perf
                    ):
                        step_start_perf[event.details.executor_id] = time.perf_counter()

                    failure_type = None
                    try:
                        message_lower = (event.details.message or "").lower()
                        error_type_lower = (event.details.error_type or "").lower()
                        if (
                            "context" in message_lower
                            and ("exceed" in message_lower or "window" in message_lower)
                        ) or ("context" in error_type_lower):
                            failure_type = FailureType.CONTEXT_SIZE_EXCEEDED
                    except Exception:
                        failure_type = None

                    report_collector.record_failure(
                        exception=WorkflowExecutorFailedException(event.details),
                        failure_type=failure_type,
                        custom_message=event.details.message,
                        stack_trace=event.details.traceback,
                        exception_type=event.details.error_type,
                    )

                    failure_details: Any = event.details.traceback
                    try:
                        failure_details = {
                            "traceback": event.details.traceback,
                            "migration_report_summary": await _generate_report_summary(
                                ReportStatus.FAILED
                            ),
                        }
                    except Exception:
                        pass

                    await telemetry.record_failure_outcome(
                        process_id=input_data.process_id,
                        failed_step=event.details.executor_id,
                        error_message=event.details.message,
                        failure_details=failure_details,
                        execution_time_seconds=(
                            time.perf_counter()
                            - step_start_perf[event.details.executor_id]
                            if event.details.executor_id in step_start_perf
                            else None
                        ),
                    )

                    await telemetry.update_process_status(
                        process_id=input_data.process_id, status="failed"
                    )
                    # Raise a rich exception containing the full WorkflowErrorDetails payload.
                    raise WorkflowExecutorFailedException(event.details)

                elif isinstance(event, ExecutorInvokedEvent):
                    # The bug. the first executor's event fired after completing execution.
                    if event.executor_id != "analysis":
                        telemetry: TelemetryManager = (
                            await self.app_context.get_service_async(TelemetryManager)
                        )
                        await telemetry.transition_to_phase(
                            process_id=event.data.process_id,
                            step=event.executor_id,
                            phase="start",
                        )
                        print(f"Executor invoked ({event.executor_id})")
                        print(text2art(event.executor_id.capitalize()))

                    report_collector.set_current_step(
                        event.executor_id, step_phase="start"
                    )
                    # Defensive: some workflow implementations may emit ExecutorInvokedEvent
                    # late (even after completion) for the first executor. Only set the start
                    # perf counter if we don't already have one, otherwise lap timing becomes
                    # near-zero and incorrect.
                    if event.executor_id not in step_start_perf:
                        step_start_perf[event.executor_id] = time.perf_counter()
                elif isinstance(event, ExecutorCompletedEvent):
                    # print(f"Executor completed ({event.executor_id}): {event.data}")

                    # step name -> executor_id
                    # output result -> event.data => if event.data is not None
                    if event.data:
                        await telemetry.record_step_result(
                            process_id=input_data.process_id,
                            step_name=event.executor_id,
                            step_result=event.data,
                            execution_time_seconds=(
                                time.perf_counter() - step_start_perf[event.executor_id]
                                if event.executor_id in step_start_perf
                                else None
                            ),
                        )

                    if event.executor_id in step_start_perf:
                        report_collector.mark_step_completed(
                            event.executor_id,
                            execution_time=time.perf_counter()
                            - step_start_perf[event.executor_id],
                        )
                else:
                    # print(f"{event.__class__.__name__} ({event.origin.value}): {event}")
                    pass
        finally:
            elapsed_seconds = time.perf_counter() - start_perf
            end_dt = datetime.now()
            elapsed_mins, elapsed_secs = divmod(int(elapsed_seconds), 60)
            print(
                f"Workflow elapsed time: {elapsed_mins:d} mins {elapsed_secs:d} sec "
                f"(start={start_dt.isoformat(timespec='seconds')}, end={end_dt.isoformat(timespec='seconds')})"
            )
