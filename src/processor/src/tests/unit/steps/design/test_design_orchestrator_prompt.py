# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio

from libs.agent_framework.groupchat_orchestrator import OrchestrationResult
from steps.analysis.models.step_output import (
    Analysis_BooleanExtendedResult,
    AnalysisOutput,
    ComplexityAnalysis,
    FileType,
    MigrationReadiness,
)
from steps.design.models.step_output import Design_ExtendedBooleanResult
from steps.design.orchestration.design_orchestrator import DesignOrchestrator


class _DummyAsyncCM:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_design_orchestrator_renders_expected_folder_params(monkeypatch):
    async def _run():
        orch = DesignOrchestrator.__new__(DesignOrchestrator)
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
                    result=Design_ExtendedBooleanResult(process_id=self.process_id),
                )

        monkeypatch.setattr(
            "steps.design.orchestration.design_orchestrator.TemplateUtility.render_from_file",
            _fake_render_from_file,
        )
        monkeypatch.setattr(
            "steps.design.orchestration.design_orchestrator.GroupChatOrchestrator",
            _FakeGroupChat,
        )

        output = AnalysisOutput(
            process_id="p1",
            platform_detected="GenericK8s",
            confidence_score="100%",
            files_discovered=[
                FileType(
                    filename="a.yaml",
                    type="Deployment",
                    complexity="Low",
                    azure_mapping="AKS",
                )
            ],
            complexity_analysis=ComplexityAnalysis(
                network_complexity="Low",
                security_complexity="Low",
                storage_complexity="Low",
                compute_complexity="Low",
            ),
            migration_readiness=MigrationReadiness(
                overall_score="High",
                concerns=[],
                recommendations=[],
            ),
            summary="ok",
            expert_insights=[],
            analysis_file="p1/converted/analysis.json",
        )
        msg = Analysis_BooleanExtendedResult(process_id="p1", output=output)

        result = await DesignOrchestrator.execute(orch, task_param=msg)
        assert result.success is True

        kwargs = captured["kwargs"]
        assert kwargs["container_name"] == "processes"
        assert kwargs["source_file_folder"] == "p1/source"
        assert kwargs["output_file_folder"] == "p1/converted"

    asyncio.run(_run())
