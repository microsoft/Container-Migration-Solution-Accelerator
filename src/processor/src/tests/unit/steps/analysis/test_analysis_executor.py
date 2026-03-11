# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio

from libs.agent_framework.groupchat_orchestrator import OrchestrationResult
from steps.analysis.models.step_output import Analysis_BooleanExtendedResult
from steps.analysis.models.step_param import Analysis_TaskParam
from steps.analysis.workflow.analysis_executor import AnalysisExecutor


class _FakeTelemetry:
    def __init__(self):
        self.transitions: list[tuple[str, str, str]] = []

    async def transition_to_phase(self, process_id: str, step: str, phase: str):
        self.transitions.append((process_id, step, phase))


class _FakeAppContext:
    def __init__(self, telemetry: _FakeTelemetry):
        self._telemetry = telemetry

    async def get_service_async(self, _service_type):
        return self._telemetry


class _FakeCtx:
    def __init__(self):
        self.sent: list[object] = []
        self.yielded: list[object] = []

    async def send_message(self, msg):
        self.sent.append(msg)

    async def yield_output(self, output):
        self.yielded.append(output)


def test_analysis_executor_sends_message_on_soft_completion(monkeypatch):
    async def _run():
        telemetry = _FakeTelemetry()
        app_context = _FakeAppContext(telemetry)
        ctx = _FakeCtx()

        class _FakeOrchestrator:
            def __init__(self, _app_context):
                pass

            async def execute(self, task_param=None):
                return OrchestrationResult(
                    success=True,
                    conversation=[],
                    agent_responses=[],
                    tool_usage={},
                    result=Analysis_BooleanExtendedResult(
                        result=True,
                        is_hard_terminated=False,
                        process_id=task_param.process_id,
                    ),
                )

        # Avoid huge ASCII art in test output.
        monkeypatch.setattr(
            "steps.analysis.workflow.analysis_executor.text2art", lambda _s: "ART"
        )
        monkeypatch.setattr(
            "steps.analysis.workflow.analysis_executor.AnalysisOrchestrator",
            _FakeOrchestrator,
        )

        executor = AnalysisExecutor(id="analysis", app_context=app_context)
        message = Analysis_TaskParam(
            process_id="p1",
            container_name="c1",
            source_file_folder="p1/source",
            workspace_file_folder="p1/workspace",
            output_file_folder="p1/output",
        )

        await executor.handle_execute(message, ctx)  # type: ignore[arg-type]

        assert telemetry.transitions == [("p1", "analysis", "start")]
        assert len(ctx.sent) == 1
        assert len(ctx.yielded) == 0
        assert isinstance(ctx.sent[0], Analysis_BooleanExtendedResult)

    asyncio.run(_run())


def test_analysis_executor_yields_output_on_hard_termination(monkeypatch):
    async def _run():
        telemetry = _FakeTelemetry()
        app_context = _FakeAppContext(telemetry)
        ctx = _FakeCtx()

        class _FakeOrchestrator:
            def __init__(self, _app_context):
                pass

            async def execute(self, task_param=None):
                return OrchestrationResult(
                    success=True,
                    conversation=[],
                    agent_responses=[],
                    tool_usage={},
                    result=Analysis_BooleanExtendedResult(
                        result=True,
                        is_hard_terminated=True,
                        process_id=task_param.process_id,
                        blocking_issues=["NO_YAML_FILES"],
                    ),
                )

        monkeypatch.setattr(
            "steps.analysis.workflow.analysis_executor.text2art", lambda _s: "ART"
        )
        monkeypatch.setattr(
            "steps.analysis.workflow.analysis_executor.AnalysisOrchestrator",
            _FakeOrchestrator,
        )

        executor = AnalysisExecutor(id="analysis", app_context=app_context)
        message = Analysis_TaskParam(
            process_id="p1",
            container_name="c1",
            source_file_folder="p1/source",
            workspace_file_folder="p1/workspace",
            output_file_folder="p1/output",
        )

        await executor.handle_execute(message, ctx)  # type: ignore[arg-type]

        assert telemetry.transitions == [("p1", "analysis", "start")]
        assert len(ctx.sent) == 0
        assert len(ctx.yielded) == 1
        assert isinstance(ctx.yielded[0], Analysis_BooleanExtendedResult)

    asyncio.run(_run())
