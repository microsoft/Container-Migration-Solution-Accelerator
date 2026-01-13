# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from agent_framework import Executor, WorkflowContext, handler

from libs.application.application_context import AppContext
from utils.agent_telemetry import TelemetryManager

from ...design.models.step_output import Design_ExtendedBooleanResult
from ..models.step_output import Yaml_ExtendedBooleanResult
from ..orchestration.yaml_convert_orchestrator import YamlConvertOrchestrator


class YamlConvertExecutor(Executor):
    def __init__(self, id: str, app_context: AppContext):
        super().__init__(id=id)
        self.app_context = app_context

    @handler
    async def handle_execute(
        self,
        message: Design_ExtendedBooleanResult,
        ctx: WorkflowContext[Yaml_ExtendedBooleanResult],
    ) -> None:
        yaml_convert_orchestrator = YamlConvertOrchestrator(self.app_context)

        telemetry: TelemetryManager = await self.app_context.get_service_async(
            TelemetryManager
        )
        await telemetry.transition_to_phase(
            process_id=message.process_id, step="yaml_conversion", phase="start"
        )

        result = await yaml_convert_orchestrator.execute(task_param=message)

        # if not result.success or result.result is None:
        #     await telemetry.record_failure_outcome(
        #         process_id=message.process_id,
        #         failed_step="yaml_conversion",
        #         error_message=result.error or "YAML conversion orchestration failed",
        #         failure_details=result.error or "YAML conversion orchestration failed",
        #     )
        #     raise Exception(
        #         f"YamlConvertExecutor: {result.error or 'YAML conversion orchestration failed'}"
        #     )

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
