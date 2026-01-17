# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio

from libs.agent_framework.groupchat_orchestrator import OrchestrationResult
from steps.analysis.models.step_output import Analysis_BooleanExtendedResult
from steps.analysis.models.step_param import Analysis_TaskParam
from steps.analysis.orchestration.analysis_orchestrator import AnalysisOrchestrator


class _DummyAsyncCM:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_analysis_orchestrator_renders_prompt_with_task_param_fields(monkeypatch):
    async def _run():
        orch = AnalysisOrchestrator.__new__(AnalysisOrchestrator)
        orch.initialized = True
        orch.mcp_tools = [
            _DummyAsyncCM(),
            _DummyAsyncCM(),
            _DummyAsyncCM(),
            _DummyAsyncCM(),
        ]
        orch.agents = []

        captured: dict[str, object] = {}

        def _fake_render_from_file(path: str, **kwargs):
            captured["path"] = path
            captured["kwargs"] = dict(kwargs)
            return "PROMPT"

        class _FakeGroupChat:
            @classmethod
            def __class_getitem__(cls, _item):
                return cls

            def __init__(
                self,
                name: str,
                process_id: str,
                participants,
                memory_client,
                result_output_format,
            ):
                self.process_id = process_id

            async def run_stream(
                self,
                input_data,
                on_agent_response,
                on_agent_response_stream,
                on_workflow_complete,
            ):
                assert input_data == "PROMPT"
                return OrchestrationResult(
                    success=True,
                    conversation=[],
                    agent_responses=[],
                    tool_usage={},
                    result=Analysis_BooleanExtendedResult(process_id=self.process_id),
                )

        monkeypatch.setattr(
            "steps.analysis.orchestration.analysis_orchestrator.TemplateUtility.render_from_file",
            _fake_render_from_file,
        )
        monkeypatch.setattr(
            "steps.analysis.orchestration.analysis_orchestrator.GroupChatOrchestrator",
            _FakeGroupChat,
        )

        task = Analysis_TaskParam(
            process_id="p1",
            container_name="processes",
            source_file_folder="p1/source",
            workspace_file_folder="p1/workspace",
            output_file_folder="p1/converted",
        )

        result = await AnalysisOrchestrator.execute(orch, task_param=task)

        assert result.success is True
        assert captured["kwargs"]["process_id"] == "p1"
        assert captured["kwargs"]["container_name"] == "processes"
        assert captured["kwargs"]["source_file_folder"] == "p1/source"
        assert captured["kwargs"]["workspace_file_folder"] == "p1/workspace"
        assert captured["kwargs"]["output_file_folder"] == "p1/converted"

    asyncio.run(_run())
