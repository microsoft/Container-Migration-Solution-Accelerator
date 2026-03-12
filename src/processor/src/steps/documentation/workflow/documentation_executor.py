# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Workflow executor for the documentation step."""

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
    """Workflow executor that runs documentation and yields the final output."""

    def __init__(self, id: str, app_context: AppContext):
        """Create a new documentation executor bound to an application context."""
        super().__init__(id=id)
        self.app_context = app_context

    @handler
    async def handle_execute(
        self,
        message: Yaml_ExtendedBooleanResult,
        ctx: WorkflowContext[Never, Documentation_ExtendedBooleanResult],
    ) -> Never:
        """Execute documentation and yield the terminal workflow output."""
        documentation_orchestrator = DocumentationOrchestrator(self.app_context)

        telemetry: TelemetryManager = await self.app_context.get_service_async(
            TelemetryManager
        )
        await telemetry.transition_to_phase(
            process_id=message.process_id, step="documentation", phase="Documentation"
        )

        result = await documentation_orchestrator.execute(task_param=message)

        if not result.success or result.result is None:
            error_msg = result.error or "Documentation orchestration failed with no output"
            raise Exception(f"DocumentationExecutor failed: {error_msg}")

        await ctx.yield_output(result.result)
