# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Clean Telemetry Manager for Agent Activity Tracking

This module provides a clean telemetry system for tracking agent activities during migration processes.
No global variables, no locks - just clean async/await based functions with a telemetry manager.

Usage:
    telemetry = TelemetryManager(app_context)
    await telemetry.init_process("process_id", "analysis", "step_1")
    await telemetry.update_agent_activity("agent_name", "thinking", "Processing data...")
"""

import asyncio
import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from pydantic import Field
from sas.cosmosdb.sql import EntityBase, RepositoryBase, RootEntityBase

from libs.application.application_context import AppContext

logger = logging.getLogger(__name__)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _byte_len_text(text: str) -> int:
    return len(text.encode("utf-8", errors="replace"))


def _get_process_blob_container_name() -> str:
    # Keep consistent with existing workflow prompts/orchestrators.
    return (
        os.getenv("PROCESS_BLOB_CONTAINER_NAME") or "processes"
    ).strip() or "processes"


def _get_storage_connection_string() -> str | None:
    # Support common env var names used across this repo/tooling.
    for key in [
        "AZURE_STORAGE_CONNECTION_STRING",
        "STORAGE_CONNECTION_STRING",
        "AzureWebJobsStorage",
    ]:
        val = os.getenv(key)
        if val and val.strip():
            return val.strip()
    return None


async def _upload_text_to_process_blob(
    *,
    process_id: str,
    folder_path: str,
    blob_name: str,
    content: str,
    container_name: str | None = None,
) -> dict[str, Any] | None:
    """Upload text content to the process blob container.

    Returns an artifact pointer dict on success; None if upload isn't configured.
    Never raises.
    """

    try:
        from azure.storage.blob import BlobServiceClient
    except Exception:
        return None

    try:
        container = container_name or _get_process_blob_container_name()
        conn_str = _get_storage_connection_string()
        if not conn_str:
            return None

        # Normalize path pieces
        folder = (folder_path or "").strip().strip("/")
        blob_file = (blob_name or "").strip().lstrip("/")
        if not blob_file:
            return None

        blob_path = f"{folder}/{blob_file}" if folder else blob_file

        service = BlobServiceClient.from_connection_string(conn_str)
        blob_client = service.get_blob_client(container=container, blob=blob_path)
        payload = content.encode("utf-8", errors="replace")
        blob_client.upload_blob(payload, overwrite=True)

        return {
            "container": container,
            "blob": blob_path,
            "bytes": len(payload),
            "sha256": _sha256_text(content),
        }
    except Exception:
        logger.exception(
            "[TELEMETRY] Failed to upload text artifact to blob (process_id=%s, blob_name=%s)",
            process_id,
            blob_name,
        )
        return None


def get_orchestration_agents() -> set[str]:
    """Get orchestration agent names - consolidated to single conversation manager."""
    return {
        # Single conversation manager for all expert discussions and orchestration
        "Coordinator"
        # Note: Consolidated from System, Orchestration_Manager, Agent_Selector
        # Provides clean, conversation-focused telemetry that users understand
    }


# def get_common_agents() -> list[str]:
#     """Get common agent names."""
#     return [
#         "Chief_Architect",
#         "EKS_Expert",
#         "GKE_Expert",
#         "Azure_Expert",
#         "Technical_Writer",
#         "QA_Engineer",
#     ]


def _get_utc_timestamp() -> str:
    """Get current UTC timestamp in human-readable format"""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


_UTC_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S UTC"


def _parse_utc_timestamp(value: str) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, _UTC_TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    except Exception:
        return None


def _build_step_lap_times(
    step_timings: dict[str, dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], float]:
    """Build a UI-friendly list of step lap times.

    Returns (step_lap_times, total_elapsed_seconds).
    """

    timings = step_timings or {}
    now_dt = datetime.now(UTC)
    preferred_order = ["analysis", "design", "yaml", "documentation"]
    order_map = {name: idx for idx, name in enumerate(preferred_order)}

    items: list[dict[str, Any]] = []
    total_elapsed = 0.0

    for step_name, timing in timings.items():
        if not isinstance(step_name, str) or not step_name.strip():
            continue
        if not isinstance(timing, dict):
            continue

        started_at = str(timing.get("started_at") or "")
        ended_at = str(timing.get("ended_at") or "")

        elapsed: float | None = None
        raw_elapsed = timing.get("elapsed_seconds")
        if isinstance(raw_elapsed, (int, float)):
            elapsed = float(raw_elapsed)
        else:
            start_dt = _parse_utc_timestamp(started_at)
            end_dt = _parse_utc_timestamp(ended_at)
            if start_dt and end_dt:
                elapsed = (end_dt - start_dt).total_seconds()
            elif start_dt and not end_dt:
                # Still running: show current lap.
                elapsed = (now_dt - start_dt).total_seconds()

        status = "unknown"
        if ended_at.strip():
            status = "completed"
        elif started_at.strip():
            status = "running"

        item = {
            "step": step_name,
            "started_at": started_at,
            "ended_at": ended_at,
            "elapsed_seconds": elapsed,
            "status": status,
        }
        items.append(item)
        if isinstance(elapsed, (int, float)):
            total_elapsed += float(elapsed)

    def _sort_key(it: dict[str, Any]) -> tuple[int, datetime]:
        step = str(it.get("step") or "")
        started_at = str(it.get("started_at") or "")
        dt = _parse_utc_timestamp(started_at) or datetime(9999, 1, 1, tzinfo=UTC)
        return (order_map.get(step, 999), dt)

    items.sort(key=_sort_key)
    return items, total_elapsed


class AgentActivityHistory(EntityBase):
    """Historical record of agent activity"""

    timestamp: str = Field(default_factory=_get_utc_timestamp)
    action: str
    message_preview: str = ""
    step: str = ""
    tool_used: str = ""


class AgentActivity(EntityBase):
    """Current activity status of an agent"""

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


class ProcessStatus(RootEntityBase["ProcessStatus", str]):
    """Overall process status for user visibility"""

    id: str  # Primary key (process_id)
    phase: str = ""
    step: str = ""
    status: str = "running"  # running, completed, failed, qa_review
    agents: dict[str, AgentActivity] = Field(default_factory=dict)
    last_update_time: str = Field(default_factory=_get_utc_timestamp)
    started_at_time: str = Field(default_factory=_get_utc_timestamp)

    # Failure information fields
    failure_reason: str = ""
    failure_details: str = ""
    failure_step: str = ""
    failure_agent: str = ""
    failure_timestamp: str = ""
    stack_trace: str = ""

    # Final Results Storage - capturing outcomes from each step
    step_results: dict[str, dict] = Field(
        default_factory=dict
    )  # Store results from each step
    final_outcome: dict | None = Field(default=None)  # Overall migration outcome
    generated_files: list[dict] = Field(default_factory=list)  # List of generated files
    conversion_metrics: dict = Field(
        default_factory=dict
    )  # Success rates, accuracy, etc.

    # Step Timing (Lap Times)
    # Example:
    #   {
    #     "analysis": {"started_at": "...", "ended_at": "...", "elapsed_seconds": 12.34},
    #     "design": {...}
    #   }
    step_timings: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Per-step start/end timestamps and elapsed_seconds for lap timing",
    )

    # UI-Optimized Telemetry Data for Frontend Consumption
    ui_telemetry_data: dict = Field(
        default_factory=dict,
        description="Comprehensive UI data including file manifests, dashboard metrics, and downloadable artifacts",
    )


class AgentActivityRepository(RepositoryBase[ProcessStatus, str]):
    def __init__(self, app_context: AppContext):
        config = app_context.configuration
        if not config:
            raise ValueError("App context configuration is required")

        super().__init__(
            account_url=config.cosmos_db_account_url,
            database_name=config.cosmos_db_database_name,
            container_name=config.cosmos_db_container_name,
        )


class TelemetryManager:
    """Clean telemetry manager for agent activity tracking."""

    def __init__(self, app_context: AppContext | None = None):
        self.app_context = app_context
        # self.current_process: ProcessStatus | None = None
        self._read_semaphore = asyncio.Semaphore(1)  # For thread-safe reads

        # Check if in development mode
        is_development = (
            not app_context
            or not app_context.configuration
            or not app_context.configuration.cosmos_db_account_url
            or app_context.configuration.cosmos_db_account_url.startswith("http://<")
            or "localhost" in app_context.configuration.cosmos_db_account_url
        )

        if is_development:
            logger.info("[TELEMETRY] Development mode - using in-memory telemetry")
            self.repository = None
        else:
            if app_context is None:
                logger.error(
                    "[TELEMETRY] Cannot create production telemetry without app_context"
                )
                self.repository = None
            else:
                self.repository = AgentActivityRepository(app_context)

    async def delete_process(self, process_id: str):
        """Delete telemetry for a process (best-effort).

        In development mode `self.repository` can be None; in that case this is a no-op.
        """

        if not self.repository:
            return

        try:
            # Check Process record first.
            if await self.repository.get_async(process_id):
                await self.repository.delete_async(process_id)
        except Exception:
            logger.exception(
                "[TELEMETRY] Failed to delete process telemetry (process_id=%s)",
                process_id,
            )

    async def init_process(self, process_id: str, phase: str, step: str):
        """Initialize telemetry for a new process."""
        initial_agents = {}

        # Initialize orchestration agents
        # for agent_name in get_orchestration_agents():
        #     initial_agents[agent_name] = AgentActivity(
        #         name=agent_name,
        #         current_action="ready",
        #         participation_status="standby",
        #         is_active=False,
        #     )

        # Initialize core system agents (not actual responding agents)
        for agent_name in get_orchestration_agents():
            initial_agents[agent_name] = AgentActivity(
                name=agent_name,
                current_action="ready",
                participation_status="standby",
                is_active=False,
            )

        # NOTE: Common agents (Chief_Architect, EKS_Expert, etc.) are NOT pre-initialized
        # They will be added to telemetry when they actually respond via agent_response_callback

        new_process = ProcessStatus(
            id=process_id, phase=phase, step=step, agents=initial_agents
        )

        # Ensure initial step timing is seeded immediately. This makes lap timing robust
        # even if the workflow emits step "invoked" events late.
        if (phase or "").strip().lower() == "start" and (step or "").strip():
            timing = new_process.step_timings.get(step) or {}
            timing["started_at"] = timing.get("started_at") or new_process.started_at_time
            timing.pop("ended_at", None)
            timing.pop("elapsed_seconds", None)
            new_process.step_timings[step] = timing

        logger.info(
            f"[TELEMETRY] Starting {step} - Process: {process_id} with {len(initial_agents)} agents"
        )

        # Initialize in persistent storage if available
        if self.repository:
            try:
                await self.repository.add_async(new_process)
                logger.info(f"[TELEMETRY] Initialized process {process_id} in storage")
            except Exception:
                await self.repository.delete_async(process_id)
                await self.repository.add_async(new_process)

    async def update_agent_activity(
        self,
        process_id: str,
        agent_name: str,
        action: str,
        message_preview: str = "",
        full_message: str | None = None,
        tool_used: bool = False,
        tool_name: str = "",
        reset_for_new_step: bool = False,
    ):
        """Update agent activity."""
        process_status: ProcessStatus | None = None

        # Get Process Object First
        if self.repository:
            try:
                process_status = await self.repository.get_async(process_id)
            except Exception:
                logger.exception(
                    "Error reading process telemetry (process_id=%s)", process_id
                )
                return

        if not process_status:
            logger.warning("No current process - cannot update agent activity")
            return

        # Set other agents to inactive (except orchestration agents)
        for name, agent in process_status.agents.items():
            if name != agent_name and name not in get_orchestration_agents():
                agent.is_active = False

        # Update or create agent activity
        if agent_name not in process_status.agents:
            process_status.agents[agent_name] = AgentActivity(name=agent_name)

        agent = process_status.agents[agent_name]

        # Handle step reset
        if reset_for_new_step:
            agent.step_reset_count += 1
            history_entry = AgentActivityHistory(
                action=f"step_transition_to_{process_status.step}",
                message_preview="Transitioning from previous step",
                step=process_status.step,
                tool_used="",
            )
            agent.activity_history.append(history_entry)

        # Add current activity to history (with tool tracking support)
        # if agent.current_action != "idle" and (
        #     agent.current_action != action or tool_used
        # ):
        if agent.current_action != "idle":
            tool_used_value = tool_name if tool_used and tool_name else ""
            history_entry = AgentActivityHistory(
                action=agent.current_action,
                message_preview=agent.last_message_preview,
                step=process_status.step,
                tool_used=tool_used_value,
            )
            agent.activity_history.append(history_entry)

        # Update current state
        agent.current_action = action
        agent.last_message_preview = (
            message_preview if message_preview is not None else ""
        )
        if full_message is not None:
            agent.last_full_message = full_message
            agent.message_word_count = len(full_message.split()) if full_message else 0
        agent.last_update_time = _get_utc_timestamp()
        agent.is_active = True

        # Set participation status based on action (skip orchestration agents)
        if agent_name not in get_orchestration_agents():
            if action in ["thinking", "analyzing", "processing"]:
                agent.participation_status = "thinking"
                agent.is_currently_thinking = True
                agent.is_currently_speaking = False
            elif action in ["speaking", "responding", "explaining"]:
                agent.participation_status = "speaking"
                agent.is_currently_speaking = True
                agent.is_currently_thinking = False
            elif action == "completed":
                agent.participation_status = "completed"
                agent.is_currently_speaking = False
                agent.is_currently_thinking = False
            else:
                agent.participation_status = "ready"
                agent.is_currently_speaking = False
                agent.is_currently_thinking = False

        process_status.last_update_time = _get_utc_timestamp()

        # Update persistent storage if available
        if self.repository:
            try:
                await self.repository.update_async(process_status)
            except Exception:
                logger.exception(
                    "Error updating agent activity (process_id=%s, agent_name=%s)",
                    process_id,
                    agent_name,
                )

    async def track_tool_usage(
        self,
        process_id: str,
        agent_name: str,
        tool_name: str,
        tool_action: str,
        tool_details: str = "",
        tool_result_preview: str = "",
    ):
        """Track when an agent uses a tool during orchestration.

        Args:
            process_id: The process ID
            agent_name: Name of the agent using the tool
            tool_name: Name of the tool being used (e.g., 'blob_operations', 'microsoft_docs', 'datetime')
            tool_action: The specific action/method called (e.g., 'list_files', 'search_docs', 'get_current_time')
            tool_details: Additional details about the tool call (e.g., parameters, context)
            tool_result_preview: Brief preview of the tool result (first 100 chars)
        """
        process_status: ProcessStatus | None = None

        # Get Process Object First
        if self.repository:
            try:
                process_status = await self.repository.get_async(process_id)
            except Exception:
                logger.exception(
                    "Error reading process telemetry for tool usage (process_id=%s)",
                    process_id,
                )
                return

        if not process_status:
            logger.warning(f"No current process {process_id} - cannot track tool usage")
            return

        # Update or create agent activity
        if agent_name not in process_status.agents:
            process_status.agents[agent_name] = AgentActivity(name=agent_name)

        agent = process_status.agents[agent_name]

        # Create tool usage history entry
        tool_usage_summary = f"Used {tool_name}.{tool_action}"
        if tool_details:
            tool_usage_summary += (
                f" ({tool_details[:50]}{'...' if len(tool_details) > 50 else ''})"
            )

        history_entry = AgentActivityHistory(
            action="tool_usage",
            message_preview=tool_usage_summary,
            step=process_status.step,
            tool_used=f"{tool_name}.{tool_action}",
        )
        agent.activity_history.append(history_entry)

        # Update current activity to reflect tool usage
        agent.current_action = "using_tool"
        agent.last_message_preview = f"Using {tool_name} - {tool_action}"
        agent.last_update_time = _get_utc_timestamp()
        agent.is_active = True

        # Add to reasoning steps for context
        reasoning_step = f"Tool: {tool_name}.{tool_action}"
        if tool_result_preview:
            reasoning_step += f" {tool_result_preview[:100]}{'...' if len(tool_result_preview) > 100 else ''}"
        agent.reasoning_steps.append(reasoning_step)

        process_status.last_update_time = _get_utc_timestamp()

        # Update persistent storage if available
        if self.repository:
            try:
                await self.repository.update_async(process_status)
                logger.info(
                    f"[TOOL_TRACKING] {agent_name} used {tool_name}.{tool_action}"
                )
            except Exception:
                logger.exception(
                    "Error tracking tool usage (process_id=%s, agent_name=%s, tool=%s.%s)",
                    process_id,
                    agent_name,
                    tool_name,
                    tool_action,
                )

    async def update_process_status(self, process_id: str, status: str):
        """Update the overall process status."""
        # if self.current_process:
        #     self.current_process.status = status
        #     self.current_process.last_update_time = _get_utc_timestamp()
        current_process: ProcessStatus | None = None

        if self.repository:
            try:
                current_process = await self.repository.get_async(process_id)
                if current_process:
                    current_process.last_update_time = _get_utc_timestamp()
                    current_process.status = status
                    await self.repository.update_async(current_process)

            except Exception:
                logger.exception(
                    "Error updating process status (process_id=%s, status=%s)",
                    process_id,
                    status,
                )

    async def set_agent_idle(self, process_id: str, agent_name: str):
        """Set an agent to idle state."""
        current_process: ProcessStatus | None = None
        if self.repository:
            try:
                current_process = await self.repository.get_async(process_id)
                if not current_process or agent_name not in current_process.agents:
                    return
            except Exception:
                logger.exception(
                    "Error reading process telemetry for set_agent_idle (process_id=%s, agent_name=%s)",
                    process_id,
                    agent_name,
                )
                return

        if current_process:
            agent = current_process.agents[agent_name]
            agent.current_action = "idle"
            agent.is_active = False
            agent.is_currently_thinking = False
            agent.is_currently_speaking = False
            agent.participation_status = "standby"
            agent.last_update_time = _get_utc_timestamp()

        if self.repository:
            try:
                await self.repository.update_async(current_process)
            except Exception:
                logger.exception(
                    "Error setting agent idle (process_id=%s, agent_name=%s)",
                    process_id,
                    agent_name,
                )

    async def transition_to_phase(self, process_id: str, phase: str, step: str):
        """Clean transition between phases with proper agent cleanup."""
        current_process: ProcessStatus | None = None
        if self.repository:
            current_process = await self.repository.get_async(process_id)
            if not current_process:
                logger.warning("No current process - cannot transition phase")
                return
            else:
                # Update phase and step
                old_phase = current_process.phase
                current_process.phase = phase
                current_process.step = step
                current_process.last_update_time = _get_utc_timestamp()

                # Record step start timing on phase=start.
                if (phase or "").strip().lower() == "start" and step:
                    timing = current_process.step_timings.get(step) or {}
                    timing["started_at"] = timing.get("started_at") or _get_utc_timestamp()
                    timing.pop("ended_at", None)
                    timing.pop("elapsed_seconds", None)
                    current_process.step_timings[step] = timing

                for agent_name, agent in current_process.agents.items():
                    if (
                        agent_name not in get_orchestration_agents()
                    ):  # Skip system agents
                        agent.participation_status = "ready"
                        agent.current_action = "ready"
                        agent.last_message_preview = f"Ready for {phase.lower()} phase"
                        agent.last_update_time = _get_utc_timestamp()

                logger.info(
                    f"[TELEMETRY] Transitioning to phase: {phase}, step: {step}"
                )
                try:
                    await self.repository.update_async(current_process)
                    logger.info(
                        f"[TELEMETRY] Phase transition completed: {old_phase} {phase}"
                    )
                except Exception:
                    logger.exception(
                        "Error updating phase transition (process_id=%s, phase=%s, step=%s)",
                        process_id,
                        phase,
                        step,
                    )

    # async def _cleanup_phase_agents(self, process_id: str, previous_phase: str):
    #     """Remove or mark inactive agents not relevant to current phase."""
    #     if not self.current_process:
    #         return

    #     # Note: Removed fake orchestration agent cleanup since we no longer create them
    #     # Phase orchestrators are Python classes, not agents to be tracked
    #     logger.debug(f"[TELEMETRY] Phase cleanup completed: {previous_phase}")

    async def _initialize_phase_agents(self, process_id: str, phase: str):
        """Initialize agents relevant to the new phase."""
        current_process: ProcessStatus | None = None
        if self.repository:
            current_process = await self.repository.get_async(process_id)
            if not current_process:
                logger.warning("No current process - cannot initialize phase agents")
                return
            else:
                # Note: We no longer pre-initialize agents.
                # Agents will be added to telemetry when they actually respond via callbacks.
                logger.info(f"[TELEMETRY] Phase initialization completed: {phase}")
                # Update status for agents that already exist (have already responded)
                for agent_name, agent in current_process.agents.items():
                    if (
                        agent_name not in get_orchestration_agents()
                    ):  # Skip system agents
                        agent.participation_status = "ready"
                        agent.current_action = "ready"
                        agent.last_message_preview = f"Ready for {phase.lower()} phase"
                        agent.last_update_time = _get_utc_timestamp()

                await self.repository.update_async(current_process)

    async def complete_all_participant_agents(self, process_id: str):
        """Mark all non-orchestration agents as completed."""
        current_process: ProcessStatus | None = None
        if self.repository:
            current_process = await self.repository.get_async(process_id)
            if not current_process:
                return
            else:
                for agent_name, agent in current_process.agents.items():
                    if agent_name not in get_orchestration_agents():
                        agent.current_action = "completed"
                        agent.participation_status = "completed"
                        agent.is_active = False
                        agent.is_currently_thinking = False
                        agent.is_currently_speaking = False
                try:
                    await self.repository.update_async(current_process)
                except Exception:
                    logger.exception(
                        "Error completing agents (process_id=%s)",
                        process_id,
                    )

    async def record_failure(
        self,
        process_id: str,
        failure_reason: str,
        failure_details: str = "",
        failure_step: str = "",
        failure_agent: str = "",
        stack_trace: str = "",
    ):
        """Record process failure information."""
        current_process: ProcessStatus | None = None
        if self.repository:
            current_process = await self.repository.get_async(process_id)
            if not current_process:
                return
            else:
                current_process.status = "failed"
                current_process.failure_reason = failure_reason
                current_process.failure_details = failure_details
                current_process.failure_step = failure_step or current_process.step
                current_process.failure_agent = failure_agent
                current_process.failure_timestamp = _get_utc_timestamp()
                current_process.stack_trace = stack_trace

                try:
                    await self.repository.update_async(current_process)
                except Exception:
                    logger.exception(
                        "Error recording failure (process_id=%s)",
                        process_id,
                    )

    async def get_current_process(self, process_id: str) -> ProcessStatus | None:
        """Get the current process status."""
        if self.repository:
            return await self.repository.get_async(process_id)

    async def get_process_outcome(self, process_id: str) -> str:
        """Get a human-readable process outcome."""
        current_process: ProcessStatus | None = None

        if self.repository:
            current_process = await self.repository.get_async(process_id)
            if not current_process:
                return "No active process"
            else:
                if current_process.status == "completed":
                    return "Process completed successfully"
                elif current_process.status == "failed":
                    return f"Process failed: {current_process.failure_reason}"
                elif current_process.status == "running":
                    return "Process is still running"
                else:
                    return f"Status: {current_process.status}"
        else:
            return ""

    async def get_process_status_by_process_id(
        self, process_id: str
    ) -> ProcessStatus | None:
        """Get process status by process ID."""
        return await self.get_current_process(process_id=process_id)

    def _get_ready_status_message(
        self, agent_name: str, current_step: str, current_phase: str, status: str
    ) -> str:
        """Generate context-aware ready status messages."""
        phase_lower = current_phase.lower() if current_phase else "current"
        step_lower = current_step.lower() if current_step else phase_lower

        # Special handling for consolidated conversation manager
        if agent_name == "Coordinator":
            if "analysis" in phase_lower:
                return "Coordinating platform analysis expert discussion"
            elif "design" in phase_lower:
                return "Coordinating Azure architecture expert discussion"
            elif "yaml" in phase_lower:
                return "Coordinating YAML conversion expert discussion"
            elif "documentation" in phase_lower:
                return "Coordinating migration documentation expert discussion"
            else:
                return "Coordinating expert discussion for migration step"

        # Phase-specific ready messages for domain expert agents
        if "analysis" in phase_lower:
            if "system" in agent_name.lower():
                return "Ready to analyze source platform"
            else:
                return f"Ready to assist with {step_lower} analysis"

        elif "design" in phase_lower:
            if "azure" in agent_name.lower():
                return "Ready to provide Azure recommendations"
            else:
                return f"Ready to assist with {step_lower} design"

        elif "yaml" in phase_lower:
            if "yaml" in agent_name.lower():
                return "Ready to generate YAML configurations"
            else:
                return f"Ready to assist with {step_lower} conversion"

        elif "documentation" in phase_lower:
            if "technical_writer" in agent_name.lower():
                return "Ready to write comprehensive documentation"
            else:
                return f"Ready to assist with {step_lower} documentation"
        else:
            return f"Ready for {phase_lower} tasks"

    async def render_agent_status(self, process_id: str) -> dict:
        """Enhanced agent status rendering with context-aware messages."""
        async with self._read_semaphore:
            process_snapshot = await self.get_process_status_by_process_id(process_id)

            if not process_snapshot:
                return {
                    "process_id": process_id,
                    "phase": "unknown",
                    "status": "not_found",
                    "agents": [],
                }

            # Status icon mapping
            status_icons = {
                "speaking": "",
                "thinking": "",
                "ready": "",
                "standby": "",
                "completed": "",
                "waiting": "",
            }

            formatted_lines = []

            # Convert agents dict to list if needed
            agents_list = []
            if isinstance(process_snapshot.agents, dict):
                agents_list = list(process_snapshot.agents.values())
            else:
                agents_list = process_snapshot.agents

            for agent in agents_list:
                # Handle both participating_status and participation_status
                status = getattr(
                    agent,
                    "participating_status",
                    getattr(agent, "participation_status", "ready"),
                ).lower()
                icon = status_icons.get(status, "")

                # ENHANCED MESSAGE DISPLAY LOGIC
                if agent.name.lower() == "Coordinator".lower():
                    # Conversation Manager gets enhanced treatment for migration coordination
                    message = f'"{getattr(agent, "current_speaking_content", "") or getattr(agent, "last_activity_summary", "") or getattr(agent, "last_message", "") or "Migration conversation continues..."}"'

                elif getattr(agent, "is_currently_speaking", False) and getattr(
                    agent, "current_speaking_content", ""
                ):
                    # Speaking agent - show actual content
                    content = agent.current_speaking_content
                    message = f'"{content}"'

                    # Add word count if available
                    if (
                        hasattr(agent, "message_word_count")
                        and agent.message_word_count > 0
                    ):
                        message += f" ({agent.message_word_count} words)"

                elif (
                    status == "thinking"
                    and hasattr(agent, "thinking_about")
                    and getattr(agent, "thinking_about", "")
                ):
                    # Thinking agent - show specific thoughts
                    message = f'"{agent.thinking_about}"'

                elif status == "ready":
                    # CONTEXT-AWARE READY MESSAGE
                    ready_message = self._get_ready_status_message(
                        agent.name,
                        getattr(process_snapshot, "step", "") or process_snapshot.phase,
                        process_snapshot.phase,
                        status,
                    )
                    message = f'"{ready_message}"'

                elif getattr(agent, "last_message", ""):
                    # Show last message if available
                    content = agent.last_message
                    message = f'"{content}"'

                elif getattr(agent, "last_activity_summary", ""):
                    # Show last activity summary
                    message = f'"{agent.last_activity_summary}"'

                elif status == "completed":
                    message = '"Task completed successfully"'

                elif status == "standby":
                    # Better standby messages for orchestration agents
                    if agent.name in get_orchestration_agents():
                        if agent.name == "Coordinator":
                            current_action = getattr(agent, "current_action", "")
                            if current_action and current_action != "standby":
                                message = (
                                    f'"{current_action.replace("_", " ").title()}"'
                                )
                            else:
                                phase = (
                                    process_snapshot.phase.lower()
                                    if process_snapshot.phase
                                    else "current"
                                )
                                message = f'"Managing {phase} phase"'
                        elif agent.name == "Coordinator":
                            message = '"Monitoring conversation flow"'
                        else:
                            phase = (
                                process_snapshot.phase.lower()
                                if process_snapshot.phase
                                else "current"
                            )
                            message = f'"Standing by for {phase} tasks"'
                    else:
                        phase = (
                            process_snapshot.phase.lower()
                            if process_snapshot.phase
                            else "current"
                        )
                        message = f'"Standing by for {phase} tasks"'

                else:
                    # Enhanced fallback
                    action = getattr(agent, "current_action", "") or "waiting"
                    message = f'"{action.replace("_", " ").title()}"'

                # Format the display line - SIMPLIFIED FOR USER-FRIENDLY DISPLAY
                agent_display_name = agent.name.replace("_", " ")
                is_active = getattr(agent, "is_active", False)

                # Simplified status display without confusing blocking information
                status_display = status.title()

                # Determine if agent is truly active/working
                is_working = (
                    is_active
                    or status in ["thinking", "speaking"]
                    or (
                        agent.name in get_orchestration_agents()
                        and getattr(agent, "current_action", "")
                        not in ["idle", "standby"]
                    )
                )

                # No additional time or blocking information to avoid confusion
                line = f"{'✓' if is_working else '✗'}[{icon}] {agent_display_name}: {status_display} - {message}"
                formatted_lines.append(line)

            step_timings = getattr(process_snapshot, "step_timings", {}) or {}
            step_lap_times, total_elapsed_seconds = _build_step_lap_times(step_timings)

            return {
                "process_id": process_id,
                "phase": process_snapshot.phase,
                "status": process_snapshot.status,
                "step": getattr(process_snapshot, "step", ""),
                "last_update_time": process_snapshot.last_update_time,
                "started_at_time": process_snapshot.started_at_time,
                "step_timings": step_timings,
                "step_lap_times": step_lap_times,
                "total_elapsed_seconds": total_elapsed_seconds,
                "agents": formatted_lines,
                "failure_reason": process_snapshot.failure_reason,
                "failure_details": process_snapshot.failure_details,
                "failure_step": process_snapshot.failure_step,
                "failure_agent": process_snapshot.failure_agent,
                "failure_timestamp": process_snapshot.failure_timestamp,
                "stack_trace": process_snapshot.stack_trace,
                "step_results": process_snapshot.step_results,
                "final_outcome": process_snapshot.final_outcome,
                "generated_files": process_snapshot.generated_files,
                "conversion_metrics": process_snapshot.conversion_metrics,
            }

    async def record_step_result(
        self,
        process_id: str,
        step_name: str,
        step_result: dict,
        execution_time_seconds: float | None = None,
    ):
        """Record the result of a completed step."""
        current_process: ProcessStatus | None = None
        if self.repository:
            current_process = await self.repository.get_async(process_id)
            if not current_process:
                logger.warning(
                    f"No current process - cannot record {step_name} step result"
                )
                return
            else:
                current_process.step_results[step_name] = {
                    "result": step_result,
                    "timestamp": _get_utc_timestamp(),
                    "step_name": step_name,
                }

                # Lap time: end the timer for this step.
                if step_name:
                    timing = current_process.step_timings.get(step_name) or {}
                    ended_at = _get_utc_timestamp()
                    timing["ended_at"] = ended_at

                    started_at = timing.get("started_at")
                    start_dt = _parse_utc_timestamp(started_at)
                    end_dt = _parse_utc_timestamp(ended_at)
                    ts_elapsed: float | None = None
                    if start_dt and end_dt:
                        ts_elapsed = (end_dt - start_dt).total_seconds()

                    if isinstance(execution_time_seconds, (int, float)):
                        candidate = float(execution_time_seconds)
                        # Guard against clearly bogus perf-counter durations (e.g. ~0s) when
                        # timestamps show minutes elapsed.
                        if (
                            ts_elapsed is not None
                            and ts_elapsed >= 1.0
                            and candidate >= 0.0
                            and candidate < 0.5
                            and ts_elapsed > 5.0
                        ):
                            timing["elapsed_seconds"] = ts_elapsed
                        else:
                            timing["elapsed_seconds"] = candidate
                    elif ts_elapsed is not None:
                        timing["elapsed_seconds"] = ts_elapsed

                    current_process.step_timings[step_name] = timing

                logger.info(f"[TELEMETRY] Recorded {step_name} step result")

            try:
                await self.repository.update_async(current_process)
            except Exception:
                logger.exception(
                    "Error recording step result (process_id=%s, step_name=%s)",
                    process_id,
                    step_name,
                )

    async def record_final_outcome(
        self, process_id: str, outcome_data: dict, success: bool = True
    ):
        """Record the final migration outcome with comprehensive results."""
        current_process: ProcessStatus | None = None
        if self.repository:
            current_process = await self.repository.get_async(process_id)
            if not current_process:
                logger.warning("No current process - cannot record final outcome")
                return
            else:
                # Extract key metrics from outcome data
                generated_files = []
                conversion_metrics = {}

                def _get_nested(obj: Any, path: list[str]) -> Any:
                    cur = obj
                    for key in path:
                        if not isinstance(cur, dict):
                            return None
                        if key not in cur:
                            return None
                        cur = cur[key]
                    return cur

                try:
                    # Handle Documentation step results.
                    # Preferred shape (pydantic model -> dict):
                    #   outcome_data["termination_output"]["generated_files"]
                    #   outcome_data["termination_output"]["process_metrics"]
                    collection = None
                    metrics = None

                    # Legacy/alternate shapes
                    if "GeneratedFilesCollection" in outcome_data:
                        collection = outcome_data.get("GeneratedFilesCollection")
                    if "ProcessMetrics" in outcome_data:
                        metrics = outcome_data.get("ProcessMetrics")

                    # Current Documentation_ExtendedBooleanResult shape
                    if collection is None:
                        collection = _get_nested(
                            outcome_data, ["termination_output", "generated_files"]
                        )
                    if metrics is None:
                        metrics = _get_nested(
                            outcome_data, ["termination_output", "process_metrics"]
                        )

                    if isinstance(collection, dict):
                        # Process each phase's files
                        for phase in ["analysis", "design", "yaml", "documentation"]:
                            phase_items = collection.get(phase)
                            if isinstance(phase_items, list):
                                for file_info in phase_items:
                                    if not isinstance(file_info, dict):
                                        continue

                                    # YAML phase uses ConvertedFile shape.
                                    if phase == "yaml":
                                        generated_files.append({
                                            "phase": phase,
                                            "source_file": file_info.get(
                                                "source_file", ""
                                            ),
                                            "file_name": file_info.get(
                                                "converted_file", ""
                                            ),
                                            "file_type": file_info.get(
                                                "file_type",
                                                file_info.get("file_kind", ""),
                                            ),
                                            "status": file_info.get(
                                                "conversion_status", "Success"
                                            ),
                                            "accuracy": file_info.get(
                                                "accuracy_rating", ""
                                            ),
                                            "summary": "",
                                            "timestamp": _get_utc_timestamp(),
                                        })
                                    else:
                                        generated_files.append({
                                            "phase": phase,
                                            "file_name": file_info.get("file_name", ""),
                                            "file_type": file_info.get("file_type", ""),
                                            "status": "Success",
                                            "accuracy": "",
                                            "summary": file_info.get(
                                                "content_summary", ""
                                            ),
                                            "timestamp": _get_utc_timestamp(),
                                        })

                    # Extract conversion metrics
                    if isinstance(metrics, dict):
                        conversion_metrics = {
                            "platform_detected": metrics.get("platform_detected", ""),
                            "conversion_accuracy": metrics.get(
                                "conversion_accuracy", ""
                            ),
                            "documentation_completeness": metrics.get(
                                "documentation_completeness", ""
                            ),
                            "enterprise_readiness": metrics.get(
                                "enterprise_readiness", ""
                            ),
                        }
                    if isinstance(collection, dict):
                        conversion_metrics["total_files_generated"] = collection.get(
                            "total_files_generated", 0
                        )
                except Exception:
                    logger.exception(
                        "Error extracting file and metrics data (process_id=%s)",
                        process_id,
                    )
                    # Continue with basic outcome recording

                # Provide a compact, UI-friendly "finalized" section inside final_outcome.
                # Keep it small: counts + pointers, not full file contents.
                container = _get_process_blob_container_name()
                output_folder = f"{process_id}/output"
                conversion_report_file = None
                try:
                    yaml_step = (current_process.step_results or {}).get("yaml")
                    yaml_result = (
                        yaml_step.get("result") if isinstance(yaml_step, dict) else None
                    )
                    if isinstance(yaml_result, dict):
                        conversion_report_file = _get_nested(
                            yaml_result,
                            ["termination_output", "conversion_report_file"],
                        )
                except Exception:
                    conversion_report_file = None

                finalized_generated = {
                    "process_id": process_id,
                    "container": container,
                    "output_folder": output_folder,
                    "generated_files_count": len(generated_files),
                    "generated_files": generated_files,
                    "conversion_metrics": conversion_metrics,
                    "artifacts": [
                        {
                            "type": "migration_report",
                            "container": container,
                            "path": f"{output_folder}/migration_report.md",
                        },
                    ],
                }
                if (
                    isinstance(conversion_report_file, str)
                    and conversion_report_file.strip()
                ):
                    finalized_generated["artifacts"].append({
                        "type": "conversion_report",
                        "container": container,
                        "path": conversion_report_file,
                    })

                # Record the final outcome
                current_process.final_outcome = {
                    "success": success,
                    "outcome_data": outcome_data,
                    "finalized_generated": finalized_generated,
                    "timestamp": _get_utc_timestamp(),
                    "total_steps_completed": len(current_process.step_results),
                }

                # Defensive: some callers also call update_process_status(), but if they
                # don't (or crash before doing so), status should still reflect reality.
                current_process.status = "completed" if success else "failed"

                current_process.generated_files = generated_files
                current_process.conversion_metrics = conversion_metrics

                logger.info(
                    f"[TELEMETRY] Recorded final outcome - Success: {success}, Files: {len(generated_files)}"
                )

                if self.repository:
                    try:
                        await self.repository.update_async(current_process)
                    except Exception:
                        logger.exception(
                            "Error recording final outcome (process_id=%s)",
                            process_id,
                        )

    async def record_failure_outcome(
        self,
        process_id: str,
        error_message: str,
        failed_step: str,
        failure_details: dict | None = None,
        execution_time_seconds: float | None = None,
    ):
        current_process: ProcessStatus | None = None
        if self.repository:
            current_process = await self.repository.get_async(process_id)
            """Record failure outcome with detailed error information."""
            if not current_process:
                logger.warning("No current process - cannot record failure outcome")
                return
            else:
                failure_data: dict[str, Any] = dict(failure_details or {})

                # Preserve full traceback without risking Cosmos item size limits:
                # If traceback is large, store it as a blob artifact and keep only a pointer in Cosmos.
                try:
                    tb = failure_data.get("traceback")
                    if isinstance(tb, str):
                        tb_bytes = _byte_len_text(tb)
                        # Conservative inline threshold to leave headroom for other fields.
                        inline_max_bytes = int(
                            os.getenv("TELEMETRY_TRACEBACK_INLINE_MAX_BYTES")
                            or "200000"
                        )
                        if tb_bytes > inline_max_bytes:
                            blob_name = f"debug/traceback_{failed_step}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.txt"
                            artifact = await _upload_text_to_process_blob(
                                process_id=process_id,
                                folder_path=f"{process_id}/output",
                                blob_name=blob_name,
                                content=tb,
                            )
                            if artifact:
                                # Replace inline traceback with artifact reference (no truncation of stored content).
                                failure_data.pop("traceback", None)
                                failure_data["traceback_artifact"] = artifact
                                failure_data["traceback_bytes"] = tb_bytes
                except Exception:
                    # Best-effort: never fail telemetry because of offload logic.
                    pass

                current_process.final_outcome = {
                    "success": False,
                    "error_message": error_message,
                    "failed_step": failed_step,
                    "failure_details": failure_data,
                    "timestamp": _get_utc_timestamp(),
                    "total_steps_completed": len(current_process.step_results),
                }

                # Defensive: ensure the top-level process status/fields are updated even if
                # the caller forgets to call update_process_status().
                current_process.status = "failed"
                if error_message:
                    current_process.failure_reason = error_message
                try:
                    # Cosmos document fields can get large; keep this compact.
                    # Full traceback content is offloaded to blob above when needed.
                    current_process.failure_details = (
                        json.dumps(failure_data, ensure_ascii=False)[:4000]
                        if failure_data
                        else current_process.failure_details
                    )
                except Exception:
                    pass
                current_process.failure_step = failed_step or current_process.step
                current_process.failure_timestamp = _get_utc_timestamp()

                # Lap time: end the timer for this failed step as well.
                if failed_step:
                    timing = current_process.step_timings.get(failed_step) or {}
                    ended_at = _get_utc_timestamp()
                    timing["ended_at"] = ended_at

                    started_at = timing.get("started_at")
                    start_dt = _parse_utc_timestamp(started_at)
                    end_dt = _parse_utc_timestamp(ended_at)
                    ts_elapsed: float | None = None
                    if start_dt and end_dt:
                        ts_elapsed = (end_dt - start_dt).total_seconds()

                    if isinstance(execution_time_seconds, (int, float)):
                        candidate = float(execution_time_seconds)
                        if (
                            ts_elapsed is not None
                            and ts_elapsed >= 1.0
                            and candidate >= 0.0
                            and candidate < 0.5
                            and ts_elapsed > 5.0
                        ):
                            timing["elapsed_seconds"] = ts_elapsed
                        else:
                            timing["elapsed_seconds"] = candidate
                    elif ts_elapsed is not None:
                        timing["elapsed_seconds"] = ts_elapsed

                    current_process.step_timings[failed_step] = timing

                logger.info(
                    f"[TELEMETRY] Recorded failure outcome - Step: {failed_step}, Error: {error_message}"
                )

                try:
                    await self.repository.update_async(current_process)
                except Exception:
                    logger.exception(
                        "Error recording failure outcome (process_id=%s, failed_step=%s)",
                        process_id,
                        failed_step,
                    )

    async def get_final_results_summary(self, process_id: str) -> dict[str, Any]:
        """Get a summary of the final results for external consumption."""
        current_process: ProcessStatus | None = None
        if self.repository:
            current_process = await self.repository.get_async(process_id)
            if not current_process:
                return {"error": "No active process"}
            else:
                step_timings = getattr(current_process, "step_timings", {}) or {}
                step_lap_times, total_elapsed_seconds = _build_step_lap_times(step_timings)
                return {
                    "process_id": current_process.id,
                    "status": current_process.status,
                    "final_outcome": current_process.final_outcome,
                    "step_results": current_process.step_results,
                    "step_timings": step_timings,
                    "step_lap_times": step_lap_times,
                    "total_elapsed_seconds": total_elapsed_seconds,
                    "generated_files_count": len(current_process.generated_files),
                    "generated_files": current_process.generated_files,
                    "conversion_metrics": current_process.conversion_metrics,
                    "completed_steps": list(current_process.step_results.keys()),
                }
        else:
            return {}

    async def record_ui_data(self, process_id: str, ui_data: dict[str, Any]) -> None:
        """
        Record UI-optimized telemetry data for frontend consumption.

        This method stores comprehensive UI data including file manifests,
        dashboard metrics, and downloadable artifacts for rich frontend rendering.
        """
        try:
            if not self.repository:
                logger.info("[TELEMETRY] Development mode - UI data recorded in memory")
                return

            async with self._read_semaphore:
                current_process = await self.repository.get_async(process_id)
                if not current_process:
                    logger.warning(
                        f"[UI-TELEMETRY] Process {process_id} not found for UI data recording"
                    )
                    return

                # Add UI data to the process status
                if not hasattr(current_process, "ui_telemetry_data"):
                    current_process.ui_telemetry_data = {}  # type: ignore

                current_process.ui_telemetry_data.update(ui_data)  # type: ignore
                current_process.last_update_time = _get_utc_timestamp()

                await self.repository.update_async(current_process)

                # Log summary
                file_count = len(
                    ui_data.get("file_manifest", {}).get("converted_files", [])
                )
                failed_count = len(
                    ui_data.get("file_manifest", {}).get("failed_files", [])
                )
                report_count = len(
                    ui_data.get("file_manifest", {}).get("report_files", [])
                )
                completion = ui_data.get("dashboard_metrics", {}).get(
                    "completion_percentage", 0
                )

                logger.info(
                    f"[UI-TELEMETRY] Recorded UI data for process {process_id} - "
                    f"Converted: {file_count}, Failed: {failed_count}, Reports: {report_count}, Completion: {completion:.1f}%"
                )

        except Exception as e:
            logger.error(f"[UI-TELEMETRY] Failed to record UI data: {e}")

    async def get_ui_telemetry_data(self, process_id: str) -> dict[str, Any]:
        """
        Retrieve UI-optimized telemetry data for frontend consumption.

        Returns comprehensive data structure including file manifests,
        dashboard metrics, and downloadable artifacts.
        """
        try:
            if not self.repository:
                logger.info("[TELEMETRY] Development mode - returning empty UI data")
                return {}

            current_process = await self.repository.get_async(process_id)
            if not current_process:
                logger.warning(f"[UI-TELEMETRY] Process {process_id} not found")
                return {}

            ui_data = getattr(current_process, "ui_telemetry_data", {})

            # Add some fallback data if UI data is empty
            if not ui_data and current_process.status == "completed":
                ui_data = {
                    "file_manifest": {
                        "source_files": [],
                        "converted_files": [],
                        "report_files": [],
                    },
                    "dashboard_metrics": {
                        "completion_percentage": 100.0,
                        "files_processed": len(current_process.generated_files),
                        "files_successful": len(current_process.generated_files),
                        "files_failed": 0,
                        "status_summary": "Migration completed successfully",
                    },
                    "step_progress": [],
                    "downloadable_artifacts": {
                        "converted_configs": [],
                        "reports": [],
                        "documentation": [],
                        "archive": None,
                    },
                }

            logger.info(
                f"[UI-TELEMETRY] Retrieved UI data for process {process_id} - "
                f"Converted: {len(ui_data.get('file_manifest', {}).get('converted_files', []))}, "
                f"Failed: {len(ui_data.get('file_manifest', {}).get('failed_files', []))}, "
                f"Completion: {ui_data.get('dashboard_metrics', {}).get('completion_percentage', 0):.1f}%"
            )

            return ui_data

        except Exception as e:
            logger.error(f"[UI-TELEMETRY] Failed to retrieve UI data: {e}")
            return {}
