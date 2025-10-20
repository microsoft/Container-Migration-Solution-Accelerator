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


class FileStatus(str, Enum):
    SUCCESS = "Success"
    PARTIAL = "Partial"
    FAILED = "Failed"


# Enhanced File Models for comprehensive file tracking
class ConvertedFile(KernelBaseModel):
    """Enhanced converted file with comprehensive metadata"""

    source_file: str = Field(description="Original source file name")
    converted_file: str = Field(description="Converted Azure file name")
    conversion_status: FileStatus = Field(description="Conversion success status")
    accuracy_rating: str = Field(description="Accuracy percentage (e.g., '95%')")
    concerns: list[str] = Field(
        default_factory=list, description="Any conversion concerns"
    )
    azure_enhancements: list[str] = Field(
        default_factory=list, description="Azure-specific enhancements added"
    )
    file_type: str = Field(
        description="Type of file (deployment, service, configmap, etc.)"
    )
    complexity_score: str | None = Field(
        default=None, description="Complexity rating (Low/Medium/High)"
    )


class GeneratedFile(KernelBaseModel):
    """Base class for generated files with common metadata"""

    file_name: str = Field(description="Generated file name")
    file_type: str = Field(description="Type of file")
    content_summary: str = Field(description="Brief summary of file contents")
    file_size_estimate: str | None = Field(
        default=None, description="Estimated file size (e.g., '2.5KB', '1.2MB')"
    )


class AnalysisFile(GeneratedFile):
    """Analysis phase generated files"""

    key_findings: list[str] = Field(
        default_factory=list, description="Key findings in this analysis"
    )
    source_platform: str | None = Field(
        default=None, description="Source platform analyzed (EKS, GKE, etc.)"
    )
    analysis_depth: str | None = Field(
        default=None, description="Analysis depth (Basic, Detailed, Comprehensive)"
    )


class DesignFile(GeneratedFile):
    """Design phase generated files"""

    azure_services: list[str] = Field(
        default_factory=list, description="Azure services covered"
    )
    design_patterns: list[str] = Field(
        default_factory=list, description="Design patterns implemented"
    )
    security_considerations: list[str] = Field(
        default_factory=list, description="Security aspects covered"
    )


class DocumentationFile(GeneratedFile):
    """Documentation phase generated files"""

    target_audience: str = Field(
        description="Intended audience (developers, ops, management, etc.)"
    )
    document_sections: list[str] = Field(
        default_factory=list, description="Main sections in the document"
    )
    technical_level: str | None = Field(
        default=None, description="Technical complexity level"
    )


class GeneratedFilesCollection(KernelBaseModel):
    """Comprehensive collection of all generated files across migration phases"""

    analysis: list[AnalysisFile] = Field(
        default_factory=list, description="Files generated during analysis phase"
    )

    design: list[DesignFile] = Field(
        default_factory=list, description="Files generated during design phase"
    )

    yaml: list[ConvertedFile] = Field(
        default_factory=list,
        description="YAML conversion results with detailed metadata",
    )

    documentation: list[DocumentationFile] = Field(
        default_factory=list, description="Files generated during documentation phase"
    )

    @property
    def total_files_generated(self) -> int:
        """
        Automatically calculate total files generated across all phases.
        This ensures the count is always accurate and prevents hardcoded values.
        """
        return (
            len(self.analysis)
            + len(self.design)
            + len(self.yaml)
            + len(self.documentation)
        )


# Existing models continue below...


class MigrationReportSections(KernelBaseModel):
    executive_summary: str = Field(
        description="High-level migration overview with quantified outcomes and success metrics"
    )
    analysis_summary: str = Field(
        description="Concise summary of analysis findings: platform assessment, file inventory, complexity evaluation"
    )
    design_summary: str = Field(
        description="Architecture overview: key Azure services selected, security model, integration patterns"
    )
    conversion_summary: str = Field(
        description="Conversion results: accuracy metrics, technical challenges resolved, validation outcomes"
    )


class ContentDescriptions(KernelBaseModel):
    analysis_insights: str = Field(
        description="Key technical discoveries and platform assessment findings"
    )
    architectural_decisions: str = Field(
        description="Major design choices, service selections, and implementation approaches"
    )
    conversion_achievements: str = Field(
        description="Technical conversion successes, accuracy scores, and validation results"
    )


class TechnicalCompleteness(KernelBaseModel):
    analysis_integration: str = Field(
        description="Analysis results integration status (e.g., '100% - All analysis results fully integrated')"
    )
    design_integration: str = Field(
        description="Design specifications integration status (e.g., '100% - All design specifications fully integrated')"
    )
    conversion_integration: str = Field(
        description="Conversion results integration status (e.g., '100% - All conversion results fully integrated')"
    )


class DocumentationQuality(KernelBaseModel):
    technical_accuracy: str = Field(
        description="Technical accuracy assessment (e.g., 'Enterprise-grade technical accuracy')"
    )
    completeness: str = Field(
        description="Completeness assessment (e.g., 'Comprehensive coverage with detail descriptions')"
    )
    professional_standard: str = Field(
        description="Professional standard assessment (e.g., 'Professional documentation suitable for enterprise use')"
    )
    usability: str = Field(
        description="Usability assessment (e.g., 'Clear, actionable procedures for implementation teams')"
    )


class AggregatedResults(KernelBaseModel):
    total_files_analyzed: str = Field(
        description="Total files analyzed from analysis phase"
    )
    total_files_converted: str = Field(
        description="Total files converted from conversion phase"
    )
    overall_migration_complexity: str = Field(
        description="Comprehensive complexity assessment"
    )
    overall_success_metrics: str = Field(
        description="Complete success and quality metrics"
    )
    # Additional fields required by documentation step
    executive_summary: str = Field(
        default="",
        description="Executive summary of the migration readiness assessment",
    )
    total_files_processed: int = Field(
        default=0, description="Total number of files processed across all phases"
    )
    overall_success_rate: str = Field(
        default="", description="Overall success rate percentage (e.g., '95%')"
    )


class ExpertCollaboration(KernelBaseModel):
    """Expert collaboration details for documentation step"""

    participating_experts: list[str] = Field(
        default_factory=list,
        description="List of experts who contributed to the documentation",
    )
    consensus_achieved: bool = Field(
        default=True, description="Whether consensus was achieved among experts"
    )
    expert_insights: list[str] = Field(
        default_factory=list,
        description="List of expert insights gathered during collaboration",
    )
    quality_validation: str = Field(
        default="", description="Quality validation status from QA review"
    )


class DocumentationOutput(KernelBaseModel):
    migration_report_sections: MigrationReportSections = Field(
        description="Migration report sections with detailed summaries"
    )
    content_descriptions: ContentDescriptions = Field(
        description="Descriptions of key content areas"
    )
    technical_completeness: TechnicalCompleteness = Field(
        description="Technical completeness assessment"
    )
    documentation_quality: DocumentationQuality = Field(
        description="Documentation quality metrics"
    )
    aggregated_results: AggregatedResults = Field(
        description="Aggregated results from all phases"
    )
    summary: str = Field(
        description="Comprehensive migration documentation completion summary"
    )
    expert_insights: list[str] = Field(
        description="List of expert insights from different agents"
    )
    expert_collaboration: ExpertCollaboration = Field(
        default_factory=ExpertCollaboration,
        description="Expert collaboration details and consensus information",
    )

    # Enhanced file collection - this replaces migration_report_file
    generated_files: GeneratedFilesCollection = Field(
        description="Comprehensive collection of all generated files across all phases"
    )


class Documentation_ExtendedBooleanResult(BooleanResult):
    """
    Extended Boolean Result class to include additional metadata for documentation phase.
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

    termination_output: DocumentationOutput | None = Field(
        default=None, description="Output of the documentation termination analysis"
    )

    termination_type: TerminationType = Field(
        default=TerminationType.SOFT_COMPLETION,
        description="Specific type of termination",
    )

    blocking_issues: list[str] = Field(
        default_factory=list, description="Specific blocking issues if hard terminated"
    )
