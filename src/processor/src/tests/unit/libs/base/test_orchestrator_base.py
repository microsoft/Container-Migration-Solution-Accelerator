# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from libs.base.orchestrator_base import OrchestratorBase


def _run(coro):
    return asyncio.run(coro)


class _ConcreteOrchestrator(OrchestratorBase):
    async def execute(self, task_param=None):
        return None

    async def prepare_mcp_tools(self):
        return None

    async def prepare_agent_infos(self):
        return []


def _make_orchestrator(memory_store=None, framework_helper=None):
    """Build an OrchestratorBase via __new__ — sidestep ABC + Azure SDK init."""
    obj = _ConcreteOrchestrator.__new__(_ConcreteOrchestrator)
    obj.initialized = False
    obj.memory_store = memory_store
    obj.step_name = "test_step"
    obj.app_context = MagicMock()
    obj.agent_framework_helper = framework_helper or MagicMock()
    obj._client_cache = {}
    obj.task_param = SimpleNamespace(process_id="proc-1")
    return obj


class TestSimpleHelpers:
    def test_console_summarization_disabled_by_default(self):
        o = _make_orchestrator()
        assert o.is_console_summarization_enabled() is False

    def test_read_prompt_file(self, tmp_path):
        p = tmp_path / "prompt.txt"
        p.write_text("hello world", encoding="utf-8")
        o = _make_orchestrator()
        assert o.read_prompt_file(str(p)) == "hello world"

    def test_load_platform_registry_valid(self, tmp_path):
        p = tmp_path / "reg.json"
        p.write_text(json.dumps({"experts": [{"name": "a"}, {"name": "b"}]}), encoding="utf-8")
        o = _make_orchestrator()
        result = o.load_platform_registry(str(p))
        assert len(result) == 2

    def test_load_platform_registry_missing_experts(self, tmp_path):
        p = tmp_path / "reg.json"
        p.write_text(json.dumps({"other": "data"}), encoding="utf-8")
        o = _make_orchestrator()
        with pytest.raises(ValueError, match="Invalid platform registry"):
            o.load_platform_registry(str(p))

    def test_load_platform_registry_experts_not_list(self, tmp_path):
        p = tmp_path / "reg.json"
        p.write_text(json.dumps({"experts": "nope"}), encoding="utf-8")
        o = _make_orchestrator()
        with pytest.raises(ValueError):
            o.load_platform_registry(str(p))


class TestFlushAgentMemories:
    def test_flush_with_no_agents(self):
        o = _make_orchestrator()
        o.agents = {}
        _run(o.flush_agent_memories())  # no error

    def test_flush_skips_agent_without_provider(self):
        o = _make_orchestrator()
        agent = MagicMock(spec=[])  # no context_provider attribute
        o.agents = {"a": agent}
        _run(o.flush_agent_memories())

    def test_flush_skips_provider_with_no_inner(self):
        o = _make_orchestrator()
        agent = MagicMock()
        agent.context_provider = MagicMock()
        agent.context_provider.providers = None
        o.agents = {"a": agent}
        _run(o.flush_agent_memories())

    def test_flush_calls_inner_provider_flush(self):
        o = _make_orchestrator()
        flush_mock = AsyncMock()
        provider = MagicMock()
        provider.flush = flush_mock
        agent = MagicMock()
        agent.context_provider = MagicMock()
        agent.context_provider.providers = [provider]
        o.agents = {"a": agent}
        _run(o.flush_agent_memories())
        flush_mock.assert_awaited_once()

    def test_flush_swallows_provider_errors(self):
        o = _make_orchestrator()
        provider = MagicMock()
        provider.flush = AsyncMock(side_effect=RuntimeError("boom"))
        agent = MagicMock()
        agent.context_provider = MagicMock()
        agent.context_provider.providers = [provider]
        o.agents = {"a": agent}
        _run(o.flush_agent_memories())  # no raise


class TestGetClient:
    def test_get_client_cache_hit(self):
        o = _make_orchestrator()
        o._client_cache["proc-1"] = "cached"
        result = _run(o.get_client(thread_id="proc-1"))
        assert result == "cached"

    def test_get_client_cache_miss_creates_and_caches(self):
        helper = MagicMock()
        helper.create_client = MagicMock(return_value="new_client")
        cfg = MagicMock(endpoint="https://x", chat_deployment_name="gpt-4", api_version="v1")
        helper.settings.get_service_config.return_value = cfg
        o = _make_orchestrator(framework_helper=helper)
        result = _run(o.get_client(thread_id="proc-9"))
        assert result == "new_client"
        assert o._client_cache["proc-9"] == "new_client"


class TestGetSummarizer:
    def test_summarizer_uses_cached_client(self):
        helper = MagicMock()
        o = _make_orchestrator(framework_helper=helper)
        o._client_cache["summarizer"] = "cached_chat_client"
        with patch("libs.base.orchestrator_base.AgentBuilder") as mock_builder_cls:
            built = MagicMock()
            built.with_name.return_value = built
            built.with_instructions.return_value = built
            built.build.return_value = "summarizer_agent"
            mock_builder_cls.return_value = built
            result = _run(o.get_summarizer())
        assert result == "summarizer_agent"
        mock_builder_cls.assert_called_once_with("cached_chat_client")

    def test_summarizer_fetches_async_when_not_cached(self):
        helper = MagicMock()
        helper.get_client_async = AsyncMock(return_value="fresh_client")
        o = _make_orchestrator(framework_helper=helper)
        with patch("libs.base.orchestrator_base.AgentBuilder") as mock_builder_cls:
            built = MagicMock()
            built.with_name.return_value = built
            built.with_instructions.return_value = built
            built.build.return_value = "summarizer_agent"
            mock_builder_cls.return_value = built
            _run(o.get_summarizer())
        assert o._client_cache["summarizer"] == "fresh_client"


class TestOnAgentResponse:
    def _make_response(self, agent_name, message, elapsed=1.5):
        return SimpleNamespace(
            agent_name=agent_name,
            message=message,
            elapsed_time=elapsed,
            timestamp="2024-01-01",
        )

    def test_result_generator_logs_only(self, caplog):
        o = _make_orchestrator()
        telemetry = MagicMock()
        telemetry.update_agent_activity = AsyncMock()
        o.app_context.get_service_async = AsyncMock(return_value=telemetry)
        with caplog.at_level(logging.INFO):
            _run(o.on_agent_response(self._make_response("ResultGenerator", "x")))

    def test_other_agent_uses_format_path(self):
        o = _make_orchestrator()
        telemetry = MagicMock()
        telemetry.update_agent_activity = AsyncMock()
        o.app_context.get_service_async = AsyncMock(return_value=telemetry)
        _run(o.on_agent_response(self._make_response("Expert", "hello")))
        telemetry.update_agent_activity.assert_awaited_once()
        kwargs = telemetry.update_agent_activity.await_args.kwargs
        assert kwargs["action"] == "responded"
        assert kwargs["agent_name"] == "Expert"

    def test_coordinator_with_valid_payload(self):
        o = _make_orchestrator()
        telemetry = MagicMock()
        telemetry.update_phase = AsyncMock()
        telemetry.update_agent_activity = AsyncMock()
        o.app_context.get_service_async = AsyncMock(return_value=telemetry)
        payload = json.dumps({
            "selected_participant": "Architect",
            "instruction": "Phase 6 : Re-Check - verify outputs",
            "finish": False,
        })
        _run(o.on_agent_response(self._make_response("Coordinator", payload)))
        telemetry.update_phase.assert_awaited_once()
        telemetry.update_agent_activity.assert_awaited_once()

    def test_coordinator_with_invalid_payload_swallowed(self):
        o = _make_orchestrator()
        telemetry = MagicMock()
        telemetry.update_phase = AsyncMock()
        telemetry.update_agent_activity = AsyncMock()
        o.app_context.get_service_async = AsyncMock(return_value=telemetry)
        # Bad JSON triggers the broad except path
        _run(o.on_agent_response(self._make_response("Coordinator", "not json {{")))
        telemetry.update_phase.assert_not_awaited()


class TestOnAgentResponseStream:
    def test_stream_message_event(self):
        o = _make_orchestrator()
        telemetry = MagicMock()
        telemetry.update_agent_activity = AsyncMock()
        o.app_context.get_service_async = AsyncMock(return_value=telemetry)
        resp = SimpleNamespace(
            response_type="message", agent_name="Expert", tool_name=None, arguments=None
        )
        _run(o.on_agent_response_stream(resp))
        kwargs = telemetry.update_agent_activity.await_args.kwargs
        assert kwargs["action"] == "thinking"

    def test_stream_tool_call_event_with_args(self):
        o = _make_orchestrator()
        telemetry = MagicMock()
        telemetry.update_agent_activity = AsyncMock()
        o.app_context.get_service_async = AsyncMock(return_value=telemetry)
        resp = SimpleNamespace(
            response_type="tool_call",
            agent_name="Expert",
            tool_name="search",
            arguments={"q": "hello"},
        )
        _run(o.on_agent_response_stream(resp))
        kwargs = telemetry.update_agent_activity.await_args.kwargs
        assert kwargs["action"] == "analyzing"
        assert "search" in kwargs["tool_name"]
        assert kwargs["tool_used"] is True

    def test_stream_tool_call_event_without_args(self):
        o = _make_orchestrator()
        telemetry = MagicMock()
        telemetry.update_agent_activity = AsyncMock()
        o.app_context.get_service_async = AsyncMock(return_value=telemetry)
        resp = SimpleNamespace(
            response_type="tool_call",
            agent_name="Expert",
            tool_name=None,
            arguments=None,
        )
        _run(o.on_agent_response_stream(resp))
        telemetry.update_agent_activity.assert_awaited_once()

    def test_stream_tool_call_with_long_args_truncates(self):
        o = _make_orchestrator()
        telemetry = MagicMock()
        telemetry.update_agent_activity = AsyncMock()
        o.app_context.get_service_async = AsyncMock(return_value=telemetry)
        resp = SimpleNamespace(
            response_type="tool_call",
            agent_name="Expert",
            tool_name="search",
            arguments={"q": "x" * 200},
        )
        _run(o.on_agent_response_stream(resp))
        kwargs = telemetry.update_agent_activity.await_args.kwargs
        assert "..." in kwargs["tool_name"]
