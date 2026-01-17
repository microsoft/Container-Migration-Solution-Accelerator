# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
GroupChat Orchestrator with Generic Type Support

Provides a type-safe, reusable orchestrator for GroupChat workflows with:
- Generic input/converted types [TInput, TOutput]
- Streaming callbacks for agent responses
- Tool usage tracking
- Automatic termination handling
- Optional post-workflow analysis
"""

import json
import logging
from abc import ABC
from collections import deque
from collections.abc import Iterable
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Generic, Mapping, Sequence, TypeVar

from agent_framework import (
    AgentProtocol,
    AgentRunUpdateEvent,
    ChatAgent,
    ChatMessage,
    Executor,
    GroupChatBuilder,
    ManagerSelectionResponse,
    Role,
    Workflow,
    WorkflowOutputEvent,
)
from mem0 import AsyncMemory
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


# Generic type variables
TInput = TypeVar("TInput")  # Input type (str, dict, BaseModel, etc.)
TOutput = TypeVar("TOutput", bound=BaseModel)  # Output must be Pydantic model


@dataclass
class AgentResponse:
    """Represents a single agent's response during workflow execution"""

    agent_id: str
    agent_name: str
    message: str
    timestamp: datetime
    elapsed_time: float | None = None
    tool_calls: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None

    def model_dump(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "message": self.message,
            "timestamp": self.timestamp.isoformat()
            if isinstance(self.timestamp, datetime)
            else str(self.timestamp),
            "elapsed_time": self.elapsed_time,
            "tool_calls": self.tool_calls,
            "metadata": self.metadata,
        }


@dataclass
class AgentResponseStream:
    """Represents streaming response from an agent during workflow execution"""

    agent_id: str
    agent_name: str
    response_type: str  # "message" or "tool_call"
    timestamp: datetime
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None


@dataclass
class OrchestrationResult(Generic[TOutput]):
    """Final workflow execution result with generic output type"""

    success: bool
    conversation: list[ChatMessage]
    agent_responses: list[AgentResponse]
    tool_usage: dict[str, list[dict[str, Any]]]
    result: TOutput | None = None
    error: str | None = None
    execution_time_seconds: float = 0.0

    @staticmethod
    def _to_jsonable(value: Any) -> Any:
        """Convert arbitrary objects into JSON-serializable structures.

        This is primarily used to ensure `result` (a Pydantic model) is emitted
        as a dict instead of becoming an opaque string when callers do
        `json.dumps(..., default=str)`.
        """

        if value is None:
            return None

        if isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, dict):
            return {
                str(k): OrchestrationResult._to_jsonable(v) for k, v in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [OrchestrationResult._to_jsonable(v) for v in value]

        # Pydantic v2
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            try:
                return OrchestrationResult._to_jsonable(model_dump())
            except Exception:
                pass

        # Pydantic v1
        dict_fn = getattr(value, "dict", None)
        if callable(dict_fn):
            try:
                return OrchestrationResult._to_jsonable(dict_fn())
            except Exception:
                pass

        if is_dataclass(value):
            try:
                return OrchestrationResult._to_jsonable(asdict(value))
            except Exception:
                pass

        try:
            return OrchestrationResult._to_jsonable(dict(vars(value)))
        except Exception:
            return str(value)

    def model_dump(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "conversation": self._to_jsonable(self.conversation),
            "agent_responses": [r.model_dump() for r in self.agent_responses],
            "tool_usage": self._to_jsonable(self.tool_usage),
            "result": self._to_jsonable(self.result),
            "error": self.error,
            "execution_time_seconds": self.execution_time_seconds,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.model_dump(), ensure_ascii=False, indent=indent)


# Callback type definitions
AgentResponseCallback = Callable[[AgentResponse], Awaitable[None]]
AgentResponseStreamCallback = Callable[[AgentResponseStream], Awaitable[None]]
OnOrchestrationCompleteCallback = Callable[
    [OrchestrationResult[TOutput]], Awaitable[None]
]


class GroupChatOrchestrator(ABC, Generic[TInput, TOutput]):
    """
    Generic GroupChat orchestrator with type-safe input/converted.

    Type Parameters:
        TInput: Type of input passed to run_stream (str, dict, BaseModel, etc.)
        TOutput: Type of final analysis output (must be Pydantic BaseModel)

    Note:
        This orchestrator expects agents to be pre-created and passed in via
        `participants`. Creation of `ChatAgent` instances (and wiring tools)
        is handled elsewhere in the app.
    """

    def __init__(
        self,
        name: str,
        process_id: str,
        participants: Mapping[str, AgentProtocol | Executor]
        | Sequence[AgentProtocol | Executor],
        memory_client: AsyncMemory,
        coordinator_name: str = "Coordinator",
        max_rounds: int = 100,
        max_seconds: float | None = None,
        result_output_format: type[TOutput] | None = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            name: Friendly workflow name (used for logging/diagnostics)
            process_id: Workflow/process identifier (used for tracing)
            participants: Mapping/sequence of pre-created agents (including the Coordinator)
            memory_client: Mem0 async memory client for multi-agent memory (may be None depending on runtime)
            coordinator_name: Name of the coordinator/manager agent
            max_rounds: Maximum conversation rounds before termination
            result_output_format: Pydantic model class to parse ResultGenerator output into.
                                 If None, post-workflow result generation is skipped.

        Termination:
            The underlying GroupChat workflow does not automatically stop when the
            Coordinator returns `finish=true`. This orchestrator enforces early-stop by
            detecting a valid `ManagerSelectionResponse` from the Coordinator and breaking
            the streaming loop.
        """
        self.name = name
        self.process_id = process_id
        # self.participants = participants
        self.memory_client = memory_client
        self.coordinator_name = coordinator_name
        self.max_rounds = max_rounds
        self.max_seconds = max_seconds
        self.result_format = result_output_format

        # Runtime state
        self.agents: dict[str, ChatAgent] = participants
        self.agent_tool_usage: dict[str, list[dict[str, Any]]] = {}
        self.agent_responses: list[AgentResponse] = []
        self._initialized: bool = False

        # Streaming response buffer
        self._last_executor_id: str | None = None
        self._current_agent_response: list[str] = []
        self._current_agent_start_time: datetime | None = None

        # Tracks when the Coordinator selected ("invoked") a participant.
        # Used to compute elapsed_time from invocation -> completed response.
        self._agent_invoked_at: dict[str, datetime] = {}

        # Tool-call streaming buffers. Some agent frameworks stream tool arguments
        # progressively; we only emit tool_call callbacks once arguments parse.
        self._tool_call_arg_buffer: dict[tuple[str, str], str] = {}
        self._tool_call_emitted: set[tuple[str, str]] = set()
        # Tracks tool calls that have been recorded into agent_tool_usage.
        # We only record a tool call once per (agent_name, call_id) to avoid
        # capturing many partial streaming argument fragments.
        self._tool_call_recorded: set[tuple[str, str]] = set()
        # Index of tool calls in `agent_tool_usage[agent_name]` keyed by (agent_name, call_id).
        # This ensures we never append duplicates for the same tool call and can update
        # the existing entry once arguments become complete.
        self._tool_call_index: dict[tuple[str, str], int] = {}

        # Termination flags (driven by manager/Coordinator finish=true)
        self._termination_requested: bool = False
        self._termination_final_message: str | None = None
        self._termination_instruction: str | None = None

        # Forced termination flags (timeouts / loop breakers)
        self._forced_termination_requested: bool = False
        self._forced_termination_reason: str | None = None
        self._forced_termination_type: str | None = None

        # Loop detection for Coordinator selections (participant + instruction)
        self._last_coordinator_selection: tuple[str, str] | None = None
        self._coordinator_selection_streak: int = 0
        self._recent_coordinator_selections: deque[tuple[str, str]] = deque(maxlen=10)

        # Progress counter used to avoid false-positive loop detection.
        # Incremented whenever any non-Coordinator agent completes a response.
        self._progress_counter: int = 0
        # Snapshot of progress_counter at the time we last saw _last_coordinator_selection.
        self._last_coordinator_selection_progress: int = 0

    def _request_forced_termination(
        self, *, reason: str, termination_type: str
    ) -> None:
        """Request a forced termination (timeouts/loop breakers).

        This is intended for safety stops (timeouts, repeated loops) rather than
        normal completion. Once set, the streaming loop will break and a best-effort
        hard-terminated result may be produced.
        """
        if self._termination_requested or self._forced_termination_requested:
            return
        self._forced_termination_requested = True
        self._forced_termination_reason = reason
        self._forced_termination_type = termination_type

    def _try_build_forced_result(
        self, *, reason: str, termination_type: str
    ) -> TOutput | None:
        """Build a best-effort hard-terminated output model.

        Many step output models share common fields such as `is_hard_terminated`,
        `termination_type`, and `blocking_issues`. This helper attempts to populate
        whatever fields are present in the configured Pydantic `result_format`.

        Returns
        -------
        TOutput | None
            A validated output model if `result_format` is configured, otherwise None.
        """
        result_format = self.result_format
        if result_format is None:
            return None

        # Build a best-effort payload that works across step output models.
        fields = getattr(result_format, "model_fields", {})
        payload: dict[str, Any] = {}

        if "result" in fields:
            payload["result"] = True
        if "reason" in fields:
            payload["reason"] = reason
        if "is_hard_terminated" in fields:
            payload["is_hard_terminated"] = True
        if "termination_type" in fields:
            payload["termination_type"] = termination_type
        if "blocking_issues" in fields:
            payload["blocking_issues"] = [reason]
        if "process_id" in fields:
            payload["process_id"] = self.process_id
        if "output" in fields:
            payload["output"] = None
        if "termination_output" in fields:
            payload["termination_output"] = None

        return result_format.model_validate(payload)

    def get_result_generator_name(self) -> str:
        """
        Override to customize ResultGenerator agent name.

        Returns:
            Name of the result generator agent (default: "ResultGenerator")
        """
        return "ResultGenerator"

    def _validate_sign_offs(self, conversation: list[ChatMessage]) -> tuple[bool, str]:
        """
        Validate that all required reviewers have SIGN-OFF: PASS.

        Returns:
            Tuple of (is_valid, reason)
            - is_valid: True if all sign-offs are PASS, False otherwise
            - reason: Empty string if valid, otherwise explanation of missing/pending/failed sign-offs
        """
        # Get all messages in reverse order (most recent first)
        recent_messages = list(reversed(conversation))

        # Track sign-off status for each agent
        sign_offs: dict[str, str] = {}

        # Track which agents actually participated (sent messages)
        participating_agents: set[str] = set()

        # Search for sign-off patterns in messages
        for msg in recent_messages:
            content = str(msg.content).upper()
            agent_name = msg.source if hasattr(msg, "source") else None

            if not agent_name or agent_name == self.coordinator_name:
                continue

            # Track this agent as a participant
            participating_agents.add(agent_name)

            # Check for explicit SIGN-OFF statements
            if "SIGN-OFF:" in content:
                if "SIGN-OFF: PASS" in content or "SIGN-OFF:PASS" in content:
                    sign_offs[agent_name] = "PASS"
                elif "SIGN-OFF: FAIL" in content or "SIGN-OFF:FAIL" in content:
                    sign_offs[agent_name] = "FAIL"
                elif "SIGN-OFF: PENDING" in content or "SIGN-OFF:PENDING" in content:
                    sign_offs[agent_name] = "PENDING"

        # Only validate sign-offs for agents that participated (excluding ResultGenerator)
        reviewer_agents = [
            name
            for name in participating_agents
            if name != self.coordinator_name
            and name != self.get_result_generator_name()
        ]

        # Validate sign-offs
        missing_or_invalid = []
        for agent_name in reviewer_agents:
            status = sign_offs.get(agent_name)
            if status != "PASS":
                if status == "PENDING":
                    missing_or_invalid.append(f"{agent_name}: PENDING")
                elif status == "FAIL":
                    missing_or_invalid.append(f"{agent_name}: FAIL")
                else:
                    missing_or_invalid.append(f"{agent_name}: missing")

        if missing_or_invalid:
            reason = f"Cannot terminate: {', '.join(missing_or_invalid)}. All reviewers must have SIGN-OFF: PASS."
            return False, reason

        return True, ""

    @staticmethod
    def _extract_first_json_payload(text: str) -> str:
        """Extract the first JSON value from text.

        Some models append extra plain text (e.g., 'SIGN-OFF: PASS') after a JSON
        object, which breaks strict JSON parsing. This helper extracts the first
        valid JSON payload so downstream JSON/schema parsing can succeed.
        """
        if not isinstance(text, str):
            raise TypeError(f"Expected str, got {type(text)}")

        candidate = text.strip()
        if not candidate:
            return candidate

        decoder = json.JSONDecoder()

        # Try parsing from the start (after stripping whitespace).
        try:
            _, end = decoder.raw_decode(candidate)
            return candidate[:end]
        except json.JSONDecodeError:
            pass

        # Try parsing from the first object/array start.
        start_positions = [
            pos for pos in (candidate.find("{"), candidate.find("[")) if pos != -1
        ]
        if not start_positions:
            return candidate

        start = min(start_positions)

        try:
            _, end = decoder.raw_decode(candidate[start:])
            return candidate[start : start + end]
        except json.JSONDecodeError:
            return candidate

    async def initialize(self) -> None:
        """Initialize all agents and setup workflow"""
        if self._initialized:
            return

        # Initialize agents if they have async init methods
        self._initialized = True

    async def run_stream(
        self,
        input_data: TInput,
        on_agent_response: AgentResponseCallback | None = None,
        on_agent_response_stream: AgentResponseStreamCallback | None = None,
        on_workflow_complete: OnOrchestrationCompleteCallback[TOutput] | None = None,
    ) -> OrchestrationResult[TOutput]:
        """
        Execute workflow with streaming callbacks.

        Args:
            input_data: Typed input data (TInput)
            on_agent_response: Callback for each agent response
            on_agent_response_stream: Callback for streaming agent responses
            on_workflow_complete: Callback when workflow completes

        Returns:
            OrchestrationResult with typed final_analysis (TOutput)
        """
        start_time = datetime.now()

        # Reset per-run tool-call streaming state.
        self._tool_call_arg_buffer.clear()
        self._tool_call_emitted.clear()
        self._tool_call_recorded.clear()
        self._tool_call_index.clear()
        self._conversation: list[ChatMessage] = []  # Track conversation during workflow

        try:
            # Ensure initialized
            if not self._initialized:
                await self.initialize()

            # Prepare task prompt
            task_prompt = input_data

            # Build GroupChat workflow
            group_chat_workflow = await self._build_groupchat()

            # Execute with streaming
            conversation: list[ChatMessage] = []

            async for event in group_chat_workflow.run_stream(task_prompt):
                # Enforce wall-clock timeout if configured.
                if self.max_seconds is not None:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if elapsed >= self.max_seconds:
                        self._request_forced_termination(
                            reason=(
                                f"Workflow timed out after {elapsed:.1f}s (max_seconds={self.max_seconds}); terminating to avoid deadlock"
                            ),
                            termination_type="hard_timeout",
                        )

                if isinstance(event, AgentRunUpdateEvent):
                    await self._handle_agent_update(
                        event,
                        stream_callback=on_agent_response_stream,
                        callback=on_agent_response,
                    )

                    # Enforce max rounds as a safety guard.
                    if self.max_rounds and len(self.agent_responses) >= self.max_rounds:
                        self._request_forced_termination(
                            reason=(
                                f"Workflow exceeded max_rounds={self.max_rounds}; terminating to avoid infinite loop"
                            ),
                            termination_type="hard_timeout",
                        )

                    if self._forced_termination_requested:
                        break

                    # If the Coordinator requested finish=true, stop immediately.
                    if self._termination_requested:
                        break
                elif isinstance(event, WorkflowOutputEvent):
                    # Complete last agent's response before finishing
                    if self._last_executor_id and self._current_agent_response:
                        await self._complete_agent_response(
                            self._last_executor_id, on_agent_response
                        )

                    # Extract final conversation from output
                    if isinstance(event.data, list):
                        conversation = event.data
                        self._conversation = conversation  # Update instance variable
                    else:
                        # Handle custom result objects with conversation attribute
                        conversation = getattr(event.data, "conversation", [])
                        self._conversation = conversation  # Update instance variable

            # Backfill tool usage from the final conversation (more reliable than streaming updates)
            # AgentRunUpdateEvent may stream text only; tool calls are represented as FunctionCallContent
            # items inside ChatMessage.contents.
            self._backfill_tool_usage_from_conversation(conversation)

            # Post-workflow analysis (optional)
            final_analysis = None
            result_format = self.result_format
            result_generator_name = self.get_result_generator_name()

            # If we were forced to stop (timeout/loop), return a hard-terminated result.
            if self._forced_termination_requested and self._forced_termination_reason:
                final_analysis = self._try_build_forced_result(
                    reason=self._forced_termination_reason,
                    termination_type=self._forced_termination_type or "hard_timeout",
                )
                # If we cannot build a typed result, we still return the conversation.
                result_format = None

            # # If coordinator terminated with a non-success instruction, return hard-terminated result directly.
            if (
                final_analysis is None
                and self._termination_requested
                and self._termination_instruction
                and self._termination_instruction.strip().lower() != "complete"
            ):
                reason = (
                    self._termination_final_message or "Workflow terminated as blocked"
                )
                final_analysis = self._try_build_forced_result(
                    reason=reason,
                    termination_type="hard_blocked",
                )
                result_format = None

            logger.info("[RESULT] Checking for result generation:")
            logger.info(f"  - result_format: {result_format}")
            logger.info(f"  - result_generator_name: {result_generator_name}")
            logger.info(f"  - Available agents: {list(self.agents.keys())}")
            logger.info(
                f"  - ResultGenerator in agents: {result_generator_name in self.agents}"
            )

            if result_format and result_generator_name in self.agents:
                logger.info(
                    f"[RESULT] Generating final result with {result_generator_name}"
                )
                # Need to generate Typed Output from conversation.
                # This is the limitation of the current GroupChat workflow model,
                # which cannot directly produce typed outputs.
                final_analysis = await self._generate_final_result(
                    conversation, result_format, result_generator_name
                )
                logger.info(
                    f"[RESULT] Final analysis generated: {type(final_analysis)}"
                )
            else:
                logger.warning(
                    f"[RESULT] Skipping result generation - result_format: {result_format}, agent exists: {result_generator_name in self.agents}"
                )

            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()

            # Build result
            result = OrchestrationResult[TOutput](
                success=True,
                conversation=conversation,
                agent_responses=self.agent_responses,
                tool_usage=self.agent_tool_usage,
                result=final_analysis,
                error=None,
                execution_time_seconds=execution_time,
            )

            # Callback for completion with Typed Result
            if on_workflow_complete:
                await on_workflow_complete(result)

            return result

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()

            error_result = OrchestrationResult[TOutput](
                success=False,
                conversation=[],
                agent_responses=self.agent_responses,
                tool_usage=self.agent_tool_usage,
                result=None,
                error=str(e),
                execution_time_seconds=execution_time,
            )

            if on_workflow_complete:
                await on_workflow_complete(error_result)

            return error_result

    async def _handle_agent_update(
        self,
        event: AgentRunUpdateEvent,
        stream_callback: AgentResponseStreamCallback | None = None,
        callback: AgentResponseCallback | None = None,
    ) -> None:
        """
        Process agent update events and invoke callback.

        Uses streaming buffer pattern:
        1. Accumulate streaming text chunks in buffer
        2. On agent switch, complete previous agent's response
        3. Trigger callback with complete response
        4. Handle tool calls separately from text streaming
        """
        agent_name = self._normalize_executor_id(event.executor_id)
        await self._start_agent_if_needed(agent_name, stream_callback, callback)
        self._append_text_chunk(event)
        await self._process_tool_calls(event, agent_name, stream_callback)

    def _normalize_executor_id(self, executor_id: str) -> str:
        """Normalize executor id to agent name.

        Example: groupchat_agent:Coordinator -> Coordinator
        """
        return executor_id.split(":")[-1]

    async def _start_agent_if_needed(
        self,
        agent_name: str,
        stream_callback: AgentResponseStreamCallback | None,
        callback: AgentResponseCallback | None,
    ) -> None:
        """Handle agent switches and emit a message-start stream event."""
        if agent_name == self._last_executor_id:
            return

        # Complete and save previous agent's response
        if self._last_executor_id and self._current_agent_response:
            await self._complete_agent_response(self._last_executor_id, callback)
            self._current_agent_response = []

        # Start new agent response
        self._last_executor_id = agent_name
        invoked_at = self._agent_invoked_at.pop(agent_name, None)
        self._current_agent_start_time = invoked_at or datetime.now()

        if stream_callback is not None:
            try:
                await stream_callback(
                    AgentResponseStream(
                        agent_id=agent_name,
                        agent_name=agent_name,
                        timestamp=datetime.now(),
                        response_type="message",
                    )
                )
            except Exception:
                logger.exception(
                    "stream_callback failed (response_type=message, agent=%s)",
                    agent_name,
                )

        logger.info(f"\n[AGENT] {agent_name}:", extra={"agent_name": agent_name})

    def _append_text_chunk(self, event: AgentRunUpdateEvent) -> None:
        """Append streamed text chunks to the current agent buffer."""
        if not hasattr(event.data, "text") or not event.data.text:
            return

        text_obj = event.data.text
        text_chunk = getattr(text_obj, "text", text_obj)
        if isinstance(text_chunk, str) and text_chunk:
            self._current_agent_response.append(text_chunk)

    async def _process_tool_calls(
        self,
        event: AgentRunUpdateEvent,
        agent_name: str,
        stream_callback: AgentResponseStreamCallback | None,
    ) -> None:
        """Process tool-call contents: buffer/parse args, record once, emit once."""
        tool_calls = self._extract_function_calls(getattr(event.data, "contents", None))
        if not tool_calls:
            return

        for tc in tool_calls:
            call_id = tc.get("call_id")
            tool_name = tc.get("name")
            args = tc.get("arguments")
            if not call_id or not tool_name:
                continue

            key = (agent_name, str(call_id))
            if key in self._tool_call_recorded:
                continue

            parsed_args, raw_args = self._parse_or_buffer_tool_args(key, args)
            if not self._args_complete(args, parsed_args):
                continue

            tool_info = {
                "tool_name": tool_name,
                "arguments": parsed_args if parsed_args is not None else raw_args,
                "call_id": call_id,
                "timestamp": datetime.now().isoformat(),
            }
            self._record_tool_call(agent_name, key, tool_info)
            await self._emit_tool_call_once(
                agent_name=agent_name,
                call_key=key,
                tool_name=tool_name,
                parsed_args=parsed_args,
                stream_callback=stream_callback,
            )

    def _parse_or_buffer_tool_args(
        self, key: tuple[str, str], args: Any
    ) -> tuple[Any | None, Any]:
        """Return (parsed_args, raw_args). For streamed string args, buffer+merge and JSON-parse."""
        if isinstance(args, dict):
            return args, args

        if isinstance(args, str) and args:
            merged = self._merge_streamed_args(
                self._tool_call_arg_buffer.get(key), args
            )
            self._tool_call_arg_buffer[key] = merged
            try:
                return json.loads(merged), merged
            except Exception:
                return None, merged

        return None, args

    def _merge_streamed_args(self, existing: str | None, incoming: str) -> str:
        """Merge streamed argument strings.

        Some SDKs send full-so-far strings, others send deltas.
        """
        if existing is None:
            return incoming
        if incoming.startswith(existing):
            return incoming
        if existing.startswith(incoming):
            return existing
        return existing + incoming

    def _args_complete(self, args: Any, parsed_args: Any | None) -> bool:
        """Determine whether tool-call arguments are complete enough to record/emit."""
        return (
            isinstance(args, dict)
            or (isinstance(args, str) and parsed_args is not None)
            or (args is None)
        )

    def _record_tool_call(
        self,
        agent_name: str,
        key: tuple[str, str],
        tool_info: dict[str, Any],
    ) -> None:
        """Record tool call in agent_tool_usage with dedupe/update-by-index."""
        tool_list = self.agent_tool_usage.setdefault(agent_name, [])
        existing_index = self._tool_call_index.get(key)
        if existing_index is None:
            tool_list.append(tool_info)
            self._tool_call_index[key] = len(tool_list) - 1
        else:
            tool_list[existing_index] = tool_info
        self._tool_call_recorded.add(key)

    async def _emit_tool_call_once(
        self,
        agent_name: str,
        call_key: tuple[str, str],
        tool_name: str,
        parsed_args: Any | None,
        stream_callback: AgentResponseStreamCallback | None,
    ) -> None:
        """Emit the tool_call stream callback at most once per (agent, call_id)."""
        if stream_callback is None or call_key in self._tool_call_emitted:
            return

        self._tool_call_emitted.add(call_key)
        try:
            await stream_callback(
                AgentResponseStream(
                    agent_id=agent_name,
                    agent_name=agent_name,
                    timestamp=datetime.now(),
                    response_type="tool_call",
                    tool_name=tool_name,
                    arguments=parsed_args if isinstance(parsed_args, dict) else None,
                )
            )
        except Exception:
            logger.exception(
                "stream_callback failed (response_type=tool_call, agent=%s, tool=%s)",
                agent_name,
                tool_name,
            )

    def _extract_function_calls(self, contents: Any) -> list[dict[str, Any]]:
        """Extract function/tool calls from agent_framework contents.

        `contents` may be None, a sequence of content objects, or raw dicts.
        We detect FunctionCallContent by the presence of `call_id` and `name`.
        """
        if not contents:
            return []

        calls: list[dict[str, Any]] = []
        for item in contents:
            # Content object path
            name = getattr(item, "name", None)
            call_id = getattr(item, "call_id", None)
            if name and call_id:
                calls.append(
                    {
                        "name": name,
                        "call_id": call_id,
                        "arguments": getattr(item, "arguments", None),
                    }
                )
                continue

            # Dict path (serialized content)
            if isinstance(item, dict) and item.get("type") in {
                "function_call",
                "tool_call",
            }:
                calls.append(
                    {
                        "name": item.get("name"),
                        "call_id": item.get("call_id"),
                        "arguments": item.get("arguments"),
                    }
                )
                continue

        return calls

    def _backfill_tool_usage_from_conversation(
        self, conversation: list[ChatMessage]
    ) -> None:
        """Populate `agent_tool_usage` from final conversation messages.

        This is a best-effort extraction that captures tool calls even when the
        streaming updates don't surface them.
        """
        for msg in conversation:
            try:
                role = getattr(msg, "role", None)
                if role != Role.ASSISTANT:
                    continue

                agent_name = getattr(msg, "author_name", None) or "assistant"
                if agent_name not in self.agent_tool_usage:
                    self.agent_tool_usage.setdefault(agent_name, [])

                contents = getattr(msg, "contents", None)
                for tc in self._extract_function_calls(contents):
                    call_id = tc.get("call_id")
                    if not call_id:
                        continue

                    key = (agent_name, str(call_id))
                    if key in self._tool_call_recorded:
                        continue

                    tool_info = {
                        "tool_name": tc.get("name"),
                        "arguments": tc.get("arguments"),
                        "call_id": call_id,
                        "timestamp": datetime.now().isoformat(),
                        "source": "conversation",
                    }
                    tool_list = self.agent_tool_usage[agent_name]
                    existing_index = self._tool_call_index.get(key)
                    if existing_index is None:
                        tool_list.append(tool_info)
                        self._tool_call_index[key] = len(tool_list) - 1
                    else:
                        tool_list[existing_index] = tool_info
                    self._tool_call_recorded.add(key)
            except Exception:
                # Best effort only; don't break orchestration
                continue

    async def _complete_agent_response(
        self,
        agent_id: str,
        callback: AgentResponseCallback | None,
    ) -> None:
        """
        Complete the current agent's response and trigger callback.

        Called when agent switches or workflow completes.
        """
        if not self._current_agent_response:
            return

        agent_name = agent_id
        complete_message = "".join(self._current_agent_response)
        completed_at = datetime.now()

        started_at = self._current_agent_start_time
        elapsed_time = (
            (completed_at - started_at).total_seconds() if started_at else None
        )

        # Get tool calls for this agent from the accumulated buffer
        tool_calls_for_agent = self.agent_tool_usage.get(agent_name, [])
        recent_tool_calls = None
        if tool_calls_for_agent:
            # Get tool calls since this agent started (approximate)
            recent_tool_calls = [
                tc
                for tc in tool_calls_for_agent
                if self._current_agent_start_time
                and datetime.fromisoformat(tc["timestamp"])
                >= self._current_agent_start_time
            ]

        # Create complete response object
        response = AgentResponse(
            agent_id=agent_id,
            agent_name=agent_name,
            message=complete_message,
            timestamp=self._current_agent_start_time or datetime.now(),
            elapsed_time=elapsed_time,
            tool_calls=recent_tool_calls if recent_tool_calls else None,
            metadata={
                "completed_at": completed_at.isoformat(),
                "is_streaming": True,
                "chunk_count": len(self._current_agent_response),
            },
        )

        self.agent_responses.append(response)

        # Mark progress on any non-Coordinator completion. This is used to ensure loop
        # detection only triggers when the Coordinator is repeating itself *and* the
        # rest of the conversation is not advancing.
        if agent_name != self.coordinator_name:
            self._progress_counter += 1

        # Detect manager termination signal (finish=true) from Coordinator.
        # NOTE: The underlying GroupChatBuilder does not automatically stop on finish,
        # so we enforce it here.
        if agent_name == self.coordinator_name:
            try:
                json_payload = self._extract_first_json_payload(complete_message)
                response_dict = json.loads(json_payload)
                manager_response = ManagerSelectionResponse.model_validate(
                    response_dict
                )
                manager_instruction = getattr(manager_response, "instruction", None)
                if isinstance(manager_instruction, str):
                    self._termination_instruction = manager_instruction

                # Record invocation time for the selected participant so their elapsed_time
                # measures from Coordinator selection -> response completion.
                selected = getattr(manager_response, "selected_participant", None)

                # Loop detection: same selection+instruction repeated.
                if (
                    isinstance(selected, str)
                    and selected
                    and selected.lower() != "none"
                ):
                    selection_key = (selected, str(manager_instruction or ""))
                    self._recent_coordinator_selections.append(selection_key)
                    if selection_key == self._last_coordinator_selection:
                        # If any other agent responded since the last identical selection,
                        # treat that as progress and reset the streak.
                        if (
                            self._progress_counter
                            != self._last_coordinator_selection_progress
                        ):
                            self._coordinator_selection_streak = 1
                            self._last_coordinator_selection_progress = (
                                self._progress_counter
                            )
                        else:
                            self._coordinator_selection_streak += 1
                    else:
                        self._last_coordinator_selection = selection_key
                        self._coordinator_selection_streak = 1
                        self._last_coordinator_selection_progress = (
                            self._progress_counter
                        )

                    # If the Coordinator repeats the exact same ask 3 times, break.
                    if self._coordinator_selection_streak >= 3:
                        self._request_forced_termination(
                            reason=(
                                f"Loop detected: Coordinator repeated the same selection to '{selected}' {self._coordinator_selection_streak} times with no progress"
                            ),
                            termination_type="hard_timeout",
                        )

                # Handle termination request
                instruction = str(manager_instruction or "").strip().lower()

                # Some prompts instruct the Coordinator/agents to avoid setting finish=true.
                # To keep the workflow robust, we also treat certain instructions as explicit
                # termination requests even when finish=false.
                selected_norm = (
                    selected.strip().lower() if isinstance(selected, str) else "none"
                )
                coordinator_signaled_stop = manager_response.finish is True or (
                    selected_norm in ("", "none")
                    and instruction in ("complete", "blocked", "fail", "failed")
                )

                if coordinator_signaled_stop:
                    # Only enforce PASS sign-offs when Coordinator claims success completion.
                    if instruction == "complete":
                        is_valid, reason = self._validate_sign_offs(self._conversation)
                        if not is_valid:
                            logger.warning(
                                "Termination rejected for success completion: %s. Workflow continues.",
                                reason,
                            )
                            # Do NOT set _termination_requested.
                            return

                    self._termination_requested = True
                    self._termination_final_message = manager_response.final_message
                    logger.info(
                        "Termination accepted (instruction=%s, finish=%s)",
                        instruction or "<empty>",
                        bool(manager_response.finish),
                    )
                elif (
                    isinstance(selected, str)
                    and selected
                    and selected.lower() != "none"
                ):
                    # Record invocation time for non-termination coordinator selections
                    self._agent_invoked_at[selected] = completed_at
            except Exception:
                # If the Coordinator didn't emit valid JSON, ignore.
                print("Coordinator response JSON parsing failed")
                pass

        # Invoke callback with complete response
        if callback:
            try:
                await callback(response)
            except Exception:
                logger.exception(
                    "on_agent_response callback failed (agent=%s)", agent_name
                )

        # # Invoke callback
        # if callback:
        #     await callback(response)

    async def _build_groupchat(self) -> Workflow:
        """Build the GroupChat Orchestrator workflow"""
        coordinator = self.agents[self.coordinator_name]
        participants = [
            agent
            for name, agent in self.agents.items()
            if name != self.coordinator_name
            and name != self.get_result_generator_name()
        ]

        return (
            GroupChatBuilder()
            .set_manager(manager=coordinator, display_name=self.coordinator_name)
            .participants(participants)
            .build()
        )

    async def _generate_final_result(
        self,
        conversation: list[ChatMessage],
        result_format: type[TOutput],
        result_generator_name: str,
    ) -> TOutput:
        """Generate structured final analysis"""
        result_generator = self.agents[result_generator_name]

        final_conversation = self._build_result_generator_conversation(
            conversation,
            exclude_authors={self.coordinator_name},
            max_messages=12,
            max_total_chars=60_000,
            max_chars_per_message=8_000,
            keep_head_chars=5_000,
            keep_tail_chars=1_500,
        )

        result = await result_generator.run(
            final_conversation,
            response_format=result_format,
        )

        text = result.messages[-1].text
        try:
            json_payload = self._extract_first_json_payload(text)
            return result_format.model_validate_json(json_payload)
        except ValidationError as e:
            # Common failure mode: model returns truncated JSON (EOF mid-string).
            # Retry once with less context to encourage a smaller, complete payload.
            preview = (
                text[:200].replace("\n", "\\n")
                if isinstance(text, str)
                else str(type(text))
            )
            logger.warning(
                "[RESULT] Invalid JSON from %s; retrying once with reduced context. preview=%s; error=%s",
                result_generator_name,
                preview,
                str(e),
            )

            retry_conversation = self._build_result_generator_conversation(
                conversation,
                exclude_authors={self.coordinator_name},
                max_messages=6,
                max_total_chars=20_000,
                max_chars_per_message=4_000,
                keep_head_chars=2_500,
                keep_tail_chars=1_000,
            )
            retry_result = await result_generator.run(
                retry_conversation,
                response_format=result_format,
            )
            retry_text = retry_result.messages[-1].text
            retry_json_payload = self._extract_first_json_payload(retry_text)
            return result_format.model_validate_json(retry_json_payload)

    @staticmethod
    def _truncate_text(
        text: str,
        *,
        max_chars: int,
        keep_head_chars: int,
        keep_tail_chars: int,
    ) -> str:
        if max_chars <= 0:
            return ""
        if not text:
            return ""
        if len(text) <= max_chars:
            return text

        # Keep both head and tail so that sign-offs (often at the end) survive.
        head = text[: max(0, min(keep_head_chars, max_chars))]
        remaining = max_chars - len(head)
        if remaining <= 0:
            return head

        tail_len = max(0, min(keep_tail_chars, remaining))
        if tail_len <= 0:
            return head

        tail = text[-tail_len:]
        omitted = len(text) - (len(head) + len(tail))
        marker = f"\n... [TRUNCATED {omitted} CHARS] ...\n"

        # Ensure marker fits within budget.
        budget = max_chars - (len(head) + len(tail))
        if budget <= 0:
            return head + tail
        if len(marker) > budget:
            marker = marker[:budget]

        return head + marker + tail

    def _build_result_generator_conversation(
        self,
        conversation: Iterable[ChatMessage],
        *,
        exclude_authors: set[str] | None,
        max_messages: int,
        max_total_chars: int,
        max_chars_per_message: int,
        keep_head_chars: int,
        keep_tail_chars: int,
    ) -> list[ChatMessage]:
        """Build a size-bounded conversation slice for the ResultGenerator.

        The raw conversation can contain extremely large tool outputs or repeated
        JSON blobs. Passing those verbatim can exceed the model context window.
        This function:
        - Walks from the end (most recent first)
        - Optionally excludes specific authors (e.g., Coordinator)
        - De-duplicates identical large messages
        - Truncates each message and enforces an overall character budget
        """
        exclude = {a.lower() for a in (exclude_authors or set())}

        selected: list[ChatMessage] = []
        seen_fingerprints: set[tuple[str | None, str, str]] = set()
        total_chars = 0

        # Traverse newest -> oldest to preserve the latest decisions/sign-offs.
        for msg in reversed(list(conversation)):
            if len(selected) >= max_messages:
                break

            author = getattr(msg, "author_name", None) or getattr(msg, "source", None)
            if author and author.lower() in exclude:
                continue

            role = getattr(msg, "role", None)

            text = getattr(msg, "text", None)
            if not text:
                # Some messages are content-object based; stringify for best-effort.
                contents = getattr(msg, "contents", None)
                text = "" if contents is None else str(contents)

            if not isinstance(text, str):
                text = str(text)

            # Cheap de-dupe: avoid feeding the same giant payload repeatedly.
            # Fingerprint uses author + first/last 200 chars.
            head_fp = text[:200]
            tail_fp = text[-200:]
            fp = (author, head_fp, tail_fp)
            if fp in seen_fingerprints:
                continue
            seen_fingerprints.add(fp)

            truncated = self._truncate_text(
                text,
                max_chars=max_chars_per_message,
                keep_head_chars=keep_head_chars,
                keep_tail_chars=keep_tail_chars,
            )

            # Enforce overall budget.
            if max_total_chars > 0 and (total_chars + len(truncated)) > max_total_chars:
                # If we have nothing yet, still include a hard-truncated message.
                remaining = max_total_chars - total_chars
                if remaining <= 0:
                    break
                truncated = self._truncate_text(
                    truncated,
                    max_chars=remaining,
                    keep_head_chars=min(keep_head_chars, max(0, remaining)),
                    keep_tail_chars=min(keep_tail_chars, max(0, remaining)),
                )

            # Preserve role + author_name so downstream can attribute sign-offs.
            selected.append(
                ChatMessage(
                    role=role,
                    text=truncated,
                    author_name=author,
                )
            )
            total_chars += len(truncated)

            if max_total_chars > 0 and total_chars >= max_total_chars:
                break

        # Selected is newest->oldest; reverse back to chronological.
        selected.reverse()
        return selected

    def get_tool_usage_summary(self) -> dict[str, Any]:
        """Get summary of tool usage across all agents"""
        total_calls = sum(len(calls) for calls in self.agent_tool_usage.values())
        tool_counts: dict[str, int] = {}

        for agent_tools in self.agent_tool_usage.values():
            for tool_call in agent_tools:
                tool_name = tool_call.get("tool_name", "unknown")
                tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        return {
            "total_tool_calls": total_calls,
            "calls_by_agent": {
                agent: len(calls) for agent, calls in self.agent_tool_usage.items()
            },
            "calls_by_tool": tool_counts,
        }
