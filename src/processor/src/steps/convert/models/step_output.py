from enum import Enum
from pydantic import Field, BaseModel


class TerminationType(str, Enum):
    SOFT_COMPLETION = "soft_completion"
    HARD_BLOCKED = "hard_blocked"
    HARD_ERROR = "hard_error"
    HARD_TIMEOUT = "hard_timeout"


class SuccessType(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"


class ConvertedFile(BaseModel):
    source_file: str = Field(description="Original source file name")
    converted_file: str = Field(description="Converted Azure-compatible file name")
    conversion_status: str = Field(description="Conversion status (Success/Failed)")
    accuracy_rating: str = Field(description="Accuracy percentage of conversion")
    concerns: list[str] = Field(description="List of conversion concerns")
    azure_enhancements: list[str] = Field(
        description="Azure-specific enhancements applied"
    )


class DimensionalAnalysis(BaseModel):
    complexity: str = Field(description="Complexity level (Low/Medium/High)")
    converted_components: list[str] = Field(description="List of converted components")
    azure_optimizations: str = Field(description="Azure-specific optimizations applied")
    concerns: list[str] = Field(description="List of conversion concerns")
    success_rate: str = Field(description="Success rate percentage")


class MultiDimensionalAnalysis(BaseModel):
    network_analysis: DimensionalAnalysis = Field(
        description="Network component analysis"
    )
    security_analysis: DimensionalAnalysis = Field(
        description="Security component analysis"
    )
    storage_analysis: DimensionalAnalysis = Field(
        description="Storage component analysis"
    )
    compute_analysis: DimensionalAnalysis = Field(
        description="Compute component analysis"
    )


class ConversionMetrics(BaseModel):
    total_files: int = Field(description="Total number of files processed")
    successful_conversions: int = Field(description="Number of successful conversions")
    failed_conversions: int = Field(description="Number of failed conversions")
    overall_accuracy: str = Field(description="Overall accuracy percentage")
    azure_compatibility: str = Field(description="Azure compatibility percentage")


class ConversionQuality(BaseModel):
    azure_best_practices: str = Field(
        description="Azure best practices implementation status"
    )
    security_hardening: str = Field(
        description="Security hardening implementation status"
    )
    performance_optimization: str = Field(description="Performance optimization status")
    production_readiness: str = Field(description="Production readiness assessment")


class YamlOutput(BaseModel):
    converted_files: list[ConvertedFile] = Field(
        description="List of converted files with details"
    )
    multi_dimensional_analysis: MultiDimensionalAnalysis = Field(
        description="Multi-dimensional conversion analysis"
    )
    overall_conversion_metrics: ConversionMetrics = Field(
        description="Overall conversion metrics"
    )
    conversion_quality: ConversionQuality = Field(
        description="Conversion quality assessment"
    )
    summary: str = Field(description="Summary of YAML conversion completion")
    expert_insights: list[str] = Field(
        description="List of expert insights from different agents"
    )
    conversion_report_file: str = Field(description="Path to conversion report file")


class Yaml_ExtendedBooleanResult(BaseModel):
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

    termination_output: YamlOutput | None = Field(
        default=None, description="Output of the termination analysis"
    )

    termination_type: TerminationType = Field(
        default=TerminationType.SOFT_COMPLETION,
        description="Specific type of termination",
    )

    blocking_issues: list[str] = Field(
        default_factory=list, description="Specific blocking issues if hard terminated"
    )

    # Workflow-carry field: lets downstream steps locate the correct process folders.
    process_id: str | None = Field(
        default=None,
        description="Workflow process identifier propagated from Design step",
    )
