# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio

from libs.agent_framework.groupchat_orchestrator import OrchestrationResult
from steps.convert.models.step_output import Yaml_ExtendedBooleanResult
from steps.documentation.models.step_output import Documentation_ExtendedBooleanResult
from steps.documentation.workflow.documentation_executor import DocumentationExecutor


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
        self.yielded: list[object] = []

    async def yield_output(self, output):
        self.yielded.append(output)


def test_documentation_executor_yields_output(monkeypatch):
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
                    result=Documentation_ExtendedBooleanResult(
                        result=True,
                        process_id=task_param.process_id,
                    ),
                )

        monkeypatch.setattr(
            "steps.documentation.workflow.documentation_executor.DocumentationOrchestrator",
            _FakeOrchestrator,
        )

        executor = DocumentationExecutor(id="documentation", app_context=app_context)
        message = Yaml_ExtendedBooleanResult(process_id="p1")
        await executor.handle_execute(message, ctx)  # type: ignore[arg-type]

        assert telemetry.transitions == [("p1", "documentation", "start")]
        assert len(ctx.yielded) == 1
        assert isinstance(ctx.yielded[0], Documentation_ExtendedBooleanResult)

    asyncio.run(_run())
