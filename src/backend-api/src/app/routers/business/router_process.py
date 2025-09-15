from libs.base.typed_fastapi import TypedFastAPI
from libs.repositories.process_status_repository import ProcessStatusRepository
from libs.sas.storage import AsyncStorageBlobHelper, AsyncStorageQueueHelper
from libs.services.interfaces import ILoggerService

from ..models.files import (
    FileInfo,
)
from ..models.process_agent_activities import ProcessStatusSnapshot
from ..models.processes import (
    enlist_process_queue_response,
)


class business_router_process:
    """
    Router Process class that extends the FastAPI application.
    This class can be used to implement specific router logic.
    """

    def __init__(self, app: TypedFastAPI):
        self.app = app

    async def save_files_to_blob(self, process_id: str, files: list[FileInfo]) -> None:
        """
        Save the provided codes to an Azure Blob Storage.
        """
        # Get the blob helper service from the application context
        async with self.app.app_context.get_service(
            AsyncStorageBlobHelper
        ) as blob_helper:
            # Ensure the blob helper is initialized
            if not blob_helper:
                raise ValueError("Blob helper service is not available")

            # Check if the container exists, if not create it
            if not await blob_helper.container_exists(
                container_name=self.app.app_context.configuration.storage_account_process_container
            ):
                await blob_helper.create_container(
                    container_name=self.app.app_context.configuration.storage_account_process_container
                )
                self.app.app_context.get_service(ILoggerService).log_info(
                    f"Container {self.app.app_context.configuration.storage_account_process_container} created"
                )

            # put logic folder name as a process_id
            for file in files:
                await blob_helper.upload_blob(
                    container_name=self.app.app_context.configuration.storage_account_process_container,
                    blob_name=f"{process_id}/source/{file.filename}",
                    data=file.content,
                )
                self.app.app_context.get_service(ILoggerService).log_info(
                    f"File {file.filename} saved to Azure Blob Storage under process ID {process_id}"
                )

    async def process_enqueue(
        self, queue_message: enlist_process_queue_response
    ) -> None:
        """
        Enlist the provided files into the process queue.
        """
        # Get the queue service from the application context
        async with self.app.app_context.get_service(
            AsyncStorageQueueHelper
        ) as queue_service:
            # Ensure the queue service is initialized
            if not queue_service:
                raise ValueError("Queue service is not available")

            # Check if the queue exists, if not create it
            if not await queue_service.queue_exists(
                queue_name=self.app.app_context.configuration.storage_account_process_queue
            ):
                await queue_service.create_queue(
                    queue_name=self.app.app_context.configuration.storage_account_process_queue
                )
                self.app.app_context.get_service(ILoggerService).log_info(
                    f"Queue {self.app.app_context.configuration.storage_account_process_queue} created"
                )

            # Enlist files into the queue
            await queue_service.send_message(
                queue_name=self.app.app_context.configuration.storage_account_process_queue,
                content=queue_message.to_base64(),
            )

    async def get_current_process_agent_activities(self, process_id: str):
        """
        Get the current agent activities of the process with the given process ID.
        """
        # Get the process status repository from the application context
        async with self.app.app_context.create_scope() as scope:
            process_status_repo = scope.get_service(ProcessStatusRepository)
            return await process_status_repo.get_process_agent_activities_by_process_id(
                process_id
            )

    async def get_current_process(
        self, process_id: str
    ) -> ProcessStatusSnapshot | None:
        """
        Get the current status of the process with the given process ID.
        """
        # Get the process status repository from the application context
        # Need to be updated later. it's just return top 3 status records
        async with self.app.app_context.create_scope() as scope:
            process_status_repo = scope.get_service(ProcessStatusRepository)
            return await process_status_repo.get_process_status_by_process_id(
                process_id
            )

    async def render_process_status(self, process_id: str) -> list[str]:
        """
        Render the status of the process with the given process ID.
        """
        # Get the process status repository from the application context
        async with self.app.app_context.create_scope() as scope:
            process_status_repo = scope.get_service(ProcessStatusRepository)
            return await process_status_repo.render_agent_status(process_id)
