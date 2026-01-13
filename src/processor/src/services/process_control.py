"""Process control plane.

This module provides a shared, replica-agnostic control mechanism for managing
process execution (e.g., requesting a hard kill by process_id).

Rationale:
- With multiple replicas, an external HTTP request cannot reliably route to the
  instance currently executing a given process_id.
- Instead, an external API writes a shared control record.
- The owning instance (the one with the process_id in-flight) observes that
  record and executes the local hard-kill logic.

Storage:
- Uses Cosmos DB via sas-cosmosdb when configured.
- Falls back to an in-memory store in development mode.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from pydantic import Field
from sas.cosmosdb.sql import RepositoryBase, RootEntityBase

from libs.application.application_context import AppContext

logger = logging.getLogger(__name__)


def _utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


class ProcessControl(RootEntityBase["ProcessControl", str]):
    """Control record keyed by process_id."""

    id: str  # process_id

    kill_requested: bool = False
    kill_requested_at: str = ""
    kill_reason: str = ""

    # pending -> executing -> executed
    kill_state: str = ""
    kill_ack_instance_id: str = ""
    kill_ack_at: str = ""
    kill_executed_at: str = ""

    last_update_time: str = Field(default_factory=_utc_timestamp)


class ProcessControlRepository(RepositoryBase[ProcessControl, str]):
    def __init__(self, app_context: AppContext):
        config = app_context.configuration
        if not config:
            raise ValueError("App context configuration is required")

        container_name = getattr(config, "cosmos_db_control_container_name", "")
        super().__init__(
            account_url=config.cosmos_db_account_url,
            database_name=config.cosmos_db_database_name,
            container_name=container_name,
        )


class ProcessControlManager:
    """Shared control manager with dev-mode in-memory fallback."""

    def __init__(self, app_context: AppContext | None = None):
        self.app_context = app_context
        self._read_semaphore = asyncio.Semaphore(1)

        self._in_memory: dict[str, ProcessControl] = {}

        is_development = (
            not app_context
            or not app_context.configuration
            or not app_context.configuration.cosmos_db_account_url
            or app_context.configuration.cosmos_db_account_url.startswith("http://<")
            or "localhost" in app_context.configuration.cosmos_db_account_url
        )

        container_name = (
            getattr(app_context.configuration, "cosmos_db_control_container_name", "")
            if app_context and app_context.configuration
            else ""
        )

        if is_development or not container_name or container_name.startswith("<"):
            logger.info("[CONTROL] Development mode - using in-memory process control")
            self.repository: ProcessControlRepository | None = None
        else:
            if app_context is None:
                self.repository = None
            else:
                self.repository = ProcessControlRepository(app_context)

    async def get(self, process_id: str) -> ProcessControl | None:
        if not process_id:
            return None

        if not self.repository:
            return self._in_memory.get(process_id)

        async with self._read_semaphore:
            try:
                return await self.repository.get_async(process_id)
            except Exception:
                logger.exception(
                    "[CONTROL] Failed to read control record (process_id=%s)",
                    process_id,
                )
                return None

    async def request_kill(self, process_id: str, reason: str = "") -> ProcessControl:
        """Idempotently request kill for a process_id."""

        record = await self.get(process_id)
        if not record:
            record = ProcessControl(id=process_id)

        record.kill_requested = True
        record.kill_requested_at = record.kill_requested_at or _utc_timestamp()
        record.kill_reason = reason or record.kill_reason
        record.kill_state = record.kill_state or "pending"
        record.last_update_time = _utc_timestamp()

        await self._upsert(record)
        return record

    async def ack_executing(self, process_id: str, instance_id: str) -> None:
        record = await self.get(process_id)
        if not record:
            # Create a minimal record; this can happen if the kill request was made
            # while Cosmos was unavailable and later restored.
            record = ProcessControl(id=process_id)

        if not record.kill_requested:
            return

        record.kill_state = "executing"
        record.kill_ack_instance_id = instance_id
        record.kill_ack_at = _utc_timestamp()
        record.last_update_time = _utc_timestamp()
        await self._upsert(record)

    async def mark_executed(self, process_id: str, instance_id: str) -> None:
        record = await self.get(process_id)
        if not record:
            record = ProcessControl(id=process_id)

        record.kill_state = "executed"
        record.kill_ack_instance_id = record.kill_ack_instance_id or instance_id
        record.kill_executed_at = _utc_timestamp()
        record.last_update_time = _utc_timestamp()
        await self._upsert(record)

    async def _upsert(self, record: ProcessControl) -> None:
        if not self.repository:
            self._in_memory[record.id] = record
            return

        try:
            existing = await self.repository.get_async(record.id)
            if existing:
                await self.repository.update_async(record)
            else:
                await self.repository.add_async(record)
        except Exception:
            # Best-effort: control plane should not crash the worker.
            logger.exception(
                "[CONTROL] Failed to upsert control record (process_id=%s)", record.id
            )
