"""
Base Failure Collection Utilities for Steps.

Provides common failure context collection methods that all steps can use.
"""

from datetime import datetime
import traceback
from typing import Any

from libs.models.failure_context import (
    HardTerminationContext,
    StepFailureState,
    SystemFailureContext,
)
from libs.models.orchestration_models import ExtendedBooleanResult, TerminationType


class StepFailureCollector:
    """Utility class for collecting failure context in steps"""

    @staticmethod
    async def collect_system_failure_context(
        error: Exception,
        step_name: str,
        process_id: str,
        context_data: dict[str, Any],
        step_start_time: float | None = None,
        step_phase: str = "unknown",
    ) -> SystemFailureContext:
        """Collect system failure context from an exception"""

        return SystemFailureContext(
            # Core error information - always available
            error_type=type(error).__name__,
            error_message=str(error),
            stack_trace=traceback.format_exc(),
            # Context information
            timestamp=datetime.utcnow(),
            process_id=process_id,
            step_name=step_name,
            step_phase=step_phase,
            # Input context summary
            input_context_summary=StepFailureCollector._summarize_input_context(
                context_data
            ),
            # Enhanced error details (equivalent to full_error_details)
            exception_module=type(error).__module__,
            exception_args=list(getattr(error, "args", [])),
            exception_cause=str(error.__cause__) if error.__cause__ else None,
            exception_context=str(error.__context__) if error.__context__ else None,
        )

    @staticmethod
    async def collect_hard_termination_context(
        extended_result: ExtendedBooleanResult,
        step_name: str,
        process_id: str,
        context_data: dict[str, Any],
    ) -> HardTerminationContext:
        """Collect hard termination context from ExtendedBooleanResult"""

        return HardTerminationContext(
            # Termination details from ExtendedBooleanResult
            termination_type=extended_result.termination_type,
            termination_reason=extended_result.reason,
            blocking_issues=extended_result.blocking_issues,
            retry_suggestions=extended_result.retry_suggestions,
            confidence_level=extended_result.confidence_level,
            # Input context
            input_files=StepFailureCollector._extract_input_files(context_data),
            # Business impact assessment
            manual_intervention_required=StepFailureCollector._requires_manual_intervention(
                extended_result
            ),
            escalation_level=StepFailureCollector._determine_escalation_level(
                extended_result
            ),
        )

    @staticmethod
    async def create_step_failure_state(
        reason: str,
        execution_time: float = 0.0,
        files_attempted: list[str] | None = None,
        system_failure_context: SystemFailureContext | None = None,
        hard_termination_context: HardTerminationContext | None = None,
    ) -> StepFailureState:
        """Create complete step failure state"""

        return StepFailureState(
            result=False,
            reason=reason,
            system_failure_context=system_failure_context,
            hard_termination_context=hard_termination_context,
            execution_time=execution_time,
            files_attempted=files_attempted or [],
        )

    @staticmethod
    def _summarize_input_context(context_data: dict[str, Any]) -> str:
        """Create a brief summary of input context for debugging"""
        summary_parts = []

        # Basic process info
        if context_data.get("source_file_folder"):
            summary_parts.append(f"source: {context_data['source_file_folder']}")

        # File information
        if context_data.get("analyzed_files"):
            files = context_data["analyzed_files"]
            summary_parts.append(f"files: {len(files)}")

        # Platform information
        if context_data.get("platform_detected"):
            summary_parts.append(f"platform: {context_data['platform_detected']}")

        # Analysis results
        if context_data.get("analysis_result"):
            summary_parts.append("has_analysis_result")

        # Design results
        if context_data.get("design_result"):
            summary_parts.append("has_design_result")

        return ", ".join(summary_parts) if summary_parts else "no context available"

    @staticmethod
    def _extract_input_files(context_data: dict[str, Any]) -> list[str]:
        """Extract list of input files from context"""
        files = []

        # From analyzed_files
        if context_data.get("analyzed_files"):
            for file_info in context_data["analyzed_files"]:
                if isinstance(file_info, dict) and file_info.get("file_name"):
                    files.append(file_info["file_name"])

        # From analysis result
        if (
            context_data.get("analysis_result", {})
            .get("state", {})
            .get("termination_output")
        ):
            analysis_output = context_data["analysis_result"]["state"][
                "termination_output"
            ]
            if hasattr(analysis_output, "files_discovered"):
                for file_obj in analysis_output.files_discovered:
                    if hasattr(file_obj, "file_name"):
                        files.append(file_obj.file_name)

        return list(set(files))  # Remove duplicates

    @staticmethod
    def _requires_manual_intervention(extended_result: ExtendedBooleanResult) -> bool:
        """Determine if manual intervention is required"""
        critical_termination_types = [
            TerminationType.HARD_BLOCKED,
            TerminationType.HARD_ERROR,
            TerminationType.HARD_RESOURCE_LIMIT,
        ]

        return (
            extended_result.termination_type in critical_termination_types
            or extended_result.confidence_level < 0.5
            or len(extended_result.blocking_issues) > 2
        )

    @staticmethod
    def _determine_escalation_level(extended_result: ExtendedBooleanResult) -> str:
        """Determine escalation level based on termination context"""
        if extended_result.termination_type == TerminationType.HARD_ERROR:
            return "HIGH"
        elif extended_result.termination_type == TerminationType.HARD_BLOCKED:
            return "CRITICAL"
        elif extended_result.confidence_level < 0.3:
            return "HIGH"
        elif extended_result.confidence_level < 0.7:
            return "MEDIUM"
        else:
            return "LOW"
