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
from datetime import UTC, datetime
import logging
from typing import Any

from pydantic import Field
from sas.cosmosdb.sql import EntityBase, RepositoryBase, RootEntityBase

from libs.application.application_context import AppContext

logger = logging.getLogger(__name__)


def get_orchestration_agents() -> set[str]:
    """Get orchestration agent names - consolidated to single conversation manager."""
    return {
        # Single conversation manager for all expert discussions and orchestration
        "Conversation_Manager",
        "Agent_Selector",
        # Note: Consolidated from System, Orchestration_Manager, Agent_Selector
        # Provides clean, conversation-focused telemetry that users understand
    }


def get_common_agents() -> list[str]:
    """Get common agent names."""
    return [
        "Chief_Architect",
        "EKS_Expert",
        "GKE_Expert",
        "Azure_Expert",
        "Technical_Writer",
        "QA_Engineer",
    ]


def _get_utc_timestamp() -> str:
    """Get current UTC timestamp in human-readable format"""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


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

    async def init_process(self, process_id: str, phase: str, step: str):
        """Initialize telemetry for a new process."""
        initial_agents = {}

        # Initialize orchestration agents
        for agent_name in get_orchestration_agents():
            initial_agents[agent_name] = AgentActivity(
                name=agent_name,
                current_action="ready",
                participation_status="standby",
                is_active=False,
            )

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

        logger.info(
            f"[TELEMETRY] Starting {step} - Process: {process_id} with {len(initial_agents)} agents"
        )

        # Initialize in persistent storage if available
        if self.repository:
            try:
                await self.repository.add_async(new_process)
                logger.info(f"[TELEMETRY] Initialized process {process_id} in storage")
            except Exception as e:
                logger.error(f"Error initializing process telemetry: {e}")

    async def update_agent_activity(
        self,
        process_id: str,
        agent_name: str,
        action: str,
        message_preview: str = "",
        tool_used: bool = False,
        tool_name: str = "",
        reset_for_new_step: bool = False,
    ):
        """Update agent activity."""
        process_status: ProcessStatus | None = None

        # Get Process Object First
        if self.repository:
            process_status = await self.repository.get_async(process_id)

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
        if agent.current_action != "idle" and agent.current_action != action:
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
        agent.last_message_preview = message_preview
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
            except Exception as e:
                logger.error(f"Error updating agent activity: {e}")

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
            process_status = await self.repository.get_async(process_id)

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
        reasoning_step = f"🔧 Tool: {tool_name}.{tool_action}"
        if tool_result_preview:
            reasoning_step += f" → {tool_result_preview[:100]}{'...' if len(tool_result_preview) > 100 else ''}"
        agent.reasoning_steps.append(reasoning_step)

        process_status.last_update_time = _get_utc_timestamp()

        # Update persistent storage if available
        if self.repository:
            try:
                await self.repository.update_async(process_status)
                logger.info(
                    f"[TOOL_TRACKING] {agent_name} used {tool_name}.{tool_action}"
                )
            except Exception as e:
                logger.error(f"Error tracking tool usage: {e}")

    async def update_process_status(self, process_id: str, status: str):
        """Update the overall process status."""
        # if self.current_process:
        #     self.current_process.status = status
        #     self.current_process.last_update_time = _get_utc_timestamp()
        current_process: ProcessStatus | None = None

        if self.repository:
            current_process = await self.repository.get_async(process_id)
            if current_process:
                current_process.last_update_time = _get_utc_timestamp()
                current_process.status = status
                await self.repository.update_async(current_process)

        # if current_process:
        #     current_process.status = status
        #     current_process.last_update_time = _get_utc_timestamp()
        #     if self.repository:
        #         try:
        #             await self.repository.update_async(self.current_process)
        #         except Exception as e:
        #             logger.error(f"Error updating process status: {e}")

    async def set_agent_idle(self, process_id: str, agent_name: str):
        """Set an agent to idle state."""
        current_process: ProcessStatus | None = None
        if self.repository:
            current_process = await self.repository.get_async(process_id)
            if not current_process or agent_name not in current_process.agents:
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
            except Exception as e:
                logger.error(f"Error setting agent idle: {e}")

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
                        f"[TELEMETRY] Phase transition completed: {old_phase} → {phase}"
                    )
                except Exception as e:
                    logger.error(f"Error updating phase transition: {e}")

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
                except Exception as e:
                    logger.error(f"Error completing agents: {e}")

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
                except Exception as e:
                    logger.error(f"Error recording failure: {e}")

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
                    return "✅ Process completed successfully"
                elif current_process.status == "failed":
                    return f"❌ Process failed: {current_process.failure_reason}"
                elif current_process.status == "running":
                    return "🔄 Process is still running"
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
        if agent_name == "Conversation_Manager":
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
                "speaking": "🗣️",
                "thinking": "🤔",
                "ready": "✅",
                "standby": "⏸️",
                "completed": "🏁",
                "waiting": "⏳",
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
                icon = status_icons.get(status, "❓")

                # ENHANCED MESSAGE DISPLAY LOGIC
                if agent.name.lower() == "conversation_manager":
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
                        if agent.name == "Conversation_Manager":
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
                        elif agent.name == "Conversation_Manager":
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

            return {
                "process_id": process_id,
                "phase": process_snapshot.phase,
                "status": process_snapshot.status,
                "step": getattr(process_snapshot, "step", ""),
                "last_update_time": process_snapshot.last_update_time,
                "started_at_time": process_snapshot.started_at_time,
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
        self, process_id: str, step_name: str, step_result: dict
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

                logger.info(f"[TELEMETRY] Recorded {step_name} step result")

            try:
                await self.repository.update_async(current_process)
            except Exception as e:
                logger.error(f"Error recording step result: {e}")

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
                try:
                    # Handle Documentation step results
                    if "GeneratedFilesCollection" in outcome_data:
                        collection = outcome_data["GeneratedFilesCollection"]

                        # Process each phase's files
                        for phase in ["analysis", "design", "yaml", "documentation"]:
                            if phase in collection and isinstance(
                                collection[phase], list
                            ):
                                for file_info in collection[phase]:
                                    generated_files.append(
                                        {
                                            "phase": phase,
                                            "file_name": file_info.get("file_name", ""),
                                            "file_type": file_info.get("file_type", ""),
                                            "status": file_info.get(
                                                "conversion_status", "Success"
                                            )
                                            if phase == "yaml"
                                            else "Success",
                                            "accuracy": file_info.get(
                                                "accuracy_rating", ""
                                            )
                                            if phase == "yaml"
                                            else "",
                                            "summary": file_info.get(
                                                "content_summary", ""
                                            ),
                                            "timestamp": _get_utc_timestamp(),
                                        }
                                    )

                        # Extract conversion metrics
                        if "ProcessMetrics" in outcome_data:
                            metrics = outcome_data["ProcessMetrics"]
                            conversion_metrics = {
                                "platform_detected": metrics.get(
                                    "platform_detected", ""
                                ),
                                "conversion_accuracy": metrics.get(
                                    "conversion_accuracy", ""
                                ),
                                "documentation_completeness": metrics.get(
                                    "documentation_completeness", ""
                                ),
                                "enterprise_readiness": metrics.get(
                                    "enterprise_readiness", ""
                                ),
                                "total_files_generated": collection.get(
                                    "total_files_generated", 0
                                ),
                            }
                except Exception as e:
                    logger.error(f"Error extracting file and metrics data: {e}")
                    # Continue with basic outcome recording

                # Record the final outcome
                current_process.final_outcome = {
                    "success": success,
                    "outcome_data": outcome_data,
                    "timestamp": _get_utc_timestamp(),
                    "total_steps_completed": len(current_process.step_results),
                }

                current_process.generated_files = generated_files
                current_process.conversion_metrics = conversion_metrics

                logger.info(
                    f"[TELEMETRY] Recorded final outcome - Success: {success}, Files: {len(generated_files)}"
                )

                if self.repository:
                    try:
                        await self.repository.update_async(current_process)
                    except Exception as e:
                        logger.error(f"Error recording final outcome: {e}")

    async def record_failure_outcome(
        self,
        process_id: str,
        error_message: str,
        failed_step: str,
        failure_details: dict | None = None,
    ):
        current_process: ProcessStatus | None = None
        if self.repository:
            current_process = await self.repository.get_async(process_id)
            """Record failure outcome with detailed error information."""
            if not current_process:
                logger.warning("No current process - cannot record failure outcome")
                return
            else:
                failure_data = failure_details or {}
                current_process.final_outcome = {
                    "success": False,
                    "error_message": error_message,
                    "failed_step": failed_step,
                    "failure_details": failure_data,
                    "timestamp": _get_utc_timestamp(),
                    "total_steps_completed": len(current_process.step_results),
                }

                logger.info(
                    f"[TELEMETRY] Recorded failure outcome - Step: {failed_step}, Error: {error_message}"
                )

                try:
                    await self.repository.update_async(current_process)
                except Exception as e:
                    logger.error(f"Error recording failure outcome: {e}")

    async def get_final_results_summary(self, process_id: str) -> dict[str, Any]:
        """Get a summary of the final results for external consumption."""
        current_process: ProcessStatus | None = None
        if self.repository:
            current_process = await self.repository.get_async(process_id)
            if not current_process:
                return {"error": "No active process"}
            else:
                return {
                    "process_id": current_process.id,
                    "status": current_process.status,
                    "final_outcome": current_process.final_outcome,
                    "step_results": current_process.step_results,
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
