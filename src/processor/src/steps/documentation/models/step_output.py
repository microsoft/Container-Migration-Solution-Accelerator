# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Pydantic models describing documentation outputs and generated artifacts."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class TerminationType(str, Enum):
    SOFT_COMPLETION = "soft_completion"
    HARD_BLOCKED = "hard_blocked"
    HARD_ERROR = "hard_error"
    HARD_TIMEOUT = "hard_timeout"


class FileStatus(str, Enum):
    SUCCESS = "Success"
    PARTIAL = "Partial"
    FAILED = "Failed"


class ConvertedFile(BaseModel):
    model_config = {"extra": "forbid"}

    source_file: str = Field(description="Original source file name")
    converted_file: str = Field(description="Converted AKS file name")
    conversion_status: FileStatus = Field(description="Conversion success status")
    accuracy_rating: str = Field(description="Accuracy percentage (e.g., '95%')")
    concerns: list[str] = Field(default_factory=list, description="Conversion concerns")
    azure_enhancements: list[str] = Field(
        default_factory=list, description="Azure-specific enhancements added"
    )
    file_type: str = Field(description="Type of file (deployment, service, etc.)")


class GeneratedFile(BaseModel):
    model_config = {"extra": "forbid"}

    file_name: str = Field(description="Generated file name")
    file_type: str = Field(description="Type of file")
    content_summary: str = Field(description="Brief summary of file contents")


class AnalysisFile(GeneratedFile):
    key_findings: list[str] = Field(default_factory=list, description="Key findings")
    source_platform: str | None = Field(default=None, description="Source platform")


class DesignFile(GeneratedFile):
    azure_services: list[str] = Field(
        default_factory=list, description="Azure services covered"
    )
    design_patterns: list[str] = Field(
        default_factory=list, description="Design patterns implemented"
    )


class DocumentationFile(GeneratedFile):
    target_audience: str = Field(description="Intended audience")
    document_sections: list[str] = Field(default_factory=list, description="Sections")


class GeneratedFilesCollection(BaseModel):
    model_config = {"extra": "forbid"}

    analysis: list[AnalysisFile] = Field(
        default_factory=list, description="Files generated during analysis"
    )
    design: list[DesignFile] = Field(
        default_factory=list, description="Files generated during design"
    )
    yaml: list[ConvertedFile] = Field(
        default_factory=list, description="YAML conversion results"
    )
    documentation: list[DocumentationFile] = Field(
        default_factory=list, description="Files generated during documentation"
    )

    total_files_generated: int = Field(
        default=0,
        description="Total files generated across all phases",
    )


class ExpertCollaboration(BaseModel):
    model_config = {"extra": "forbid"}

    participating_experts: list[str] = Field(
        default_factory=list, description="Experts who contributed"
    )
    consensus_achieved: bool = Field(
        default=False, description="Whether consensus was achieved"
    )
    expert_insights: list[str] = Field(
        default_factory=list, description="Expert insights gathered"
    )
    quality_validation: str = Field(default="", description="QA validation status")


class AggregatedResults(BaseModel):
    model_config = {"extra": "forbid"}

    executive_summary: str = Field(description="Executive migration summary")
    total_files_processed: int = Field(description="Total files processed")
    overall_success_rate: str = Field(description="Overall success rate (e.g., '95%')")
    platform_detected: str = Field(description="Detected source platform")
    conversion_accuracy: str = Field(description="Overall conversion accuracy")
    documentation_completeness: str = Field(
        description="Documentation completeness assessment"
    )
    enterprise_readiness: str = Field(description="Enterprise readiness assessment")


class ProcessMetrics(BaseModel):
    model_config = {"extra": "forbid"}

    platform_detected: str = Field(description="Detected source platform")
    conversion_accuracy: str = Field(description="Overall conversion accuracy")
    documentation_completeness: str = Field(
        description="Documentation completeness assessment"
    )
    enterprise_readiness: str = Field(description="Enterprise readiness assessment")


class DocumentationOutput(BaseModel):
    """Aggregated documentation results and generated artifacts."""

    model_config = {"extra": "forbid"}

    aggregated_results: AggregatedResults = Field(description="Aggregated results")
    generated_files: GeneratedFilesCollection = Field(
        description="Collection of all generated files"
    )
    expert_collaboration: ExpertCollaboration = Field(
        description="Expert collaboration and consensus"
    )
    process_metrics: ProcessMetrics = Field(description="Process metrics")
    summary: str = Field(description="Documentation completion summary")


class Documentation_ExtendedBooleanResult(BaseModel):
    """Wrapper result for the documentation step, including termination metadata."""

    model_config = {"arbitrary_types_allowed": True, "extra": "forbid"}

    result: bool = Field(default=False, description="Whether the step completed")
    reason: str = Field(default="", description="Reason for the decision")
    is_hard_terminated: bool = Field(
        default=False, description="True if termination is due to blocking issues"
    )
    termination_output: DocumentationOutput | None = Field(
        default=None, description="Structured documentation output"
    )
    termination_type: TerminationType = Field(
        default=TerminationType.SOFT_COMPLETION, description="Termination type"
    )
    blocking_issues: list[str] = Field(default_factory=list, description="Blockers")

    process_id: str | None = Field(
        default=None, description="Workflow process identifier propagated from Convert"
    )
