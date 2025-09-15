"""
Base Orchestrator for Step-Specific Group Chat Management.

This module provides the foundational classes for step-specific orchestrations:
- StepSpecificGroupChatManager: Base manager for all step conversations
- StepGroupChatOrchestrator: Factory for creating step orchestrations

Following SK Process Framework best practices:
- Kernel isolation per step with per-step MCP plugins
- Single responsibility per orchestration
- Event-driven communication
- Modular and reusable design
- Intelligent chat history management
- MCP plugin lifecycle aligned with orchestration lifecycle
"""

import logging
from typing import Any

from jinja2 import Template
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.agents.orchestration.group_chat import (
    BooleanResult,
    GroupChatManager,
    StringResult,
)
from semantic_kernel.agents.runtime import InProcessRuntime
from semantic_kernel.connectors.ai.chat_completion_client_base import (
    ChatCompletionClientBase,
)
from semantic_kernel.contents import AuthorRole, ChatHistory

from plugins.mcp_server import MCPBlobIOPlugin, MCPDatetimePlugin, MCPMicrosoftDocs
from utils.agent_telemetry import TelemetryManager

logger = logging.getLogger(__name__)


class StepSpecificGroupChatManager(GroupChatManager):
    """
    Base group chat manager for step-specific orchestrations.

    Following best practices:
    - Focused on single step responsibility
    - Clear termination criteria per step
    - Appropriate agent selection for step context
    - Intelligent chat history management that preserves function calls
    - Agent response telemetry tracking
    """

    service: ChatCompletionClientBase
    step_name: str
    step_objective: str
    process_context: dict[str, Any]
    telemetry: TelemetryManager

    def __init__(
        self,
        step_name: str,
        step_objective: str,
        service: ChatCompletionClientBase,
        **kwargs,
    ) -> None:
        """Initialize step-specific group chat manager."""
        # Pass step_name and step_objective as part of kwargs for Pydantic validation
        kwargs["step_name"] = step_name
        kwargs["step_objective"] = step_objective
        kwargs["service"] = service
        # self.process_context = kwargs["process_context"]
        super().__init__(**kwargs)

    async def _track_agent_message_if_new(self, chat_history: ChatHistory):
        """
        Track new agent messages in telemetry with enhanced detail.

        This method checks for new agent messages in the chat history
        and tracks them using our telemetry system to provide visibility
        into what each agent is actually doing during the conversation.
        """
        if not chat_history.messages:
            return

        # Get the most recent message
        recent_message = chat_history.messages[-1]

        # Only track assistant messages (agent responses)
        if recent_message.role == AuthorRole.ASSISTANT and hasattr(
            recent_message, "name"
        ):
            agent_name = getattr(recent_message, "name", "Unknown_Agent")
            raw_content = recent_message.content
            message_content = raw_content or ""

            # Enhanced message preview for telemetry
            message_preview = ""
            action_type = "responding"

            # Analyze message content to determine activity type
            if message_content:
                # Truncate for preview (first 150 chars)
                message_preview = (
                    message_content[:150] + "..."
                    if len(message_content) > 150
                    else message_content
                )

                # Determine activity based on content patterns
                content_lower = message_content.lower()
                if any(
                    word in content_lower
                    for word in ["analyzing", "examining", "investigating", "checking"]
                ):
                    action_type = "analyzing"
                elif any(
                    word in content_lower
                    for word in ["designing", "planning", "creating", "building"]
                ):
                    action_type = "designing"
                elif any(
                    word in content_lower
                    for word in ["found", "discovered", "detected", "identified"]
                ):
                    action_type = "reporting_findings"
                elif any(
                    word in content_lower
                    for word in ["let me", "i will", "i'll check", "i need to"]
                ):
                    action_type = "thinking"
                elif any(
                    word in content_lower
                    for word in ["completed", "finished", "done", "ready"]
                ):
                    action_type = "completed"
                elif "function_call" in str(recent_message) or "tool" in content_lower:
                    action_type = "using_tools"

            # Track agent activity with enhanced detail
            await self.telemetry.update_agent_activity(
                process_id=self.process_context.get("process_id"),
                agent_name=agent_name,
                action=action_type,
                message_preview=message_preview,
            )

            # Log detailed activity for debugging
            logger.info(f"[TELEMETRY] {agent_name} -> {action_type}: {message_preview}")

            # Debug logging to track content issues (force INFO level for visibility)
            if raw_content is None:
                logger.info(
                    f"[SEARCH] TELEMETRY DEBUG: Agent {agent_name} has None content in recent_message"
                )
            elif raw_content == "":
                logger.info(
                    f"[SEARCH] TELEMETRY DEBUG: Agent {agent_name} has empty string content"
                )
            else:
                logger.info(
                    f"[SUCCESS] TELEMETRY DEBUG: Agent {agent_name} has content: {len(raw_content)} chars"
                )

            # Track the agent response using enhanced reasoning tracking
            try:
                # Extract reasoning from response if present
                reasoning = ""
                reasoning_steps = []

                # Look for reasoning patterns in the response
                if message_content:
                    content_lower = message_content.lower()

                    # Extract reasoning from common patterns
                    reasoning_indicators = [
                        "because",
                        "since",
                        "due to",
                        "given that",
                        "considering",
                        "based on",
                    ]
                    if any(
                        indicator in content_lower for indicator in reasoning_indicators
                    ):
                        for indicator in reasoning_indicators:
                            if indicator in content_lower:
                                idx = content_lower.find(indicator)
                                if idx >= 0:  # Allow reasoning at start of response
                                    # Extract reasoning from that point
                                    reasoning_text = message_content[
                                        idx : idx + 200
                                    ]  # Get ~200 chars of reasoning
                                    sentence_end = reasoning_text.find(". ")
                                    if sentence_end > 0:
                                        reasoning = reasoning_text[
                                            :sentence_end
                                        ].strip()
                                    else:
                                        reasoning = reasoning_text.strip()
                                    break

                    # Look for step-by-step reasoning (numbered lists, bullet points)
                    lines = message_content.split("\n")
                    for line in lines:
                        line_stripped = line.strip()
                        if (
                            line_stripped.startswith(("1.", "2.", "3.", "•", "-", "*"))
                            and len(line_stripped) > 10
                        ):  # Reasonable length for a step
                            reasoning_steps.append(line_stripped)
                            if (
                                len(reasoning_steps) >= 5
                            ):  # Limit to 5 steps to avoid bloat
                                break

                # Use enhanced tracking with reasoning
                if reasoning or reasoning_steps:
                    # Log the enhanced telemetry instead of calling track_agent_response
                    logger.info(
                        f"[SUCCESS] Agent {agent_name} response tracked: {len(message_content)} chars, reasoning: {len(reasoning)} chars, steps: {len(reasoning_steps) if reasoning_steps else 0}"
                    )
                else:
                    # Fallback to basic tracking if no reasoning detected
                    logger.info(
                        f"[SUCCESS] Agent {agent_name} response tracked: {len(message_content)} chars"
                    )

            except Exception as e:
                logger.warning(f"Failed to track agent response for {agent_name}: {e}")

    def _smart_truncate_chat_history(
        self,
        chat_history: ChatHistory,
        max_messages: int = 20,
        preserve_system: bool = True,
        preserve_recent_functions: bool = True,
    ) -> None:
        """
        Intelligently truncate chat history preserving important context.

        Args:
            chat_history: The chat history to truncate (modified in place)
            max_messages: Maximum number of messages to keep
            preserve_system: Whether to preserve system messages
            preserve_recent_functions: Whether to preserve function call pairs
        """
        if len(chat_history.messages) <= max_messages:
            return

        logger.info(
            f"[INFO] {self.step_name}: Truncating chat history from {len(chat_history.messages)} to ~{max_messages} messages"
        )

        # Separate message types
        system_messages = []
        function_messages = []
        regular_messages = []

        for msg in chat_history.messages:
            if msg.role == AuthorRole.SYSTEM:
                system_messages.append(msg)
            elif hasattr(msg, "function_call") or msg.role == AuthorRole.TOOL:
                function_messages.append(msg)
            else:
                regular_messages.append(msg)

        # Calculate available space
        available_space = max_messages
        if preserve_system and system_messages:
            available_space -= 1  # Reserve space for latest system message

        # Preserve recent function call pairs (critical for migration workflow)
        preserved_functions = []
        if preserve_recent_functions and function_messages:
            # Take last few function messages (they often come in pairs)
            preserved_functions = function_messages[-min(6, len(function_messages)) :]
            available_space -= len(preserved_functions)
            logger.info(
                f"[TOOLS] {self.step_name}: Preserving {len(preserved_functions)} function call messages"
            )

        # Fill remaining space with recent regular messages
        recent_regular = regular_messages[-max(0, available_space) :]

        # Rebuild chat history
        new_messages = []

        # Add latest system message if preserving
        if preserve_system and system_messages:
            new_messages.append(system_messages[-1])
            logger.info(
                f"[SPEECH_BUBBLE] {self.step_name}: Preserving latest system message"
            )

        # Add preserved function messages
        new_messages.extend(preserved_functions)

        # Add recent regular messages
        new_messages.extend(recent_regular)

        # Sort by original order
        original_order = {id(msg): i for i, msg in enumerate(chat_history.messages)}
        new_messages.sort(key=lambda msg: original_order.get(id(msg), float("inf")))

        # Update chat history in place
        chat_history.messages.clear()
        chat_history.messages.extend(new_messages)

        logger.info(
            f"[SUCCESS] {self.step_name}: Chat history truncated to {len(chat_history.messages)} messages preserving context"
        )

    def _estimate_token_count(self, text: str) -> int:
        """
        Improved estimation of token count for text.
        Uses 3.5 characters per token approximation (closer to GPT tokenization).
        """
        return int(len(text) / 3.5) if text else 0

    def _truncate_message_content(self, content: str, max_tokens: int = 1000) -> str:
        """
        Truncate message content to keep within token limits while preserving key info.

        Args:
            content: Message content to truncate
            max_tokens: Maximum tokens to keep (default 1000 tokens = ~4000 chars)

        Returns:
            Truncated content with preservation markers
        """
        if not content:
            return content

        max_chars = max_tokens * 4  # ~4 chars per token

        if len(content) <= max_chars:
            return content

        # Preserve start and end of content to maintain context
        start_portion = max_chars // 3  # First third
        end_portion = max_chars // 3  # Last third

        truncated = (
            content[:start_portion]
            + f"\n\n[... CONTENT TRUNCATED - REMOVED {len(content) - start_portion - end_portion} CHARACTERS ...]\n\n"
            + content[-end_portion:]
        )

        logger.info(
            f"[INFO] Content truncated from {len(content)} to {len(truncated)} chars (~{self._estimate_token_count(truncated)} tokens)"
        )
        return truncated

    def _smart_truncate_chat_history_with_token_limit(
        self,
        chat_history: ChatHistory,
        max_total_tokens: int = 3000,  # Optimized: Reduced by 40% for cost efficiency
        max_messages: int = 8,  # Optimized: Reduced to 8 messages max
        max_tokens_per_message: int = 400,  # Optimized: Reduced to 400 tokens per message
        preserve_system: bool = True,
        preserve_recent_functions: bool = True,
    ) -> None:
        """
        Enhanced truncation that considers both message count AND token limits.

        This method addresses the context length exceeded error by:
        1. Limiting total number of messages more aggressively
        2. Truncating individual message content to reasonable sizes
        3. Estimating total token usage and staying under limits

        Args:
            chat_history: The chat history to truncate (modified in place)
            max_total_tokens: Maximum total tokens across all messages
            max_messages: Maximum number of messages to keep
            max_tokens_per_message: Maximum tokens per individual message
            preserve_system: Whether to preserve system messages
            preserve_recent_functions: Whether to preserve function call pairs
        """
        if not chat_history.messages:
            return

        logger.info(
            f"[INFO] {self.step_name}: Enhanced truncation - {len(chat_history.messages)} messages, estimating token usage..."
        )

        # First pass: estimate current token usage and log per-message breakdown
        message_tokens = []
        total_tokens = 0
        for i, msg in enumerate(chat_history.messages):
            msg_tokens = self._estimate_token_count(msg.content or "")
            message_tokens.append(msg_tokens)
            total_tokens += msg_tokens
            logger.info(
                f"[TOKEN_DEBUG] Message {i}: ~{msg_tokens} tokens, role: {msg.role}, author: {getattr(msg, 'name', 'N/A')}"
            )

        logger.info(
            f"[INFO] {self.step_name}: Estimated current token usage: ~{total_tokens} tokens across {len(chat_history.messages)} messages"
        )

        # If we're already under limits and message count is reasonable, do minimal truncation
        if (
            total_tokens <= max_total_tokens
            and len(chat_history.messages) <= max_messages
        ):
            # Still apply per-message truncation to prevent individual messages from being too large
            for msg in chat_history.messages:
                if (
                    msg.content
                    and self._estimate_token_count(msg.content) > max_tokens_per_message
                ):
                    msg.content = self._truncate_message_content(
                        msg.content, max_tokens_per_message
                    )
            return

        # Separate message types
        system_messages = []
        function_messages = []
        regular_messages = []

        for msg in chat_history.messages:
            if msg.role == AuthorRole.SYSTEM:
                system_messages.append(msg)
            elif hasattr(msg, "function_call") or msg.role == AuthorRole.TOOL:
                function_messages.append(msg)
            else:
                regular_messages.append(msg)

        # Be more aggressive with message count limits
        available_space = max_messages
        if preserve_system and system_messages:
            available_space -= 1

        # Preserve fewer function messages to save space
        preserved_functions = []
        if preserve_recent_functions and function_messages:
            # Only keep 2-4 most recent function messages instead of 6
            preserved_functions = function_messages[-min(4, len(function_messages)) :]
            available_space -= len(preserved_functions)
            logger.info(
                f"[TOOLS] {self.step_name}: Preserving {len(preserved_functions)} function call messages"
            )

        # Take fewer regular messages
        recent_regular = regular_messages[-max(0, available_space) :]

        # Rebuild chat history with aggressive truncation
        new_messages = []

        # Add latest system message if preserving (and truncate its content)
        if preserve_system and system_messages:
            sys_msg = system_messages[-1]
            if sys_msg.content:
                sys_msg.content = self._truncate_message_content(
                    sys_msg.content, max_tokens_per_message
                )
            new_messages.append(sys_msg)
            logger.info(f"[SPEECH_BUBBLE] {self.step_name}: Preserving system message")

        # Add function messages (truncate their content too)
        for func_msg in preserved_functions:
            if func_msg.content:
                func_msg.content = self._truncate_message_content(
                    func_msg.content, max_tokens_per_message
                )
            new_messages.append(func_msg)

        # Add recent regular messages (truncate their content)
        for reg_msg in recent_regular:
            if reg_msg.content:
                reg_msg.content = self._truncate_message_content(
                    reg_msg.content, max_tokens_per_message
                )
            new_messages.append(reg_msg)

        # Sort by original order
        original_order = {id(msg): i for i, msg in enumerate(chat_history.messages)}
        new_messages.sort(key=lambda msg: original_order.get(id(msg), float("inf")))

        # Update chat history
        chat_history.messages.clear()
        chat_history.messages.extend(new_messages)

        # Final token estimation
        final_tokens = sum(
            self._estimate_token_count(msg.content or "")
            for msg in chat_history.messages
        )

        logger.info(
            f"[SUCCESS] {self.step_name}: Enhanced truncation complete - {len(chat_history.messages)} messages, ~{final_tokens} tokens"
        )

    async def _render_prompt(self, prompt: str, **kwargs) -> str:
        """Helper to render a prompt with arguments."""
        template = Template(prompt)
        return template.render(
            step_name=self.step_name, step_objective=self.step_objective, **kwargs
        )

    async def should_terminate(self, chat_history: ChatHistory) -> BooleanResult:
        """
        Check termination with agent response tracking.

        Override this method in step-specific managers, but always call
        this parent method to ensure agent response tracking.
        """
        # CRITICAL: Apply aggressive chat history truncation BEFORE termination check
        # This prevents the 428K token context length exceeded errors
        logger.info(
            f"[TRUNCATION] {self.step_name}: Applying pre-termination truncation - current messages: {len(chat_history.messages)}"
        )

        # self._smart_truncate_chat_history_with_token_limit(
        #     chat_history,
        #     max_total_tokens=8000,  # Optimized: Reduced by 73% for termination efficiency
        #     max_messages=10,  # Optimized: Reduced to 10 messages
        #     max_tokens_per_message=800,  # Optimized: Reduced to 800 tokens per message
        # )

        # logger.info(
        #     f"[TRUNCATION] {self.step_name}: Post-truncation messages: {len(chat_history.messages)}"
        # )

        # Track any new agent messages before termination check
        await self._track_agent_message_if_new(chat_history)

        # Fallback termination (should be overridden by subclasses)
        return BooleanResult(
            result=False,
            reason=f"Step {self.step_name} termination logic not implemented",
        )

    async def select_next_agent(
        self,
        chat_history: ChatHistory,
        participant_descriptions: dict[str, str],
    ) -> StringResult:
        """
        Select next agent with response tracking.

        Override this method in step-specific managers, but always call
        this parent method to ensure agent response tracking.
        """
        # CRITICAL: Apply aggressive chat history truncation BEFORE any agent operations
        # This prevents the 428K token context length exceeded errors
        logger.info(
            f"[TRUNCATION] {self.step_name}: Applying pre-agent truncation - current messages: {len(chat_history.messages)}"
        )

        # self._smart_truncate_chat_history_with_token_limit(
        #     chat_history,
        #     max_total_tokens=8000,  # Optimized: Reduced by 73% for agent selection efficiency
        #     max_messages=10,  # Optimized: Reduced to 10 messages
        #     max_tokens_per_message=800,  # Optimized: Reduced to 800 tokens per message
        # )

        logger.info(
            f"[TRUNCATION] {self.step_name}: Post-truncation messages: {len(chat_history.messages)}"
        )

        # Track any new agent messages before selecting next agent
        await self._track_agent_message_if_new(chat_history)

        # Starting conversation turn
        logger.debug(f"[PROCESSING] Starting conversation turn for {self.step_name}")

        # Get the selected agent result from child implementation
        result = await self._select_next_agent_implementation(
            chat_history, participant_descriptions
        )

        # Track that the selected agent is now thinking
        if result and hasattr(result, "result") and result.result != "Unknown":
            try:
                thinking_description = f"Processing {self.step_name} step requirements"
                selection_reasoning = getattr(
                    result, "reason", "Agent selected by orchestrator"
                )

                # Log the agent thinking instead of calling track_agent_thinking
                logger.info(
                    f"[SUCCESS] Agent thinking tracked for {result.result}: {thinking_description}, reasoning: {selection_reasoning}"
                )
                logger.info(
                    f"[THINKING] Agent {result.result} is now thinking about {self.step_name}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to track thinking status for {result.result}: {e}"
                )

        return result

    async def _select_next_agent_implementation(
        self,
        chat_history: ChatHistory,
        participant_descriptions: dict[str, str],
    ) -> StringResult:
        """
        Implementation-specific agent selection logic.

        Override this method in step-specific managers with your selection logic.
        The base implementation provides a fallback.
        """
        # Fallback selection (should be overridden by subclasses)
        return StringResult(
            result="Unknown",
            reason=f"Step {self.step_name} agent selection logic not implemented",
        )

    def _safe_get_content(self, response) -> str:
        """Safely get content from response, handling None case."""
        if response is None or response.content is None:
            raise RuntimeError(
                f"No response received from service for {self.step_name} step"
            )
        return response.content

    async def should_request_user_input(
        self, chat_history: ChatHistory
    ) -> BooleanResult:
        """No user input required for automated step processing."""
        return BooleanResult(
            result=False,
            reason=f"Step {self.step_name} processes automatically without user input.",
        )


class StepGroupChatOrchestrator:
    """
    Factory class for creating step-specific group chat orchestrations.

    Following SK Process Framework best practices:
    - Isolated orchestration per step
    - Appropriate agent selection per step
    - Focused objectives and termination criteria
    """

    def __init__(
        self,
        kernel_agent,
        process_context: dict[str, Any],
    ):
        """Initialize with isolated kernel agent and process context."""
        self.kernel_agent = kernel_agent
        self.process_context = process_context
        self.logger = logging.getLogger(__name__)

    async def cleanup(self):
        """Clean up orchestrator resources - TaskGroup-safe pattern."""
        try:
            self.logger.info("[CLEANUP] Cleaning up orchestrator resources...")
            # Note: MCP contexts are now handled with async context managers
            # in task-local scope, so no manual cleanup needed here
            self.logger.info("[SUCCESS] Orchestrator resources cleaned up")
        except Exception as e:
            self.logger.warning(f"[WARNING] Error during orchestrator cleanup: {e}")

    async def create_agent_with_kernel_plugins(
        self, agent_config, service_id: str = "default"
    ):
        """
        Create agent directly using kernel-level MCP plugins.

        This bypasses PluginContext to avoid task boundary violations.
        Since MCP plugins are already connected at kernel level during
        app initialization, agents can use them directly.

        Args:
            agent_config: Agent configuration object
            service_id: Service ID for AI service

        Returns:
            ChatCompletionAgent with kernel MCP plugins
        """
        # Debug: Check kernel plugins availability
        self.logger.info(
            f"[SEARCH] DEBUG: Available kernel plugins: {list(self.kernel_agent.kernel.plugins.keys())}"
        )

        # Get all available kernel plugins (use all of them instead of filtering by name)
        available_plugins = []

        # Add ALL kernel plugins (this ensures we get the MCP plugins regardless of their names)
        for plugin_name, plugin in self.kernel_agent.kernel.plugins.items():
            available_plugins.append(plugin)
            self.logger.info(
                f"[TOOLS] Adding kernel plugin: '{plugin_name}' with {len(plugin.functions)} functions"
            )

        self.logger.info(f"[TOOLS] Total plugins for agent: {len(available_plugins)}")

        # Create agent with kernel plugins directly
        agent = ChatCompletionAgent(
            kernel=self.kernel_agent.kernel,
            name=agent_config.agent_name,
            instructions=agent_config.instructions,
            plugins=available_plugins,
        )

        # Track agent creation in telemetry
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name=agent_config.agent_name,
            action="agent_created",
            message_preview=f"Agent created with {len(available_plugins)} plugins for orchestration",
        )

        self.logger.info(
            f"[SUCCESS] Created agent '{agent_config.agent_name}' with {len(available_plugins)} kernel plugins"
        )

        return agent

    async def run_step_orchestration(
        self, orchestration, task: str, step_name: str
    ) -> Any:
        """
        Run a step-specific orchestration with proper runtime management.

        Following best practices:
        - Isolated runtime per step
        - Proper cleanup
        - Clear task objectives
        """
        self.logger.info(
            f"[START] Starting {step_name} orchestration with task: {task}"
        )

        # Track orchestration start in telemetry
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name="Conversation_Manager",
            action="expert_collaboration_framework_starting",
            message_preview=f"{step_name} expert discussion framework starting with multi-agent collaboration",
        )

        # Create isolated runtime for this step
        runtime = InProcessRuntime()
        runtime.start()

        try:
            # Invoke the orchestration
            orchestration_result = await orchestration.invoke(
                task=task,
                runtime=runtime,
            )

            # Wait for the results
            result = await orchestration_result.get()

            # Track successful completion
            await self.telemetry.update_agent_activity(
                process_id=self.process_context.get("process_id"),
                agent_name="Conversation_Manager",
                action="expert_collaboration_framework_completed",
                message_preview=f"{step_name} expert discussion framework completed with successful collaboration",
            )

            self.logger.info(
                f"[SUCCESS] {step_name} orchestration completed successfully"
            )
            return result

        except Exception as e:
            # Enhanced error logging for orchestration failures (including AzureChatCompletion)
            import traceback

            full_error_details = {
                "exception_type": type(e).__name__,
                "exception_module": type(e).__module__,
                "exception_message": str(e),
                "full_traceback": traceback.format_exc(),
                "exception_args": getattr(e, "args", []),
                "exception_cause": str(e.__cause__) if e.__cause__ else None,
                "exception_context": str(e.__context__) if e.__context__ else None,
            }

            # Track orchestration failure with complete details
            await self.telemetry.update_agent_activity(
                process_id=self.process_context.get("process_id"),
                agent_name="Conversation_Manager",
                action="expert_collaboration_failed",
                message_preview=f"{step_name} expert collaboration failed - {full_error_details['exception_type']}: {full_error_details['exception_message']}",
            )

            # Log complete error details
            self.logger.error(
                "[FAILED] Complete %s orchestration error details:\n"
                "Exception Type: %s\n"
                "Exception Module: %s\n"
                "Exception Message: %s\n"
                "Exception Args: %s\n"
                "Exception Cause: %s\n"
                "Exception Context: %s\n"
                "Full Traceback:\n%s",
                step_name,
                full_error_details["exception_type"],
                full_error_details["exception_module"],
                full_error_details["exception_message"],
                full_error_details["exception_args"],
                full_error_details["exception_cause"],
                full_error_details["exception_context"],
                full_error_details["full_traceback"],
            )
            raise
        finally:
            # Always clean up runtime
            await runtime.stop_when_idle()
            self.logger.info(f"[CLEANUP] {step_name} runtime cleaned up")

    async def setup_orchestration_mcp_plugins(
        self, orchestration_name: str
    ) -> dict[str, Any]:
        """
        Setup per-orchestration MCP plugins with comprehensive lifecycle management.

        This method creates and connects MCP plugin instances specifically for this
        orchestration, following Microsoft best practices for kernel isolation.

        Args:
            orchestration_name: Name of the orchestration for logging and tracking

        Returns:
            Dictionary containing connected MCP plugins and metadata

        Raises:
            Exception: If critical plugins fail to setup
        """
        self.logger.info(
            f"[TOOLS] {orchestration_name}: Setting up per-orchestration MCP plugins"
        )

        mcp_context = {
            "orchestration_name": orchestration_name,
            "plugins": {},
            "failed_plugins": [],
            "setup_timestamp": None,
            "connection_status": "initializing",
        }

        # Plugin factory functions for per-orchestration instances
        plugin_factories = {
            "blob_ops": (
                "MCPBlobIOPlugin",
                MCPBlobIOPlugin.get_blob_file_operation_plugin,
            ),
            "datetime": ("MCPDatetimePlugin", MCPDatetimePlugin.get_datetime_plugin),
            "ms_docs": ("MCPMicrosoftDocs", MCPMicrosoftDocs.get_microsoft_docs_plugin),
        }

        successful_plugins = 0

        for plugin_key, (plugin_name, factory_func) in plugin_factories.items():
            try:
                self.logger.info(
                    f"[PLUG] {orchestration_name}: Creating {plugin_name} instance"
                )

                # Create plugin instance
                plugin_instance = factory_func()

                if plugin_instance is None:
                    self.logger.warning(
                        f"[WARNING] {orchestration_name}: {plugin_name} factory returned None"
                    )
                    mcp_context["failed_plugins"].append(
                        {
                            "name": plugin_name,
                            "key": plugin_key,
                            "error": "Factory returned None",
                            "critical": plugin_key
                            == "blob_ops",  # blob_ops is critical for migration
                        }
                    )
                    continue

                # Connect plugin instance
                await plugin_instance.connect()
                self.logger.info(
                    f"[SUCCESS] {orchestration_name}: {plugin_name} connected successfully"
                )

                # Add to orchestration kernel
                self.kernel_agent.kernel.plugins.add_plugin(plugin_instance, plugin_key)

                # Get function count safely
                function_count = 0
                try:
                    if hasattr(plugin_instance, "function_count"):
                        function_count = getattr(plugin_instance, "function_count", 0)
                    elif hasattr(plugin_instance, "functions"):
                        functions = getattr(plugin_instance, "functions", None)
                        if functions:
                            function_count = len(functions)
                except (AttributeError, TypeError):
                    function_count = 0

                mcp_context["plugins"][plugin_key] = {
                    "plugin": plugin_instance,
                    "name": plugin_name,
                    "functions": function_count,
                    "connected": True,
                }

                successful_plugins += 1

            except Exception as e:
                self.logger.error(
                    f"[FAILED] {orchestration_name}: Failed to setup {plugin_name}: {str(e)}"
                )
                mcp_context["failed_plugins"].append(
                    {
                        "name": plugin_name,
                        "key": plugin_key,
                        "error": str(e),
                        "critical": plugin_key == "blob_ops",
                    }
                )

                # If this was a critical plugin, attempt emergency cleanup
                if plugin_key == "blob_ops":
                    self.logger.error(
                        f"[EXPLOSION] {orchestration_name}: CRITICAL PLUGIN FAILURE - blob operations unavailable"
                    )

        # Update context status
        mcp_context["connection_status"] = "completed"
        import datetime

        mcp_context["setup_timestamp"] = datetime.datetime.now().isoformat()

        # Report results
        total_plugins = len(plugin_factories)
        failed_count = len(mcp_context["failed_plugins"])

        if successful_plugins == 0:
            self.logger.error(
                f"[EXPLOSION] {orchestration_name}: TOTAL MCP PLUGIN FAILURE - no plugins available"
            )
            raise RuntimeError(
                f"All MCP plugins failed to setup for {orchestration_name}"
            )
        elif failed_count > 0:
            critical_failures = [
                p for p in mcp_context["failed_plugins"] if p.get("critical", False)
            ]
            if critical_failures:
                self.logger.error(
                    f"[EXPLOSION] {orchestration_name}: CRITICAL MCP PLUGIN FAILURES: {[p['name'] for p in critical_failures]}"
                )
                # Perform partial cleanup before failing
                await self._emergency_cleanup_mcp_plugins(
                    mcp_context, orchestration_name
                )
                raise RuntimeError(
                    f"Critical MCP plugins failed for {orchestration_name}: {[p['name'] for p in critical_failures]}"
                )
            else:
                self.logger.warning(
                    f"[WARNING] {orchestration_name}: Partial MCP plugin setup - {successful_plugins}/{total_plugins} plugins available"
                )
        else:
            self.logger.info(
                f"[SUCCESS] {orchestration_name}: Complete MCP plugin setup - {successful_plugins}/{total_plugins} plugins connected"
            )

        return mcp_context

    async def cleanup_orchestration_mcp_plugins(
        self, mcp_context: dict[str, Any], orchestration_name: str
    ) -> None:
        """
        Clean up per-orchestration MCP plugins with comprehensive error handling.

        Args:
            mcp_context: MCP context dictionary from setup_orchestration_mcp_plugins
            orchestration_name: Name of the orchestration for logging
        """
        if not mcp_context or "plugins" not in mcp_context:
            self.logger.warning(
                f"[WARNING] {orchestration_name}: No MCP context to cleanup"
            )
            return

        self.logger.info(
            f"[CLEANUP] {orchestration_name}: Cleaning up per-orchestration MCP plugins"
        )

        cleanup_errors = []
        successful_cleanup = 0

        for plugin_key, plugin_info in mcp_context["plugins"].items():
            try:
                plugin_instance = plugin_info["plugin"]
                plugin_name = plugin_info["name"]

                self.logger.info(
                    f"[PLUG] {orchestration_name}: Disconnecting {plugin_name}"
                )

                # Remove from kernel first
                if plugin_key in self.kernel_agent.kernel.plugins:
                    del self.kernel_agent.kernel.plugins[plugin_key]

                # Disconnect plugin instance
                if hasattr(plugin_instance, "disconnect"):
                    await plugin_instance.disconnect()
                elif hasattr(plugin_instance, "close"):
                    await plugin_instance.close()

                successful_cleanup += 1
                self.logger.info(
                    f"[SUCCESS] {orchestration_name}: {plugin_name} cleaned up successfully"
                )

            except Exception as e:
                self.logger.error(
                    f"[FAILED] {orchestration_name}: Failed to cleanup {plugin_info.get('name', plugin_key)}: {str(e)}"
                )
                cleanup_errors.append(
                    {
                        "plugin": plugin_key,
                        "name": plugin_info.get("name", plugin_key),
                        "error": str(e),
                    }
                )

        # Report cleanup results
        total_plugins = len(mcp_context["plugins"])
        if cleanup_errors:
            self.logger.warning(
                f"[WARNING] {orchestration_name}: Partial cleanup - {successful_cleanup}/{total_plugins} plugins cleaned, {len(cleanup_errors)} errors"
            )
        else:
            self.logger.info(
                f"[SUCCESS] {orchestration_name}: Complete cleanup - {successful_cleanup}/{total_plugins} plugins cleaned successfully"
            )

        # Clear the context
        mcp_context["plugins"].clear()
        mcp_context["connection_status"] = "cleaned_up"

    async def _emergency_cleanup_mcp_plugins(
        self, mcp_context: dict[str, Any], orchestration_name: str
    ) -> None:
        """
        Emergency cleanup for partial MCP plugin setup failures.

        Used when setup fails midway and we need to clean up successfully
        connected plugins before raising the error.

        Args:
            mcp_context: MCP context dictionary (possibly partial)
            orchestration_name: Name of the orchestration for logging
        """
        self.logger.warning(
            f"[ALERT] {orchestration_name}: Emergency MCP plugin cleanup initiated"
        )

        if not mcp_context or "plugins" not in mcp_context:
            self.logger.info(f"ℹ {orchestration_name}: No plugins to emergency cleanup")
            return

        emergency_cleanup_count = 0

        for plugin_key, plugin_info in list(mcp_context["plugins"].items()):
            try:
                plugin_instance = plugin_info["plugin"]
                plugin_name = plugin_info["name"]

                # Remove from kernel
                if plugin_key in self.kernel_agent.kernel.plugins:
                    del self.kernel_agent.kernel.plugins[plugin_key]

                # Disconnect
                if hasattr(plugin_instance, "disconnect"):
                    await plugin_instance.disconnect()
                elif hasattr(plugin_instance, "close"):
                    await plugin_instance.close()

                emergency_cleanup_count += 1
                self.logger.info(
                    f"[ALERT] {orchestration_name}: Emergency cleaned up {plugin_name}"
                )

            except Exception as e:
                self.logger.error(
                    f"[EXPLOSION] {orchestration_name}: Emergency cleanup failed for {plugin_info.get('name', plugin_key)}: {str(e)}"
                )

        self.logger.warning(
            f"[ALERT] {orchestration_name}: Emergency cleanup completed - {emergency_cleanup_count} plugins cleaned"
        )
        mcp_context["plugins"].clear()
        mcp_context["connection_status"] = "emergency_cleaned"

    async def create_agent_with_orchestration_mcp_plugins(
        self, agent_config, mcp_context: dict[str, Any], service_id: str = "default"
    ):
        """
        Create agent using per-orchestration MCP plugins.

        This method creates agents with the specific MCP plugin instances
        that were set up for this orchestration, ensuring proper isolation
        and lifecycle management.

        Args:
            agent_config: Agent configuration object
            mcp_context: MCP context from setup_orchestration_mcp_plugins
            service_id: Service ID for AI service

        Returns:
            ChatCompletionAgent with orchestration-specific MCP plugins
        """
        orchestration_name = mcp_context.get("orchestration_name", "unknown")

        if not mcp_context or "plugins" not in mcp_context:
            self.logger.warning(
                f"[WARNING] {orchestration_name}: No MCP plugins available for agent creation"
            )
            return await self.create_agent_with_kernel_plugins(agent_config, service_id)

        # Extract plugins from orchestration context
        orchestration_plugins = []

        for _plugin_key, plugin_info in mcp_context["plugins"].items():
            plugin_instance = plugin_info["plugin"]
            plugin_name = plugin_info["name"]
            function_count = plugin_info.get("functions", 0)

            orchestration_plugins.append(plugin_instance)
            self.logger.info(
                f"[TOOLS] {orchestration_name}: Adding orchestration plugin '{plugin_name}' with {function_count} functions"
            )

        self.logger.info(
            f"[TOOLS] {orchestration_name}: Total orchestration plugins for agent: {len(orchestration_plugins)}"
        )

        # Create agent with orchestration-specific plugins
        agent = ChatCompletionAgent(
            kernel=self.kernel_agent.kernel,
            name=agent_config.agent_name,
            instructions=agent_config.instructions,
            plugins=orchestration_plugins,
        )

        # Track agent creation with orchestration-specific plugins
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name=agent_config.agent_name,
            action="agent_created_with_plugins",
            message_preview=f"Agent created with {len(orchestration_plugins)} orchestration-specific plugins",
        )

        self.logger.info(
            f"[SUCCESS] {orchestration_name}: Created agent '{agent_config.agent_name}' with {len(orchestration_plugins)} orchestration-specific MCP plugins"
        )

        return agent

    # The orchestration creation methods will be implemented in specific files
    # This keeps the base class focused on common functionality
