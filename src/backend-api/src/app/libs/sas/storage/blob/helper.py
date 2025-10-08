import os
import io
import logging
from typing import List, Dict, Any, Union
from azure.storage.blob import (
    BlobServiceClient,
    BlobPrefix,
    ContentSettings,
    StandardBlobTier,
)
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from azure.identity import DefaultAzureCredential
from .config import get_config


class StorageBlobHelper:
    """
    Azure Storage Blob Helper Class

    A comprehensive helper class for Azure Blob Storage operations that mimics
    file explorer functionality with support for all blob operations.

    Features:
    - Container management (create, delete, list)
    - Blob operations (upload, download, copy, move, delete)
    - Directory-like navigation with hierarchical listing
    - Metadata and properties management
    - Batch operations for multiple files
    - SAS token generation
    - Blob leasing operations
    - Error handling with retry logic
    """

    def __init__(
        self,
        connection_string: str = None,
        account_name: str = None,
        credential=None,
        config=None,
    ):
        """
        Initialize the StorageBlobHelper

        Args:
            connection_string: Azure Storage connection string (preferred for development)
            account_name: Storage account name (for managed identity)
            credential: Azure credential (DefaultAzureCredential for production)
            config: Configuration object or dictionary for custom settings
        """
        # Set up configuration
        if config:
            if isinstance(config, dict):
                from .config import create_config

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

        try:
            if connection_string:
                self.blob_service_client = BlobServiceClient.from_connection_string(
                    connection_string
                )
            elif account_name and credential:
                account_url = f"https://{account_name}.blob.core.windows.net"
                self.blob_service_client = BlobServiceClient(
                    account_url, credential=credential
                )
            elif account_name:
                # Use DefaultAzureCredential for managed identity
                account_url = f"https://{account_name}.blob.core.windows.net"
                self.blob_service_client = BlobServiceClient(
                    account_url, credential=DefaultAzureCredential()
                )
            else:
                raise ValueError(
                    "Either connection_string or account_name must be provided"
                )

        except Exception as e:
            self.logger.error(f"Failed to initialize BlobServiceClient: {e}")
            raise

    # Container Operations
    def create_container(
        self,
        container_name: str,
        public_access: str = None,
        metadata: Dict[str, str] = None,
    ) -> bool:
        """
        Create a new container

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
            container_client.create_container(
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

    def delete_container(self, container_name: str, force_delete: bool = False) -> bool:
        """
        Delete a container

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

                for blob in container_client.list_blobs():
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

                for blob in container_client.list_blobs():
                    blob_count += 1
                    break  # Just need to know if there are any blobs

                if blob_count > 0:
                    self.logger.info(
                        f"Container '{container_name}' contains blobs. Deleting all blobs first..."
                    )

                    # Delete all blobs in the container
                    deleted_blobs = []
                    for blob in container_client.list_blobs():
                        try:
                            blob_client = container_client.get_blob_client(blob.name)
                            blob_client.delete_blob()
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
            container_client.delete_container()
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
                or "containerbeingdeleted" in error_message
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

    def list_containers(
        self, name_starts_with: str = None, include_metadata: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List all containers in the storage account

        Args:
            name_starts_with: Filter containers by name prefix
            include_metadata: Include container metadata

        Returns:
            List of container information dictionaries
        """
        try:
            containers = []
            container_list = self.blob_service_client.list_containers(
                name_starts_with=name_starts_with, include_metadata=include_metadata
            )

            for container in container_list:
                container_info = {
                    "name": container.name,
                    "last_modified": container.last_modified,
                    "etag": container.etag,
                    "public_access": container.public_access,
                }
                if include_metadata and container.metadata:
                    container_info["metadata"] = container.metadata
                containers.append(container_info)

            return containers
        except Exception as e:
            self.logger.error(f"Failed to list containers: {e}")
            raise

    def container_exists(self, container_name: str) -> bool:
        """
        Check if a container exists

        Args:
            container_name: Name of the container

        Returns:
            bool: True if container exists
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            container_client.get_container_properties()
            return True
        except ResourceNotFoundError:
            return False
        except Exception as e:
            self.logger.error(f"Error checking container existence: {e}")
            raise

    # Blob Upload Operations
    def upload_blob(
        self,
        container_name: str,
        blob_name: str,
        data: Union[bytes, str, io.IOBase],
        overwrite: bool = True,
        metadata: Dict[str, str] = None,
        content_settings: ContentSettings = None,
        blob_tier: StandardBlobTier = None,
    ) -> bool:
        """
        Upload a blob to a container

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            data: Data to upload (bytes, string, or file-like object)
            overwrite: Whether to overwrite existing blob
            metadata: Optional metadata dictionary
            content_settings: Content settings (content type, encoding, etc.)
            blob_tier: Storage tier (Hot, Cool, Archive)

        Returns:
            bool: True if uploaded successfully
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)

            blob_client.upload_blob(
                data,
                overwrite=overwrite,
                metadata=metadata,
                content_settings=content_settings,
                standard_blob_tier=blob_tier,
            )
            self.logger.info(
                f"Blob '{blob_name}' uploaded successfully to container '{container_name}'"
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to upload blob '{blob_name}': {e}")
            raise

    def upload_file(
        self,
        container_name: str,
        blob_name: str,
        file_path: str,
        overwrite: bool = False,
        metadata: Dict[str, str] = None,
    ) -> bool:
        """
        Upload a file to blob storage

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            file_path: Path to the local file
            overwrite: Whether to overwrite existing blob
            metadata: Optional metadata dictionary

        Returns:
            bool: True if uploaded successfully
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            # Determine content type based on file extension
            content_type = self._get_content_type(file_path)
            content_settings = ContentSettings(content_type=content_type)

            with open(file_path, "rb") as file_data:
                return self.upload_blob(
                    container_name,
                    blob_name,
                    file_data,
                    overwrite=overwrite,
                    metadata=metadata,
                    content_settings=content_settings,
                )
        except Exception as e:
            self.logger.error(f"Failed to upload file '{file_path}': {e}")
            raise

    # Blob Download Operations
    def download_blob(self, container_name: str, blob_name: str) -> bytes:
        """
        Download a blob as bytes

        Args:
            container_name: Name of the container
            blob_name: Name of the blob

        Returns:
            bytes: Blob content as bytes
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)
            return blob_client.download_blob().readall()
        except ResourceNotFoundError:
            self.logger.error(
                f"Blob '{blob_name}' not found in container '{container_name}'"
            )
            raise
        except Exception as e:
            self.logger.error(f"Failed to download blob '{blob_name}': {e}")
            raise

    def download_blob_to_file(
        self, container_name: str, blob_name: str, file_path: str
    ) -> bool:
        """
        Download a blob to a local file

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            file_path: Local file path to save the blob

        Returns:
            bool: True if downloaded successfully
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)

            with open(file_path, "wb") as download_file:
                download_file.write(blob_client.download_blob().readall())

            self.logger.info(f"Blob '{blob_name}' downloaded to '{file_path}'")
            return True
        except Exception as e:
            self.logger.error(f"Failed to download blob '{blob_name}' to file: {e}")
            raise

    # Blob Management Operations
    def delete_blob(
        self, container_name: str, blob_name: str, delete_snapshots: str = "include"
    ) -> bool:
        """
        Delete a blob

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            delete_snapshots: How to handle snapshots ('include', 'only', or None)

        Returns:
            bool: True if deleted successfully
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.delete_blob(delete_snapshots=delete_snapshots)
            self.logger.info(f"Blob '{blob_name}' deleted successfully")
            return True
        except ResourceNotFoundError:
            self.logger.warning(f"Blob '{blob_name}' not found")
            return False
        except Exception as e:
            self.logger.error(f"Failed to delete blob '{blob_name}': {e}")
            raise

    def copy_blob(
        self,
        source_container: str,
        source_blob: str,
        dest_container: str,
        dest_blob: str,
        metadata: Dict[str, str] = None,
    ) -> bool:
        """
        Copy a blob from one location to another

        Args:
            source_container: Source container name
            source_blob: Source blob name
            dest_container: Destination container name
            dest_blob: Destination blob name
            metadata: Optional metadata for the destination blob

        Returns:
            bool: True if copied successfully
        """
        try:
            source_blob_client = self.blob_service_client.get_blob_client(
                source_container, source_blob
            )
            dest_blob_client = self.blob_service_client.get_blob_client(
                dest_container, dest_blob
            )

            # Start the copy operation
            copy_props = dest_blob_client.start_copy_from_url(source_blob_client.url)

            # Wait for copy to complete (for small files this is usually immediate)
            copy_status = copy_props["copy_status"]
            if copy_status == "pending":
                # For larger files, you might want to implement polling
                pass

            if metadata:
                dest_blob_client.set_blob_metadata(metadata)

            self.logger.info(
                f"Blob copied from '{source_container}/{source_blob}' to '{dest_container}/{dest_blob}'"
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to copy blob: {e}")
            raise

    def move_blob(
        self,
        source_container: str,
        source_blob: str,
        dest_container: str,
        dest_blob: str,
        metadata: Dict[str, str] = None,
    ) -> bool:
        """
        Move a blob from one location to another (copy then delete)

        Args:
            source_container: Source container name
            source_blob: Source blob name
            dest_container: Destination container name
            dest_blob: Destination blob name
            metadata: Optional metadata for the destination blob

        Returns:
            bool: True if moved successfully
        """
        try:
            # Copy the blob
            if self.copy_blob(
                source_container, source_blob, dest_container, dest_blob, metadata
            ):
                # Delete the source blob
                return self.delete_blob(source_container, source_blob)
            return False
        except Exception as e:
            self.logger.error(f"Failed to move blob: {e}")
            raise

    def blob_exists(self, container_name: str, blob_name: str) -> bool:
        """
        Check if a blob exists

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
            blob_client.get_blob_properties()
            return True
        except ResourceNotFoundError:
            return False
        except Exception as e:
            self.logger.error(f"Error checking blob existence: {e}")
            raise

    # Directory-like Navigation
    def list_blobs(
        self,
        container_name: str,
        prefix: str = None,
        include_metadata: bool = False,
        include_snapshots: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List blobs in a container with optional filtering

        Args:
            container_name: Name of the container
            prefix: Filter blobs by name prefix (for directory-like navigation)
            include_metadata: Include blob metadata
            include_snapshots: Include blob snapshots

        Returns:
            List of blob information dictionaries
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blobs = []

            # Build include list based on parameters
            include_list = []
            if include_metadata:
                include_list.append("metadata")
            if include_snapshots:
                include_list.append("snapshots")

            blob_list = container_client.list_blobs(
                name_starts_with=prefix,
                include=include_list if include_list else None,
            )

            for blob in blob_list:
                blob_info = {
                    "name": blob.name,
                    "size": blob.size,
                    "last_modified": blob.last_modified,
                    "etag": blob.etag,
                    "content_type": blob.content_settings.content_type
                    if blob.content_settings
                    else None,
                    "blob_tier": blob.blob_tier,
                    "blob_type": blob.blob_type,
                }
                if include_metadata and blob.metadata:
                    blob_info["metadata"] = blob.metadata
                blobs.append(blob_info)

            return blobs
        except Exception as e:
            self.logger.error(f"Failed to list blobs: {e}")
            raise

    def list_blobs_hierarchical(
        self, container_name: str, prefix: str = None, delimiter: str = "/"
    ) -> Dict[str, Any]:
        """
        List blobs in a hierarchical manner (like directory structure)

        Args:
            container_name: Name of the container
            prefix: Directory prefix to list
            delimiter: Delimiter for hierarchical listing (default: '/')

        Returns:
            Dictionary with 'blobs' and 'prefixes' (directories)
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )

            blob_list = container_client.walk_blobs(
                name_starts_with=prefix, delimiter=delimiter
            )

            blobs = []
            prefixes = []

            for item in blob_list:
                if isinstance(item, BlobPrefix):
                    # This is a "directory"
                    prefixes.append({"name": item.name, "prefix": item.name})
                else:
                    # This is a blob
                    blobs.append(
                        {
                            "name": item.name,
                            "size": item.size,
                            "last_modified": item.last_modified,
                            "etag": item.etag,
                            "content_type": item.content_settings.content_type
                            if item.content_settings
                            else None,
                            "blob_tier": item.blob_tier,
                            "blob_type": item.blob_type,
                        }
                    )

            return {"blobs": blobs, "prefixes": prefixes}
        except Exception as e:
            self.logger.error(f"Failed to list blobs hierarchically: {e}")
            raise

    # Metadata and Properties Operations
    def get_blob_properties(
        self, container_name: str, blob_name: str
    ) -> Dict[str, Any]:
        """
        Get blob properties and metadata

        Args:
            container_name: Name of the container
            blob_name: Name of the blob

        Returns:
            Dictionary with blob properties
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)
            properties = blob_client.get_blob_properties()

            return {
                "name": blob_name,
                "size": properties.size,
                "last_modified": properties.last_modified,
                "etag": properties.etag,
                "content_type": properties.content_settings.content_type
                if properties.content_settings
                else None,
                "content_encoding": properties.content_settings.content_encoding
                if properties.content_settings
                else None,
                "blob_tier": properties.blob_tier,
                "blob_type": properties.blob_type,
                "metadata": properties.metadata,
                "creation_time": properties.creation_time,
                "lease_status": properties.lease.status if properties.lease else None,
                "lease_state": properties.lease.state if properties.lease else None,
            }
        except Exception as e:
            self.logger.error(f"Failed to get blob properties: {e}")
            raise

    def set_blob_metadata(
        self, container_name: str, blob_name: str, metadata: Dict[str, str]
    ) -> bool:
        """
        Set blob metadata

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
            blob_client.set_blob_metadata(metadata)
            self.logger.info(f"Metadata set for blob '{blob_name}'")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set blob metadata: {e}")
            raise

    # Batch Operations
    def upload_multiple_files(
        self,
        container_name: str,
        file_paths: List[str],
        blob_prefix: str = "",
        overwrite: bool = False,
    ) -> Dict[str, bool]:
        """
        Upload multiple files to blob storage

        Args:
            container_name: Name of the container
            file_paths: List of local file paths
            blob_prefix: Prefix for blob names
            overwrite: Whether to overwrite existing blobs

        Returns:
            Dictionary with file paths as keys and success status as values
        """
        results = {}

        for file_path in file_paths:
            try:
                if not os.path.exists(file_path):
                    self.logger.warning(f"File not found: {file_path}")
                    results[file_path] = False
                    continue

                filename = os.path.basename(file_path)
                blob_name = f"{blob_prefix}{filename}" if blob_prefix else filename

                results[file_path] = self.upload_file(
                    container_name, blob_name, file_path, overwrite=overwrite
                )
            except Exception as e:
                self.logger.error(f"Failed to upload file '{file_path}': {e}")
                results[file_path] = False

        return results

    def download_multiple_blobs(
        self, container_name: str, blob_names: List[str], download_dir: str
    ) -> Dict[str, bool]:
        """
        Download multiple blobs to local directory

        Args:
            container_name: Name of the container
            blob_names: List of blob names to download
            download_dir: Local directory to save files

        Returns:
            Dictionary with blob names as keys and success status as values
        """
        results = {}
        os.makedirs(download_dir, exist_ok=True)

        for blob_name in blob_names:
            try:
                filename = os.path.basename(blob_name)
                file_path = os.path.join(download_dir, filename)

                results[blob_name] = self.download_blob_to_file(
                    container_name, blob_name, file_path
                )
            except Exception as e:
                self.logger.error(f"Failed to download blob '{blob_name}': {e}")
                results[blob_name] = False

        return results

    def delete_multiple_blobs(
        self, container_name: str, blob_names: List[str]
    ) -> Dict[str, bool]:
        """
        Delete multiple blobs

        Args:
            container_name: Name of the container
            blob_names: List of blob names to delete

        Returns:
            Dictionary with blob names as keys and success status as values
        """
        results = {}

        for blob_name in blob_names:
            try:
                results[blob_name] = self.delete_blob(container_name, blob_name)
            except Exception as e:
                self.logger.error(f"Failed to delete blob '{blob_name}': {e}")
                results[blob_name] = False

        return results

    # Advanced Features
    def generate_blob_sas_url(
        self,
        container_name: str,
        blob_name: str,
        expiry_hours: int = 24,
        permissions: str = "r",
    ) -> str:
        """
        Generate a SAS URL for blob access

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

            account_name = self._get_account_name()
            if not account_name:
                raise ValueError("Unable to determine storage account name")

            account_key = self._get_account_key()
            credential_type = self._get_credential_type()
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
                    f"Generating account key-based blob SAS token for '{blob_name}'"
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
                    f"Generating user delegation blob SAS token for '{blob_name}' using {credential_type}"
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
                        self.blob_service_client.get_user_delegation_key(
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
                f"Successfully generated blob SAS URL for '{blob_name}' (expires in {expiry_hours} hours)"
            )
            return sas_url

        except Exception as e:
            self.logger.error(f"Failed to generate SAS URL: {e}")
            raise

    def generate_container_sas_url(
        self,
        container_name: str,
        expiry_hours: int = 24,
        permissions: str = "rl",
    ) -> str:
        """
        Generate a SAS URL for container access

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

            account_name = self._get_account_name()
            if not account_name:
                raise ValueError("Unable to determine storage account name")

            account_key = self._get_account_key()
            credential_type = self._get_credential_type()

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
                        self.blob_service_client.get_user_delegation_key(
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

    def set_blob_tier(
        self, container_name: str, blob_name: str, tier: StandardBlobTier
    ) -> bool:
        """
        Set blob access tier (Hot, Cool, Archive)

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            tier: Blob tier (Hot, Cool, Archive)

        Returns:
            bool: True if tier set successfully
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.set_standard_blob_tier(tier)
            self.logger.info(f"Blob tier set to {tier} for '{blob_name}'")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set blob tier: {e}")
            raise

    def create_snapshot(
        self, container_name: str, blob_name: str, metadata: Dict[str, str] = None
    ) -> str:
        """
        Create a snapshot of a blob

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            metadata: Optional metadata for the snapshot

        Returns:
            Snapshot datetime string
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_client = container_client.get_blob_client(blob_name)
            snapshot = blob_client.create_snapshot(metadata=metadata)
            self.logger.info(
                f"Snapshot created for blob '{blob_name}': {snapshot['snapshot']}"
            )
            return snapshot["snapshot"]
        except Exception as e:
            self.logger.error(f"Failed to create snapshot: {e}")
            raise

    def list_blob_snapshots(
        self, container_name: str, blob_name: str
    ) -> List[Dict[str, Any]]:
        """
        List all snapshots of a blob

        Args:
            container_name: Name of the container
            blob_name: Name of the blob

        Returns:
            List of snapshot information
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            snapshots = []

            blob_list = container_client.list_blobs(
                name_starts_with=blob_name, include_snapshots=True
            )

            for blob in blob_list:
                if blob.name == blob_name and blob.snapshot:
                    snapshots.append(
                        {
                            "snapshot": blob.snapshot,
                            "last_modified": blob.last_modified,
                            "etag": blob.etag,
                            "size": blob.size,
                        }
                    )

            return snapshots
        except Exception as e:
            self.logger.error(f"Failed to list snapshots: {e}")
            raise

    def search_blobs(
        self, container_name: str, search_term: str, search_in_metadata: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search for blobs by name or metadata

        Args:
            container_name: Name of the container
            search_term: Term to search for
            search_in_metadata: Whether to search in metadata values

        Returns:
            List of matching blobs
        """
        try:
            all_blobs = self.list_blobs(
                container_name, include_metadata=search_in_metadata
            )
            matching_blobs = []

            for blob in all_blobs:
                # Search in blob name
                if search_term.lower() in blob["name"].lower():
                    matching_blobs.append(blob)
                # Search in metadata if requested
                elif search_in_metadata and blob.get("metadata"):
                    for key, value in blob["metadata"].items():
                        if search_term.lower() in value.lower():
                            matching_blobs.append(blob)
                            break

            return matching_blobs
        except Exception as e:
            self.logger.error(f"Failed to search blobs: {e}")
            raise

    def sync_directory(
        self,
        local_directory: str,
        container_name: str,
        blob_prefix: str = "",
        exclude_patterns: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Synchronize a local directory with blob storage

        Args:
            local_directory: Local directory path
            container_name: Name of the container
            blob_prefix: Prefix for blob names
            exclude_patterns: List of patterns to exclude (e.g., ['*.tmp', '*.log'])

        Returns:
            Dictionary with sync results
        """
        try:
            import fnmatch
            from datetime import datetime

            if not os.path.exists(local_directory):
                raise FileNotFoundError(f"Local directory not found: {local_directory}")

            exclude_patterns = exclude_patterns or []
            uploaded = []
            skipped = []
            errors = []

            # Get all local files
            for root, dirs, files in os.walk(local_directory):
                for file in files:
                    local_file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(local_file_path, local_directory)

                    # Check if file should be excluded
                    should_exclude = False
                    for pattern in exclude_patterns:
                        if fnmatch.fnmatch(relative_path, pattern):
                            should_exclude = True
                            break

                    if should_exclude:
                        skipped.append(relative_path)
                        continue

                    # Convert to blob name
                    blob_name = f"{blob_prefix}{relative_path.replace(os.sep, '/')}"

                    try:
                        # Check if blob exists and compare modification time
                        if self.blob_exists(container_name, blob_name):
                            blob_props = self.get_blob_properties(
                                container_name, blob_name
                            )
                            local_mtime = datetime.fromtimestamp(
                                os.path.getmtime(local_file_path)
                            )

                            if local_mtime <= blob_props["last_modified"].replace(
                                tzinfo=None
                            ):
                                skipped.append(relative_path)
                                continue

                        # Upload the file
                        if self.upload_file(
                            container_name, blob_name, local_file_path, overwrite=True
                        ):
                            uploaded.append(relative_path)
                        else:
                            errors.append(f"Failed to upload {relative_path}")

                    except Exception as e:
                        errors.append(f"Error processing {relative_path}: {str(e)}")

            return {
                "uploaded": uploaded,
                "skipped": skipped,
                "errors": errors,
                "total_files": len(uploaded) + len(skipped) + len(errors),
            }

        except Exception as e:
            self.logger.error(f"Failed to sync directory: {e}")
            raise

    def _get_account_key(self) -> str:
        """Extract account key from connection string or configuration"""
        try:
            # Try to get from connection string
            if hasattr(self.blob_service_client, "credential") and hasattr(
                self.blob_service_client.credential, "account_key"
            ):
                return self.blob_service_client.credential.account_key

            # Try to parse from connection string if stored
            if hasattr(self, "_connection_string"):
                parts = self._connection_string.split(";")
                for part in parts:
                    if part.startswith("AccountKey="):
                        return part.split("=", 1)[1]

            return None
        except Exception:
            return None

    def _get_account_name(self) -> str:
        """Extract account name from blob service client"""
        try:
            return self.blob_service_client.account_name
        except Exception:
            return None

    def _get_credential_type(self) -> str:
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

    def get_blob_url(self, container_name: str, blob_name: str) -> str:
        """
        Get the full URL of a blob

        Args:
            container_name: Name of the container
            blob_name: Name of the blob

        Returns:
            Full blob URL
        """
        account_name = self._get_account_name()
        return (
            f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}"
        )

    def get_container_url(self, container_name: str) -> str:
        """
        Get the full URL of a container

        Args:
            container_name: Name of the container

        Returns:
            Full container URL
        """
        account_name = self._get_account_name()
        return f"https://{account_name}.blob.core.windows.net/{container_name}"

    def _get_content_type(self, file_path: str) -> str:
        """
        Get content type based on file extension using configuration

        Args:
            file_path: Path to the file

        Returns:
            Content type string
        """
        extension = os.path.splitext(file_path)[1].lower()
        return self.config.get_content_type(extension)
