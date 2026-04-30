# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Tests for libs.base.orchestrator_base.OrchestratorBase."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from libs.base import orchestrator_base as ob_module
from libs.base.orchestrator_base import OrchestratorBase


def _run(coro):
    return asyncio.run(coro)


class _FakeAgentInfo:
    def __init__(self, name, instruction="i", tools=None):
        self.agent_name = name
        self.agent_instruction = instruction
        self.tools = tools


class _FakeOrchestrator(OrchestratorBase):
    """Concrete subclass for testing."""

    def __init__(self, app_context, agentinfos=None, mcp_tools=None):
        super().__init__(app_context=app_context)
        self._agentinfos = agentinfos or []
        self._mcp_tools = mcp_tools or {}

    async def execute(self, task_param=None):  # pragma: no cover
        return None

    async def prepare_mcp_tools(self):
        return self._mcp_tools

    async def prepare_agent_infos(self):
        return self._agentinfos


def _make_app_context(register_memory=False, helper=None):
    app_context = MagicMock()
    helper = helper or MagicMock()
    # AgentBase.__init__ requires AgentFrameworkHelper to be registered.
    app_context.is_registered.side_effect = (
        lambda cls: True if "AgentFrameworkHelper" in str(cls) else False
    )
    if register_memory:
        # Both AgentFrameworkHelper and QdrantMemoryStore should be "registered"
        app_context.is_registered.side_effect = lambda cls: True
    app_context.get_service.return_value = helper
    return app_context, helper


def test_constructor_initializes_defaults():
    app_context, _ = _make_app_context()
    orch = _FakeOrchestrator(app_context=app_context)
    assert orch.initialized is False
    assert orch.memory_store is None
    assert orch.step_name == ""


def test_is_console_summarization_enabled_default_false():
    app_context, _ = _make_app_context()
    orch = _FakeOrchestrator(app_context=app_context)
    assert orch.is_console_summarization_enabled() is False


def test_initialize_resolves_memory_store_when_registered():
    app_context, helper = _make_app_context()
    fake_memory = MagicMock()
    fake_memory._initialized = True
    app_context.is_registered.side_effect = lambda cls: True
    app_context.get_service.side_effect = lambda cls: (
        fake_memory if "QdrantMemoryStore" in str(cls) else helper
    )

    orch = _FakeOrchestrator(
        app_context=app_context, agentinfos=[_FakeAgentInfo("A")]
    )
    with patch.object(orch, "create_agents", new=AsyncMock(return_value={"A": MagicMock()})):
        _run(orch.initialize("p1"))
    assert orch.initialized is True
    assert orch.memory_store is fake_memory


def test_initialize_swallows_get_service_errors():
    app_context, helper = _make_app_context()
    app_context.is_registered.side_effect = lambda cls: True
    app_context.get_service.side_effect = lambda cls: (
        (_ for _ in ()).throw(RuntimeError("nope"))
        if "QdrantMemoryStore" in str(cls)
        else helper
    )
    orch = _FakeOrchestrator(app_context=app_context)
    with patch.object(orch, "create_agents", new=AsyncMock(return_value={})):
        _run(orch.initialize("p1"))
    assert orch.memory_store is None


def test_flush_agent_memories_calls_flush_on_each_provider():
    app_context, _ = _make_app_context()
    orch = _FakeOrchestrator(app_context=app_context)

    flush_a = AsyncMock()
    flush_b = AsyncMock()
    provider_a = SimpleNamespace(flush=flush_a)
    provider_b = SimpleNamespace(flush=flush_b)

    agg = SimpleNamespace(providers=[provider_a, provider_b])
    agent = SimpleNamespace(context_provider=agg)
    orch.agents = {"A": agent}
    _run(orch.flush_agent_memories())
    flush_a.assert_awaited_once()
    flush_b.assert_awaited_once()


def test_flush_agent_memories_handles_missing_providers():
    app_context, _ = _make_app_context()
    orch = _FakeOrchestrator(app_context=app_context)
    orch.agents = {
        "no_ctx": SimpleNamespace(),
        "no_inner": SimpleNamespace(context_provider=SimpleNamespace(providers=None)),
    }
    # Should not raise.
    _run(orch.flush_agent_memories())


def test_flush_agent_memories_swallows_flush_errors():
    app_context, _ = _make_app_context()
    orch = _FakeOrchestrator(app_context=app_context)
    bad_flush = AsyncMock(side_effect=RuntimeError("flush boom"))
    agg = SimpleNamespace(providers=[SimpleNamespace(flush=bad_flush)])
    orch.agents = {"A": SimpleNamespace(context_provider=agg)}
    _run(orch.flush_agent_memories())  # should swallow
    bad_flush.assert_awaited_once()


def test_load_platform_registry_returns_experts(tmp_path):
    app_context, _ = _make_app_context()
    orch = _FakeOrchestrator(app_context=app_context)
    p = tmp_path / "reg.json"
    p.write_text(json.dumps({"experts": [{"a": 1}, {"a": 2}]}))
    out = orch.load_platform_registry(str(p))
    assert out == [{"a": 1}, {"a": 2}]


def test_load_platform_registry_missing_experts(tmp_path):
    app_context, _ = _make_app_context()
    orch = _FakeOrchestrator(app_context=app_context)
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"other": "x"}))
    with pytest.raises(ValueError):
        orch.load_platform_registry(str(p))


def test_read_prompt_file_returns_contents(tmp_path):
    app_context, _ = _make_app_context()
    orch = _FakeOrchestrator(app_context=app_context)
    p = tmp_path / "prompt.txt"
    p.write_text("Hello world")
    assert orch.read_prompt_file(str(p)) == "Hello world"


def test_get_client_uses_cache_when_thread_id_in_cache():
    app_context, _ = _make_app_context()
    orch = _FakeOrchestrator(app_context=app_context)
    cached_client = MagicMock()
    OrchestratorBase._client_cache.clear()
    OrchestratorBase._client_cache["t1"] = cached_client
    out = _run(orch.get_client(thread_id="t1"))
    assert out is cached_client


def test_get_client_creates_and_caches_when_missing():
    app_context, helper = _make_app_context()
    helper.settings.get_service_config.return_value = SimpleNamespace(
        endpoint="https://e",
        chat_deployment_name="chat",
        api_version="2024",
    )
    helper.create_client.return_value = MagicMock(name="client")
    orch = _FakeOrchestrator(app_context=app_context)
    OrchestratorBase._client_cache.clear()
    out = _run(orch.get_client(thread_id="t-new"))
    assert out is helper.create_client.return_value
    assert OrchestratorBase._client_cache["t-new"] is out


def test_create_agents_builds_agents_for_each_info():
    app_context, helper = _make_app_context()
    orch = _FakeOrchestrator(app_context=app_context)
    orch.memory_store = None
    fake_client = MagicMock(name="client")
    with patch.object(
        orch, "get_client", new=AsyncMock(return_value=fake_client)
    ):
        # AgentBuilder is heavily chained; we use a stand-in.
        class _Builder:
            def __init__(self, _client):
                self._client = _client

            def with_name(self, n): self.name = n; return self
            def with_instructions(self, i): self.instr = i; return self
            def with_tools(self, t): return self
            def with_temperature(self, t): return self
            def with_max_tokens(self, n): return self
            def with_response_format(self, fmt): return self
            def with_tool_choice(self, c): return self
            def with_context_providers(self, *p): return self
            def build(self): return SimpleNamespace(name=self.name)

        with patch.object(ob_module, "AgentBuilder", _Builder):
            orch._agentinfos = [
                _FakeAgentInfo("Coordinator", tools=MagicMock()),
                _FakeAgentInfo("ResultGenerator", tools=MagicMock()),
                _FakeAgentInfo("Expert", tools=MagicMock()),
                _FakeAgentInfo("NoTools", tools=None),
            ]
            agents = _run(orch.create_agents(orch._agentinfos, process_id="p1"))
    assert set(agents) == {"Coordinator", "ResultGenerator", "Expert", "NoTools"}


def test_create_agents_attaches_memory_provider_for_expert_only():
    app_context, helper = _make_app_context()
    orch = _FakeOrchestrator(app_context=app_context)
    orch.memory_store = MagicMock()
    orch.step_name = "design"

    fake_client = MagicMock()
    contexts_seen = []

    class _Builder:
        def __init__(self, _c): pass
        def with_name(self, n): self.name = n; return self
        def with_instructions(self, i): return self
        def with_tools(self, t): return self
        def with_temperature(self, t): return self
        def with_max_tokens(self, n): return self
        def with_response_format(self, fmt): return self
        def with_tool_choice(self, c): return self
        def with_context_providers(self, *p):
            contexts_seen.append(self.name)
            return self
        def build(self): return SimpleNamespace(name=self.name)

    with (
        patch.object(orch, "get_client", new=AsyncMock(return_value=fake_client)),
        patch.object(ob_module, "AgentBuilder", _Builder),
        patch.object(ob_module, "SharedMemoryContextProvider", MagicMock()),
    ):
        orch._agentinfos = [
            _FakeAgentInfo("Coordinator", tools=MagicMock()),
            _FakeAgentInfo("Expert", tools=MagicMock()),
        ]
        _run(orch.create_agents(orch._agentinfos, process_id="p"))
    assert contexts_seen == ["Expert"]


def test_get_summarizer_uses_cache():
    app_context, _ = _make_app_context()
    orch = _FakeOrchestrator(app_context=app_context)
    cached = MagicMock()
    OrchestratorBase._client_cache["summarizer"] = cached

    class _Builder:
        def __init__(self, _c): pass
        def with_name(self, n): return self
        def with_instructions(self, i): return self
        def build(self): return "agent"

    with patch.object(ob_module, "AgentBuilder", _Builder):
        out = _run(orch.get_summarizer())
    assert out == "agent"


def test_get_summarizer_creates_when_no_cache():
    app_context, helper = _make_app_context()
    helper.get_client_async = AsyncMock(return_value=MagicMock())
    orch = _FakeOrchestrator(app_context=app_context)
    OrchestratorBase._client_cache.pop("summarizer", None)

    class _Builder:
        def __init__(self, _c): pass
        def with_name(self, n): return self
        def with_instructions(self, i): return self
        def build(self): return "agent"

    with patch.object(ob_module, "AgentBuilder", _Builder):
        out = _run(orch.get_summarizer())
    assert out == "agent"
    assert "summarizer" in OrchestratorBase._client_cache


def test_on_agent_response_handles_coordinator_with_phase_match():
    app_context, _ = _make_app_context()
    telemetry = MagicMock()
    telemetry.update_phase = AsyncMock()
    telemetry.update_agent_activity = AsyncMock()
    app_context.get_service_async = AsyncMock(return_value=telemetry)

    orch = _FakeOrchestrator(app_context=app_context)
    orch.task_param = SimpleNamespace(process_id="p1")

    coord_payload = {
        "selected_participant": "Expert",
        "instruction": "Phase 6 : Re-Check - look",
        "finish": False,
    }

    fake_resp_obj = SimpleNamespace(
        instruction="Phase 6 : Re-Check - look",
        finish=False,
        selected_participant="Expert",
    )
    with patch.object(
        ob_module, "ManagerSelectionResponse",
        SimpleNamespace(model_validate=lambda d: fake_resp_obj),
    ):
        response = SimpleNamespace(
            timestamp="t",
            agent_name="Coordinator",
            message=json.dumps(coord_payload),
            elapsed_time=1.5,
        )
        _run(orch.on_agent_response(response))
    telemetry.update_phase.assert_awaited_once()
    telemetry.update_agent_activity.assert_awaited_once()


def test_on_agent_response_coordinator_with_finish_true_skips_speaking():
    app_context, _ = _make_app_context()
    telemetry = MagicMock()
    telemetry.update_phase = AsyncMock()
    telemetry.update_agent_activity = AsyncMock()
    app_context.get_service_async = AsyncMock(return_value=telemetry)

    orch = _FakeOrchestrator(app_context=app_context)
    orch.task_param = SimpleNamespace(process_id="p1")

    fake_resp_obj = SimpleNamespace(
        instruction="no phase here", finish=True, selected_participant="None"
    )
    with patch.object(
        ob_module, "ManagerSelectionResponse",
        SimpleNamespace(model_validate=lambda d: fake_resp_obj),
    ):
        response = SimpleNamespace(
            timestamp="t",
            agent_name="Coordinator",
            message="{}",
            elapsed_time=1.0,
        )
        _run(orch.on_agent_response(response))
    telemetry.update_agent_activity.assert_not_awaited()


def test_on_agent_response_coordinator_invalid_json_swallowed():
    app_context, _ = _make_app_context()
    telemetry = MagicMock()
    app_context.get_service_async = AsyncMock(return_value=telemetry)

    orch = _FakeOrchestrator(app_context=app_context)
    orch.task_param = SimpleNamespace(process_id="p1")

    response = SimpleNamespace(
        timestamp="t", agent_name="Coordinator", message="not json", elapsed_time=1.0
    )
    _run(orch.on_agent_response(response))  # must not raise


def test_on_agent_response_result_generator_branch():
    app_context, _ = _make_app_context()
    telemetry = MagicMock()
    app_context.get_service_async = AsyncMock(return_value=telemetry)

    orch = _FakeOrchestrator(app_context=app_context)
    orch.task_param = SimpleNamespace(process_id="p1")
    response = SimpleNamespace(
        timestamp="t", agent_name="ResultGenerator", message="m", elapsed_time=1.0
    )
    _run(orch.on_agent_response(response))


def test_on_agent_response_other_agent_logs_and_updates_telemetry():
    app_context, _ = _make_app_context()
    telemetry = MagicMock()
    telemetry.update_agent_activity = AsyncMock()
    app_context.get_service_async = AsyncMock(return_value=telemetry)

    orch = _FakeOrchestrator(app_context=app_context)
    orch.task_param = SimpleNamespace(process_id="p1")
    response = SimpleNamespace(
        timestamp="t", agent_name="Expert", message="hi", elapsed_time=2.0
    )
    _run(orch.on_agent_response(response))
    telemetry.update_agent_activity.assert_awaited_once()


def test_on_agent_response_with_summarization_enabled_coordinator():
    app_context, _ = _make_app_context()
    telemetry = MagicMock()
    telemetry.update_phase = AsyncMock()
    telemetry.update_agent_activity = AsyncMock()
    app_context.get_service_async = AsyncMock(return_value=telemetry)

    orch = _FakeOrchestrator(app_context=app_context)
    orch.task_param = SimpleNamespace(process_id="p1")
    orch.is_console_summarization_enabled = lambda: True

    fake_summary = SimpleNamespace(text="summary")
    summarizer = SimpleNamespace(run=AsyncMock(return_value=fake_summary))

    fake_resp_obj = SimpleNamespace(
        instruction="Phase 1 : Init - go", finish=False, selected_participant="Expert"
    )
    with (
        patch.object(
            ob_module, "ManagerSelectionResponse",
            SimpleNamespace(model_validate=lambda d: fake_resp_obj),
        ),
        patch.object(orch, "get_summarizer", new=AsyncMock(return_value=summarizer)),
    ):
        response = SimpleNamespace(
            timestamp="t", agent_name="Coordinator", message="{}", elapsed_time=1.0
        )
        _run(orch.on_agent_response(response))
    telemetry.update_agent_activity.assert_awaited_once()


def test_on_agent_response_with_summarization_coordinator_summarizer_failure():
    app_context, _ = _make_app_context()
    telemetry = MagicMock()
    telemetry.update_phase = AsyncMock()
    telemetry.update_agent_activity = AsyncMock()
    app_context.get_service_async = AsyncMock(return_value=telemetry)

    orch = _FakeOrchestrator(app_context=app_context)
    orch.task_param = SimpleNamespace(process_id="p1")
    orch.is_console_summarization_enabled = lambda: True

    fake_resp_obj = SimpleNamespace(
        instruction="no phase", finish=False, selected_participant="Expert"
    )
    with (
        patch.object(
            ob_module, "ManagerSelectionResponse",
            SimpleNamespace(model_validate=lambda d: fake_resp_obj),
        ),
        patch.object(
            orch, "get_summarizer",
            new=AsyncMock(side_effect=RuntimeError("nope")),
        ),
    ):
        response = SimpleNamespace(
            timestamp="t", agent_name="Coordinator", message="{}", elapsed_time=1.0
        )
        _run(orch.on_agent_response(response))


def test_on_agent_response_with_summarization_other_agent():
    app_context, _ = _make_app_context()
    telemetry = MagicMock()
    telemetry.update_agent_activity = AsyncMock()
    app_context.get_service_async = AsyncMock(return_value=telemetry)

    orch = _FakeOrchestrator(app_context=app_context)
    orch.task_param = SimpleNamespace(process_id="p1")
    orch.is_console_summarization_enabled = lambda: True

    fake_summary = SimpleNamespace(text="summary")
    summarizer = SimpleNamespace(run=AsyncMock(return_value=fake_summary))
    with patch.object(
        orch, "get_summarizer", new=AsyncMock(return_value=summarizer)
    ):
        response = SimpleNamespace(
            timestamp="t", agent_name="Expert", message="m", elapsed_time=1.0
        )
        _run(orch.on_agent_response(response))
    telemetry.update_agent_activity.assert_awaited_once()


def test_on_agent_response_with_summarization_other_agent_failure():
    app_context, _ = _make_app_context()
    telemetry = MagicMock()
    app_context.get_service_async = AsyncMock(return_value=telemetry)

    orch = _FakeOrchestrator(app_context=app_context)
    orch.task_param = SimpleNamespace(process_id="p1")
    orch.is_console_summarization_enabled = lambda: True

    with patch.object(
        orch, "get_summarizer",
        new=AsyncMock(side_effect=RuntimeError("nope")),
    ):
        response = SimpleNamespace(
            timestamp="t", agent_name="Expert", message="m", elapsed_time=1.0
        )
        _run(orch.on_agent_response(response))


def test_on_agent_response_stream_message_type():
    app_context, _ = _make_app_context()
    telemetry = MagicMock()
    telemetry.update_agent_activity = AsyncMock()
    app_context.get_service_async = AsyncMock(return_value=telemetry)

    orch = _FakeOrchestrator(app_context=app_context)
    orch.task_param = SimpleNamespace(process_id="p1")
    response = SimpleNamespace(response_type="message", agent_name="Expert")
    _run(orch.on_agent_response_stream(response))
    telemetry.update_agent_activity.assert_awaited_once()


def test_on_agent_response_stream_tool_call_with_args():
    app_context, _ = _make_app_context()
    telemetry = MagicMock()
    telemetry.update_agent_activity = AsyncMock()
    app_context.get_service_async = AsyncMock(return_value=telemetry)

    orch = _FakeOrchestrator(app_context=app_context)
    orch.task_param = SimpleNamespace(process_id="p1")
    response = SimpleNamespace(
        response_type="tool_call",
        agent_name="Expert",
        tool_name="search",
        arguments={"q": "x" * 100},
    )
    _run(orch.on_agent_response_stream(response))
    telemetry.update_agent_activity.assert_awaited_once()


def test_on_agent_response_stream_tool_call_no_args_no_tool_name():
    app_context, _ = _make_app_context()
    telemetry = MagicMock()
    telemetry.update_agent_activity = AsyncMock()
    app_context.get_service_async = AsyncMock(return_value=telemetry)

    orch = _FakeOrchestrator(app_context=app_context)
    orch.task_param = SimpleNamespace(process_id="p1")
    response = SimpleNamespace(
        response_type="tool_call",
        agent_name="Expert",
        tool_name=None,
        arguments=None,
    )
    _run(orch.on_agent_response_stream(response))


def test_on_agent_response_stream_tool_call_with_unserializable_args():
    app_context, _ = _make_app_context()
    telemetry = MagicMock()
    telemetry.update_agent_activity = AsyncMock()
    app_context.get_service_async = AsyncMock(return_value=telemetry)

    orch = _FakeOrchestrator(app_context=app_context)
    orch.task_param = SimpleNamespace(process_id="p1")

    class _NotJsonable:
        def __repr__(self):
            return "raw"

    response = SimpleNamespace(
        response_type="tool_call",
        agent_name="Expert",
        tool_name="search",
        arguments=_NotJsonable(),
    )
    _run(orch.on_agent_response_stream(response))


def test_on_agent_response_stream_unknown_type_no_op():
    app_context, _ = _make_app_context()
    telemetry = MagicMock()
    app_context.get_service_async = AsyncMock(return_value=telemetry)
    orch = _FakeOrchestrator(app_context=app_context)
    orch.task_param = SimpleNamespace(process_id="p1")
    response = SimpleNamespace(response_type="other", agent_name="x")
    _run(orch.on_agent_response_stream(response))
