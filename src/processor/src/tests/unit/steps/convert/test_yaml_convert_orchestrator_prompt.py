# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio

from libs.agent_framework.groupchat_orchestrator import OrchestrationResult
from steps.convert.models.step_output import Yaml_ExtendedBooleanResult
from steps.convert.orchestration.yaml_convert_orchestrator import (
    YamlConvertOrchestrator,
)
from steps.design.models.step_output import Design_ExtendedBooleanResult


class _DummyAsyncCM:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_yaml_convert_orchestrator_renders_expected_folder_params(monkeypatch):
    async def _run():
        orch = YamlConvertOrchestrator.__new__(YamlConvertOrchestrator)
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
                max_seconds,
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
                    result=Yaml_ExtendedBooleanResult(process_id=self.process_id),
                )

        monkeypatch.setattr(
            "steps.convert.orchestration.yaml_convert_orchestrator.TemplateUtility.render_from_file",
            _fake_render_from_file,
        )
        monkeypatch.setattr(
            "steps.convert.orchestration.yaml_convert_orchestrator.GroupChatOrchestrator",
            _FakeGroupChat,
        )

        msg = Design_ExtendedBooleanResult(process_id="p1")
        result = await YamlConvertOrchestrator.execute(orch, task_param=msg)
        assert result.success is True

        kwargs = captured["kwargs"]
        assert kwargs["container_name"] == "processes"
        assert kwargs["source_file_folder"] == "p1/source"
        assert kwargs["workspace_file_folder"] == "p1/workspace"
        assert kwargs["output_file_folder"] == "p1/converted"

    asyncio.run(_run())
