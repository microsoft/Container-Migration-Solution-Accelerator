"""
Failure Context Models

Defines structured data models for capturing comprehensive failure context
across different levels of the migration process.
"""

from datetime import datetime
from enum import Enum
import time
from typing import Any

from pydantic import BaseModel, Field


class FailureType(Enum):
    """Classification of failure types for targeted remediation."""

    # Process Level Failures
    TIMEOUT = "timeout"
    AUTHENTICATION_FAILURE = "authentication_failure"
    CONFIGURATION_ERROR = "configuration_error"
    RESOURCE_EXHAUSTION = "resource_exhaustion"

    # Step Level Failures
    ORCHESTRATOR_ERROR = "orchestrator_error"
    AGENT_COMMUNICATION_FAILURE = "agent_communication_failure"
    STEP_PROCESSING_ERROR = "step_processing_error"

    # File Level Failures
    YAML_PARSING_ERROR = "yaml_parsing_error"
    UNSUPPORTED_API_VERSION = "unsupported_api_version"
    COMPLEX_RESOURCE_MAPPING = "complex_resource_mapping"

    # Agent Level Failures
    LLM_API_FAILURE = "llm_api_failure"
    PROMPT_PROCESSING_ERROR = "prompt_processing_error"
    CONTEXT_SIZE_EXCEEDED = "context_size_exceeded"

    # Infrastructure Failures
    NETWORK_ERROR = "network_error"
    AZURE_SERVICE_UNAVAILABLE = "azure_service_unavailable"
    STORAGE_ACCESS_DENIED = "storage_access_denied"

    # Unknown/Generic
    UNKNOWN_ERROR = "unknown_error"


class FailureSeverity(Enum):
    """Severity levels for failure prioritization."""

    CRITICAL = "critical"  # Blocks entire migration, immediate attention required
    HIGH = "high"  # Prevents step completion, significant impact
    MEDIUM = "medium"  # Partial functionality loss, workaround possible
    LOW = "low"  # Minor issues, process can continue
    INFO = "info"  # Informational, no action required


class FileContext(BaseModel):
    """Context about the file being processed when failure occurred."""

    file_name: str
    file_path: str
    file_size_bytes: int | None = None
    yaml_kind: str | None = None
    yaml_api_version: str | None = None
    processing_stage: str | None = None  # "parsing", "analysis", "conversion", etc.


class AgentContext(BaseModel):
    """Context about the agent involved in the failure."""

    agent_name: str
    agent_role: str  # "azure_expert", "eks_expert", etc.
    current_activity: str | None = None
    conversation_turn: int | None = None
    token_usage: dict[str, int] | None = None


class StepContext(BaseModel):
    """Context about the migration step where failure occurred."""

    step_name: str  # "analysis", "design", "yaml", "documentation"
    step_phase: str | None = (
        None  # "initialization", "orchestration", "result_processing"
    )
    execution_time_seconds: float | None = None
    completed_sub_tasks: list[str] = Field(default_factory=list)


class EnvironmentContext(BaseModel):
    """Environment and system context at time of failure."""

    python_version: str | None = None
    semantic_kernel_version: str | None = None
    azure_region: str | None = None
    container_environment: bool | None = None
    available_memory_mb: int | None = None
    cpu_usage_percent: float | None = None


class FailureContext(BaseModel):
    """
    Comprehensive failure context capturing all relevant information
    for debugging and remediation guidance.
    """

    # Core failure information
    failure_id: str = Field(description="Unique identifier for this failure")
    failure_type: FailureType
    severity: FailureSeverity
    error_message: str
    timestamp: float = Field(default_factory=time.time)

    # Exception details
    exception_type: str | None = None
    stack_trace: str | None = None
    inner_exception: str | None = None

    # Contextual information
    file_context: FileContext | None = None
    agent_context: AgentContext | None = None
    step_context: StepContext | None = None
    environment_context: EnvironmentContext | None = None

    # Additional metadata
    correlation_id: str | None = None  # Links related failures
    retry_count: int = 0
    previous_attempts: list[str] = Field(default_factory=list)
    custom_metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def timestamp_iso(self) -> str:
        """Get timestamp in ISO format for human readability."""
        return datetime.fromtimestamp(self.timestamp).isoformat()

    def add_retry_attempt(self, attempt_description: str) -> None:
        """Track retry attempts for this failure."""
        self.retry_count += 1
        self.previous_attempts.append(
            f"Attempt {self.retry_count}: {attempt_description}"
        )

    def correlate_with(self, other_failure_id: str) -> None:
        """Link this failure with another related failure."""
        if self.correlation_id is None:
            self.correlation_id = other_failure_id


class RemediationSuggestion(BaseModel):
    """Structured remediation guidance for specific failures."""

    action_type: str  # "immediate", "configuration", "code_fix", "retry"
    priority: int  # 1 = highest priority
    title: str
    description: str
    commands: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    estimated_effort: str | None = None  # "5 minutes", "30 minutes", etc.
    success_indicators: list[str] = Field(default_factory=list)


class FailurePattern(BaseModel):
    """Identified patterns in failures for prevention and optimization."""

    pattern_id: str
    pattern_name: str
    description: str
    frequency: int  # How often this pattern occurs
    affected_file_types: list[str] = Field(default_factory=list)
    affected_steps: list[str] = Field(default_factory=list)
    prevention_strategies: list[RemediationSuggestion] = Field(default_factory=list)
