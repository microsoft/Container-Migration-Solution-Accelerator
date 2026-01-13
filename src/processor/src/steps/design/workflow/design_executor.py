from agent_framework import Executor, WorkflowContext, handler

from libs.application.application_context import AppContext
from steps.design.models.step_output import Design_ExtendedBooleanResult
from steps.design.orchestration.design_orchestrator import DesignOrchestrator
from utils.agent_telemetry import TelemetryManager

from ...analysis.models.step_output import Analysis_BooleanExtendedResult


class DesignExecutor(Executor):
    def __init__(self, id: str, app_context: AppContext):
        super().__init__(id=id)
        self.app_context = app_context

    @handler
    async def handle_execute(
        self,
        message: Analysis_BooleanExtendedResult,
        ctx: WorkflowContext[Design_ExtendedBooleanResult],
    ) -> None:
        design_orchestrator = DesignOrchestrator(self.app_context)

        telemetry: TelemetryManager = await self.app_context.get_service_async(
            TelemetryManager
        )
        await telemetry.transition_to_phase(
            process_id=message.process_id, step="design", phase="start"
        )
        result = await design_orchestrator.execute(task_param=message)

        # if not result.success or result.result is None:
        #     await telemetry.record_failure_outcome(
        #         process_id=message.process_id,
        #         failed_step="design",
        #         error_message=result.error or "Design orchestration failed",
        #         failure_details=result.error or "Design orchestration failed",
        #     )
        #     raise Exception(
        #         f"DesignExecutor: {result.error or 'Design orchestration failed'}"
        #     )

        if result.result:
            if not result.result.is_hard_terminated:
                await ctx.send_message(result.result)

                # await telemetry.record_step_result(
                #     process_id=message.process_id,
                #     step_name="design",
                #     step_result=result.result,
                # )
            else:
                # raise Exception(f"DesignExecutor: {result.result.reason}")
                # await telemetry.record_failure_outcome(
                #     process_id=message.process_id,
                #     failed_step="design",
                #     error_message=result.result.reason or "Hard terminated",
                #     failure_details=result.result.reason or "Hard terminated",
                # )
                await ctx.yield_output(result.result)
