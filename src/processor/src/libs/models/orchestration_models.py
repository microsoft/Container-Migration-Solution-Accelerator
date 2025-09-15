"""
Extended Orchestration Models for Enhanced Process Control.

This module provides enhanced models that extend Semantic Kernel's base models
with additional semantic information for better process control and decision making.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from semantic_kernel.agents.orchestration.group_chat import BooleanResult


class TerminationType(str, Enum):
    """Types of conversation termination."""

    SOFT_COMPLETION = "soft_completion"  # Work completed successfully
    HARD_BLOCKED = "hard_blocked"  # Cannot proceed due to blockers
    HARD_ERROR = "hard_error"  # Critical error prevents continuation
    HARD_TIMEOUT = "hard_timeout"  # Time limits exceeded
    HARD_RESOURCE_LIMIT = "hard_resource_limit"  # Resource constraints hit
    SOFT_EARLY_EXIT = "soft_early_exit"  # Early completion (e.g., base class)


class ExtendedBooleanResult(BaseModel):
    """
    Extended termination result with enhanced semantic information.

    Extends the basic BooleanResult concept with additional context about
    the nature of termination - whether it's a successful completion or
    a blocking issue that prevents further progress.
    """

    model_config = {"validate_assignment": True}

    # Core termination decision (compatible with BooleanResult)
    result: bool = Field(description="Whether the conversation should terminate")

    reason: str = Field(
        description="Human-readable explanation for the termination decision",
        min_length=1,
    )

    # Enhanced semantic information
    is_hard_terminated: bool = Field(
        description="True if termination is due to blocking issues, False if completion",
        default=False,
    )

    termination_type: TerminationType = Field(
        description="Specific type of termination for better process control",
        default=TerminationType.SOFT_COMPLETION,
    )

    # Additional context
    blocking_issues: list[str] = Field(
        description="List of specific issues that caused hard termination",
        default_factory=list,
    )

    retry_suggestions: list[str] = Field(
        description="Suggested actions for resolving blocking issues",
        default_factory=list,
    )

    confidence_level: float = Field(
        description="Confidence in the termination decision (0.0-1.0)",
        default=1.0,
        ge=0.0,
        le=1.0,
    )

    metadata: dict[str, Any] = Field(
        description="Additional context-specific metadata", default_factory=dict
    )

    @classmethod
    def from_boolean_result(
        cls,
        boolean_result: BooleanResult,
        is_hard_terminated: bool = False,
        termination_type: TerminationType = TerminationType.SOFT_COMPLETION,
    ) -> "ExtendedBooleanResult":
        """Convert a standard BooleanResult to ExtendedBooleanResult."""
        return cls(
            result=boolean_result.result,
            reason=boolean_result.reason,
            is_hard_terminated=is_hard_terminated,
            termination_type=termination_type,
        )

    def to_boolean_result(self) -> BooleanResult:
        """Convert back to standard BooleanResult for SK compatibility."""
        return BooleanResult(result=self.result, reason=self.reason)

    def is_successful_completion(self) -> bool:
        """Check if this represents successful work completion."""
        return (
            self.result
            and not self.is_hard_terminated
            and self.termination_type == TerminationType.SOFT_COMPLETION
        )

    def is_blocking_termination(self) -> bool:
        """Check if this represents a blocking termination."""
        return self.result and self.is_hard_terminated

    def should_retry(self) -> bool:
        """Check if the process should be retried based on termination type."""
        retry_types = {
            TerminationType.HARD_ERROR,
            TerminationType.HARD_TIMEOUT,
            TerminationType.HARD_RESOURCE_LIMIT,
        }
        return self.termination_type in retry_types

    def should_escalate(self) -> bool:
        """Check if the issue should be escalated to human intervention."""
        return (
            self.is_hard_terminated
            and self.termination_type == TerminationType.HARD_BLOCKED
        )


class OrchestrationDecision(BaseModel):
    """
    Comprehensive orchestration decision with multiple choice types.

    This model can represent various orchestration decisions beyond just
    termination, such as agent selection, flow control, etc.
    """

    model_config = {"validate_assignment": True}

    decision_type: str = Field(description="Type of decision being made")
    primary_choice: str = Field(description="Primary decision/choice")
    confidence: float = Field(description="Confidence in decision", ge=0.0, le=1.0)
    reasoning: str = Field(description="Detailed reasoning for the decision")
    alternative_choices: list[str] = Field(default_factory=list)
    context_factors: dict[str, Any] = Field(default_factory=dict)


# Convenience factory functions
def create_soft_termination(
    reason: str, confidence: float = 1.0
) -> ExtendedBooleanResult:
    """Create a soft termination (successful completion)."""
    return ExtendedBooleanResult(
        result=True,
        reason=reason,
        is_hard_terminated=False,
        termination_type=TerminationType.SOFT_COMPLETION,
        confidence_level=confidence,
    )


def create_hard_termination(
    reason: str,
    termination_type: TerminationType,
    blocking_issues: list[str] = None,
    retry_suggestions: list[str] = None,
    confidence: float = 1.0,
) -> ExtendedBooleanResult:
    """Create a hard termination (blocked/error)."""
    return ExtendedBooleanResult(
        result=True,
        reason=reason,
        is_hard_terminated=True,
        termination_type=termination_type,
        blocking_issues=blocking_issues or [],
        retry_suggestions=retry_suggestions or [],
        confidence_level=confidence,
    )


def create_continuation(reason: str, confidence: float = 1.0) -> ExtendedBooleanResult:
    """Create a continuation decision (don't terminate)."""
    return ExtendedBooleanResult(
        result=False,
        reason=reason,
        is_hard_terminated=False,
        termination_type=TerminationType.SOFT_COMPLETION,
        confidence_level=confidence,
    )
