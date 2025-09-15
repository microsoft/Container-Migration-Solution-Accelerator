from typing import Any

from libs.base.typed_fastapi import TypedFastAPI
from libs.repositories.process_repository import ProcessRepository
from libs.repositories.process_status_repository import ProcessStatusRepository
from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper
from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper
from libs.services.interfaces import ILoggerService
from routers.models.files import FileInfo
from routers.models.process_agent_activities import ProcessStatusSnapshot
from routers.models.processes import enlist_process_queue_response


class ProcessService:
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

    async def get_all_uploaded_files(self, process_id: str) -> list[FileInfo]:
        """
        Get all uploaded files for a specific process from the source folder.
        Returns files from {process_id}/source/ in blob storage.
        """
        # Get the blob helper service from the application context
        async with self.app.app_context.get_service(
            AsyncStorageBlobHelper
        ) as blob_helper:
            # Ensure the blob helper is initialized
            if not blob_helper:
                raise ValueError("Blob helper service is not available")

            container_name = (
                self.app.app_context.configuration.storage_account_process_container
            )
            if not container_name:
                raise ValueError("Blob storage container name is not configured")

            source_folder_prefix = f"{process_id}/source/"

            try:
                # List all blobs with the source folder prefix
                blob_list = await blob_helper.list_blobs(
                    container_name=container_name, prefix=source_folder_prefix
                )

                uploaded_files = []
                for blob in blob_list:
                    # Extract filename from blob path (remove the folder prefix)
                    filename = blob["name"].replace(source_folder_prefix, "")

                    if filename:  # Skip empty strings (folder entries)
                        # Get blob properties for content type and size
                        blob_properties = await blob_helper.get_blob_properties(
                            container_name=container_name, blob_name=blob["name"]
                        )

                        # Create FileInfo object (without downloading content for performance)
                        file_info = FileInfo(
                            filename=filename,
                            content=b"",  # Empty content for listing purposes
                            content_type=blob_properties.get(
                                "content_type", "application/octet-stream"
                            ),
                            size=blob_properties.get("size", 0),
                        )
                        uploaded_files.append(file_info)

                self.app.app_context.get_service(ILoggerService).log_info(
                    f"Retrieved {len(uploaded_files)} uploaded files for process {process_id}"
                )

                return uploaded_files

            except Exception as e:
                self.app.app_context.get_service(ILoggerService).log_error(
                    f"Error retrieving uploaded files for process {process_id}: {str(e)}"
                )
                raise

    async def delete_file_from_blob(self, process_id: str, filename: str) -> None:
        """
        Delete a specific file from Azure Blob Storage for a given process.
        Removes the file from {process_id}/source/{filename} in blob storage.
        """
        # Get the blob helper service from the application context
        async with self.app.app_context.get_service(
            AsyncStorageBlobHelper
        ) as blob_helper:
            # Ensure the blob helper is initialized
            if not blob_helper:
                raise ValueError("Blob helper service is not available")

            container_name = (
                self.app.app_context.configuration.storage_account_process_container
            )
            if not container_name:
                raise ValueError("Blob storage container name is not configured")

            blob_name = f"{process_id}/source/{filename}"

            try:
                # Check if the blob exists before trying to delete
                blob_exists = await blob_helper.blob_exists(
                    container_name=container_name, blob_name=blob_name
                )

                if not blob_exists:
                    raise FileNotFoundError(
                        f"File '{filename}' not found for process '{process_id}'"
                    )

                # Delete the blob
                await blob_helper.delete_blob(
                    container_name=container_name, blob_name=blob_name
                )

                self.app.app_context.get_service(ILoggerService).log_info(
                    f"Deleted file {filename} from process {process_id}"
                )

            except FileNotFoundError:
                # Re-raise FileNotFoundError as is
                raise
            except Exception as e:
                self.app.app_context.get_service(ILoggerService).log_error(
                    f"Error deleting file {filename} from process {process_id}: {str(e)}"
                )
                raise

    async def delete_all_files_from_blob(self, process_id: str) -> int:
        """
        Delete all files from Azure Blob Storage for a given process.
        Removes all files from {process_id}/source/ folder in blob storage.
        Returns the count of deleted files.
        """
        # Get the blob helper service from the application context
        async with self.app.app_context.get_service(
            AsyncStorageBlobHelper
        ) as blob_helper:
            # Ensure the blob helper is initialized
            if not blob_helper:
                raise ValueError("Blob helper service is not available")

            container_name = (
                self.app.app_context.configuration.storage_account_process_container
            )
            if not container_name:
                raise ValueError("Blob storage container name is not configured")

            source_folder_prefix = f"{process_id}/source/"

            try:
                # List all blobs with the source folder prefix
                blob_list = await blob_helper.list_blobs(
                    container_name=container_name, prefix=source_folder_prefix
                )

                deleted_count = 0
                for blob in blob_list:
                    # Extract filename from blob path (remove the folder prefix)
                    filename = blob["name"].replace(source_folder_prefix, "")

                    if filename:  # Skip empty strings (folder entries)
                        try:
                            # Delete the blob
                            await blob_helper.delete_blob(
                                container_name=container_name, blob_name=blob["name"]
                            )
                            deleted_count += 1

                            self.app.app_context.get_service(ILoggerService).log_info(
                                f"Deleted file {filename} from process {process_id}"
                            )
                        except Exception as e:
                            self.app.app_context.get_service(ILoggerService).log_error(
                                f"Error deleting file {filename} from process {process_id}: {str(e)}"
                            )
                            # Continue with other files even if one fails

                self.app.app_context.get_service(ILoggerService).log_info(
                    f"Deleted {deleted_count} files from process {process_id}"
                )

                return deleted_count

            except Exception as e:
                self.app.app_context.get_service(ILoggerService).log_error(
                    f"Error deleting all files from process {process_id}: {str(e)}"
                )
                raise

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
            # print(f"🔍 DEBUG: queue name: '{queue_name}' (type: {type(queue_name)})")
            # Enlist files into the queue
            await queue_service.send_message(
                queue_name=self.app.app_context.configuration.storage_account_process_queue,
                content=queue_message.to_base64(),
                time_to_live=60,
            )

    async def get_current_process(
        self, process_id: str
    ) -> ProcessStatusSnapshot | None:
        """
        Get the current status of the process with the given process ID.
        """
        # Get the process status repository from the application context
        async with self.app.app_context.create_scope() as scope:
            process_status_repo = scope.get_service(ProcessStatusRepository)
            return await process_status_repo.get_process_status_by_process_id(
                process_id
            )

    async def render_current_process(self, process_id: str) -> list[str]:
        """
        Render the current status of the process with the given process ID.
        """
        # Get the process status repository from the application context
        async with self.app.app_context.create_scope() as scope:
            process_status_repo = scope.get_service(ProcessStatusRepository)
            return await process_status_repo.render_agent_status(process_id)

    async def get_converted_files(self, process_id: str) -> list[FileInfo]:
        """
        Get all converted files for a specific process from the converted folder.
        Returns files from {process_id}/converted/ in blob storage.
        """
        # Get the blob helper service from the application context
        async with self.app.app_context.get_service(
            AsyncStorageBlobHelper
        ) as blob_helper:
            # Ensure the blob helper is initialized
            if not blob_helper:
                raise ValueError("Blob helper service is not available")

            container_name = (
                self.app.app_context.configuration.storage_account_process_container
            )
            if not container_name:
                raise ValueError("Blob storage container name is not configured")

            converted_folder_prefix = f"{process_id}/converted/"

            try:
                # List all blobs with the converted folder prefix
                blob_list = await blob_helper.list_blobs(
                    container_name=container_name, prefix=converted_folder_prefix
                )

                converted_files = []
                for blob in blob_list:
                    # Download blob content
                    blob_content = await blob_helper.download_blob(
                        container_name=container_name, blob_name=blob["name"]
                    )

                    # Extract filename from blob path (remove the folder prefix)
                    filename = blob["name"].replace(converted_folder_prefix, "")

                    # Create FileInfo object
                    file_info = FileInfo(
                        filename=filename,
                        content=blob_content,
                        content_type="application/octet-stream",  # Default content type
                        size=len(blob_content) if blob_content else 0,
                    )
                    converted_files.append(file_info)

                self.app.app_context.get_service(ILoggerService).log_info(
                    f"Retrieved {len(converted_files)} converted files for process {process_id}"
                )

                return converted_files

            except Exception as e:
                self.app.app_context.get_service(ILoggerService).log_error(
                    f"Error retrieving converted files for process {process_id}: {str(e)}"
                )
                raise

    async def get_process_summary(self, process_id: str) -> tuple[Any, list[str]]:
        """
        Get process summary including process details and list of converted file names.
        Returns a tuple of (process_entity, list_of_filenames).
        """
        try:
            # Get process entity from repository
            async with self.app.app_context.create_scope() as scope:
                process_repo = scope.get_service(ProcessRepository)
                process_entity = await process_repo.get_async(process_id)

                if not process_entity:
                    raise ValueError(f"Process {process_id} not found")

            # Get converted file names (without downloading content)
            async with self.app.app_context.get_service(
                AsyncStorageBlobHelper
            ) as blob_helper:
                if not blob_helper:
                    raise ValueError("Blob helper service is not available")

                container_name = (
                    self.app.app_context.configuration.storage_account_process_container
                )
                if not container_name:
                    raise ValueError("Blob storage container name is not configured")

                converted_folder_prefix = f"{process_id}/converted/"

                # List all blobs with the converted folder prefix (without downloading content)
                blob_list = await blob_helper.list_blobs(
                    container_name=container_name, prefix=converted_folder_prefix
                )

                # Extract filenames from blob paths
                filenames = []
                for blob in blob_list:
                    filename = blob["name"].replace(converted_folder_prefix, "")
                    if filename:  # Skip empty strings (folder entries)
                        filenames.append(filename)

                self.app.app_context.get_service(ILoggerService).log_info(
                    f"Retrieved summary for process {process_id}: {len(filenames)} files"
                )

                return process_entity, filenames

        except Exception as e:
            self.app.app_context.get_service(ILoggerService).log_error(
                f"Error retrieving process summary for process {process_id}: {str(e)}"
            )
            raise

    async def get_converted_file_content(self, process_id: str, filename: str) -> str:
        """
        Get the content of a specific converted file for a process.
        Returns the file content as a string from {process_id}/converted/{filename}.
        """
        # Get the blob helper service from the application context
        async with self.app.app_context.get_service(
            AsyncStorageBlobHelper
        ) as blob_helper:
            # Ensure the blob helper is initialized
            if not blob_helper:
                raise ValueError("Blob helper service is not available")

            container_name = (
                self.app.app_context.configuration.storage_account_process_container
            )
            if not container_name:
                raise ValueError("Blob storage container name is not configured")

            blob_name = f"{process_id}/converted/{filename}"

            try:
                # Download the specific file content
                blob_content = await blob_helper.download_blob(
                    container_name=container_name, blob_name=blob_name
                )

                # Convert bytes to string (assuming text files)
                if blob_content:
                    content = blob_content.decode("utf-8")
                else:
                    content = ""

                self.app.app_context.get_service(ILoggerService).log_info(
                    f"Retrieved file content for {filename} in process {process_id}"
                )

                return content

            except Exception as e:
                self.app.app_context.get_service(ILoggerService).log_error(
                    f"Error retrieving file content for {filename} in process {process_id}: {str(e)}"
                )
                raise
