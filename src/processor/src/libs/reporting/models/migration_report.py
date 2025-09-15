"""
Migration Report Models

Defines the main data structures for comprehensive migration reports
including success and failure scenarios.
"""

from datetime import datetime
from enum import Enum
import time
from typing import Any

from pydantic import BaseModel, Field

from .failure_context import FailureContext, RemediationSuggestion


class ReportStatus(Enum):
    """Overall status of the migration process."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ExecutiveSummary(BaseModel):
    """High-level summary for stakeholders."""

    completion_percentage: float  # 0.0 to 100.0
    completed_steps: list[str] = Field(default_factory=list)
    failed_step: str | None = None
    total_files: int = 0
    files_processed: int = 0
    files_failed: int = 0
    critical_issues_count: int = 0
    actionable_recommendations_count: int = 0
    estimated_fix_time: str | None = None  # "30 minutes", "2 hours", etc.


class InputAnalysis(BaseModel):
    """Analysis of the input files and source platform."""

    source_platform: str  # "EKS", "GKE", "AKS", etc.
    total_files: int
    file_breakdown: dict[str, int] = Field(default_factory=dict)  # kind -> count
    complexity_score: float | None = None  # 0.0 to 10.0
    supported_features: list[str] = Field(default_factory=list)
    unsupported_features: list[str] = Field(default_factory=list)


class StepDetail(BaseModel):
    """Detailed information about each migration step."""

    step_name: str
    status: str  # "completed", "failed", "skipped", "partial"
    execution_time_seconds: float | None = None
    files_processed: list[str] = Field(default_factory=list)
    files_failed: list[str] = Field(default_factory=list)
    output_files: list[str] = Field(default_factory=list)
    agent_activities: list[dict[str, Any]] = Field(default_factory=list)
    failure_contexts: list[FailureContext] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    success_metrics: dict[str, Any] = Field(default_factory=dict)


class FailureAnalysis(BaseModel):
    """Comprehensive analysis of what went wrong."""

    root_cause: str | None = None
    contributing_factors: list[str] = Field(default_factory=list)
    failure_pattern: str | None = None
    recurrence_likelihood: str | None = None  # "LOW", "MEDIUM", "HIGH"
    impact_assessment: str | None = None
    related_failures: list[str] = Field(default_factory=list)  # correlation IDs


class RemediationGuide(BaseModel):
    """Structured guidance for resolving issues."""

    priority_actions: list[RemediationSuggestion] = Field(default_factory=list)
    configuration_recommendations: list[RemediationSuggestion] = Field(
        default_factory=list
    )
    code_fixes_suggested: list[RemediationSuggestion] = Field(default_factory=list)
    when_to_retry: str | None = None
    escalation_criteria: list[str] = Field(default_factory=list)


class SupportingData(BaseModel):
    """Additional data for debugging and analysis."""

    log_excerpts: list[dict[str, str]] = Field(
        default_factory=list
    )  # timestamp -> message
    environment_info: dict[str, Any] = Field(default_factory=dict)
    dependency_versions: dict[str, str] = Field(default_factory=dict)
    performance_metrics: dict[str, float] = Field(default_factory=dict)
    resource_usage: dict[str, Any] = Field(default_factory=dict)


class MigrationReport(BaseModel):
    """
    Comprehensive migration report capturing all aspects of the migration process.

    This report serves multiple audiences:
    - Executives: Executive summary and high-level metrics
    - Engineers: Technical details and debugging information
    - Operations: Remediation guidance and monitoring data
    """

    # Report metadata
    report_id: str = Field(description="Unique identifier for this report")
    process_id: str = Field(description="Migration process ID this report covers")
    timestamp: float = Field(default_factory=time.time)
    report_version: str = "1.0"

    # Core status and summary
    overall_status: ReportStatus
    executive_summary: ExecutiveSummary

    # Input and processing details
    input_analysis: InputAnalysis
    step_details: list[StepDetail] = Field(default_factory=list)

    # Failure information (if applicable)
    failure_analysis: FailureAnalysis | None = None
    remediation_guide: RemediationGuide | None = None

    # Supporting information
    supporting_data: SupportingData = Field(default_factory=SupportingData)

    # Performance and metrics
    total_execution_time_seconds: float | None = None
    memory_peak_mb: float | None = None
    api_calls_made: int = 0
    tokens_consumed: int = 0

    @property
    def timestamp_iso(self) -> str:
        """Get timestamp in ISO format for human readability."""
        return datetime.fromtimestamp(self.timestamp).isoformat()

    @property
    def is_success(self) -> bool:
        """Check if migration was successful."""
        return self.overall_status in [
            ReportStatus.SUCCESS,
            ReportStatus.PARTIAL_SUCCESS,
        ]

    @property
    def has_failures(self) -> bool:
        """Check if there were any failures."""
        return any(step.failure_contexts for step in self.step_details)

    def get_failed_steps(self) -> list[StepDetail]:
        """Get all steps that had failures."""
        return [step for step in self.step_details if step.failure_contexts]

    def get_all_failures(self) -> list[FailureContext]:
        """Get all failure contexts across all steps."""
        failures = []
        for step in self.step_details:
            failures.extend(step.failure_contexts)
        return failures

    def add_step_detail(self, step_detail: StepDetail) -> None:
        """Add a step detail to the report."""
        # Remove any existing step with the same name (replace)
        self.step_details = [
            s for s in self.step_details if s.step_name != step_detail.step_name
        ]
        self.step_details.append(step_detail)

    def update_executive_summary(self) -> None:
        """Update executive summary based on current step details."""
        total_steps = len(self.step_details)
        completed_steps = [s for s in self.step_details if s.status == "completed"]
        failed_steps = [s for s in self.step_details if s.status == "failed"]

        self.executive_summary.completion_percentage = (
            len(completed_steps) / total_steps * 100 if total_steps > 0 else 0
        )

        self.executive_summary.completed_steps = [s.step_name for s in completed_steps]

        if failed_steps:
            self.executive_summary.failed_step = failed_steps[0].step_name

        # Count files
        all_processed = set()
        all_failed = set()
        for step in self.step_details:
            all_processed.update(step.files_processed)
            all_failed.update(step.files_failed)

        self.executive_summary.files_processed = len(all_processed)
        self.executive_summary.files_failed = len(all_failed)

        # Count critical issues
        all_failures = self.get_all_failures()
        self.executive_summary.critical_issues_count = len(
            [f for f in all_failures if f.severity.value in ["critical", "high"]]
        )

        # Count recommendations
        if self.remediation_guide:
            total_recommendations = (
                len(self.remediation_guide.priority_actions)
                + len(self.remediation_guide.configuration_recommendations)
                + len(self.remediation_guide.code_fixes_suggested)
            )
            self.executive_summary.actionable_recommendations_count = (
                total_recommendations
            )
