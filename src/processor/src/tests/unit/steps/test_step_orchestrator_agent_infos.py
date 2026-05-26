# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for prepare_agent_infos and forwarding hooks of analysis/design/yaml orchestrators."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from steps.analysis.models.step_param import Analysis_TaskParam
from steps.analysis.orchestration.analysis_orchestrator import AnalysisOrchestrator
from steps.convert.orchestration.yaml_convert_orchestrator import (
    YamlConvertOrchestrator,
)
from steps.design.orchestration.design_orchestrator import DesignOrchestrator


def _run(coro):
    return asyncio.run(coro)


def _make(cls):
    o = cls.__new__(cls)
    o.initialized = True
    o.app_context = MagicMock()
    o.memory_store = None
    o.agents = {}
    return o


REGISTRY_ENTRIES = [
    {"agent_name": "EKS Expert", "prompt_file": "prompt_eks_expert.txt"},
    {"agent_name": "GKE Expert", "prompt_file": "prompt_gke_expert.txt"},
    # invalid entries — must be skipped
    {"agent_name": "", "prompt_file": "x.txt"},
    {"agent_name": "X", "prompt_file": ""},
    {"agent_name": 1, "prompt_file": "y.txt"},
    {"agent_name": "Z", "prompt_file": 1},
]


class TestAnalysisOrchestrator:
    def test_prepare_agent_infos_raises_when_mcp_tools_missing(self):
        orch = _make(AnalysisOrchestrator)
        orch.mcp_tools = None
        with pytest.raises(ValueError, match=r"MCP tools must be prepared"):
            _run(orch.prepare_agent_infos())

    def test_prepare_agent_infos_builds_full_set(self):
        orch = _make(AnalysisOrchestrator)
        orch.mcp_tools = [MagicMock(), MagicMock(), MagicMock()]
        orch.task_param = Analysis_TaskParam(
            process_id="p1",
            container_name="processes",
            source_file_folder="p1/source",
            output_file_folder="p1/converted",
            workspace_file_folder="p1/workspace",
        )
        with patch.object(
            AnalysisOrchestrator,
            "load_platform_registry",
            return_value=REGISTRY_ENTRIES,
        ), patch.object(
            AnalysisOrchestrator,
            "read_prompt_file",
            return_value="PROMPT",
        ):
            infos = _run(orch.prepare_agent_infos())
        names = [i.agent_name for i in infos]
        for must in (
            "EKS Expert",
            "GKE Expert",
            "AKS Expert",
            "Chief Architect",
            "Coordinator",
            "ResultGenerator",
        ):
            assert must in names
        # Coordinator should be near the end with proper participant rendering.
        assert names[-2] == "Coordinator"
        assert names[-1] == "ResultGenerator"

    def test_on_agent_response_calls_super(self):
        orch = _make(AnalysisOrchestrator)
        with patch(
            "libs.base.orchestrator_base.OrchestratorBase.on_agent_response",
            new_callable=AsyncMock,
        ) as super_call:
            _run(orch.on_agent_response(MagicMock()))
            assert super_call.await_count == 1

    def test_on_agent_response_stream_calls_super(self):
        orch = _make(AnalysisOrchestrator)
        with patch(
            "libs.base.orchestrator_base.OrchestratorBase.on_agent_response_stream",
            new_callable=AsyncMock,
        ) as super_call:
            _run(orch.on_agent_response_stream(MagicMock()))
            assert super_call.await_count == 1

    def test_on_orchestration_complete_runs(self, capsys):
        orch = _make(AnalysisOrchestrator)
        result = MagicMock()
        result.execution_time_seconds = 4.2
        _run(orch.on_orchestration_complete(result))
        out = capsys.readouterr().out
        assert "Analysis Orchestration complete." in out


class TestDesignOrchestrator:
    def _task_param(self):
        # design uses self.task_param.output.process_id
        tp = MagicMock()
        tp.output = MagicMock()
        tp.output.process_id = "p1"
        return tp

    def test_prepare_agent_infos_builds_full_set(self):
        orch = _make(DesignOrchestrator)
        orch.mcp_tools = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
        orch.task_param = self._task_param()
        with patch.object(
            DesignOrchestrator,
            "load_platform_registry",
            return_value=REGISTRY_ENTRIES,
        ), patch.object(
            DesignOrchestrator,
            "read_prompt_file",
            return_value="PROMPT",
        ):
            infos = _run(orch.prepare_agent_infos())
        names = [i.agent_name for i in infos]
        for must in (
            "EKS Expert",
            "GKE Expert",
            "AKS Expert",
            "Chief Architect",
            "Coordinator",
            "ResultGenerator",
        ):
            assert must in names

    def test_on_agent_response_calls_super(self):
        orch = _make(DesignOrchestrator)
        with patch(
            "libs.base.orchestrator_base.OrchestratorBase.on_agent_response",
            new_callable=AsyncMock,
        ) as super_call:
            _run(orch.on_agent_response(MagicMock()))
            assert super_call.await_count == 1

    def test_on_agent_response_stream_calls_super(self):
        orch = _make(DesignOrchestrator)
        with patch(
            "libs.base.orchestrator_base.OrchestratorBase.on_agent_response_stream",
            new_callable=AsyncMock,
        ) as super_call:
            _run(orch.on_agent_response_stream(MagicMock()))
            assert super_call.await_count == 1

    def test_on_orchestration_complete_runs(self, capsys):
        orch = _make(DesignOrchestrator)
        result = MagicMock()
        result.execution_time_seconds = 1.5
        _run(orch.on_orchestration_complete(result))
        # design prints to stdout
        out = capsys.readouterr().out
        assert "Design" in out or "Elapsed" in out or out == ""


class TestYamlConvertOrchestrator:
    def test_prepare_agent_infos_builds_full_set(self):
        orch = _make(YamlConvertOrchestrator)
        orch.mcp_tools = [MagicMock(), MagicMock(), MagicMock()]
        # task_param for yaml convert uses self.task_param.process_id directly
        tp = MagicMock()
        tp.process_id = "p1"
        orch.task_param = tp
        with patch.object(
            YamlConvertOrchestrator,
            "load_platform_registry",
            return_value=REGISTRY_ENTRIES,
        ), patch.object(
            YamlConvertOrchestrator,
            "read_prompt_file",
            return_value="PROMPT",
        ):
            infos = _run(orch.prepare_agent_infos())
        names = [i.agent_name for i in infos]
        for must in (
            "YAML Expert",
            "AKS Expert",
            "Azure Architect",
            "QA Engineer",
            "Chief Architect",
            "Coordinator",
            "ResultGenerator",
        ):
            assert must in names

    def test_prepare_agent_infos_raises_when_mcp_tools_missing(self):
        orch = _make(YamlConvertOrchestrator)
        orch.mcp_tools = None
        with pytest.raises(ValueError, match=r"MCP tools must be prepared"):
            _run(orch.prepare_agent_infos())

    def test_on_agent_response_calls_super(self):
        orch = _make(YamlConvertOrchestrator)
        with patch(
            "libs.base.orchestrator_base.OrchestratorBase.on_agent_response",
            new_callable=AsyncMock,
        ) as super_call:
            _run(orch.on_agent_response(MagicMock()))
            assert super_call.await_count == 1

    def test_on_agent_response_stream_calls_super(self):
        orch = _make(YamlConvertOrchestrator)
        with patch(
            "libs.base.orchestrator_base.OrchestratorBase.on_agent_response_stream",
            new_callable=AsyncMock,
        ) as super_call:
            _run(orch.on_agent_response_stream(MagicMock()))
            assert super_call.await_count == 1

    def test_on_orchestration_complete_logs(self, caplog):
        orch = _make(YamlConvertOrchestrator)
        result = MagicMock()
        result.execution_time_seconds = 2.0
        with caplog.at_level("INFO"):
            _run(orch.on_orchestration_complete(result))
        assert any(
            "Yaml Convert Orchestration complete" in r.message
            for r in caplog.records
        )
