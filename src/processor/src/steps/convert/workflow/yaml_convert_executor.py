# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Workflow executor for the YAML conversion step."""

from agent_framework import Executor, WorkflowContext, handler

from libs.application.application_context import AppContext
from utils.agent_telemetry import TelemetryManager

from ...design.models.step_output import Design_ExtendedBooleanResult
from ..models.step_output import Yaml_ExtendedBooleanResult
from ..orchestration.yaml_convert_orchestrator import YamlConvertOrchestrator


class YamlConvertExecutor(Executor):
    """Workflow executor that runs the YAML conversion orchestrator."""

    def __init__(self, id: str, app_context: AppContext):
        """Create a new YAML conversion executor bound to an application context."""
        super().__init__(id=id)
        self.app_context = app_context

    @handler
    async def handle_execute(
        self,
        message: Design_ExtendedBooleanResult,
        ctx: WorkflowContext[Yaml_ExtendedBooleanResult],
    ) -> None:
        """Execute YAML conversion for the given workflow message."""
        yaml_convert_orchestrator = YamlConvertOrchestrator(self.app_context)

        telemetry: TelemetryManager = await self.app_context.get_service_async(
            TelemetryManager
        )
        await telemetry.transition_to_phase(
            process_id=message.process_id, step="yaml", phase="YAML"
        )

        result = await yaml_convert_orchestrator.execute(task_param=message)

        if not result.success or result.result is None:
            error_msg = (
                result.error or "YAML conversion orchestration failed with no output"
            )
            raise Exception(f"YamlConvertExecutor failed: {error_msg}")

        if result.result:
            if not result.result.is_hard_terminated:
                await ctx.send_message(result.result)

                # await telemetry.record_step_result(
                #     process_id=message.process_id,
                #     step_name="yaml_conversion",
                #     step_result=result.result,
                # )
            else:
                # raise Exception(f"YamlConvertExecutor: {result.result.reason}")
                # await telemetry.record_failure_outcome(
                #     process_id=message.process_id,
                #     failed_step="yaml_conversion",
                #     error_message=result.result.reason or "Hard terminated",
                #     failure_details=result.result.reason or "Hard terminated",
                # )
                await ctx.yield_output(result.result)
