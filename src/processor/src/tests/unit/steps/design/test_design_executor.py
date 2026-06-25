# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio

from libs.agent_framework.groupchat_orchestrator import OrchestrationResult
from steps.analysis.models.step_output import Analysis_BooleanExtendedResult
from steps.design.models.step_output import (
    DesignOutput,
    Design_ExtendedBooleanResult,
    OutputFile,
)
from steps.design.workflow.design_executor import DesignExecutor


def _make_design_output() -> DesignOutput:
    return DesignOutput(
        result="Success",
        summary="ok",
        azure_services=["AKS"],
        architecture_decisions=["use managed identity"],
        outputs=[OutputFile(file="design.md", description="design doc")],
    )


class _FakeTelemetry:
    def __init__(self):
        self.transitions: list[tuple[str, str, str]] = []

    async def transition_to_phase(self, process_id: str, phase: str, step: str):
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


def test_design_executor_sends_message_on_soft_completion(monkeypatch):
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
                    result=Design_ExtendedBooleanResult(
                        result=True,
                        is_hard_terminated=False,
                        process_id=task_param.process_id,
                        termination_output=_make_design_output(),
                    ),
                )

        monkeypatch.setattr(
            "steps.design.workflow.design_executor.DesignOrchestrator",
            _FakeOrchestrator,
        )

        executor = DesignExecutor(id="design", app_context=app_context)
        message = Analysis_BooleanExtendedResult(process_id="p1")
        await executor.handle_execute(message, ctx)  # type: ignore[arg-type]

        assert telemetry.transitions == [("p1", "design", "Design")]
        assert len(ctx.sent) == 1
        assert len(ctx.yielded) == 0
        assert isinstance(ctx.sent[0], Design_ExtendedBooleanResult)

    asyncio.run(_run())


def test_design_executor_yields_output_on_hard_termination(monkeypatch):
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
                    result=Design_ExtendedBooleanResult(
                        result=True,
                        is_hard_terminated=True,
                        process_id=task_param.process_id,
                        blocking_issues=["SOME_BLOCKER"],
                    ),
                )

        monkeypatch.setattr(
            "steps.design.workflow.design_executor.DesignOrchestrator",
            _FakeOrchestrator,
        )

        executor = DesignExecutor(id="design", app_context=app_context)
        message = Analysis_BooleanExtendedResult(process_id="p1")
        await executor.handle_execute(message, ctx)  # type: ignore[arg-type]

        assert telemetry.transitions == [("p1", "design", "Design")]
        assert len(ctx.sent) == 0
        assert len(ctx.yielded) == 1
        assert isinstance(ctx.yielded[0], Design_ExtendedBooleanResult)

    asyncio.run(_run())


def test_design_executor_raises_when_soft_completion_has_no_output(monkeypatch):
    """Soft completion with termination_output=None is incoherent: must raise."""
    async def _run():
        import pytest

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
                    result=Design_ExtendedBooleanResult(
                        result=True,
                        is_hard_terminated=False,
                        process_id=task_param.process_id,
                        reason="agents never produced output",
                    ),
                )

        monkeypatch.setattr(
            "steps.design.workflow.design_executor.DesignOrchestrator",
            _FakeOrchestrator,
        )

        executor = DesignExecutor(id="design", app_context=app_context)
        message = Analysis_BooleanExtendedResult(process_id="p1")

        with pytest.raises(Exception, match="produced no DesignOutput"):
            await executor.handle_execute(message, ctx)  # type: ignore[arg-type]

        assert len(ctx.sent) == 0
        assert len(ctx.yielded) == 0

    asyncio.run(_run())
