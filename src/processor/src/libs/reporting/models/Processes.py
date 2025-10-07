from logging import getLogger
from datetime import UTC, datetime
from typing import Any

from pydantic import Field
from sas.cosmosdb.sql import EntityBase, RootEntityBase, RepositoryBase

from src.libs.application.application_context import AppContext

from .Processes import Process

logger = getLogger(__name__)


def _get_utc_timestamp(self) -> str:
    """Get current UTC timestamp in human-readable format"""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


class AgentActivityHistory(EntityBase):
    timestamp: str = Field(default_factory=_get_utc_timestamp)
    action: str
    message_preview: str = ""
    step: str = ""
    tool_used: str = ""


class AgentActivity(EntityBase):
    name: str
    current_action: str = "idle"
    last_message_preview: str = ""
    last_full_message: str = ""
    current_speaking_content: str = ""
    last_update_time: str = Field(default_factory=_get_utc_timestamp)
    is_active: bool = False
    is_currently_speaking: bool = False
    is_currently_thinking: bool = False
    thinking_about: str = ""
    current_reasoning: str = ""
    last_reasoning: str = ""
    reasoning_steps: list[str] = Field(default_factory=list)
    participation_status: str = "ready"
    last_activity_summary: str = ""
    message_word_count: int = 0
    activity_history: list[AgentActivityHistory] = Field(default_factory=list)
    step_reset_count: int = 0


class Agent(EntityBase):
    name: str
    activity: AgentActivity


class Step(EntityBase):
    name: str
    start_time: str = Field(datetime.now().isoformat())
    end_time: str = Field(datetime.now().isoformat())
    elapsed_time: float = Field(0.0)
    result: dict[str, Any]
    agents: list[str] = Field(default_factory=list)


class Process(RootEntityBase[Process, str]):
    id: str = Field(...)
    start_time: str = Field(datetime.now().isoformat())
    end_time: str = Field(datetime.now().isoformat())
    elapsed_time: float = Field(0.0)
    is_successful: bool = Field(True)
    active_step: str = Field(...)
    active_phase: str = Field(...)
    steps: list[Step] = Field(default_factory=list)


class ProcessRepository(RepositoryBase[Process, str]):
    def __init__(self, app_context: AppContext):
        config = app_context.configuration
        if not config:
            raise ValueError("Configuration is required")

        super().__init__(
            account_url=config.cosmos_db_account_url,
            database_name=config.cosmos_db_database_name,
            container_name=config.cosmos_db_container_name
        )


class ProcessTelemetry:
    process_repository: ProcessRepository

    def __init__(self, app_context: AppContext):
        self.app_context = app_context
        # self.process_repository = ProcessRepository(app_context)

    # Async context manager methods
    async def __aenter__(self):
        self.process_repository = ProcessRepository(self.app_context)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.process_repository.__aexit__(exc_type, exc_val, exc_tb)

    async def create_process(self, process_id: str, step: str, phase: str):
        if not self.process_repository:
            raise ValueError("Process repository is not initialized")

        process = Process(id=process_id, active_step=step, active_phase=phase)
        # step initialization
        process.steps.append(Step(name=step))

        async with self.process_repository as process_repo:
            await process_repo.add_async(process)
            logger.info(f"Process created: {process.id}")
            return process

    async def get_process(self, process_id: str):
        if not self.process_repository:
            raise ValueError("Process repository is not initialized")

        async with self.process_repository as process_repo:
            logger.info(f"Getting process: {process_id}")
            return await process_repo.get_async(process_id)