# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio

from libs.agent_framework.groupchat_orchestrator import OrchestrationResult
from steps.convert.models.step_output import Yaml_ExtendedBooleanResult
from steps.documentation.models.step_output import Documentation_ExtendedBooleanResult
from steps.documentation.orchestration.documentation_orchestrator import (
    DocumentationOrchestrator,
)


class _DummyAsyncCM:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_documentation_orchestrator_renders_expected_folder_params(monkeypatch):
    async def _run():
        orch = DocumentationOrchestrator.__new__(DocumentationOrchestrator)
        orch.initialized = True
        orch.mcp_tools = [
            _DummyAsyncCM(),
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
                on_workflow_complete,
                on_agent_response_stream,
            ):
                assert input_data == "PROMPT"
                return OrchestrationResult(
                    success=True,
                    conversation=[],
                    agent_responses=[],
                    tool_usage={},
                    result=Documentation_ExtendedBooleanResult(process_id=self.process_id),
                )

        monkeypatch.setattr(
            "steps.documentation.orchestration.documentation_orchestrator.TemplateUtility.render_from_file",
            _fake_render_from_file,
        )
        monkeypatch.setattr(
            "steps.documentation.orchestration.documentation_orchestrator.GroupChatOrchestrator",
            _FakeGroupChat,
        )

        msg = Yaml_ExtendedBooleanResult(process_id="p1")
        result = await DocumentationOrchestrator.execute(orch, task_param=msg)
        assert result.success is True

        kwargs = captured["kwargs"]
        assert kwargs["container_name"] == "processes"
        assert kwargs["source_file_folder"] == "p1/source"
        assert kwargs["workspace_file_folder"] == "p1/workspace"
        assert kwargs["output_file_folder"] == "p1/output"

    asyncio.run(_run())
