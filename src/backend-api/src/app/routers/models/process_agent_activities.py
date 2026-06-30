from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sas.cosmosdb.sql import EntityBase, RepositoryBase, RootEntityBase


def _get_utc_timestamp() -> str:
    """Get current UTC timestamp in human-readable format"""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


class AgentActivityHistory(EntityBase):
    """Historical record of agent activity"""

    timestamp: str = Field(default_factory=_get_utc_timestamp)
    action: str
    message_preview: str = ""
    step: str = ""
    tool_used: str = ""  # Name of tool used, empty if no tool


class AgentActivity(EntityBase):
    """Current activity status of an agent"""

    name: str
    current_action: str = "idle"
    last_message_preview: str = ""
    last_full_message: str = ""  # NEW: Store full message content for dashboard
    current_speaking_content: str = ""  # NEW: What agent is currently saying
    last_update_time: str = Field(default_factory=_get_utc_timestamp)
    is_active: bool = False
    is_currently_speaking: bool = False  # NEW: Track if agent is currently speaking
    is_currently_thinking: bool = False  # NEW: Track if agent is processing/analyzing
    thinking_about: str = ""  # NEW: What the agent is thinking about/working on
    current_reasoning: str = ""  # NEW: Agent's current reasoning process
    last_reasoning: str = ""  # NEW: Agent's reasoning from last response
    reasoning_steps: list[str] = Field(
        default_factory=list
    )  # NEW: Step-by-step reasoning trail
    participation_status: str = (
        "ready"  # NEW: ready, thinking, speaking, completed, waiting
    )
    last_activity_summary: str = ""  # NEW: Brief summary of last significant action
    message_word_count: int = 0  # NEW: Track message length for dashboard
    activity_history: list[AgentActivityHistory] = Field(
        default_factory=list
    )  # Historical activities
    step_reset_count: int = 0  # Track how many times agent was reset for new steps


class ProcessStatus(RootEntityBase["ProcessStatus", str]):
    """Overall process status for user visibility"""

    id: str  # This is the primary key (process_id)
    phase: str = ""
    step: str = ""
    status: str = "running"  # running, completed, failed, qa_review
    agents: dict[str, AgentActivity] = Field(default_factory=dict)
    last_update_time: str = Field(default_factory=_get_utc_timestamp)
    started_at_time: str = Field(default_factory=_get_utc_timestamp)

    # Failure information fields
    failure_reason: str = ""  # High-level failure reason
    failure_details: str = ""  # Detailed error message
    failure_step: str = ""  # Which step failed
    failure_agent: str = ""  # Which agent caused the failure (if applicable)
    failure_timestamp: str = ""  # When the failure occurred
    stack_trace: str = ""  # Full stack trace for debugging


class AgentActivityRepository(RepositoryBase[ProcessStatus, str]):
    def __init__(self, account_url: str, database_name: str, container_name: str):
        super().__init__(
            account_url=account_url,
            database_name=database_name,
            container_name=container_name,
        )


class AgentStatus(BaseModel):
    name: str
    is_currently_speaking: bool
    is_active: bool
    current_action: str
    current_speaking_content: str
    last_message: str
    participating_status: str
    last_reasoning: str
    last_activity_summary: str
    current_reasoning: str
    thinking_about: str
    reasoning_steps: list[str] = Field(default_factory=list)


class ProcessStatusSnapshot(BaseModel):
    """Snapshot of the process status for a specific point in time"""

    process_id: str
    step: str
    phase: str
    status: str
    agents: list[AgentStatus]
    last_update_time: str
    started_at_time: str
    # Failure information fields
    failure_reason: str = ""  # High-level failure reason
    failure_details: str = ""  # Detailed error message
    failure_step: str = ""  # Which step failed
    failure_agent: str = ""  # Which agent caused the failure (if applicable)
    failure_timestamp: str = ""  # When the failure occurred
    stack_trace: str = ""  # Full stack trace for debugging
