# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""LLM Token Usage Tracker for comprehensive consumption monitoring.

Tracks token usage across four dimensions:
- Per agent (e.g. Chief_Architect, EKS_Expert)
- Per team/step (analysis, design, yaml, documentation)
- Per user/process
- Per model deployment

Usage data is emitted to Application Insights as custom events and can be
persisted to Cosmos DB via the TelemetryManager.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from utils.event_utils import track_event_if_configured

logger = logging.getLogger(__name__)


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
    Emits Application Insights custom events for each recorded interaction and
    provides summary emission at process completion.
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

        Accumulates into all relevant dimensions and emits a per-call
        Application Insights event.
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

        # Emit per-call event to Application Insights
        try:
            track_event_if_configured(
                "LLM_Token_Usage",
                {
                    "process_id": self.process_id,
                    "user_id": self.user_id,
                    "agent_name": agent_name,
                    "step_name": step_name,
                    "model_deployment_name": model_deployment_name,
                    "input_tokens": str(input_tokens),
                    "output_tokens": str(output_tokens),
                    "total_tokens": str(total_tokens),
                },
            )
        except Exception:
            logger.debug("Failed to emit per-call token usage event", exc_info=True)

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
        that are easy to query in KQL.
        """
        summary = self.get_summary()

        try:
            # Overall summary
            track_event_if_configured(
                "LLM_Token_Usage_Summary",
                {
                    "process_id": self.process_id,
                    "user_id": self.user_id,
                    "total_input_tokens": str(summary["total"]["input_tokens"]),
                    "total_output_tokens": str(summary["total"]["output_tokens"]),
                    "total_tokens": str(summary["total"]["total_tokens"]),
                    "total_calls": str(summary["total"]["call_count"]),
                    "agent_count": str(len(summary["by_agent"])),
                    "model_count": str(len(summary["by_model"])),
                    "step_count": str(len(summary["by_step"])),
                },
            )

            # Per-agent events
            for agent_name, usage in summary["by_agent"].items():
                model = self._agent_model_map.get(agent_name, "")
                track_event_if_configured(
                    "LLM_Agent_Token_Usage",
                    {
                        "process_id": self.process_id,
                        "user_id": self.user_id,
                        "agent_name": agent_name,
                        "model_deployment_name": model,
                        "input_tokens": str(usage["input_tokens"]),
                        "output_tokens": str(usage["output_tokens"]),
                        "total_tokens": str(usage["total_tokens"]),
                        "call_count": str(usage["call_count"]),
                    },
                )

            # Per-model events
            for model_name, usage in summary["by_model"].items():
                track_event_if_configured(
                    "LLM_Model_Token_Usage",
                    {
                        "process_id": self.process_id,
                        "user_id": self.user_id,
                        "model_deployment_name": model_name,
                        "input_tokens": str(usage["input_tokens"]),
                        "output_tokens": str(usage["output_tokens"]),
                        "total_tokens": str(usage["total_tokens"]),
                        "call_count": str(usage["call_count"]),
                    },
                )

            # Per-step (team) events
            for step_name, usage in summary["by_step"].items():
                track_event_if_configured(
                    "LLM_Step_Token_Usage",
                    {
                        "process_id": self.process_id,
                        "user_id": self.user_id,
                        "step_name": step_name,
                        "input_tokens": str(usage["input_tokens"]),
                        "output_tokens": str(usage["output_tokens"]),
                        "total_tokens": str(usage["total_tokens"]),
                        "call_count": str(usage["call_count"]),
                    },
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

    Handles multiple response shapes:
    1. response.usage (OpenAI SDK ChatCompletion)
    2. response.usage_details (agent_framework Content objects)
    3. response dict with usage keys
    4. AgentResponseUpdate with contents containing usage
    """
    if response is None:
        return None

    # 1. Direct .usage attribute (OpenAI ChatCompletion, Responses API)
    usage = getattr(response, "usage", None)
    if usage is not None:
        record = _parse_usage_object(usage)
        if record:
            return record

    # 2. .usage_details or .details attribute
    usage_details = getattr(response, "details", None) or getattr(response, "usage_details", None)
    if usage_details is not None:
        record = _parse_usage_object(usage_details)
        if record:
            return record

    # 3. raw_representation with usage
    raw = getattr(response, "raw_representation", None)
    if raw is not None:
        raw_usage = getattr(raw, "usage", None)
        if raw_usage is not None:
            record = _parse_usage_object(raw_usage)
            if record:
                return record
        if isinstance(raw, dict) and "usage" in raw:
            record = _parse_usage_object(raw["usage"])
            if record:
                return record

    # 4. contents list with usage items (AgentResponseUpdate)
    contents = getattr(response, "contents", None)
    if contents:
        for item in contents:
            # Try usage-typed content items first, then any item with details
            ud = None
            if getattr(item, "type", None) == "usage":
                ud = getattr(item, "details", None) or getattr(item, "usage_details", None)
            if ud is None:
                ud = getattr(item, "details", None) or getattr(item, "usage_details", None)
            if ud is not None:
                record = _parse_usage_object(ud)
                if record:
                    return record
            # Dict content item
            if isinstance(item, dict):
                for key in ("details", "usage_details"):
                    if key in item:
                        record = _parse_usage_object(item[key])
                        if record:
                            return record
                if "input_token_count" in item or "total_token_count" in item:
                    record = _parse_usage_object(item)
                    if record:
                        return record

    # 5. additional_properties
    addl = getattr(response, "additional_properties", None)
    if isinstance(addl, dict) and "usage" in addl:
        record = _parse_usage_object(addl["usage"])
        if record:
            return record

    # 6. Dict response
    if isinstance(response, dict):
        if "usage" in response:
            record = _parse_usage_object(response["usage"])
            if record:
                return record
        record = _parse_usage_object(response)
        if record:
            return record

    return None


def _get_field(obj: Any, *names: str) -> int:
    """Read the first non-zero value from *obj* for the given field names.

    Works uniformly for dicts (via ``get``) and objects (via ``getattr``).
    """
    getter = obj.get if isinstance(obj, dict) else lambda k, d=0: getattr(obj, k, d)
    for name in names:
        val = getter(name, 0)
        if val:
            return int(val)
    return 0


def _parse_usage_object(usage: Any) -> TokenUsageRecord | None:
    """Parse a usage object (dict or object with attrs) into a TokenUsageRecord."""
    if usage is None:
        return None

    inp = _get_field(usage, "input_token_count", "prompt_tokens", "input_tokens")
    out = _get_field(usage, "output_token_count", "completion_tokens", "output_tokens")
    tot = _get_field(usage, "total_token_count", "total_tokens") or (inp + out)

    if tot > 0 or inp > 0 or out > 0:
        return TokenUsageRecord(
            input_tokens=inp,
            output_tokens=out,
            total_tokens=tot if tot > 0 else inp + out,
        )
    return None
