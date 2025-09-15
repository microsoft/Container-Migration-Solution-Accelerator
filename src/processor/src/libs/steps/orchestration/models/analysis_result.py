from enum import Enum

from pydantic import Field
from semantic_kernel.agents.orchestration.group_chat import (
    BooleanResult,
)
from semantic_kernel.kernel_pydantic import KernelBaseModel


class TerminationType(str, Enum):
    SOFT_COMPLETION = "soft_completion"
    HARD_BLOCKED = "hard_blocked"
    HARD_ERROR = "hard_error"
    HARD_TIMEOUT = "hard_timeout"


class SuccessType(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"


class FileType(KernelBaseModel):
    filename: str = Field(description="Discovered file name")
    type: str = Field(description="File type (e.g., Deployment, Service, ConfigMap)")
    complexity: str = Field(description="Complexity level (Low/Medium/High)")
    azure_mapping: str = Field(description="Corresponding Azure service/resource")


class ComplexityAnalysis(KernelBaseModel):
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


class MigrationReadiness(KernelBaseModel):
    overall_score: str = Field(description="Overall migration readiness score")
    concerns: list[str] = Field(description="List of migration concerns")
    recommendations: list[str] = Field(description="List of migration recommendations")


class AnalysisOutput(KernelBaseModel):
    platform_detected: str = Field(description="Platform detected (EKS or GKE only)")
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


class Analysis_ExtendedBooleanResult(BooleanResult):
    """
    Extended Boolean Result class to include additional metadata.
    """

    model_config = {"arbitrary_types_allowed": True, "extra": "forbid"}

    # Base fields required by BooleanResult
    result: bool = Field(
        default=False, description="Whether the conversation should terminate"
    )
    reason: str = Field(
        default="",
        description="Human-readable explanation for the termination decision",
    )

    # Your new fields
    is_hard_terminated: bool = Field(
        default=False, description="True if termination is due to blocking issues"
    )

    termination_output: AnalysisOutput | None = Field(
        default=None, description="Output of the termination analysis"
    )

    termination_type: TerminationType = Field(
        default=TerminationType.SOFT_COMPLETION,
        description="Specific type of termination",
    )

    blocking_issues: list[str] = Field(
        default_factory=list, description="Specific blocking issues if hard terminated"
    )
