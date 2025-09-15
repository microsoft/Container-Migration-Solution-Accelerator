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


class OutputFile(KernelBaseModel):
    file: str = Field(description="Design document or architecture file path")
    description: str = Field(description="Description of design output")


class DesignOutput(KernelBaseModel):
    result: str = Field(description="The result of the design step (Success or Fail)")
    summary: str = Field(description="Summary of the Azure architecture design")
    azure_services: list[str] = Field(description="List of recommended Azure services")
    architecture_decisions: list[str] = Field(
        description="Key architecture decisions made"
    )
    outputs: list[OutputFile] = Field(
        description="List of generated design output files"
    )
    # Optional reasoning fields for when agents cannot complete certain aspects
    incomplete_reason: str | None = Field(
        default=None,
        description="Reason provided when design cannot be fully completed",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="List of information that was missing or unavailable during design",
    )


class Design_ExtendedBooleanResult(BooleanResult):
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

    termination_output: DesignOutput | None = Field(
        default=None, description="Output of the termination analysis"
    )

    termination_type: TerminationType = Field(
        default=TerminationType.SOFT_COMPLETION,
        description="Specific type of termination",
    )

    blocking_issues: list[str] = Field(
        default_factory=list, description="Specific blocking issues if hard terminated"
    )
