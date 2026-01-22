# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Pydantic models for analysis step outputs and termination metadata."""

from enum import Enum

from pydantic import BaseModel, Field


class TerminationType(str, Enum):
    SOFT_COMPLETION = "soft_completion"
    HARD_BLOCKED = "hard_blocked"
    HARD_ERROR = "hard_error"
    HARD_TIMEOUT = "hard_timeout"


class SuccessType(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"


class FileType(BaseModel):
    filename: str = Field(description="Discovered file name")
    type: str = Field(description="File type (e.g., Deployment, Service, ConfigMap)")
    complexity: str = Field(description="Complexity level (Low/Medium/High)")
    azure_mapping: str = Field(description="Corresponding Azure service/resource")


class ComplexityAnalysis(BaseModel):
    network_complexity: str = Field(
        description="Network complexity assessment with details"
    )
    security_complexity: str = Field(
        description="Security complexity assessment with details"
    )
    storage_complexity: str = Field(
        description="Storage complexity assessment with details"
    )
    compute_complexity: str = Field(
        description="Compute complexity assessment with details"
    )


class MigrationReadiness(BaseModel):
    overall_score: str = Field(description="Overall migration readiness score")
    concerns: list[str] = Field(description="List of migration concerns")
    recommendations: list[str] = Field(description="List of migration recommendations")


class AnalysisOutput(BaseModel):
    process_id: str = Field(description="Unique identifier for the analysis process")
    platform_detected: str = Field(
        description="Detected source platform (e.g., EKS, GKE, OpenShift, Rancher, Tanzu, OnPremK8s, GenericK8s)"
    )
    confidence_score: str = Field(
        description="Confidence score for platform detection (e.g., '95%')"
    )
    files_discovered: list[FileType] = Field(
        description="List of discovered YAML files with details"
    )
    complexity_analysis: ComplexityAnalysis = Field(
        description="Multi-dimensional complexity assessment"
    )
    migration_readiness: MigrationReadiness = Field(
        description="Migration readiness assessment"
    )
    summary: str = Field(description="Comprehensive summary of analysis completion")
    expert_insights: list[str] = Field(
        description="List of expert insights from different agents"
    )
    analysis_file: str = Field(description="Path to generated analysis result file")


class Analysis_BooleanExtendedResult(BaseModel):
    """
    Concrete Boolean Result class for Analysis step.
    Non-generic to avoid OpenAI API schema naming issues.
    """

    model_config = {"extra": "forbid"}

    # Base fields required by BooleanResult
    result: bool = Field(
        default=False, description="Whether the conversation should terminate"
    )
    reason: str = Field(
        default="",
        description="Human-readable explanation for the termination decision",
    )

    # Termination metadata
    is_hard_terminated: bool = Field(
        default=False, description="True if termination is due to blocking issues"
    )

    output: AnalysisOutput | None = Field(
        default=None, description="Output of the termination analysis"
    )

    blocking_issues: list[str] = Field(
        default_factory=list, description="Specific blocking issues if hard terminated"
    )

    # Workflow-carry field: lets downstream steps locate the correct process folders.
    process_id: str | None = Field(
        default=None,
        description="Workflow process identifier propagated from process parameter",
    )
