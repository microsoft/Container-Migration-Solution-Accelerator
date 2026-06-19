# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""LLM Token Usage Tracker for comprehensive consumption monitoring.

Tracks token usage across four dimensions:
- Per agent (e.g. Chief_Architect, EKS_Expert)
- Per team/step (analysis, design, yaml, documentation)
- Per user/process
- Per model deployment

Uses the cross-accelerator ``llm_token_telemetry`` module for extraction
and emission, keeping this tracker as a thin orchestration-specific layer
that adds thread-safe aggregation and per-step tracking.
"""
from __future__ import annotations

import contextvars
import logging
import threading
from dataclasses import dataclass
from typing import Any

from utils.llm_token_telemetry import (
    TokenUsage,
    TokenUsageEmitter,
    extract_usage,
    extract_usage_from_dict,
    extract_usage_from_stream_chunk,
)

logger = logging.getLogger(__name__)

# Module-level emitter instance shared across the processor service.
_emitter = TokenUsageEmitter()


@dataclass
class TokenUsageRecord:
    """Token counts for a single LLM interaction."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class AggregatedTokenUsage:
    """Accumulated token usage with call count."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    call_count: int = 0

    def add(self, record: TokenUsageRecord) -> None:
        self.input_tokens += record.input_tokens
        self.output_tokens += record.output_tokens
        self.total_tokens += record.total_tokens
        self.call_count += 1

    def to_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "call_count": self.call_count,
        }


class TokenUsageTracker:
    """Thread-safe tracker that aggregates LLM token usage across multiple dimensions.

    Accumulates usage per agent, per step (team), per model, and overall per process.
    Emits Application Insights custom events via ``TokenUsageEmitter`` from the
    cross-accelerator ``llm_token_telemetry`` module.
    """

    def __init__(self, process_id: str, user_id: str = ""):
        self.process_id = process_id
        self.user_id = user_id
        self._lock = threading.Lock()

        # Aggregation buckets
        self._by_agent: dict[str, AggregatedTokenUsage] = {}
        self._by_step: dict[str, AggregatedTokenUsage] = {}
        self._by_model: dict[str, AggregatedTokenUsage] = {}
        self._total = AggregatedTokenUsage()

        # Agent-to-model mapping for richer telemetry
        self._agent_model_map: dict[str, str] = {}

    def set_agent_model(self, agent_name: str, model_deployment_name: str) -> None:
        """Register the model deployment used by a specific agent."""
        with self._lock:
            self._agent_model_map[agent_name] = model_deployment_name

    def record(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        agent_name: str = "",
        step_name: str = "",
        model_deployment_name: str = "",
    ) -> None:
        """Record a single LLM call's token usage.

        Accumulates into all relevant dimensions and emits per-call
        Application Insights events via ``TokenUsageEmitter``.
        """
        if total_tokens <= 0 and input_tokens <= 0 and output_tokens <= 0:
            return

        if total_tokens <= 0:
            total_tokens = input_tokens + output_tokens

        record = TokenUsageRecord(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

        # Resolve model from agent map if not provided
        if not model_deployment_name and agent_name:
            model_deployment_name = self._agent_model_map.get(agent_name, "")

        with self._lock:
            self._total.add(record)

            if agent_name:
                if agent_name not in self._by_agent:
                    self._by_agent[agent_name] = AggregatedTokenUsage()
                self._by_agent[agent_name].add(record)

            if step_name:
                if step_name not in self._by_step:
                    self._by_step[step_name] = AggregatedTokenUsage()
                self._by_step[step_name].add(record)

            if model_deployment_name:
                if model_deployment_name not in self._by_model:
                    self._by_model[model_deployment_name] = AggregatedTokenUsage()
                self._by_model[model_deployment_name].add(record)

        # Emit per-call events via the cross-accelerator emitter
        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
        _emitter.emit_all(
            agent_name=agent_name or "unknown",
            model_deployment_name=model_deployment_name or "unknown",
            usage=usage,
            process_id=self.process_id,
            user_id=self.user_id,
            step_name=step_name,
        )

        logger.info(
            "[TOKEN] Recorded: agent=%s step=%s model=%s input=%d output=%d total=%d | cumulative=%d",
            agent_name,
            step_name,
            model_deployment_name,
            input_tokens,
            output_tokens,
            total_tokens,
            self._total.total_tokens,
        )

    def get_summary(self) -> dict[str, Any]:
        """Return a snapshot of all accumulated token usage."""
        with self._lock:
            return {
                "process_id": self.process_id,
                "user_id": self.user_id,
                "total": self._total.to_dict(),
                "by_agent": {k: v.to_dict() for k, v in self._by_agent.items()},
                "by_step": {k: v.to_dict() for k, v in self._by_step.items()},
                "by_model": {k: v.to_dict() for k, v in self._by_model.items()},
            }

    def emit_summary_events(self) -> None:
        """Emit summary-level Application Insights custom events.

        Call this at the end of a process/workflow to produce aggregated events
        that are easy to query in KQL. Uses ``TokenUsageEmitter`` from
        ``llm_token_telemetry`` for all event emission.
        """
        summary = self.get_summary()

        try:
            total = summary["total"]
            total_usage = TokenUsage(
                input_tokens=total["input_tokens"],
                output_tokens=total["output_tokens"],
                total_tokens=total["total_tokens"],
            )

            # Overall summary
            _emitter.emit_summary(
                usage=total_usage,
                agent_count=len(summary["by_agent"]),
                model_count=len(summary["by_model"]),
                process_id=self.process_id,
                user_id=self.user_id,
                total_calls=str(total["call_count"]),
                step_count=str(len(summary["by_step"])),
            )

            # Per-agent events
            for agent_name, usage_dict in summary["by_agent"].items():
                model = self._agent_model_map.get(agent_name, "")
                agent_usage = TokenUsage(
                    input_tokens=usage_dict["input_tokens"],
                    output_tokens=usage_dict["output_tokens"],
                    total_tokens=usage_dict["total_tokens"],
                )
                _emitter.emit_agent(
                    agent_name=agent_name,
                    model_deployment_name=model,
                    usage=agent_usage,
                    process_id=self.process_id,
                    user_id=self.user_id,
                    call_count=str(usage_dict["call_count"]),
                )

            # Per-model events
            for model_name, usage_dict in summary["by_model"].items():
                model_usage = TokenUsage(
                    input_tokens=usage_dict["input_tokens"],
                    output_tokens=usage_dict["output_tokens"],
                    total_tokens=usage_dict["total_tokens"],
                )
                _emitter.emit_model(
                    model_deployment_name=model_name,
                    usage=model_usage,
                    process_id=self.process_id,
                    user_id=self.user_id,
                    call_count=str(usage_dict["call_count"]),
                )

            # Per-step (team) events
            for step_name, usage_dict in summary["by_step"].items():
                step_usage = TokenUsage(
                    input_tokens=usage_dict["input_tokens"],
                    output_tokens=usage_dict["output_tokens"],
                    total_tokens=usage_dict["total_tokens"],
                )
                _emitter.emit_team(
                    team_name=step_name,
                    usage=step_usage,
                    process_id=self.process_id,
                    user_id=self.user_id,
                    call_count=str(usage_dict["call_count"]),
                )

            logger.info(
                "[TOKEN] Emitted summary events: total=%d agents=%d models=%d steps=%d",
                summary["total"]["total_tokens"],
                len(summary["by_agent"]),
                len(summary["by_model"]),
                len(summary["by_step"]),
            )
        except Exception:
            logger.exception("[TOKEN] Failed to emit summary events")


def extract_usage_from_response(response: Any) -> TokenUsageRecord | None:
    """Extract token usage from an agent_framework or OpenAI SDK response object.

    Delegates to ``llm_token_telemetry.extract_usage()`` and converts the
    result to a ``TokenUsageRecord`` for backward compatibility.
    """
    usage = extract_usage(response)
    if usage is None:
        return None
    return TokenUsageRecord(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
    )


def _parse_usage_object(usage: Any) -> TokenUsageRecord | None:
    """Parse a usage object (dict or object with attrs) into a TokenUsageRecord.

    Delegates to ``llm_token_telemetry.extract_usage_from_dict()``.
    """
    result = extract_usage_from_dict(usage)
    if result is None:
        return None
    return TokenUsageRecord(
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_tokens=result.total_tokens,
    )


# ---------------------------------------------------------------------------
# Active-tracker context plumbing
#
# Token usage is reliably extracted deep inside the chat client retry wrapper
# (``azure_openai_response_retry``), which has the raw LLM response with
# ``usage_details``. That layer, however, has no reference to the per-workflow
# ``TokenUsageTracker`` (which owns process/user identity and the App Insights
# emitter). We bridge the two with a context-local + module-global reference to
# the currently active tracker, plus the current agent/step labels. The chat
# client calls :func:`record_usage_from_context` so every LLM call's tokens are
# emitted as ``LLM_*`` custom events even though the orchestrator's streaming
# events and final conversation never surface usage Content.
#
# A ContextVar is used so the value propagates to asyncio tasks created after it
# is set; a module-level global is kept as a fallback because the processor
# handles a single workflow at a time per process (TokenUsageTracker is a
# per-workflow app_context singleton).
# ---------------------------------------------------------------------------

_current_tracker_ctx: contextvars.ContextVar[TokenUsageTracker | None] = (
    contextvars.ContextVar("token_usage_current_tracker", default=None)
)
_current_agent_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "token_usage_current_agent", default=""
)
_current_step_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "token_usage_current_step", default=""
)

# Module-level fallback (single active workflow per process).
_active_tracker: TokenUsageTracker | None = None


def set_active_tracker(tracker: TokenUsageTracker | None) -> None:
    """Mark ``tracker`` as the active tracker for token emission from the chat client."""
    global _active_tracker
    _active_tracker = tracker
    try:
        _current_tracker_ctx.set(tracker)
    except Exception:  # pragma: no cover - contextvar set is effectively infallible
        pass


def clear_active_tracker() -> None:
    """Clear the active tracker reference (call when a workflow finishes)."""
    set_active_tracker(None)


def set_token_context(
    *, agent_name: str | None = None, step_name: str | None = None
) -> None:
    """Update the current agent/step labels used when recording from context."""
    if agent_name is not None:
        _current_agent_ctx.set(agent_name)
    if step_name is not None:
        _current_step_ctx.set(step_name)


def get_active_tracker() -> TokenUsageTracker | None:
    """Return the active tracker (ContextVar first, module-global fallback)."""
    tracker = _current_tracker_ctx.get()
    if tracker is not None:
        return tracker
    return _active_tracker


def record_usage_from_context(
    *,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    model_deployment_name: str = "",
    agent_name: str = "",
    step_name: str = "",
) -> bool:
    """Record a single LLM call's token usage against the active tracker.

    Resolves the tracker and agent/step labels from context when not provided.
    Returns ``True`` if a tracker was available and the usage was recorded (which
    also emits per-call ``LLM_*`` App Insights events), ``False`` otherwise.
    """
    tracker = get_active_tracker()
    if tracker is None:
        return False

    agent = agent_name or _current_agent_ctx.get("") or ""
    step = step_name or _current_step_ctx.get("") or ""
    try:
        tracker.record(
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            total_tokens=int(total_tokens),
            agent_name=agent,
            step_name=step,
            model_deployment_name=model_deployment_name,
        )
        return True
    except Exception:
        logger.exception("[TOKEN] record_usage_from_context failed")
        return False

