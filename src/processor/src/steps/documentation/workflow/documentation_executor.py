# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing_extensions import Never

from agent_framework import Executor, WorkflowContext, handler
from libs.application.application_context import AppContext
from steps.convert.models.step_output import Yaml_ExtendedBooleanResult
from steps.documentation.models.step_output import Documentation_ExtendedBooleanResult
from steps.documentation.orchestration.documentation_orchestrator import (
    DocumentationOrchestrator,
)
from utils.agent_telemetry import TelemetryManager


class DocumentationExecutor(Executor):
    def __init__(self, id: str, app_context: AppContext):
        super().__init__(id=id)
        self.app_context = app_context

    @handler
    async def handle_execute(
        self,
        message: Yaml_ExtendedBooleanResult,
        ctx: WorkflowContext[Never, Documentation_ExtendedBooleanResult],
    ) -> Never:
        documentation_orchestrator = DocumentationOrchestrator(self.app_context)

        telemetry: TelemetryManager = await self.app_context.get_service_async(
            TelemetryManager
        )
        await telemetry.transition_to_phase(
            process_id=message.process_id, step="documentation", phase="start"
        )

        result = await documentation_orchestrator.execute(task_param=message)

        # if result.result is None:
        #     await telemetry.record_failure_outcome(
        #         process_id=message.process_id,
        #         failed_step="documentation",
        #         error_message=result.error or "No result",
        #         failure_details=result.error or "No result",
        #     )
        #     raise Exception(f"DocumentationExecutor: {result.error or 'No result'}")

        # await telemetry.record_step_result(
        #     process_id=message.process_id,
        #     step_name="documentation",
        #     step_result=result.result,
        # )

        # await telemetry.update_process_status(
        #     process_id=message.process_id, status="completed"
        # )

        await ctx.yield_output(result.result)
