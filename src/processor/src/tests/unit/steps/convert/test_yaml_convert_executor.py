# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio

from libs.agent_framework.groupchat_orchestrator import OrchestrationResult
from steps.convert.models.step_output import Yaml_ExtendedBooleanResult
from steps.convert.workflow.yaml_convert_executor import YamlConvertExecutor
from steps.design.models.step_output import Design_ExtendedBooleanResult


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


def test_yaml_convert_executor_sends_message_on_soft_completion(monkeypatch):
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
                    result=Yaml_ExtendedBooleanResult(
                        result=True,
                        is_hard_terminated=False,
                        process_id=task_param.process_id,
                    ),
                )

        monkeypatch.setattr(
            "steps.convert.workflow.yaml_convert_executor.YamlConvertOrchestrator",
            _FakeOrchestrator,
        )

        executor = YamlConvertExecutor(id="yaml", app_context=app_context)
        message = Design_ExtendedBooleanResult(process_id="p1")
        await executor.handle_execute(message, ctx)  # type: ignore[arg-type]

        assert telemetry.transitions == [("p1", "yaml_conversion", "start")]
        assert len(ctx.sent) == 1
        assert len(ctx.yielded) == 0
        assert isinstance(ctx.sent[0], Yaml_ExtendedBooleanResult)

    asyncio.run(_run())


def test_yaml_convert_executor_yields_output_on_hard_termination(monkeypatch):
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
                    result=Yaml_ExtendedBooleanResult(
                        result=True,
                        is_hard_terminated=True,
                        process_id=task_param.process_id,
                        blocking_issues=["BLOCKED"],
                    ),
                )

        monkeypatch.setattr(
            "steps.convert.workflow.yaml_convert_executor.YamlConvertOrchestrator",
            _FakeOrchestrator,
        )

        executor = YamlConvertExecutor(id="yaml", app_context=app_context)
        message = Design_ExtendedBooleanResult(process_id="p1")
        await executor.handle_execute(message, ctx)  # type: ignore[arg-type]

        assert telemetry.transitions == [("p1", "yaml_conversion", "start")]
        assert len(ctx.sent) == 0
        assert len(ctx.yielded) == 1
        assert isinstance(ctx.yielded[0], Yaml_ExtendedBooleanResult)

    asyncio.run(_run())
