# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from steps.convert.models.step_output import Yaml_ExtendedBooleanResult
from steps.documentation.orchestration.documentation_orchestrator import (
    DocumentationOrchestrator,
)


def _run(coro):
    return asyncio.run(coro)


def _make_orch():
    """Create an instance bypassing __init__ to keep tests isolated."""
    orch = DocumentationOrchestrator.__new__(DocumentationOrchestrator)
    orch.initialized = True
    orch.step_name = "Documentation"
    orch.app_context = MagicMock()
    orch.memory_store = None
    orch.agents = {}
    return orch


class TestPrepareAgentInfos:
    def test_raises_when_mcp_tools_none(self):
        orch = _make_orch()
        orch.mcp_tools = None
        with pytest.raises(ValueError, match=r"MCP tools must be prepared"):
            _run(orch.prepare_agent_infos())

    def test_builds_agents_with_registry_entries(self, tmp_path):
        orch = _make_orch()
        orch.mcp_tools = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
        orch.task_param = Yaml_ExtendedBooleanResult(process_id="proc-X")

        registry_entries = [
            {"agent_name": "EKS Expert", "prompt_file": "prompt_eks_expert.txt"},
            {"agent_name": "GKE Expert", "prompt_file": "prompt_gke_expert.txt"},
            {"agent_name": "", "prompt_file": "skip.txt"},  # invalid agent_name
            {"agent_name": "Bad", "prompt_file": ""},  # invalid prompt_file
            {"agent_name": "Missing", "prompt_file": "nonexistent.txt"},  # path missing
            {"agent_name": 42, "prompt_file": "x.txt"},  # wrong type
        ]

        # Patch helpers on the instance
        with patch.object(
            DocumentationOrchestrator,
            "load_platform_registry",
            return_value=registry_entries,
        ), patch.object(
            DocumentationOrchestrator,
            "read_prompt_file",
            return_value="PROMPT BODY",
        ), patch(
            "steps.documentation.orchestration.documentation_orchestrator.Path"
        ) as path_cls:
            # Make Path(...).exists() True only for known prompt files.
            existing = {
                "prompt_eks_expert.txt",
                "prompt_gke_expert.txt",
            }

            class _FakePath:
                def __init__(self, *parts):
                    self._parts = [str(p) for p in parts]

                def __truediv__(self, other):
                    return _FakePath(*self._parts, other)

                def resolve(self):
                    return self

                @property
                def parents(self):
                    # Pretend parents[3] returns repo root that supports __truediv__
                    return [self, self, self, _FakePath("repo_root")]

                @property
                def parent(self):
                    return self

                def exists(self):
                    name = self._parts[-1]
                    return name in existing

                def __str__(self):
                    return "/".join(self._parts)

                def __fspath__(self):
                    return str(self)

            path_cls.side_effect = lambda *a, **k: _FakePath(*a)

            agent_infos = _run(orch.prepare_agent_infos())

        names = [a.agent_name for a in agent_infos]
        # Built-ins
        assert "Technical Writer" in names
        assert "AKS Expert" in names
        assert "Azure Architect" in names
        assert "Chief Architect" in names
        # Registry experts that exist
        assert "EKS Expert" in names
        assert "GKE Expert" in names
        # Coordinator + ResultGenerator are appended last
        assert "Coordinator" in names
        assert "ResultGenerator" in names
        # Skipped invalid entries
        assert "Bad" not in names
        assert "Missing" not in names
        assert 42 not in names


class TestForwardingHooks:
    def test_on_agent_response_calls_super(self):
        orch = _make_orch()
        with patch(
            "libs.base.orchestrator_base.OrchestratorBase.on_agent_response",
            new_callable=AsyncMock,
        ) as super_call:
            _run(orch.on_agent_response(MagicMock()))
            assert super_call.await_count == 1

    def test_on_agent_response_stream_calls_super(self):
        orch = _make_orch()
        with patch(
            "libs.base.orchestrator_base.OrchestratorBase.on_agent_response_stream",
            new_callable=AsyncMock,
        ) as super_call:
            _run(orch.on_agent_response_stream(MagicMock()))
            assert super_call.await_count == 1

    def test_on_orchestration_complete_logs(self, caplog):
        orch = _make_orch()
        result = MagicMock()
        result.execution_time_seconds = 12.5
        with caplog.at_level("INFO"):
            _run(orch.on_orchestration_complete(result))
        assert any(
            "Documentation Orchestration complete" in r.message for r in caplog.records
        )
