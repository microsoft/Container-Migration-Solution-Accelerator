from datetime import datetime, timezone

from pydantic import Field
from sas.cosmosdb.sql import EntityBase, RootEntityBase


class Process(RootEntityBase["Process", str]):
    user_id: str
    source_file_count: int = 0
    result_file_count: int = 0
    status: str = "initialized"
    # files: list[File] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class File(RootEntityBase["File", str]):  # todo - EntityBase
    process_id: str
    name: str
    blob_path: str
    error_count: int = 0
    syntax_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentStatus(EntityBase):
    name: str
    role: str
    status: str
    time_stamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ProcessStatus(RootEntityBase["ProcessStatus", str]):
    process_id: str
    phase: str
    status: list[AgentStatus]
