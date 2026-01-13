# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Migration Report Generator

Core engine for collecting failure context and generating comprehensive migration reports.
Integrates with existing telemetry and provides structured reporting capabilities.
"""

import asyncio
import logging
import os
import platform
import sys
import time
import traceback
import uuid
from typing import Any

from .models.failure_context import (
    AgentContext,
    EnvironmentContext,
    FailureContext,
    FailureSeverity,
    FailureType,
    FileContext,
    RemediationSuggestion,
    StepContext,
)
from .models.migration_report import (
    ExecutiveSummary,
    FailureAnalysis,
    InputAnalysis,
    MigrationReport,
    RemediationGuide,
    ReportStatus,
    StepDetail,
    SupportingData,
)

logger = logging.getLogger(__name__)


class MigrationReportCollector:
    """
    Collects context and data throughout the migration process for comprehensive reporting.

    This class is designed to be thread-safe and work with the existing migration pipeline
    without disrupting the core processing logic.
    """

    def __init__(self, process_id: str):
        self.process_id = process_id
        self.report_id = str(uuid.uuid4())
        self.start_time = time.time()

        # Context storage
        self._step_contexts: dict[str, StepContext] = {}
        self._failure_contexts: list[FailureContext] = []
        self._agent_activities: list[dict[str, Any]] = []
        self._file_contexts: dict[str, FileContext] = {}

        # Current processing context
        self._current_step: str | None = None
        self._current_file: str | None = None
        self._current_agent: str | None = None

        # Environment context (collected once)
        self._environment_context = self._collect_environment_context()

        logger.info(f"Initialized migration report collector for process {process_id}")

    def set_current_step(self, step_name: str, step_phase: str | None = None) -> None:
        """Set the current step being processed."""
        if not isinstance(step_name, str) or not step_name.strip():
            step_name = "unknown"
        self._current_step = step_name

        if step_name not in self._step_contexts:
            self._step_contexts[step_name] = StepContext(
                step_name=step_name, step_phase=step_phase
            )
        elif step_phase:
            self._step_contexts[step_name].step_phase = step_phase

    def set_current_file(
        self, file_name: str, file_path: str, yaml_kind: str | None = None
    ) -> None:
        """Set the current file being processed."""
        self._current_file = file_name

        if file_name not in self._file_contexts:
            file_size = None
            try:
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
            except Exception:
                pass

            self._file_contexts[file_name] = FileContext(
                file_name=file_name,
                file_path=file_path,
                file_size_bytes=file_size,
                yaml_kind=yaml_kind,
            )

    def set_current_agent(
        self, agent_name: str, agent_role: str, activity: str | None = None
    ) -> None:
        """Set the current agent in context."""
        self._current_agent = agent_name

        # Track agent activity
        self._agent_activities.append({
            "timestamp": time.time(),
            "agent_name": agent_name,
            "agent_role": agent_role,
            "activity": activity,
            "step": self._current_step,
            "file": self._current_file,
        })

    def record_failure(
        self,
        exception: Exception,
        failure_type: FailureType | None = None,
        severity: FailureSeverity | None = None,
        custom_message: str | None = None,
        stack_trace: str | None = None,
        exception_type: str | None = None,
    ) -> FailureContext:
        """Record a failure with full context."""

        # Auto-detect failure type if not provided
        if failure_type is None:
            failure_type = self._classify_failure_type(exception)

        # Auto-detect severity if not provided
        if severity is None:
            severity = self._classify_failure_severity(exception, failure_type)

        # Create failure context
        effective_stack_trace = stack_trace if stack_trace is not None else traceback.format_exc()
        if effective_stack_trace and len(effective_stack_trace) > 20000:
            # Keep head+tail to preserve the most useful frames.
            head = effective_stack_trace[:8000]
            tail = effective_stack_trace[-8000:]
            effective_stack_trace = (
                f"{head}\n\n... [stack trace truncated] ...\n\n{tail}"
            )

        failure_context = FailureContext(
            failure_id=str(uuid.uuid4()),
            failure_type=failure_type,
            severity=severity,
            error_message=custom_message or str(exception),
            exception_type=exception_type or type(exception).__name__,
            stack_trace=effective_stack_trace,
            # Add current context
            file_context=self._file_contexts.get(self._current_file)
            if self._current_file
            else None,
            step_context=self._step_contexts.get(self._current_step)
            if self._current_step
            else None,
            environment_context=self._environment_context,
        )

        # Add agent context if available
        if self._current_agent:
            failure_context.agent_context = AgentContext(
                agent_name=self._current_agent,
                agent_role="unknown",  # Could be enhanced to track this
                current_activity=f"Processing in {self._current_step or 'unknown'} step",
            )

        self._failure_contexts.append(failure_context)

        logger.error(
            f"Recorded failure: {failure_type.value} - {failure_context.error_message}"
        )

        return failure_context

    def mark_step_completed(
        self, step_name: str, execution_time: float | None = None
    ) -> None:
        """Mark a step as completed successfully."""
        if step_name in self._step_contexts:
            self._step_contexts[step_name].execution_time_seconds = execution_time

    def _collect_environment_context(self) -> EnvironmentContext:
        """Collect current environment information."""
        try:
            import psutil

            memory_info = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent()
        except ImportError:
            memory_info = None
            cpu_percent = None

        return EnvironmentContext(
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            semantic_kernel_version=None,
            azure_region=os.environ.get("AZURE_REGION"),
            container_environment=os.environ.get("CONTAINER_ENVIRONMENT") == "true",
            available_memory_mb=memory_info.available // (1024 * 1024)
            if memory_info
            else None,
            cpu_usage_percent=cpu_percent,
        )

    def _classify_failure_type(self, exception: Exception) -> FailureType:
        """Automatically classify failure type based on exception."""
        exception_name = type(exception).__name__
        error_message = str(exception).lower()

        # Network and connectivity
        if (
            isinstance(exception, (ConnectionError, OSError))
            or "connection" in error_message
        ):
            return FailureType.NETWORK_ERROR

        # Timeout
        if isinstance(exception, asyncio.TimeoutError) or "timeout" in error_message:
            return FailureType.TIMEOUT

        # Authentication
        if (
            "auth" in error_message
            or "credential" in error_message
            or "permission" in error_message
        ):
            return FailureType.AUTHENTICATION_FAILURE

        # Configuration
        if isinstance(exception, (ValueError, TypeError)) or "config" in error_message:
            return FailureType.CONFIGURATION_ERROR

        # YAML parsing
        if "yaml" in error_message or "parsing" in error_message:
            return FailureType.YAML_PARSING_ERROR

        # Orchestrator issues
        if "orchestrator" in error_message or "manager" in error_message:
            return FailureType.ORCHESTRATOR_ERROR

        return FailureType.UNKNOWN_ERROR

    def _classify_failure_severity(
        self, exception: Exception, failure_type: FailureType
    ) -> FailureSeverity:
        """Automatically classify failure severity."""

        # Critical failures that block everything
        if failure_type in [
            FailureType.AUTHENTICATION_FAILURE,
            FailureType.CONFIGURATION_ERROR,
        ]:
            return FailureSeverity.CRITICAL

        # High impact failures
        if failure_type in [FailureType.TIMEOUT, FailureType.ORCHESTRATOR_ERROR]:
            return FailureSeverity.HIGH

        # Medium impact failures
        if failure_type in [
            FailureType.YAML_PARSING_ERROR,
            FailureType.UNSUPPORTED_API_VERSION,
        ]:
            return FailureSeverity.MEDIUM

        # Low impact by default
        return FailureSeverity.LOW


class MigrationReportGenerator:
    """
    Generates comprehensive migration reports from collected context.
    """

    def __init__(self, collector: MigrationReportCollector):
        self.collector = collector

    async def generate_failure_report(
        self, overall_status: ReportStatus = ReportStatus.FAILED
    ) -> MigrationReport:
        """Generate a comprehensive failure report."""

        # Calculate execution time
        total_execution_time = time.time() - self.collector.start_time

        # Create executive summary
        executive_summary = ExecutiveSummary(
            completion_percentage=0.0,  # Will be updated based on steps
            total_files=len(self.collector._file_contexts),
            critical_issues_count=len([
                f
                for f in self.collector._failure_contexts
                if f.severity in [FailureSeverity.CRITICAL, FailureSeverity.HIGH]
            ]),
        )

        # Create input analysis
        input_analysis = InputAnalysis(
            source_platform="Unknown",  # Could be detected from file analysis
            total_files=len(self.collector._file_contexts),
            file_breakdown=self._analyze_file_breakdown(),
        )

        # Create step details
        step_details = self._create_step_details()

        # Create failure analysis
        failure_analysis = self._create_failure_analysis()

        # Create remediation guide
        remediation_guide = self._create_remediation_guide()

        # Create supporting data
        supporting_data = self._create_supporting_data()

        # Create the main report
        report = MigrationReport(
            report_id=self.collector.report_id,
            process_id=self.collector.process_id,
            overall_status=overall_status,
            executive_summary=executive_summary,
            input_analysis=input_analysis,
            step_details=step_details,
            failure_analysis=failure_analysis,
            remediation_guide=remediation_guide,
            supporting_data=supporting_data,
            total_execution_time_seconds=total_execution_time,
        )

        # Update executive summary based on step details
        report.update_executive_summary()

        return report

    def _analyze_file_breakdown(self) -> dict[str, int]:
        """Analyze the breakdown of file types."""
        breakdown = {}
        for file_context in self.collector._file_contexts.values():
            if file_context.yaml_kind:
                breakdown[file_context.yaml_kind] = (
                    breakdown.get(file_context.yaml_kind, 0) + 1
                )
            else:
                breakdown["Unknown"] = breakdown.get("Unknown", 0) + 1
        return breakdown

    def _create_step_details(self) -> list[StepDetail]:
        """Create detailed step information."""
        step_details = []

        for step_name, step_context in self.collector._step_contexts.items():
            # Find failures for this step
            step_failures = [
                f
                for f in self.collector._failure_contexts
                if f.step_context and f.step_context.step_name == step_name
            ]

            # Determine step status
            if step_failures:
                status = "failed"
            elif step_context.execution_time_seconds is not None:
                status = "completed"
            else:
                status = "partial"

            step_detail = StepDetail(
                step_name=step_name,
                status=status,
                execution_time_seconds=step_context.execution_time_seconds,
                failure_contexts=step_failures,
            )

            step_details.append(step_detail)

        return step_details

    def _create_failure_analysis(self) -> FailureAnalysis | None:
        """Create failure analysis if there are failures."""
        if not self.collector._failure_contexts:
            return None

        # Find the most critical failure as root cause
        critical_failures = [
            f
            for f in self.collector._failure_contexts
            if f.severity == FailureSeverity.CRITICAL
        ]

        root_cause_failure = (
            critical_failures[0]
            if critical_failures
            else self.collector._failure_contexts[0]
        )

        return FailureAnalysis(
            root_cause=root_cause_failure.error_message,
            contributing_factors=[
                f.error_message for f in self.collector._failure_contexts[1:5]
            ],  # Top 5
            failure_pattern=root_cause_failure.failure_type.value,
            recurrence_likelihood="HIGH"
            if root_cause_failure.retry_count > 0
            else "MEDIUM",
        )

    def _create_remediation_guide(self) -> RemediationGuide | None:
        """Create remediation guidance based on failures."""
        if not self.collector._failure_contexts:
            return None

        priority_actions = []
        config_recommendations = []

        # Generate remediation suggestions based on failure types
        for failure in self.collector._failure_contexts:
            suggestions = self._generate_remediation_suggestions(failure)

            for suggestion in suggestions:
                if suggestion.action_type == "immediate":
                    priority_actions.append(suggestion)
                elif suggestion.action_type == "configuration":
                    config_recommendations.append(suggestion)

        return RemediationGuide(
            priority_actions=priority_actions,
            configuration_recommendations=config_recommendations,
            when_to_retry="After addressing configuration issues and verifying connectivity",
        )

    def _generate_remediation_suggestions(
        self, failure: FailureContext
    ) -> list[RemediationSuggestion]:
        """Generate specific remediation suggestions for a failure."""
        suggestions = []

        if failure.failure_type == FailureType.AUTHENTICATION_FAILURE:
            suggestions.append(
                RemediationSuggestion(
                    action_type="immediate",
                    priority=1,
                    title="Verify Azure Authentication",
                    description="Check Azure CLI login and permissions",
                    commands=["az account show", "az account list"],
                    estimated_effort="5 minutes",
                )
            )

        elif failure.failure_type == FailureType.TIMEOUT:
            suggestions.append(
                RemediationSuggestion(
                    action_type="configuration",
                    priority=2,
                    title="Increase Timeout Settings",
                    description="Consider increasing the migration timeout from current settings",
                    estimated_effort="2 minutes",
                )
            )

        elif failure.failure_type == FailureType.ORCHESTRATOR_ERROR:
            suggestions.append(
                RemediationSuggestion(
                    action_type="immediate",
                    priority=1,
                    title="Debug Orchestrator State",
                    description="Check orchestrator initialization and manager state",
                    estimated_effort="15 minutes",
                )
            )

        return suggestions

    def _create_supporting_data(self) -> SupportingData:
        """Create supporting data for the report."""
        # Get recent log excerpts (this could be enhanced to capture actual logs)
        log_excerpts = []
        for failure in self.collector._failure_contexts[-3:]:  # Last 3 failures
            log_excerpts.append({
                "timestamp": failure.timestamp_iso,
                "level": "ERROR",
                "message": failure.error_message,
                "source": failure.step_context.step_name
                if failure.step_context
                else "unknown",
            })

        # Environment info
        env_info = {}
        if self.collector._environment_context:
            env_info = {
                "python_version": self.collector._environment_context.python_version,
                "semantic_kernel_version": self.collector._environment_context.semantic_kernel_version,
                "platform": platform.platform(),
                "container": self.collector._environment_context.container_environment,
            }

        return SupportingData(
            log_excerpts=log_excerpts,
            environment_info=env_info,
            dependency_versions={},
        )
