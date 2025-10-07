#!/usr/bin/env python3
"""
Asynchronous Azure Storage Blob Helper

This module provides an asynchronous version of the StorageBlobHelper class
for high-performance, non-blocking blob operations.
"""

import asyncio
import logging
import aiofiles
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

from azure.storage.blob.aio import BlobServiceClient
from azure.storage.blob import ContentSettings
from azure.identity.aio import DefaultAzureCredential
from azure.core.exceptions import (
    ResourceNotFoundError,
    ResourceExistsError,
)

from ..shared_config import get_config
from .config import create_config


class AsyncStorageBlobHelper:
    """
    Asynchronous Azure Storage Blob Helper Class

    Provides high-performance, non-blocking operations for Azure Blob Storage
    with support for concurrent operations and batch processing.
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        account_name: Optional[str] = None,
        credential: Optional[Any] = None,
        config: Optional[Union[Dict, Any]] = None,
    ):
        """
        Initialize the AsyncStorageBlobHelper

        Args:
            connection_string: Azure Storage connection string (preferred for development)
            account_name: Storage account name (for managed identity)
            credential: Azure credential (DefaultAzureCredential for production)
            config: Configuration object or dictionary for custom settings
        """
        # Set up configuration
        if config:
            if isinstance(config, dict):
                self.config = create_config(config)
            else:
                self.config = config
        else:
            self.config = get_config()

        # Set up logging
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=getattr(logging, self.config.get("logging_level", "INFO"))
        )

        self._connection_string = connection_string  # Store for SAS token generation
        self._account_name = account_name
        self._credential = credential
        self._blob_service_client = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self._initialize_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def _initialize_client(self):
        """Initialize the async blob service client"""
        try:
            if self._connection_string:
                self._blob_service_client = BlobServiceClient.from_connection_string(
                    self._connection_string
                )
            elif self._account_name and self._credential:
                account_url = f"https://{self._account_name}.blob.core.windows.net"
                self._blob_service_client = BlobServiceClient(
                    account_url, credential=self._credential
                )
            elif self._account_name:
                # Use DefaultAzureCredential for managed identity
                account_url = f"https://{self._account_name}.blob.core.windows.net"
                self._blob_service_client = BlobServiceClient(
                    account_url, credential=DefaultAzureCredential()
                )
            else:
                raise ValueError(
                    "Either connection_string or account_name must be provided"
                )

        except Exception as e:
            self.logger.error(f"Failed to initialize BlobServiceClient: {e}")
            raise

    async def close(self):
        """Close the blob service client"""
        if self._blob_service_client:
            await self._blob_service_client.close()

    @property
    def blob_service_client(self):
        """Get the blob service client, initializing if needed"""
        if self._blob_service_client is None:
            raise RuntimeError(
                "Client not initialized. Use 'async with AsyncStorageBlobHelper(...) as helper:' or call await helper._initialize_client()"
            )
        return self._blob_service_client

    # Container Operations
    async def create_container(
        self,
        container_name: str,
        public_access: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Create a new container asynchronously

        Args:
            container_name: Name of the container
            public_access: Public access level ('container' or 'blob')
            metadata: Optional metadata dictionary

        Returns:
            bool: True if created successfully, False if already exists
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            await container_client.create_container(
                public_access=public_access, metadata=metadata
            )
            self.logger.info(f"Container '{container_name}' created successfully")
            return True
        except ResourceExistsError:
            self.logger.warning(f"Container '{container_name}' already exists")
            return False
        except Exception as e:
            self.logger.error(f"Failed to create container '{container_name}': {e}")
            raise

    async def delete_container(
        self, container_name: str, force_delete: bool = False
    ) -> bool:
        """
        Delete a container asynchronously

        Args:
            container_name: Name of the container to delete
            force_delete: If True, deletes all blobs in the container first.
                         If False and container has blobs, deletion will fail.

        Returns:
            bool: True if deleted successfully

        Raises:
            Exception: If container contains blobs and force_delete is False,
                      or if there are other deletion errors
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )

            # Check if container has blobs when force_delete is False
            if not force_delete:
                blob_count = 0
                self.logger.info(
                    f"Checking if container '{container_name}' is empty..."
                )

                async for blob in container_client.list_blobs():
                    blob_count += 1
                    break  # Just need to know if there are any blobs

                if blob_count > 0:
                    self.logger.error(
                        f"Container '{container_name}' contains blobs. "
                        f"Use force_delete=True to delete all blobs first, or manually empty the container."
                    )
                    raise ValueError(
                        f"Container '{container_name}' is not empty. "
                        f"Set force_delete=True to delete all blobs first."
                    )

            if force_delete:
                # First, check if container has any blobs
                blob_count = 0
                self.logger.info(
                    f"Checking for blobs in container '{container_name}'..."
                )

                async for blob in container_client.list_blobs():
                    blob_count += 1
                    break  # Just need to know if there are any blobs

                if blob_count > 0:
                    self.logger.info(
                        f"Container '{container_name}' contains blobs. Deleting all blobs first..."
                    )

                    # Delete all blobs in the container
                    deleted_blobs = []
                    async for blob in container_client.list_blobs():
                        try:
                            blob_client = container_client.get_blob_client(blob.name)
                            await blob_client.delete_blob()
                            deleted_blobs.append(blob.name)
                            self.logger.debug(f"Deleted blob: {blob.name}")
                        except Exception as blob_error:
                            self.logger.error(
                                f"Failed to delete blob '{blob.name}': {blob_error}"
                            )
                            # Continue with other blobs even if one fails

                    self.logger.info(
                        f"Deleted {len(deleted_blobs)} blobs from container '{container_name}'"
                    )
                else:
                    self.logger.info(f"Container '{container_name}' is already empty")

            # Now delete the container
            await container_client.delete_container()
            self.logger.info(f"Container '{container_name}' deleted successfully")
            return True

        except ResourceNotFoundError:
            self.logger.warning(f"Container '{container_name}' not found")
            return False
        except Exception as e:
            # Check if the error is due to container having blobs
            error_message = str(e).lower()
            if (
                "container has blobs" in error_message
                or "container being deleted" in error_message
            ):
                if not force_delete:
                    self.logger.error(
                        f"Container '{container_name}' contains blobs. "
                        f"Use force_delete=True to delete all blobs first, or manually empty the container."
                    )
                    raise ValueError(
                        f"Container '{container_name}' is not empty. "
                        f"Set force_delete=True to delete all blobs first."
                    )
                else:
                    # This shouldn't happen if force_delete worked correctly
                    self.logger.error(
                        f"Failed to delete container '{container_name}' even after force deletion: {e}"
                    )
            else:
                self.logger.error(f"Failed to delete container '{container_name}': {e}")
            raise

    async def container_exists(self, container_name: str) -> bool:
        """
        Check if a container exists asynchronously

        Args:
            container_name: Name of the container

        Returns:
            bool: True if container exists
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            await container_client.get_container_properties()
            return True
        except ResourceNotFoundError:
            return False
        except Exception as e:
            self.logger.error(f"Error checking container existence: {e}")
            raise

    async def list_containers(self) -> List[Dict[str, Any]]:
        """
        List all containers asynchronously

        Returns:
            List[Dict]: List of container information
        """
        try:
            containers = []
            async for container in self.blob_service_client.list_containers(
                include_metadata=True
            ):
                containers.append(
                    {
                        "name": container.name,
                        "last_modified": container.last_modified,
                        "metadata": container.metadata or {},
                        "lease": container.lease,
                        "public_access": container.public_access,
                    }
                )
            return containers
        except Exception as e:
            self.logger.error(f"Failed to list containers: {e}")
            raise

    # Blob Operations
    async def upload_blob(
        self,
        container_name: str,
        blob_name: str,
        data: Union[bytes, str],
        overwrite: bool = False,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        max_concurrency: int = 4,
    ) -> dict[str, Any]:
        """
        Upload data to a blob asynchronously

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            data: Data to upload (bytes or string)
            overwrite: Whether to overwrite existing blob
            content_type: Content type of the blob
            metadata: Optional metadata dictionary
            max_concurrency: Maximum concurrent connections

        Returns:
            bool: True if uploaded successfully
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)

            # Convert string to bytes if needed
            if isinstance(data, str):
                data = data.encode("utf-8")

            # Auto-detect content type if not provided
            if content_type is None:
                content_type = self._get_content_type(blob_name)

            # Create ContentSettings object if content_type is provided
            content_settings = None
            if content_type:
                content_settings = ContentSettings(content_type=content_type)

            upload_result = await blob_client.upload_blob(
                data,
                overwrite=overwrite,
                content_settings=content_settings,
                metadata=metadata,
                max_concurrency=max_concurrency,
            )

            self.logger.info(f"Blob '{blob_name}' uploaded successfully")
            return upload_result
        except Exception as e:
            self.logger.error(f"Failed to upload blob '{blob_name}': {e}")
            raise

    async def download_blob(self, container_name: str, blob_name: str) -> bytes:
        """
        Download a blob asynchronously

        Args:
            container_name: Name of the container
            blob_name: Name of the blob

        Returns:
            bytes: Blob content
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)

            download_stream = await blob_client.download_blob()
            return await download_stream.readall()
        except Exception as e:
            self.logger.error(f"Failed to download blob '{blob_name}': {e}")
            raise

    async def download_blob_to_file(
        self,
        container_name: str,
        blob_name: str,
        destination_file_path: str,
    ) -> bool:
        """
        Download a blob to a file asynchronously

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            file_path: Path to the local file

        Returns:
            bool: True if downloaded successfully
        """
        try:
            blob_data = await self.download_blob(container_name, blob_name)
            async with aiofiles.open(destination_file_path, "wb") as file:
                await file.write(blob_data)
            self.logger.info(
                f"Blob '{blob_name}' downloaded to file '{destination_file_path}'"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to download blob '{blob_name}' to file '{destination_file_path}': {e}"
            )
            raise

    async def upload_blob_from_text(
        self, container_name: str, blob_name: str, text: str
    ) -> bool:
        """
        Upload a text string as a blob asynchronously

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            text: Text content to upload

        Returns:
            bool: True if uploaded successfully
        """
        try:
            # Convert text to bytes
            data = text.encode("utf-8")
            return await self.upload_blob(
                container_name, blob_name, data, content_type="text/plain"
            )
        except Exception as e:
            self.logger.error(f"Failed to upload text blob '{blob_name}': {e}")
            raise

    async def upload_file(
        self,
        container_name: str,
        blob_name: str,
        file_path: str,
        overwrite: bool = False,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        max_concurrency: int = 4,
    ) -> bool:
        """
        Upload a file to blob storage asynchronously

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            file_path: Path to the local file
            overwrite: Whether to overwrite existing blob
            content_type: Content type of the blob
            metadata: Optional metadata dictionary
            max_concurrency: Maximum concurrent connections

        Returns:
            bool: True if uploaded successfully
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)

            # Auto-detect content type if not provided
            if content_type is None:
                content_type = self._get_content_type(file_path)

            # Create ContentSettings object if content_type is provided
            content_settings = None
            if content_type:
                content_settings = ContentSettings(content_type=content_type)

            async with aiofiles.open(file_path, "rb") as file:
                await blob_client.upload_blob(
                    file,
                    overwrite=overwrite,
                    content_settings=content_settings,
                    metadata=metadata,
                    max_concurrency=max_concurrency,
                )

            self.logger.info(f"File '{file_path}' uploaded as blob '{blob_name}'")
            return True
        except Exception as e:
            self.logger.error(f"Failed to upload file '{file_path}': {e}")
            raise

    async def download_file(
        self, container_name: str, blob_name: str, file_path: str
    ) -> bool:
        """
        Download a blob to a file asynchronously

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            file_path: Path to save the file

        Returns:
            bool: True if downloaded successfully
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)

            # Ensure directory exists
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)

            download_stream = await blob_client.download_blob()
            async with aiofiles.open(file_path, "wb") as file:
                async for chunk in download_stream.chunks():
                    await file.write(chunk)

            self.logger.info(f"Blob '{blob_name}' downloaded to '{file_path}'")
            return True
        except Exception as e:
            self.logger.error(f"Failed to download blob '{blob_name}': {e}")
            raise

    async def blob_exists(self, container_name: str, blob_name: str) -> bool:
        """
        Check if a blob exists asynchronously

        Args:
            container_name: Name of the container
            blob_name: Name of the blob

        Returns:
            bool: True if blob exists
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)
            await blob_client.get_blob_properties()
            return True
        except ResourceNotFoundError:
            return False
        except Exception as e:
            self.logger.error(f"Error checking blob existence: {e}")
            raise

    async def delete_blob(self, container_name: str, blob_name: str) -> bool:
        """
        Delete a blob asynchronously

        Args:
            container_name: Name of the container
            blob_name: Name of the blob

        Returns:
            bool: True if deleted successfully
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)
            await blob_client.delete_blob()
            self.logger.info(f"Blob '{blob_name}' deleted successfully")
            return True
        except ResourceNotFoundError:
            self.logger.warning(f"Blob '{blob_name}' not found")
            return False
        except Exception as e:
            self.logger.error(f"Failed to delete blob '{blob_name}': {e}")
            raise

    async def list_blobs(
        self, container_name: str, prefix: str = "", include_metadata: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List blobs in a container asynchronously

        Args:
            container_name: Name of the container
            prefix: Prefix to filter blobs
            include_metadata: Whether to include metadata

        Returns:
            List[Dict]: List of blob information
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )

            blobs = []
            async for blob in container_client.list_blobs(
                name_starts_with=prefix,
                include=["metadata"] if include_metadata else None,
            ):
                blob_info = {
                    "name": blob.name,
                    "size": blob.size,
                    "last_modified": blob.last_modified,
                    "etag": blob.etag,
                    "content_type": (
                        getattr(blob.content_settings, "content_type", None)
                        if blob.content_settings
                        else None
                    ),
                    "blob_tier": getattr(blob, "blob_tier", None),
                    "blob_type": str(blob.blob_type) if blob.blob_type else None,
                }

                if include_metadata and blob.metadata:
                    blob_info["metadata"] = blob.metadata

                blobs.append(blob_info)

            return blobs
        except Exception as e:
            self.logger.error(f"Failed to list blobs: {e}")
            raise

    # Batch Operations
    async def upload_multiple_files(
        self,
        container_name: str,
        file_paths: List[str],
        blob_prefix: str = "",
        overwrite: bool = False,
        max_concurrency: int = 4,
    ) -> Dict[str, bool]:
        """
        Upload multiple files concurrently

        Args:
            container_name: Name of the container
            file_paths: List of local file paths
            blob_prefix: Prefix for blob names
            overwrite: Whether to overwrite existing blobs
            max_concurrency: Maximum concurrent uploads

        Returns:
            Dict[str, bool]: Mapping of file paths to upload success status
        """
        semaphore = asyncio.Semaphore(max_concurrency)

        async def upload_single_file(file_path: str) -> tuple[str, bool]:
            async with semaphore:
                try:
                    blob_name = blob_prefix + Path(file_path).name
                    success = await self.upload_file(
                        container_name, blob_name, file_path, overwrite=overwrite
                    )
                    return file_path, success
                except Exception as e:
                    self.logger.error(f"Failed to upload {file_path}: {e}")
                    return file_path, False

        # Execute uploads concurrently
        tasks = [upload_single_file(file_path) for file_path in file_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        upload_results = {}
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Upload task failed: {result}")
                continue
            file_path, success = result
            upload_results[file_path] = success

        return upload_results

    async def download_multiple_blobs(
        self,
        container_name: str,
        blob_names: List[str],
        download_dir: str,
        max_concurrency: int = 4,
    ) -> Dict[str, bool]:
        """
        Download multiple blobs concurrently

        Args:
            container_name: Name of the container
            blob_names: List of blob names to download
            download_dir: Directory to save downloaded files
            max_concurrency: Maximum concurrent downloads

        Returns:
            Dict[str, bool]: Mapping of blob names to download success status
        """
        semaphore = asyncio.Semaphore(max_concurrency)

        async def download_single_blob(blob_name: str) -> tuple[str, bool]:
            async with semaphore:
                try:
                    file_path = Path(download_dir) / blob_name
                    success = await self.download_file(
                        container_name, blob_name, str(file_path)
                    )
                    return blob_name, success
                except Exception as e:
                    self.logger.error(f"Failed to download {blob_name}: {e}")
                    return blob_name, False

        # Execute downloads concurrently
        tasks = [download_single_blob(blob_name) for blob_name in blob_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        download_results = {}
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Download task failed: {result}")
                continue
            blob_name, success = result
            download_results[blob_name] = success

        return download_results

    # Utility methods
    def _get_content_type(self, filename: str) -> str:
        """
        Get content type based on file extension

        Args:
            filename: Name of the file

        Returns:
            str: Content type
        """
        import mimetypes

        content_type, _ = mimetypes.guess_type(filename)
        return content_type or "application/octet-stream"

    async def get_blob_properties(
        self, container_name: str, blob_name: str
    ) -> Dict[str, Any]:
        """
        Get blob properties asynchronously

        Args:
            container_name: Name of the container
            blob_name: Name of the blob

        Returns:
            Dict: Blob properties
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)
            properties = await blob_client.get_blob_properties()

            return {
                "name": blob_name,
                "size": properties.size,
                "last_modified": properties.last_modified,
                "etag": properties.etag,
                "content_type": (
                    properties.content_settings.content_type
                    if properties.content_settings
                    else None
                ),
                "content_encoding": (
                    properties.content_settings.content_encoding
                    if properties.content_settings
                    else None
                ),
                "metadata": properties.metadata or {},
                "blob_tier": properties.blob_tier,
                "blob_type": str(properties.blob_type),
                "lease_status": properties.lease.status if properties.lease else None,
                "creation_time": properties.creation_time,
            }
        except Exception as e:
            self.logger.error(f"Failed to get blob properties: {e}")
            raise

    async def set_blob_metadata(
        self, container_name: str, blob_name: str, metadata: Dict[str, str]
    ) -> bool:
        """
        Set blob metadata asynchronously

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            metadata: Metadata dictionary

        Returns:
            bool: True if metadata set successfully
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)
            await blob_client.set_blob_metadata(metadata)
            self.logger.info(f"Metadata set for blob '{blob_name}'")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set blob metadata: {e}")
            raise

    # Advanced Features
    async def search_blobs(
        self,
        container_name: str,
        search_term: str,
        search_in_metadata: bool = False,
        case_sensitive: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Search for blobs by name or metadata asynchronously

        Args:
            container_name: Name of the container
            search_term: Term to search for
            search_in_metadata: Whether to search in metadata
            case_sensitive: Whether search is case sensitive

        Returns:
            List[Dict]: List of matching blobs
        """
        try:
            blobs = await self.list_blobs(
                container_name, include_metadata=search_in_metadata
            )

            if not case_sensitive:
                search_term = search_term.lower()

            matching_blobs = []
            for blob in blobs:
                blob_name = blob["name"] if case_sensitive else blob["name"].lower()

                # Search in blob name
                if search_term in blob_name:
                    matching_blobs.append(blob)
                    continue

                # Search in metadata if requested
                if search_in_metadata and "metadata" in blob:
                    metadata_text = " ".join(blob["metadata"].values())
                    if not case_sensitive:
                        metadata_text = metadata_text.lower()

                    if search_term in metadata_text:
                        matching_blobs.append(blob)

            return matching_blobs
        except Exception as e:
            self.logger.error(f"Failed to search blobs: {e}")
            raise

    async def generate_blob_sas_url(
        self,
        container_name: str,
        blob_name: str,
        expiry_hours: int = 24,
        permissions: str = "r",
    ) -> str:
        """
        Generate a SAS URL for blob access asynchronously

        This method supports both account key-based SAS and user delegation SAS tokens.
        When using DefaultAzureCredential or Managed Identity (no account key available),
        it automatically uses user delegation SAS tokens.

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            expiry_hours: Hours until the SAS token expires
            permissions: Permissions string (r=read, w=write, d=delete, l=list)

        Returns:
            SAS URL string

        Raises:
            ValueError: If user delegation key cannot be obtained or if authentication fails
            Exception: For other SAS generation errors
        """
        try:
            from azure.storage.blob import BlobSasPermissions, generate_blob_sas
            from datetime import datetime, timedelta

            account_name = await self._get_account_name()
            if not account_name:
                raise ValueError("Unable to determine storage account name")

            account_key = await self._get_account_key()
            credential_type = await self._get_credential_type()
            expiry_time = datetime.utcnow() + timedelta(hours=expiry_hours)

            # Set permissions
            sas_permissions = BlobSasPermissions(
                read="r" in permissions,
                write="w" in permissions,
                delete="d" in permissions,
                list="l" in permissions,
            )

            if account_key:
                # Use account key-based SAS (traditional method)
                self.logger.info(
                    f"Generating account key-based SAS token for blob '{blob_name}'"
                )
                sas_token = generate_blob_sas(
                    account_name=account_name,
                    container_name=container_name,
                    blob_name=blob_name,
                    account_key=account_key,
                    permission=sas_permissions,
                    expiry=expiry_time,
                )
            else:
                # Use user delegation SAS (works with Azure AD credentials)
                self.logger.info(
                    f"Generating user delegation SAS token for blob '{blob_name}' using {credential_type}"
                )

                # Validate that we have proper Azure AD authentication
                if credential_type == "unknown":
                    raise ValueError(
                        "Cannot generate user delegation SAS: Unable to determine credential type. "
                        "Ensure you're using DefaultAzureCredential, ManagedIdentity, or have proper Azure AD authentication."
                    )

                # Get user delegation key (requires 'Storage Blob Delegator' role)
                # Use a small buffer for start time to account for clock skew
                delegation_key_start_time = datetime.utcnow() - timedelta(minutes=5)
                delegation_key_expiry_time = delegation_key_start_time + timedelta(
                    hours=expiry_hours + 1  # Give extra time for the delegation key
                )

                try:
                    self.logger.debug("Requesting user delegation key from Azure AD")
                    user_delegation_key = (
                        await self.blob_service_client.get_user_delegation_key(
                            key_start_time=delegation_key_start_time,
                            key_expiry_time=delegation_key_expiry_time,
                        )
                    )
                    self.logger.debug("Successfully obtained user delegation key")
                except Exception as e:
                    error_msg = str(e).lower()
                    if "forbidden" in error_msg or "403" in error_msg:
                        raise ValueError(
                            f"Access denied when requesting user delegation key. "
                            f"Ensure the identity ({credential_type}) has the 'Storage Blob Delegator' role "
                            f"assigned at the storage account level. Error: {e}"
                        )
                    elif "unauthorized" in error_msg or "401" in error_msg:
                        raise ValueError(
                            f"Authentication failed when requesting user delegation key. "
                            f"Verify that {credential_type} is properly configured and has valid permissions. Error: {e}"
                        )
                    else:
                        raise ValueError(
                            f"Failed to get user delegation key using {credential_type}. "
                            f"This could be due to missing permissions or network issues. Error: {e}"
                        )

                # Generate user delegation SAS token
                sas_token = generate_blob_sas(
                    account_name=account_name,
                    container_name=container_name,
                    blob_name=blob_name,
                    user_delegation_key=user_delegation_key,
                    permission=sas_permissions,
                    start=delegation_key_start_time,  # Add start time
                    expiry=expiry_time,
                )

            # Construct full URL
            blob_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}"
            sas_url = f"{blob_url}?{sas_token}"

            self.logger.info(
                f"Successfully generated SAS URL for blob '{blob_name}' (expires in {expiry_hours} hours)"
            )
            return sas_url

        except Exception as e:
            self.logger.error(f"Failed to generate SAS URL: {e}")
            raise

    async def generate_container_sas_url(
        self,
        container_name: str,
        expiry_hours: int = 24,
        permissions: str = "rl",
    ) -> str:
        """
        Generate a SAS URL for container access asynchronously

        This method supports both account key-based SAS and user delegation SAS tokens.
        When using DefaultAzureCredential or Managed Identity (no account key available),
        it automatically uses user delegation SAS tokens.

        Args:
            container_name: Name of the container
            expiry_hours: Hours until the SAS token expires
            permissions: Permissions string (r=read, w=write, d=delete, l=list)

        Returns:
            Container SAS URL string

        Raises:
            ValueError: If user delegation key cannot be obtained or if authentication fails
            Exception: For other SAS generation errors
        """
        try:
            from azure.storage.blob import (
                ContainerSasPermissions,
                generate_container_sas,
            )
            from datetime import datetime, timedelta

            account_name = await self._get_account_name()
            if not account_name:
                raise ValueError("Unable to determine storage account name")

            account_key = await self._get_account_key()
            credential_type = await self._get_credential_type()

            # Use a small buffer for start time to account for clock skew
            start_time = datetime.utcnow() - timedelta(minutes=5)
            expiry_time = datetime.utcnow() + timedelta(hours=expiry_hours)

            # Set permissions
            sas_permissions = ContainerSasPermissions(
                read="r" in permissions,
                write="w" in permissions,
                delete="d" in permissions,
                list="l" in permissions,
            )

            if account_key:
                # Use account key-based SAS (traditional method)
                self.logger.info(
                    f"Generating account key-based container SAS token for '{container_name}'"
                )
                sas_token = generate_container_sas(
                    account_name=account_name,
                    container_name=container_name,
                    account_key=account_key,
                    permission=sas_permissions,
                    start=start_time,  # Add start time for account key SAS too
                    expiry=expiry_time,
                )
            else:
                # Use user delegation SAS (works with Azure AD credentials)
                self.logger.info(
                    f"Generating user delegation container SAS token for '{container_name}' using {credential_type}"
                )

                # Validate that we have proper Azure AD authentication
                if credential_type == "unknown":
                    raise ValueError(
                        "Cannot generate user delegation SAS: Unable to determine credential type. "
                        "Ensure you're using DefaultAzureCredential, ManagedIdentity, or have proper Azure AD authentication."
                    )

                # Get user delegation key (requires 'Storage Blob Delegator' role)
                # Use the same start time that we defined earlier for consistency
                delegation_key_expiry_time = start_time + timedelta(
                    hours=expiry_hours + 1  # Give extra time for the delegation key
                )

                try:
                    self.logger.debug("Requesting user delegation key from Azure AD")
                    user_delegation_key = (
                        await self.blob_service_client.get_user_delegation_key(
                            key_start_time=start_time,  # Use consistent start time
                            key_expiry_time=delegation_key_expiry_time,
                        )
                    )
                    self.logger.debug("Successfully obtained user delegation key")
                except Exception as e:
                    error_msg = str(e).lower()
                    if "forbidden" in error_msg or "403" in error_msg:
                        raise ValueError(
                            f"Access denied when requesting user delegation key. "
                            f"Ensure the identity ({credential_type}) has the 'Storage Blob Delegator' role "
                            f"assigned at the storage account level. Error: {e}"
                        )
                    elif "unauthorized" in error_msg or "401" in error_msg:
                        raise ValueError(
                            f"Authentication failed when requesting user delegation key. "
                            f"Verify that {credential_type} is properly configured and has valid permissions. Error: {e}"
                        )
                    else:
                        raise ValueError(
                            f"Failed to get user delegation key using {credential_type}. "
                            f"This could be due to missing permissions or network issues. Error: {e}"
                        )

                # Generate user delegation SAS token
                sas_token = generate_container_sas(
                    account_name=account_name,
                    container_name=container_name,
                    user_delegation_key=user_delegation_key,
                    permission=sas_permissions,
                    start=start_time,  # Use consistent start time
                    expiry=expiry_time,
                )

            # Construct full URL
            container_url = (
                f"https://{account_name}.blob.core.windows.net/{container_name}"
            )
            sas_url = f"{container_url}?{sas_token}"

            self.logger.info(
                f"Successfully generated container SAS URL for '{container_name}' (expires in {expiry_hours} hours)"
            )
            return sas_url

        except Exception as e:
            self.logger.error(f"Failed to generate container SAS URL: {e}")
            raise

    async def _get_account_key(self) -> Optional[str]:
        """Extract account key from connection string or configuration"""
        try:
            # Try to get from connection string
            if hasattr(self.blob_service_client, "credential") and hasattr(
                self.blob_service_client.credential, "account_key"
            ):
                return self.blob_service_client.credential.account_key

            # Try to parse from connection string if stored
            if hasattr(self, "_connection_string") and self._connection_string:
                parts = self._connection_string.split(";")
                for part in parts:
                    if part.startswith("AccountKey="):
                        return part.split("=", 1)[1]

            return None
        except Exception:
            return None

    async def _get_account_name(self) -> str:
        """Extract account name from blob service client"""
        try:
            return self.blob_service_client.account_name
        except Exception:
            return None

    async def _get_credential_type(self) -> str:
        """
        Determine the type of credential being used for authentication

        Returns:
            String description of the credential type for logging and error reporting
        """
        try:
            if (
                not hasattr(self.blob_service_client, "credential")
                or self.blob_service_client.credential is None
            ):
                return "unknown"

            credential = self.blob_service_client.credential
            credential_type = type(credential).__name__

            # Map common credential types to friendly names
            if "StorageSharedKeyCredential" in credential_type:
                return "Storage Account Key"
            elif "DefaultAzureCredential" in credential_type:
                return "DefaultAzureCredential"
            elif "ManagedIdentityCredential" in credential_type:
                return "Managed Identity"
            elif "AzureCliCredential" in credential_type:
                return "Azure CLI"
            elif "EnvironmentCredential" in credential_type:
                return "Environment Variables"
            elif "WorkloadIdentityCredential" in credential_type:
                return "Workload Identity"
            elif "ChainedTokenCredential" in credential_type:
                return "Chained Token Credential"
            else:
                return f"Azure AD ({credential_type})"

        except Exception:
            return "unknown"
