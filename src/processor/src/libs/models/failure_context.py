"""
Simple Failure Context Models for Unhappy Path Handling.

Focused on practical, collectable failure information for migration debugging.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from .orchestration_models import TerminationType


class SystemFailureContext(BaseModel):
    """Realistic failure context we can actually collect reliably"""

    # Core error information
    error_type: str = Field(description="Exception class name")
    error_message: str = Field(description="Exception message")
    stack_trace: str = Field(description="Full traceback")

    # Context information
    timestamp: datetime = Field(description="When failure occurred")
    process_id: str = Field(description="Process identifier")
    step_name: str = Field(description="Which step failed")
    step_phase: str = Field(description="Phase within step", default="unknown")

    # Input context for debugging
    input_context_summary: str = Field(
        description="Summary of what was being processed when failure occurred",
        default="no context available",
    )

    # Enhanced error details (from full_error_details) to ensure no data loss
    exception_module: str | None = Field(
        default=None, description="Exception module name"
    )
    exception_args: list = Field(
        default_factory=list, description="Exception arguments"
    )
    exception_cause: str | None = Field(
        default=None, description="Exception cause if available"
    )
    exception_context: str | None = Field(
        default=None, description="Exception context if available"
    )


class HardTerminationContext(BaseModel):
    """Context for hard terminations requiring detailed analysis"""

    # Termination details from ExtendedBooleanResult
    termination_type: TerminationType = Field(description="Type of hard termination")
    termination_reason: str = Field(description="Human-readable termination reason")
    blocking_issues: list[str] = Field(
        description="Specific issues that caused termination", default_factory=list
    )
    retry_suggestions: list[str] = Field(
        description="Suggested recovery actions", default_factory=list
    )
    confidence_level: float = Field(
        description="Confidence in termination decision", default=1.0
    )

    # Input context
    input_files: list[str] = Field(
        description="Files being processed when terminated", default_factory=list
    )

    # Business impact assessment
    manual_intervention_required: bool = Field(
        description="Whether manual intervention is needed", default=False
    )
    escalation_level: str = Field(
        description="LOW, MEDIUM, HIGH, CRITICAL", default="MEDIUM"
    )


class StepFailureState(BaseModel):
    """Complete failure state for a step - combines both context types"""

    # Basic failure info
    result: bool = Field(
        default=False, description="Step result - always False for failures"
    )
    reason: str = Field(description="Brief failure reason")

    # Detailed context (one will be populated based on failure type)
    system_failure_context: SystemFailureContext | None = Field(default=None)
    hard_termination_context: HardTerminationContext | None = Field(default=None)

    # Execution metadata
    execution_time: float = Field(
        description="How long step ran before failing", default=0.0
    )
    files_attempted: list[str] = Field(
        description="Files that were attempted to be processed", default_factory=list
    )
