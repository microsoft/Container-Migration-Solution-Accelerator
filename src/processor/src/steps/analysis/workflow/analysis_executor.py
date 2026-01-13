from agent_framework import Executor, WorkflowContext, handler
from art import text2art

from libs.application.application_context import AppContext
from utils.agent_telemetry import TelemetryManager

from ..models.step_output import Analysis_BooleanExtendedResult
from ..models.step_param import Analysis_TaskParam
from ..orchestration.analysis_orchestrator import AnalysisOrchestrator


class AnalysisExecutor(Executor):
    def __init__(self, id: str, app_context: AppContext):
        super().__init__(id=id)
        self.app_context = app_context

    @handler
    async def handle_execute(
        self,
        message: Analysis_TaskParam,
        ctx: WorkflowContext[Analysis_BooleanExtendedResult],
    ) -> None:
        analysis_orchestrator = AnalysisOrchestrator(self.app_context)

        #######################################################################################################
        # Start to logging the process
        # Due to the bug, first Executor's ExecutorInvokedEvent is not fired so I had to put it here
        #########################################################################################################
        print("Executor invoked (analysis)")
        telemetry: TelemetryManager = await self.app_context.get_service_async(
            TelemetryManager
        )
        await telemetry.transition_to_phase(
            process_id=message.process_id, step="analysis", phase="start"
        )

        print(text2art("Analysis"))
        #######################################################################################################

        result = await analysis_orchestrator.execute(task_param=message)

        if result.result:
            if not result.result.is_hard_terminated:
                await ctx.send_message(result.result)

            else:
                await ctx.yield_output(result.result)
