# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
import os

from libs.agent_framework.agent_framework_helper import AgentFrameworkHelper
from libs.agent_framework.mem0_async_memory import Mem0AsyncMemoryManager
from libs.agent_framework.middlewares import (
    DebuggingMiddleware,
    InputObserverMiddleware,
    LoggingFunctionMiddleware,
)
from libs.base.application_base import ApplicationBase
from steps.analysis.models.step_param import Analysis_TaskParam
from steps.migration_processor import MigrationProcessor
from utils.agent_telemetry import TelemetryManager


class Application(ApplicationBase):
    """
    Application class that extends the base application class.
    This class can be used to implement specific application logic.
    """

    def __init__(self):
        super().__init__(env_file_path=os.path.join(os.path.dirname(__file__), ".env"))

    def initialize(self):
        """
        Initialize the application.
        This method can be overridden by subclasses to perform any necessary setup.
        """
        print(
            "Application initialized with configuration:",
            self.application_context.configuration,
        )

        self.register_services()

    def register_services(self):
        # Additional initialization logic can be added here
        # Initialize AgentFrameworkHelper and add it to the application context
        self.application_context.add_singleton(
            AgentFrameworkHelper, AgentFrameworkHelper()
        )
        # Initialize AgentFrameworkHelper with LLM settings from application context
        self.application_context.get_service(AgentFrameworkHelper).initialize(
            self.application_context.llm_settings
        )

        # Initialize middlewares - All Middlewares below are registered as a singleton
        # -------------------------------------------------------------------------
        # InputObserverMiddleware(Agent Level)
        # LoggingFunctionMiddleware(Agent Level)
        # DebuggingMiddleware(Run Level)
        (
            # Register DebuggingMiddleware as a singleton
            self.application_context.add_singleton(
                DebuggingMiddleware, DebuggingMiddleware
            )
            # Register LoggingFunctionMiddleware as a singleton
            .add_singleton(LoggingFunctionMiddleware, LoggingFunctionMiddleware)
            # Register InputObserverMiddleware as a singleton
            .add_singleton(InputObserverMiddleware, InputObserverMiddleware)
            .add_singleton(Mem0AsyncMemoryManager, Mem0AsyncMemoryManager)
            .add_async_singleton(
                TelemetryManager, lambda: TelemetryManager(self.application_context)
            )
            .add_transient(
                MigrationProcessor,
                lambda: MigrationProcessor(app_context=self.application_context),
            )
        )

        # Optional: Cosmos checkpoint storage. This dependency can be version-sensitive
        # (agent_framework exports have changed across versions). If it's unavailable,
        # we skip registration so the app can still run.
        try:
            from libs.agent_framework.cosmos_checkpoint_storage import (
                CosmosCheckpointStorage,
                CosmosWorkflowCheckpointRepository,
            )

            self.application_context.add_singleton(
                CosmosCheckpointStorage,
                lambda: CosmosCheckpointStorage(
                    CosmosWorkflowCheckpointRepository(
                        account_url="https://[your cosmosdb].documents.azure.com:443/",
                        database_name="checkpoints",
                        container_name="workflow_checkpoints",
                    )
                ),
            )
        except Exception as e:
            # Keep it as a print to match the current style of this entrypoint.
            print(
                "[WARN] Cosmos checkpoint storage disabled due to import/config error:",
                e,
            )

    async def run(self):
        """
        Run the application logic.
        This method should be implemented by subclasses to define the application's behavior.
        """
        migration_processor = self.application_context.get_service(MigrationProcessor)
        input_data = Analysis_TaskParam(
            process_id="e7fc15e2-13c9-4587-b8ed-6f3015990229",
            container_name="processes",
            source_file_folder="e7fc15e2-13c9-4587-b8ed-6f3015990229/source",
            output_file_folder="e7fc15e2-13c9-4587-b8ed-6f3015990229/converted",
            workspace_file_folder="e7fc15e2-13c9-4587-b8ed-6f3015990229/workspace",
        )
        await migration_processor.run(input_data=input_data)


async def main():
    app = Application()
    app.initialize()
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
