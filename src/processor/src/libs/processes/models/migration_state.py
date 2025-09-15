"""
Shared state models for the Semantic Kernel Process Framework migration process.

TODO :// Implement shared state management for migration process steps
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MigrationProcessState(BaseModel):
    """
    Shared state that flows between all migration process steps.

    This represents the complete state of a migration process,
    designed to be passed as events between SK Process steps.
    All step-specific agents and PluginContext remain isolated
    within their respective steps.
    """

    # Process Identity
    process_id: str
    user_request: str = ""

    # Step Control
    current_step: str = "initialization"

    # Shared Configuration
    source_platform: str = ""  # eks, gke, etc.
    target_platform: str = "azure"
    workspace_file_folder: str = "workspace"

    # Global Process State
    migration_type: str = ""

    # Analysis Step Results
    platform_detected: str = ""
    files_discovered: list[str] = Field(default_factory=list)
    file_count: int = 0
    analysis_summary: str = ""
    analysis_completed: bool = False

    # Design Step Results
    architecture_created: str = ""
    design_recommendations: list[str] = Field(default_factory=list)
    azure_services: list[str] = Field(default_factory=list)
    migration_strategy: str = ""
    design_completed: bool = False

    # YAML Step Results
    yaml_files_generated: list[str] = Field(default_factory=list)
    conversion_summary: str = ""
    yaml_completed: bool = False

    # Documentation Step Results
    documentation_created: str = ""
    final_report: str = ""
    documentation_completed: bool = False

    # Accumulated Expert Insights (across all steps)
    expert_insights: list[str] = Field(default_factory=list)

    # Error Tracking
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    # Step Execution Tracking
    steps_completed: list[str] = Field(default_factory=list)
    current_step_start_time: datetime | None = None

    def mark_step_started(self, step_name: str) -> "MigrationProcessState":
        """Mark a step as started and update current step."""
        self.current_step = step_name
        self.current_step_start_time = datetime.now()
        return self

    def mark_step_completed(self, step_name: str) -> "MigrationProcessState":
        """Mark a step as completed."""
        if step_name not in self.steps_completed:
            self.steps_completed.append(step_name)
        return self

    def add_error(self, error: str) -> "MigrationProcessState":
        """Add an error to the error log."""
        error_msg = f"[{self.current_step}] {error}"
        if error_msg not in self.errors:
            self.errors.append(error_msg)
        return self

    def add_warning(self, warning: str) -> "MigrationProcessState":
        """Add a warning to the warning log."""
        warning_msg = f"[{self.current_step}] {warning}"
        if warning_msg not in self.warnings:
            self.warnings.append(warning_msg)
        return self

    def add_expert_insight(self, insight: str) -> "MigrationProcessState":
        """Add expert insight from current step."""
        insight_msg = f"[{self.current_step}] {insight}"
        if insight_msg not in self.expert_insights:
            self.expert_insights.append(insight_msg)
        return self

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the current process state."""
        return {
            "process_id": self.process_id,
            "current_step": self.current_step,
            "steps_completed": self.steps_completed,
            "platform_detected": self.platform_detected,
            "files_discovered": len(self.files_discovered),
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "expert_insights": len(self.expert_insights),
            "progress": {
                "analysis_completed": self.analysis_completed,
                "design_completed": self.design_completed,
                "yaml_completed": self.yaml_completed,
                "documentation_completed": self.documentation_completed,
            },
        }


class StepResult(BaseModel):
    """
    Base class for step-specific results that get merged into shared state.
    """

    step_name: str
    success: bool
    duration_seconds: float = 0.0
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class AnalysisStepResult(StepResult):
    """Specific result structure for Analysis step."""

    platform_detected: str = ""
    files_discovered: list[str] = Field(default_factory=list)
    analysis_summary: str = ""


class DesignStepResult(StepResult):
    """Specific result structure for Design step."""

    architecture_created: str = ""
    recommendations: list[str] = Field(default_factory=list)
    azure_services: list[str] = Field(default_factory=list)
    migration_strategy: str = ""


class YamlStepResult(StepResult):
    """Specific result structure for YAML step."""

    yaml_files_generated: list[str] = Field(default_factory=list)
    conversion_summary: str = ""


class DocumentationStepResult(StepResult):
    """Specific result structure for Documentation step."""

    documentation_created: str = ""
    final_report: str = ""
