# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Coverage tests for the four step orchestrators (analysis, design,
documentation, yaml_convert).

These tests focus on `prepare_mcp_tools`, `prepare_agent_infos`,
`on_orchestration_complete`, and trivial constructor behavior. Heavy
`execute()` coverage is left to the existing executor/integration tests.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def _run(coro):
    return asyncio.run(coro)


def _bypass_init(orch_cls):
    """Build an orchestrator instance that skips the AgentBase ctor checks."""
    orch = orch_cls.__new__(orch_cls)
    orch.app_context = MagicMock()
    orch.agent_framework_helper = MagicMock()
    orch.initialized = False
    orch.memory_store = None
    orch.step_name = ""
    orch.task_param = None
    return orch


# ============== AnalysisOrchestrator ==============

def test_analysis_on_orchestration_complete_logs(capsys):
    from steps.analysis.orchestration import analysis_orchestrator as ao
    orch = _bypass_init(ao.AnalysisOrchestrator)
    result = SimpleNamespace(execution_time_seconds=1.5)
    _run(orch.on_orchestration_complete(result))
    out = capsys.readouterr().out
    assert "Analysis Orchestration complete" in out


def test_analysis_prepare_mcp_tools_returns_three_tools():
    from steps.analysis.orchestration import analysis_orchestrator as ao
    orch = _bypass_init(ao.AnalysisOrchestrator)
    with (
        patch.object(ao, "MCPStreamableHTTPTool", return_value=MagicMock()),
        patch.object(ao, "MCPStdioTool", return_value=MagicMock()),
        patch.object(ao, "get_blob_file_mcp", return_value=MagicMock()),
    ):
        tools = _run(orch.prepare_mcp_tools())
    assert len(tools) == 3


def test_analysis_prepare_agent_infos_builds_full_set():
    from steps.analysis.orchestration import analysis_orchestrator as ao
    orch = _bypass_init(ao.AnalysisOrchestrator)
    orch.task_param = MagicMock()
    orch.task_param.model_dump.return_value = {
        "process_id": "p1", "container_name": "processes",
        "source_file_folder": "p1/source", "workspace_file_folder": "p1/ws",
        "output_file_folder": "p1/out",
    }
    orch.mcp_tools = [MagicMock(), MagicMock(), MagicMock()]

    registry_data = [
        {"agent_name": "EKS Expert", "prompt_file": "prompt_eks.txt"},
        {"agent_name": "", "prompt_file": "skip.txt"},  # invalid - skipped
        {"agent_name": "GKE Expert", "prompt_file": ""},  # invalid - skipped
    ]

    fake_info = MagicMock()
    fake_info.agent_name = "X"
    with (
        patch.object(orch, "load_platform_registry", return_value=registry_data),
        patch.object(orch, "read_prompt_file", return_value="instr"),
        patch.object(ao, "AgentInfo", return_value=fake_info),
    ):
        infos = _run(orch.prepare_agent_infos())
    # 1 expert + AKS + ChiefArchitect + Coordinator + ResultGenerator = 5
    assert len(infos) == 5


def test_analysis_prepare_agent_infos_raises_when_tools_missing():
    from steps.analysis.orchestration import analysis_orchestrator as ao
    orch = _bypass_init(ao.AnalysisOrchestrator)
    orch.mcp_tools = None
    with pytest.raises(ValueError):
        _run(orch.prepare_agent_infos())


def test_analysis_on_agent_response_forwards_to_super():
    from steps.analysis.orchestration import analysis_orchestrator as ao
    orch = _bypass_init(ao.AnalysisOrchestrator)
    parent_called = {}

    async def _fake_super(self, response):
        parent_called["called"] = response
    with patch(
        "steps.analysis.orchestration.analysis_orchestrator.OrchestratorBase.on_agent_response",
        new=_fake_super,
    ):
        _run(orch.on_agent_response(SimpleNamespace()))
    assert "called" in parent_called


def test_analysis_on_agent_response_stream_forwards_to_super():
    from steps.analysis.orchestration import analysis_orchestrator as ao
    orch = _bypass_init(ao.AnalysisOrchestrator)
    parent_called = {}

    async def _fake_super(self, response):
        parent_called["called"] = response
    with patch(
        "steps.analysis.orchestration.analysis_orchestrator.OrchestratorBase.on_agent_response_stream",
        new=_fake_super,
    ):
        _run(orch.on_agent_response_stream(SimpleNamespace()))
    assert "called" in parent_called


# ============== DesignOrchestrator ==============

def test_design_on_orchestration_complete_prints(capsys):
    from steps.design.orchestration import design_orchestrator as do
    orch = _bypass_init(do.DesignOrchestrator)
    result = SimpleNamespace(execution_time_seconds=2.5)
    _run(orch.on_orchestration_complete(result))
    out = capsys.readouterr().out
    assert "Design Orchestration complete" in out


def test_design_prepare_mcp_tools_returns_four_tools():
    from steps.design.orchestration import design_orchestrator as do
    orch = _bypass_init(do.DesignOrchestrator)
    with (
        patch.object(do, "MCPStreamableHTTPTool", return_value=MagicMock()),
        patch.object(do, "MCPStdioTool", return_value=MagicMock()),
        patch.object(do, "get_blob_file_mcp", return_value=MagicMock()),
        patch.object(do, "get_mermaid_mcp", return_value=MagicMock()),
    ):
        tools = _run(orch.prepare_mcp_tools())
    assert len(tools) == 4


def test_design_prepare_agent_infos_builds_full_set():
    from steps.design.orchestration import design_orchestrator as do
    orch = _bypass_init(do.DesignOrchestrator)
    orch.task_param = SimpleNamespace(output=SimpleNamespace(process_id="p1"))
    orch.mcp_tools = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    registry_data = [
        {"agent_name": "EKS Expert", "prompt_file": "prompt_eks.txt"},
        {"agent_name": 1, "prompt_file": "skip.txt"},  # invalid
        {"agent_name": "GKE Expert", "prompt_file": None},  # invalid
    ]
    fake_info = MagicMock()
    fake_info.agent_name = "X"
    with (
        patch.object(orch, "load_platform_registry", return_value=registry_data),
        patch.object(orch, "read_prompt_file", return_value="instr"),
        patch.object(do, "AgentInfo", return_value=fake_info),
    ):
        infos = _run(orch.prepare_agent_infos())
    # 1 expert + AKS + Architect + Coordinator + ResultGenerator = 5
    assert len(infos) == 5


def test_design_on_agent_response_forwards():
    from steps.design.orchestration import design_orchestrator as do
    orch = _bypass_init(do.DesignOrchestrator)
    called = {}

    async def _fake(self, r): called["x"] = True
    with patch(
        "steps.design.orchestration.design_orchestrator.OrchestratorBase.on_agent_response",
        new=_fake,
    ):
        _run(orch.on_agent_response(SimpleNamespace()))
    assert called


def test_design_on_agent_response_stream_forwards():
    from steps.design.orchestration import design_orchestrator as do
    orch = _bypass_init(do.DesignOrchestrator)
    called = {}

    async def _fake(self, r): called["x"] = True
    with patch(
        "steps.design.orchestration.design_orchestrator.OrchestratorBase.on_agent_response_stream",
        new=_fake,
    ):
        _run(orch.on_agent_response_stream(SimpleNamespace()))
    assert called


# ============== DocumentationOrchestrator ==============

def test_documentation_on_orchestration_complete_prints(capsys):
    from steps.documentation.orchestration import documentation_orchestrator as do
    orch = _bypass_init(do.DocumentationOrchestrator)
    result = SimpleNamespace(execution_time_seconds=3.0)
    _run(orch.on_orchestration_complete(result))  # uses logger; just must not raise


def test_documentation_prepare_mcp_tools():
    from steps.documentation.orchestration import documentation_orchestrator as do
    orch = _bypass_init(do.DocumentationOrchestrator)
    with (
        patch.object(do, "MCPStreamableHTTPTool", return_value=MagicMock()),
        patch.object(do, "MCPStdioTool", return_value=MagicMock()),
        patch.object(do, "get_blob_file_mcp", return_value=MagicMock()),
        patch.object(do, "get_yaml_inventory_mcp", return_value=MagicMock()),
    ):
        tools = _run(orch.prepare_mcp_tools())
    assert isinstance(tools, list)
    assert len(tools) >= 3


def test_documentation_prepare_agent_infos():
    from steps.documentation.orchestration import documentation_orchestrator as do
    orch = _bypass_init(do.DocumentationOrchestrator)
    orch.task_param = SimpleNamespace(process_id="p1")
    orch.mcp_tools = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    registry_data = [
        {"agent_name": "Tech Writer", "prompt_file": "prompt_tw.txt"},
        {"agent_name": None, "prompt_file": "skip.txt"},  # invalid
    ]
    fake_info = MagicMock()
    fake_info.agent_name = "X"
    fake_path = MagicMock()
    fake_path.exists.return_value = True
    with (
        patch.object(orch, "load_platform_registry", return_value=registry_data),
        patch.object(orch, "read_prompt_file", return_value="instr"),
        patch.object(do, "AgentInfo", return_value=fake_info),
        # Force any path used by the orchestrator to claim it exists.
        patch("pathlib.Path.exists", return_value=True),
    ):
        infos = _run(orch.prepare_agent_infos())
    assert len(infos) >= 5  # technical_writer + aks + azure_arch + chief + coord + result_gen + 1 expert


def test_documentation_on_agent_response_forwards():
    from steps.documentation.orchestration import documentation_orchestrator as do
    orch = _bypass_init(do.DocumentationOrchestrator)
    called = {}

    async def _fake(self, r): called["x"] = True
    with patch(
        "steps.documentation.orchestration.documentation_orchestrator.OrchestratorBase.on_agent_response",
        new=_fake,
    ):
        _run(orch.on_agent_response(SimpleNamespace()))
    assert called


def test_documentation_on_agent_response_stream_forwards():
    from steps.documentation.orchestration import documentation_orchestrator as do
    orch = _bypass_init(do.DocumentationOrchestrator)
    called = {}

    async def _fake(self, r): called["x"] = True
    with patch(
        "steps.documentation.orchestration.documentation_orchestrator.OrchestratorBase.on_agent_response_stream",
        new=_fake,
    ):
        _run(orch.on_agent_response_stream(SimpleNamespace()))
    assert called


# ============== YamlConvertOrchestrator ==============

def test_yaml_convert_on_orchestration_complete_prints(capsys):
    from steps.convert.orchestration import yaml_convert_orchestrator as yo
    orch = _bypass_init(yo.YamlConvertOrchestrator)
    result = SimpleNamespace(execution_time_seconds=4.0)
    _run(orch.on_orchestration_complete(result))  # uses logger; just must not raise


def test_yaml_convert_prepare_mcp_tools():
    from steps.convert.orchestration import yaml_convert_orchestrator as yo
    orch = _bypass_init(yo.YamlConvertOrchestrator)
    with (
        patch.object(yo, "MCPStreamableHTTPTool", return_value=MagicMock()),
        patch.object(yo, "MCPStdioTool", return_value=MagicMock()),
        patch.object(yo, "get_blob_file_mcp", return_value=MagicMock()),
    ):
        tools = _run(orch.prepare_mcp_tools())
    assert len(tools) >= 2


def test_yaml_convert_prepare_agent_infos():
    from steps.convert.orchestration import yaml_convert_orchestrator as yo
    orch = _bypass_init(yo.YamlConvertOrchestrator)
    orch.task_param = SimpleNamespace(process_id="p1")
    orch.mcp_tools = [MagicMock(), MagicMock(), MagicMock()]

    fake_info = MagicMock()
    fake_info.agent_name = "X"
    with (
        patch.object(orch, "read_prompt_file", return_value="instr"),
        patch.object(yo, "AgentInfo", return_value=fake_info),
    ):
        infos = _run(orch.prepare_agent_infos())
    assert len(infos) >= 5


def test_yaml_convert_on_agent_response_forwards():
    from steps.convert.orchestration import yaml_convert_orchestrator as yo
    orch = _bypass_init(yo.YamlConvertOrchestrator)
    called = {}

    async def _fake(self, r): called["x"] = True
    with patch(
        "steps.convert.orchestration.yaml_convert_orchestrator.OrchestratorBase.on_agent_response",
        new=_fake,
    ):
        _run(orch.on_agent_response(SimpleNamespace()))
    assert called


def test_yaml_convert_on_agent_response_stream_forwards():
    from steps.convert.orchestration import yaml_convert_orchestrator as yo
    orch = _bypass_init(yo.YamlConvertOrchestrator)
    called = {}

    async def _fake(self, r): called["x"] = True
    with patch(
        "steps.convert.orchestration.yaml_convert_orchestrator.OrchestratorBase.on_agent_response_stream",
        new=_fake,
    ):
        _run(orch.on_agent_response_stream(SimpleNamespace()))
    assert called



# ============== Constructor tests + execute() coverage ==============

class _AsyncCM:
    """Minimal async context manager used to wrap mcp_tools."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _async_returning(value):
    async def _fn(*a, **kw):
        return value
    return _fn


def _make_orch_with_init_patched(orch_cls):
    """Construct an orchestrator with OrchestratorBase.__init__ stubbed out so the real ctor body executes."""
    with patch(
        "libs.base.orchestrator_base.OrchestratorBase.__init__",
        return_value=None,
    ):
        return orch_cls(MagicMock())


def test_analysis_constructor_sets_step_name():
    from steps.analysis.orchestration import analysis_orchestrator as ao
    orch = _make_orch_with_init_patched(ao.AnalysisOrchestrator)
    assert orch.step_name == "Analysis"


def test_design_constructor_sets_step_name():
    from steps.design.orchestration import design_orchestrator as do
    orch = _make_orch_with_init_patched(do.DesignOrchestrator)
    assert orch.step_name == "Design"


def test_documentation_constructor_sets_step_name():
    from steps.documentation.orchestration import documentation_orchestrator as do
    orch = _make_orch_with_init_patched(do.DocumentationOrchestrator)
    assert orch.step_name == "Documentation"


def test_yaml_convert_constructor_sets_step_name():
    from steps.convert.orchestration import yaml_convert_orchestrator as yo
    orch = _make_orch_with_init_patched(yo.YamlConvertOrchestrator)
    assert orch.step_name == "Convert"


# ---- execute() value-error guards ----

def test_analysis_execute_raises_when_task_param_none():
    from steps.analysis.orchestration import analysis_orchestrator as ao
    orch = _bypass_init(ao.AnalysisOrchestrator)
    with pytest.raises(ValueError):
        _run(orch.execute(None))


def test_design_execute_raises_when_task_param_none():
    from steps.design.orchestration import design_orchestrator as do
    orch = _bypass_init(do.DesignOrchestrator)
    with pytest.raises(ValueError):
        _run(orch.execute(None))


def test_documentation_execute_raises_when_task_param_none():
    from steps.documentation.orchestration import documentation_orchestrator as do
    orch = _bypass_init(do.DocumentationOrchestrator)
    with pytest.raises(ValueError):
        _run(orch.execute(None))


def test_documentation_execute_raises_when_process_id_missing():
    from steps.documentation.orchestration import documentation_orchestrator as do
    orch = _bypass_init(do.DocumentationOrchestrator)
    bad = SimpleNamespace(process_id="")
    with pytest.raises(ValueError):
        _run(orch.execute(bad))


def test_yaml_convert_execute_raises_when_task_param_none():
    from steps.convert.orchestration import yaml_convert_orchestrator as yo
    orch = _bypass_init(yo.YamlConvertOrchestrator)
    with pytest.raises(ValueError):
        _run(orch.execute(None))


def test_yaml_convert_execute_raises_when_process_id_missing():
    from steps.convert.orchestration import yaml_convert_orchestrator as yo
    orch = _bypass_init(yo.YamlConvertOrchestrator)
    bad = SimpleNamespace(process_id="")
    with pytest.raises(ValueError):
        _run(orch.execute(bad))


# ---- prepare_agent_infos guard tests ----

def test_documentation_prepare_agent_infos_raises_when_tools_missing():
    from steps.documentation.orchestration import documentation_orchestrator as do
    orch = _bypass_init(do.DocumentationOrchestrator)
    orch.mcp_tools = None
    with pytest.raises(ValueError):
        _run(orch.prepare_agent_infos())


def test_yaml_convert_prepare_agent_infos_raises_when_tools_missing():
    from steps.convert.orchestration import yaml_convert_orchestrator as yo
    orch = _bypass_init(yo.YamlConvertOrchestrator)
    orch.mcp_tools = None
    with pytest.raises(ValueError):
        _run(orch.prepare_agent_infos())


# ---- Documentation prepare_agent_infos: skip-branch coverage ----

def test_documentation_prepare_agent_infos_skips_invalid_prompt_file_and_missing_path():
    from steps.documentation.orchestration import documentation_orchestrator as do
    orch = _bypass_init(do.DocumentationOrchestrator)
    orch.task_param = SimpleNamespace(process_id="p1")
    orch.mcp_tools = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]

    registry_data = [
        {"agent_name": "Bad1", "prompt_file": ""},        # empty prompt -> skipped (line 222)
        {"agent_name": "Bad2", "prompt_file": "missing_prompt.txt"},  # path doesn't exist -> skipped (line 226)
        {"agent_name": "Good", "prompt_file": "prompt_eks_expert.txt"},  # exists in real agents dir
    ]
    fake_info = MagicMock()
    fake_info.agent_name = "X"
    with (
        patch.object(orch, "load_platform_registry", return_value=registry_data),
        patch.object(orch, "read_prompt_file", return_value="instr"),
        patch.object(do, "AgentInfo", return_value=fake_info),
    ):
        infos = _run(orch.prepare_agent_infos())
    # Tech writer + AKS + Azure Architect + Chief + 1 valid expert (Good) +
    # Coordinator + ResultGenerator = 7
    assert len(infos) == 7


# ---- execute() happy-path coverage (orchestrates async-context-manager exit + run_stream) ----

def _patch_groupchat_orch(module, returned_result):
    """Return a patcher that swaps `GroupChatOrchestrator` in *module* with a stub
    whose `run_stream` returns *returned_result* and which also accepts subscript `[]`."""

    class _StubOrch:
        def __init__(self, *a, **kw):
            pass

        async def run_stream(self, **kw):
            return returned_result

    class _SubscriptStub:
        def __getitem__(self, item):
            return _StubOrch

        def __call__(self, *a, **kw):
            return _StubOrch(*a, **kw)

    return patch.object(module, "GroupChatOrchestrator", _SubscriptStub())


def test_analysis_execute_happy_path():
    from steps.analysis.orchestration import analysis_orchestrator as ao
    orch = _bypass_init(ao.AnalysisOrchestrator)
    orch.initialized = True
    orch.agents = []
    orch.mcp_tools = [_AsyncCM(), _AsyncCM(), _AsyncCM()]
    orch.flush_agent_memories = _async_returning(None)

    task_param = MagicMock()
    task_param.process_id = "p1"
    task_param.model_dump.return_value = {"process_id": "p1"}

    sentinel = object()
    with (
        patch.object(ao.TemplateUtility, "render_from_file", return_value="prompt"),
        patch.object(ao, "get_current_timestamp_utc", return_value="ts"),
        _patch_groupchat_orch(ao, sentinel),
    ):
        result = _run(orch.execute(task_param))
    assert result is sentinel


def test_analysis_execute_calls_initialize_when_not_initialized():
    from steps.analysis.orchestration import analysis_orchestrator as ao
    orch = _bypass_init(ao.AnalysisOrchestrator)
    orch.initialized = False
    orch.agents = []
    orch.mcp_tools = [_AsyncCM(), _AsyncCM(), _AsyncCM()]
    orch.flush_agent_memories = _async_returning(None)
    init_called = {}

    async def _init(process_id):
        init_called["pid"] = process_id
        orch.initialized = True

    orch.initialize = _init

    task_param = MagicMock()
    task_param.process_id = "px"
    task_param.model_dump.return_value = {"process_id": "px"}

    with (
        patch.object(ao.TemplateUtility, "render_from_file", return_value="prompt"),
        patch.object(ao, "get_current_timestamp_utc", return_value="ts"),
        _patch_groupchat_orch(ao, "ok"),
    ):
        _run(orch.execute(task_param))
    assert init_called["pid"] == "px"


def test_design_execute_happy_path():
    from steps.design.orchestration import design_orchestrator as do
    orch = _bypass_init(do.DesignOrchestrator)
    orch.initialized = True
    orch.agents = []
    orch.mcp_tools = [_AsyncCM(), _AsyncCM(), _AsyncCM(), _AsyncCM()]
    orch.flush_agent_memories = _async_returning(None)

    task_param = SimpleNamespace(output=SimpleNamespace(process_id="pX"))

    sentinel = object()
    with (
        patch.object(do.TemplateUtility, "render_from_file", return_value="prompt"),
        patch.object(do, "get_current_timestamp_utc", return_value="ts"),
        _patch_groupchat_orch(do, sentinel),
    ):
        result = _run(orch.execute(task_param))
    assert result is sentinel


def test_design_execute_initializes_when_needed():
    from steps.design.orchestration import design_orchestrator as do
    orch = _bypass_init(do.DesignOrchestrator)
    orch.initialized = False
    orch.agents = []
    orch.mcp_tools = [_AsyncCM(), _AsyncCM(), _AsyncCM(), _AsyncCM()]
    orch.flush_agent_memories = _async_returning(None)
    seen = {}

    async def _init(process_id):
        seen["pid"] = process_id
        orch.initialized = True

    orch.initialize = _init
    task_param = SimpleNamespace(output=SimpleNamespace(process_id="pY"))
    with (
        patch.object(do.TemplateUtility, "render_from_file", return_value="prompt"),
        patch.object(do, "get_current_timestamp_utc", return_value="ts"),
        _patch_groupchat_orch(do, "ok"),
    ):
        _run(orch.execute(task_param))
    assert seen["pid"] == "pY"


def test_documentation_execute_happy_path():
    from steps.documentation.orchestration import documentation_orchestrator as do
    orch = _bypass_init(do.DocumentationOrchestrator)
    orch.initialized = True
    orch.agents = []
    orch.mcp_tools = [_AsyncCM(), _AsyncCM(), _AsyncCM(), _AsyncCM()]
    orch.flush_agent_memories = _async_returning(None)
    task_param = SimpleNamespace(process_id="p1")

    sentinel = object()
    with (
        patch.object(do.TemplateUtility, "render_from_file", return_value="prompt"),
        patch.object(do, "get_current_timestamp_utc", return_value="ts"),
        _patch_groupchat_orch(do, sentinel),
    ):
        result = _run(orch.execute(task_param))
    assert result is sentinel


def test_documentation_execute_initializes_when_needed():
    from steps.documentation.orchestration import documentation_orchestrator as do
    orch = _bypass_init(do.DocumentationOrchestrator)
    orch.initialized = False
    orch.agents = []
    orch.mcp_tools = [_AsyncCM(), _AsyncCM(), _AsyncCM(), _AsyncCM()]
    orch.flush_agent_memories = _async_returning(None)
    seen = {}

    async def _init(process_id):
        seen["pid"] = process_id
        orch.initialized = True

    orch.initialize = _init
    task_param = SimpleNamespace(process_id="pZ")
    with (
        patch.object(do.TemplateUtility, "render_from_file", return_value="prompt"),
        patch.object(do, "get_current_timestamp_utc", return_value="ts"),
        _patch_groupchat_orch(do, "ok"),
    ):
        _run(orch.execute(task_param))
    assert seen["pid"] == "pZ"


def test_yaml_convert_execute_happy_path():
    from steps.convert.orchestration import yaml_convert_orchestrator as yo
    orch = _bypass_init(yo.YamlConvertOrchestrator)
    orch.initialized = True
    orch.agents = []
    orch.mcp_tools = [_AsyncCM(), _AsyncCM(), _AsyncCM()]
    orch.flush_agent_memories = _async_returning(None)
    task_param = SimpleNamespace(process_id="p1")

    sentinel = object()
    with (
        patch.object(yo.TemplateUtility, "render_from_file", return_value="prompt"),
        patch.object(yo, "get_current_timestamp_utc", return_value="ts"),
        _patch_groupchat_orch(yo, sentinel),
    ):
        result = _run(orch.execute(task_param))
    assert result is sentinel


def test_yaml_convert_execute_initializes_when_needed():
    from steps.convert.orchestration import yaml_convert_orchestrator as yo
    orch = _bypass_init(yo.YamlConvertOrchestrator)
    orch.initialized = False
    orch.agents = []
    orch.mcp_tools = [_AsyncCM(), _AsyncCM(), _AsyncCM()]
    orch.flush_agent_memories = _async_returning(None)
    seen = {}

    async def _init(process_id):
        seen["pid"] = process_id
        orch.initialized = True

    orch.initialize = _init
    task_param = SimpleNamespace(process_id="pQ")
    with (
        patch.object(yo.TemplateUtility, "render_from_file", return_value="prompt"),
        patch.object(yo, "get_current_timestamp_utc", return_value="ts"),
        _patch_groupchat_orch(yo, "ok"),
    ):
        _run(orch.execute(task_param))
    assert seen["pid"] == "pQ"


# ---- _parse_conversion_report_quality_gates coverage ----

def test_yaml_convert_parse_quality_gates_blockers_and_signoffs():
    from steps.convert.orchestration import yaml_convert_orchestrator as yo
    md = """
## Blockers

- title: Missing image registry
  status: Open

## Sign-off
**Architect:** SIGN-OFF: PASS
**QA Engineer**: SIGN-OFF: FAIL
"""
    signoffs, has_open = yo._parse_conversion_report_quality_gates(md)
    assert has_open is True
    assert signoffs == {"Architect": "PASS", "QA Engineer": "FAIL"}


def test_yaml_convert_parse_quality_gates_no_blockers_no_signoffs():
    from steps.convert.orchestration import yaml_convert_orchestrator as yo
    signoffs, has_open = yo._parse_conversion_report_quality_gates("# Empty document")
    assert has_open is False
    assert signoffs == {}


def test_yaml_convert_parse_quality_gates_empty_blockers_section():
    from steps.convert.orchestration import yaml_convert_orchestrator as yo
    md = """
## Blockers

(none reported)

## Sign-off
"""
    signoffs, has_open = yo._parse_conversion_report_quality_gates(md)
    assert has_open is False
    assert signoffs == {}
