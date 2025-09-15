import os

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient
from credential_util import get_azure_credential
from fastmcp import FastMCP

mcp = FastMCP(
    name="azure_blob_io_service",
    instructions="Azure Blob Storage operations. Use container_name=None for 'default'. folder_path=None for root.",
)

# Global variables for storage client
_blob_service_client = None
_default_container = "default"


def _get_blob_service_client() -> BlobServiceClient | None:
    """Get or create blob service client with proper authentication.

    Returns:
        BlobServiceClient if successful, None if authentication fails
    """
    global _blob_service_client

    if _blob_service_client is None:
        # Try account name with Azure AD (DefaultAzureCredential) first - recommended approach
        account_name = os.getenv("STORAGE_ACCOUNT_NAME")
        if account_name:
            try:
                account_url = f"https://{account_name}.blob.core.windows.net"
                credential = get_azure_credential()
                _blob_service_client = BlobServiceClient(
                    account_url=account_url, credential=credential
                )
            except Exception:
                return None
        else:
            # Fallback to connection string if account name is not provided
            connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
            if connection_string:
                try:
                    _blob_service_client = BlobServiceClient.from_connection_string(
                        connection_string
                    )
                except Exception:
                    return None
            else:
                return None

    return _blob_service_client


def _get_full_blob_name(blob_name: str, folder_path: str | None = None) -> str:
    """Combine folder path and blob name."""
    if folder_path:
        # Ensure folder path ends with /
        if not folder_path.endswith("/"):
            folder_path += "/"
        return f"{folder_path}{blob_name}"
    return blob_name


def _ensure_container_exists(container_name: str) -> tuple[bool, str]:
    """Ensure container exists, create if it doesn't.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        client = _get_blob_service_client()
        container_client = client.get_container_client(container_name)
        # Try to get container properties to check if it exists
        container_client.get_container_properties()
        return True, f"Container '{container_name}' exists"
    except ResourceNotFoundError:
        # Container doesn't exist, create it
        try:
            client = _get_blob_service_client()
            client.create_container(container_name)
            return True, f"Container '{container_name}' created successfully"
        except ResourceExistsError:
            # Container was created by another process
            return (
                True,
                f"Container '{container_name}' exists (created by another process)",
            )
        except Exception as e:
            return False, f"Failed to create container '{container_name}': {str(e)}"
    except Exception as e:
        return False, f"Failed to access container '{container_name}': {str(e)}"


@mcp.tool()
def save_content_to_blob(
    blob_name: str,
    content: str,
    container_name: str | None = None,
    folder_path: str | None = None,
) -> str:
    """Save content to a blob in Azure Storage.

    Args:
        blob_name: Name of the blob to create (e.g., 'document.txt', 'config.yaml')
        content: Content to write to the blob
        container_name: Azure storage container name. If None, uses 'default'
        folder_path: Virtual folder path within container (e.g., 'configs/', 'data/processed/')

    Returns:
        Success message with the full blob path where content was saved

    Note:
        Creates container if it doesn't exist. Overwrites existing blobs.
    """
    try:
        if container_name is None:
            container_name = _default_container

        # Get blob service client
        client = _get_blob_service_client()
        if client is None:
            return """[FAILED] AZURE STORAGE AUTHENTICATION FAILED

No valid authentication method found.

[IDEA] REQUIRED ENVIRONMENT VARIABLES:
Option 1 (Recommended): Set STORAGE_ACCOUNT_NAME (uses Azure AD authentication)
Option 2: Set AZURE_STORAGE_CONNECTION_STRING (for development)

[SECURE] AUTHENTICATION SETUP:
- For production: Set STORAGE_ACCOUNT_NAME and use Azure AD (az login, managed identity, or service principal)
- For development: Use Azure CLI 'az login' with STORAGE_ACCOUNT_NAME
- Alternative: Set connection string for quick testing"""

        # Ensure container exists
        success, message = _ensure_container_exists(container_name)
        if not success:
            return f"[FAILED] CONTAINER ACCESS FAILED\n\n{message}"

        # Get full blob name with folder path
        full_blob_name = _get_full_blob_name(blob_name, folder_path)

        # Upload content to blob
        blob_client = client.get_blob_client(
            container=container_name, blob=full_blob_name
        )
        blob_client.upload_blob(content, overwrite=True, encoding="utf-8")

        blob_url = f"https://{client.account_name}.blob.core.windows.net/{container_name}/{full_blob_name}"
        return f"[SUCCESS] Content successfully saved to blob: {blob_url}"

    except Exception as e:
        return f"""[FAILED] BLOB SAVE FAILED

Blob: {container_name}/{_get_full_blob_name(blob_name, folder_path)}
Reason: {str(e)}

[IDEA] SUGGESTIONS:
- Verify Azure Storage credentials are configured
- Check if container name is valid (lowercase, no special chars)
- Ensure you have write permissions to the storage account
- Try with a different container or blob name"""


@mcp.tool()
def read_blob_content(
    blob_name: str,
    container_name: str | None = None,
    folder_path: str | None = None,
) -> str:
    """Read and return the content of a blob from Azure Storage.

    Args:
        blob_name: Name of the blob to read (e.g., 'config.yaml', 'report.md')
        container_name: Azure storage container name. If None, uses 'default'
        folder_path: Virtual folder path within container (e.g., 'configs/', 'data/processed/')

    Returns:
        Complete blob content as a string, or error message if blob cannot be read
    """
    try:
        if container_name is None:
            container_name = _default_container

        # Get full blob name with folder path
        full_blob_name = _get_full_blob_name(blob_name, folder_path)

        # Download blob content
        client = _get_blob_service_client()
        blob_client = client.get_blob_client(
            container=container_name, blob=full_blob_name
        )

        try:
            download_stream = blob_client.download_blob()
            return download_stream.readall().decode("utf-8")
        except ResourceNotFoundError:
            return f"""[FAILED] BLOB READ FAILED

Blob: {container_name}/{full_blob_name}
Reason: Blob does not exist

[IDEA] SUGGESTIONS:
- Check if the blob name is spelled correctly: '{blob_name}'
- Verify the container name is correct: '{container_name}'
- Check the folder path: '{folder_path}'
- Use list_blobs_in_container() to see available blobs"""

    except Exception as e:
        return f"""[FAILED] BLOB READ FAILED

Blob: {container_name}/{_get_full_blob_name(blob_name, folder_path)}
Reason: {str(e)}

[IDEA] SUGGESTIONS:
- Verify Azure Storage credentials are configured
- Check if you have read permissions to the storage account
- Ensure the container exists
- Try the operation again"""


@mcp.tool()
def check_blob_exists(
    blob_name: str,
    container_name: str | None = None,
    folder_path: str | None = None,
) -> str:
    """Check if a blob exists and return detailed metadata.

    Args:
        blob_name: Name of the blob to check
        container_name: Azure storage container name. If None, uses 'default'
        folder_path: Virtual folder path within container

    Returns:
        Detailed blob information or existence status
    """
    try:
        if container_name is None:
            container_name = _default_container

        full_blob_name = _get_full_blob_name(blob_name, folder_path)

        client = _get_blob_service_client()
        blob_client = client.get_blob_client(
            container=container_name, blob=full_blob_name
        )

        try:
            properties = blob_client.get_blob_properties()

            return f"""[SUCCESS] BLOB EXISTS

[PIN] Location: {container_name}/{full_blob_name}
[RULER] Size: {properties.size:,} bytes
[CALENDAR] Last Modified: {properties.last_modified}
[TAG]  Content Type: {properties.content_settings.content_type or "application/octet-stream"}
[PROCESSING] ETag: {properties.etag}
[TARGET] Access Tier: {properties.blob_tier or "Hot"}
[SECURE] Encryption Scope: {"Enabled" if properties.server_encrypted else "Not specified"}

[INFO] METADATA:
{chr(10).join([f"  • {k}: {v}" for k, v in (properties.metadata or {}).items()]) or "  No custom metadata"}"""

        except ResourceNotFoundError:
            return f"""[FAILED] BLOB DOES NOT EXIST

Blob: {container_name}/{full_blob_name}

[IDEA] SUGGESTIONS:
- Verify the blob name and path are correct
- Check if the blob might be in a different container
- Use list_blobs_in_container() to explore available blobs
- The blob may have been moved or deleted"""

    except Exception as e:
        return f"""[FAILED] BLOB CHECK FAILED

Blob: {container_name}/{_get_full_blob_name(blob_name, folder_path)}
Error: {str(e)}"""


@mcp.tool()
def delete_blob(
    blob_name: str,
    container_name: str | None = None,
    folder_path: str | None = None,
) -> str:
    """Permanently delete a blob from Azure Storage.

    Args:
        blob_name: Name of the blob to delete
        container_name: Azure storage container name. If None, uses 'default'
        folder_path: Virtual folder path within container

    Returns:
        Success or error message

    Warning:
        This operation is permanent and cannot be undone!
    """
    try:
        if container_name is None:
            container_name = _default_container

        full_blob_name = _get_full_blob_name(blob_name, folder_path)

        client = _get_blob_service_client()
        blob_client = client.get_blob_client(
            container=container_name, blob=full_blob_name
        )

        try:
            blob_client.delete_blob()
            return f"[SUCCESS] Blob successfully deleted: {container_name}/{full_blob_name}"
        except ResourceNotFoundError:
            return f"[WARNING] Blob not found (may already be deleted): {container_name}/{full_blob_name}"

    except Exception as e:
        return f"""[FAILED] BLOB DELETE FAILED

Blob: {container_name}/{_get_full_blob_name(blob_name, folder_path)}
Error: {str(e)}

[IDEA] SUGGESTIONS:
- Verify you have delete permissions
- Check if the blob is not locked or being used by another process"""


@mcp.tool()
def list_blobs_in_container(
    container_name: str | None = None,
    folder_path: str | None = None,
    recursive: bool = False,  # ✅ Changed default to False for migration workflows
) -> str:
    """List all blobs in a container with detailed information.

    Args:
        container_name: Azure storage container name. If None, uses 'default'
        folder_path: Virtual folder path to list (e.g., 'configs/'). If None, lists from root
        recursive: Whether to list blobs in subfolders recursively

    Returns:
        Formatted list of blobs with details (excludes .KEEP marker files)

    Note:
        .KEEP files used for folder creation are automatically excluded from results
        Default recursive=False to avoid counting cache files in migration workflows
    """
    try:
        if container_name is None:
            container_name = _default_container

        client = _get_blob_service_client()
        container_client = client.get_container_client(container_name)

        # Set up name prefix for folder filtering
        name_starts_with = folder_path if folder_path else None

        try:
            blobs = container_client.list_blobs(name_starts_with=name_starts_with)
            blob_list = []
            total_size = 0

            for blob in blobs:
                # Skip .KEEP marker files used for folder creation
                filename = os.path.basename(blob.name)
                if filename == ".KEEP" or filename.endswith(".KEEP"):
                    continue

                # Skip if not recursive and blob is in a subfolder
                if not recursive and folder_path:
                    relative_path = blob.name[len(folder_path) :]
                    if "/" in relative_path:
                        continue
                elif not recursive and not folder_path:
                    if "/" in blob.name:
                        continue

                size_mb = blob.size / 1024 / 1024 if blob.size else 0
                total_size += blob.size if blob.size else 0

                blob_list.append(
                    {
                        "name": blob.name,
                        "size": blob.size or 0,
                        "size_mb": size_mb,
                        "last_modified": blob.last_modified,
                        "content_type": blob.content_settings.content_type
                        if blob.content_settings
                        else "unknown",
                    }
                )

            if not blob_list:
                return f"""[FOLDER] CONTAINER: {container_name}
[SEARCH] FOLDER: {folder_path or "Root"}
[CLIPBOARD] STATUS: Empty (no blobs found)

[IDEA] SUGGESTIONS:
- Check if the container exists and has blobs
- Try without folder filter to see all blobs
- Verify you have read permissions"""

            # Sort by name
            blob_list.sort(key=lambda x: x["name"])

            # Format output
            result = f"""[FOLDER] CONTAINER: {container_name}
[SEARCH] FOLDER: {folder_path or "Root"} {"(Recursive)" if recursive else "(Non-recursive)"}
[INFO] TOTAL: {len(blob_list)} blobs, {total_size / 1024 / 1024:.2f} MB

[CLIPBOARD] BLOBS:
"""

            for blob in blob_list:
                result += f"""
  [DOCUMENT] {blob["name"]}
     [SAVE] Size: {blob["size"]:,} bytes ({blob["size_mb"]:.2f} MB)
     [CALENDAR] Modified: {blob["last_modified"]}
     [TAG]  Type: {blob["content_type"]}"""

            return result

        except ResourceNotFoundError:
            return f"""[FAILED] CONTAINER NOT FOUND

Container: {container_name}

[IDEA] SUGGESTIONS:
- Verify the container name is spelled correctly
- Check if the container exists using list_containers()
- The container may have been deleted"""

    except Exception as e:
        return f"""[FAILED] BLOB LISTING FAILED

Container: {container_name}
Folder: {folder_path or "Root"}
Error: {str(e)}"""


@mcp.tool()
def create_container(container_name: str) -> str:
    """Create a new Azure Storage container.

    Args:
        container_name: Name for the new container (must be lowercase, 3-63 chars)

    Returns:
        Success or error message
    """
    try:
        client = _get_blob_service_client()

        try:
            client.create_container(container_name)
            return f"[SUCCESS] Container successfully created: {container_name}"
        except ResourceExistsError:
            return f"[WARNING] Container already exists: {container_name}"

    except Exception as e:
        return f"""[FAILED] CONTAINER CREATION FAILED

Container: {container_name}
Error: {str(e)}

[IDEA] SUGGESTIONS:
- Container names must be 3-63 characters long
- Use only lowercase letters, numbers, and hyphens
- Cannot start or end with hyphen
- Must be globally unique across Azure Storage"""


@mcp.tool()
def list_containers() -> str:
    """List all containers in the Azure Storage account.

    Returns:
        Formatted list of containers with details
    """
    try:
        client = _get_blob_service_client()
        containers = client.list_containers(include_metadata=True)

        container_list = []
        for container in containers:
            container_list.append(
                {
                    "name": container.name,
                    "last_modified": container.last_modified,
                    "metadata": container.metadata or {},
                }
            )

        if not container_list:
            return """[PACKAGE] STORAGE ACCOUNT CONTAINERS

[CLIPBOARD] STATUS: No containers found

[IDEA] SUGGESTIONS:
- Create a container using create_container()
- Verify you have access to this storage account"""

        result = f"""[PACKAGE] STORAGE ACCOUNT CONTAINERS

[INFO] TOTAL: {len(container_list)} containers

[CLIPBOARD] CONTAINERS:
"""

        for container in container_list:
            result += f"""
  [FOLDER] {container["name"]}
     [CALENDAR] Modified: {container["last_modified"]}
     [TAG]  Metadata: {len(container["metadata"])} items"""

        return result

    except Exception as e:
        return f"""[FAILED] CONTAINER LISTING FAILED

Error: {str(e)}

[IDEA] SUGGESTIONS:
- Verify Azure Storage credentials are configured
- Check if you have access to list containers
- Ensure the storage account exists"""


@mcp.tool()
def find_blobs(
    pattern: str,
    container_name: str | None = None,
    folder_path: str | None = None,
    recursive: bool = False,  # ✅ Changed default to False for migration workflows
) -> str:
    """Find blobs matching a wildcard pattern.

    Args:
        pattern: Wildcard pattern (e.g., '*.json', 'config*', '*report*')
        container_name: Azure storage container name. If None, uses 'default'
        folder_path: Virtual folder path to search within
        recursive: Whether to search in subfolders

    Returns:
        List of matching blobs with details (excludes .KEEP marker files)

    Note:
        .KEEP files used for folder creation are automatically excluded from results
        Default recursive=False to avoid counting cache files in migration workflows
    """
    try:
        if container_name is None:
            container_name = _default_container

        import fnmatch

        client = _get_blob_service_client()
        container_client = client.get_container_client(container_name)

        name_starts_with = folder_path if folder_path else None

        try:
            blobs = container_client.list_blobs(name_starts_with=name_starts_with)
            matching_blobs = []

            for blob in blobs:
                # Extract just the filename for pattern matching
                if folder_path:
                    if not blob.name.startswith(folder_path):
                        continue
                    relative_path = blob.name[len(folder_path) :]
                else:
                    relative_path = blob.name

                # Skip subdirectories if not recursive
                if not recursive and "/" in relative_path:
                    continue

                # Extract filename for pattern matching
                filename = os.path.basename(blob.name)

                # Skip .KEEP marker files used for folder creation
                if filename == ".KEEP" or filename.endswith(".KEEP"):
                    continue

                if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(
                    blob.name, pattern
                ):
                    size_mb = blob.size / 1024 / 1024 if blob.size else 0
                    matching_blobs.append(
                        {
                            "name": blob.name,
                            "size": blob.size or 0,
                            "size_mb": size_mb,
                            "last_modified": blob.last_modified,
                        }
                    )

            if not matching_blobs:
                return f"""[SEARCH] BLOB SEARCH RESULTS

[FOLDER] Container: {container_name}
[SEARCH] Folder: {folder_path or "Root"}
[TARGET] Pattern: {pattern}
[CLIPBOARD] Results: No matching blobs found

[IDEA] SUGGESTIONS:
- Try a broader pattern (e.g., '*config*' instead of 'config.json')
- Check if the folder path is correct
- Use list_blobs_in_container() to see all available blobs"""

            # Sort by name
            matching_blobs.sort(key=lambda x: x["name"])

            total_size = sum(blob["size"] for blob in matching_blobs)

            result = f"""[SEARCH] BLOB SEARCH RESULTS

[FOLDER] Container: {container_name}
[SEARCH] Folder: {folder_path or "Root"} {"(Recursive)" if recursive else "(Non-recursive)"}
[TARGET] Pattern: {pattern}
[INFO] Results: {len(matching_blobs)} blobs, {total_size / 1024 / 1024:.2f} MB

[CLIPBOARD] MATCHING BLOBS:
"""

            for blob in matching_blobs:
                result += f"""
  [DOCUMENT] {blob["name"]}
     [SAVE] {blob["size"]:,} bytes ({blob["size_mb"]:.2f} MB)
     [CALENDAR] {blob["last_modified"]}"""

            return result

        except ResourceNotFoundError:
            return f"""[FAILED] CONTAINER NOT FOUND

Container: {container_name}

[IDEA] SUGGESTIONS:
- Verify the container name is spelled correctly
- Use list_containers() to see available containers"""

    except Exception as e:
        return f"""[FAILED] BLOB SEARCH FAILED

Pattern: {pattern}
Container: {container_name}
Error: {str(e)}"""


@mcp.tool()
def get_storage_account_info() -> str:
    """Get information about the Azure Storage account.

    Returns:
        Storage account information and statistics
    """
    try:
        client = _get_blob_service_client()

        # Get account information
        account_info = client.get_account_information()

        # List containers and get basic stats
        containers = list(client.list_containers())
        total_containers = len(containers)

        # Get service properties
        try:
            properties = client.get_service_properties()
            cors_rules = len(properties.cors) if properties.cors else 0
        except Exception:
            cors_rules = "Unknown"

        result = f"""[OFFICE] AZURE STORAGE ACCOUNT INFORMATION

[INFO] ACCOUNT DETAILS:
  • Account Name: {client.account_name}
  • Primary Endpoint: {client.primary_endpoint}
  • Account Kind: {account_info.account_kind.value if account_info.account_kind else "Unknown"}
  • SKU Name: {account_info.sku_name.value if account_info.sku_name else "Unknown"}

[FOLDER] CONTAINER STATISTICS:
  • Total Containers: {total_containers}
  • Default Container: {_default_container}

[CONFIG] SERVICE CONFIGURATION:
  • CORS Rules: {cors_rules}
  • Authentication: {"Azure AD (DefaultAzureCredential)" if os.getenv("STORAGE_ACCOUNT_NAME") else "Connection String"}

[CLIPBOARD] AVAILABLE CONTAINERS:"""

        for container in containers[:10]:  # Show first 10 containers
            result += f"\n  • {container.name}"

        if total_containers > 10:
            result += f"\n  ... and {total_containers - 10} more containers"

        return result

    except Exception as e:
        return f"""[FAILED] STORAGE ACCOUNT INFO FAILED

Error: {str(e)}

[IDEA] SUGGESTIONS:
- Verify Azure Storage credentials are configured
- Check if you have access to the storage account
- Ensure the storage account exists and is accessible"""


@mcp.tool()
def copy_blob(
    source_blob: str,
    target_blob: str,
    source_container: str | None = None,
    target_container: str | None = None,
    source_folder: str | None = None,
    target_folder: str | None = None,
) -> str:
    """Copy a blob within or across containers.

    Args:
        source_blob: Name of the source blob
        target_blob: Name of the target blob
        source_container: Source container name. If None, uses 'default'
        target_container: Target container name. If None, uses source_container
        source_folder: Virtual folder path for source blob
        target_folder: Virtual folder path for target blob

    Returns:
        Success or error message
    """
    try:
        if source_container is None:
            source_container = _default_container
        if target_container is None:
            target_container = source_container

        source_full_name = _get_full_blob_name(source_blob, source_folder)
        target_full_name = _get_full_blob_name(target_blob, target_folder)

        # Ensure target container exists
        _ensure_container_exists(target_container)

        client = _get_blob_service_client()

        # Get source blob URL
        source_blob_client = client.get_blob_client(
            container=source_container, blob=source_full_name
        )
        source_url = source_blob_client.url

        # Copy blob
        target_blob_client = client.get_blob_client(
            container=target_container, blob=target_full_name
        )
        target_blob_client.start_copy_from_url(source_url)

        return f"[SUCCESS] Blob successfully copied from {source_container}/{source_full_name} to {target_container}/{target_full_name}"

    except ResourceNotFoundError:
        return f"[FAILED] Source blob not found: {source_container}/{_get_full_blob_name(source_blob, source_folder)}"
    except Exception as e:
        return f"""[FAILED] BLOB COPY FAILED

Source: {source_container}/{_get_full_blob_name(source_blob, source_folder)}
Target: {target_container}/{_get_full_blob_name(target_blob, target_folder)}
Error: {str(e)}"""


@mcp.tool()
def move_blob(
    blob_name: str,
    source_container: str | None = None,
    target_container: str | None = None,
    source_folder: str | None = None,
    target_folder: str | None = None,
    new_name: str | None = None,
) -> str:
    """Move/rename a blob between containers or folders.

    Args:
        blob_name: Name of the blob to move
        source_container: Source container name. If None, uses 'default'
        target_container: Target container name. If None, uses source_container
        source_folder: Virtual folder path for source blob
        target_folder: Virtual folder path for target blob
        new_name: New name for the blob. If None, keeps original name

    Returns:
        Success or error message
    """
    try:
        if source_container is None:
            source_container = _default_container
        if target_container is None:
            target_container = source_container
        if new_name is None:
            new_name = blob_name

        # Get blob service client
        client = _get_blob_service_client()
        if client is None:
            return "[FAILED] AZURE STORAGE AUTHENTICATION FAILED\n\nNo valid authentication method found. Please check your environment variables."

        source_full_name = _get_full_blob_name(blob_name, source_folder)
        target_full_name = _get_full_blob_name(new_name, target_folder)

        # Ensure target container exists
        success, message = _ensure_container_exists(target_container)
        if not success:
            return f"[FAILED] TARGET CONTAINER ACCESS FAILED\n\n{message}"

        # Get source blob URL
        source_blob_client = client.get_blob_client(
            container=source_container, blob=source_full_name
        )
        source_url = source_blob_client.url

        # Copy blob to target
        target_blob_client = client.get_blob_client(
            container=target_container, blob=target_full_name
        )
        target_blob_client.start_copy_from_url(source_url)

        # Delete source blob
        source_blob_client.delete_blob()

        return f"[SUCCESS] Blob successfully moved from {source_container}/{source_full_name} to {target_container}/{target_full_name}"

    except ResourceNotFoundError:
        return f"[FAILED] Source blob not found: {source_container}/{_get_full_blob_name(blob_name, source_folder)}"
    except Exception as e:
        return f"""[FAILED] BLOB MOVE FAILED

Source: {source_container}/{_get_full_blob_name(blob_name, source_folder)}
Target: {target_container}/{_get_full_blob_name(new_name or blob_name, target_folder)}
Error: {str(e)}

[IDEA] SUGGESTION:
- The copy operation may have succeeded but delete failed
- Check both source and target locations"""


@mcp.tool()
def delete_multiple_blobs(
    blob_patterns: str,
    container_name: str | None = None,
    folder_path: str | None = None,
) -> str:
    """Delete multiple blobs matching patterns.

    Args:
        blob_patterns: Comma-separated patterns (e.g., '*.tmp,*.log,old-*')
        container_name: Azure storage container name. If None, uses 'default'
        folder_path: Virtual folder path to search within

    Returns:
        Summary of deletion results

    Warning:
        This operation is permanent and cannot be undone!

    Note:
        .KEEP files used for folder creation are automatically excluded from deletion
    """
    try:
        if container_name is None:
            container_name = _default_container

        import fnmatch

        patterns = [p.strip() for p in blob_patterns.split(",")]

        client = _get_blob_service_client()
        container_client = client.get_container_client(container_name)

        name_starts_with = folder_path if folder_path else None

        try:
            blobs = container_client.list_blobs(name_starts_with=name_starts_with)
            matching_blobs = []

            for blob in blobs:
                filename = os.path.basename(blob.name)

                # Skip .KEEP marker files used for folder creation
                if filename == ".KEEP" or filename.endswith(".KEEP"):
                    continue

                for pattern in patterns:
                    if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(
                        blob.name, pattern
                    ):
                        matching_blobs.append(blob.name)
                        break

            if not matching_blobs:
                return f"""[WARNING] NO BLOBS TO DELETE

[FOLDER] Container: {container_name}
[SEARCH] Folder: {folder_path or "Root"}
[TARGET] Patterns: {blob_patterns}

[IDEA] SUGGESTION:
- Use find_blobs() to verify which blobs match your patterns"""

            # Delete matching blobs
            deleted_count = 0
            failed_count = 0
            results = []

            for blob_name in matching_blobs:
                try:
                    blob_client = client.get_blob_client(
                        container=container_name, blob=blob_name
                    )
                    blob_client.delete_blob()
                    deleted_count += 1
                    results.append(f"[SUCCESS] {blob_name}")
                except Exception as e:
                    failed_count += 1
                    results.append(f"[FAILED] {blob_name}: {str(e)}")

            result = f"""[CLEANUP] BULK DELETE RESULTS

[FOLDER] Container: {container_name}
[SEARCH] Folder: {folder_path or "Root"}
[TARGET] Patterns: {blob_patterns}
[INFO] Results: {deleted_count} deleted, {failed_count} failed

[CLIPBOARD] DETAILED RESULTS:
"""

            for res in results:
                result += f"\n  {res}"

            if failed_count > 0:
                result += "\n\n[IDEA] Some deletions failed. Check permissions and blob status."

            return result

        except ResourceNotFoundError:
            return f"[FAILED] Container not found: {container_name}"

    except Exception as e:
        return f"""[FAILED] BULK DELETE FAILED

Patterns: {blob_patterns}
Container: {container_name}
Error: {str(e)}"""


@mcp.tool()
def clear_container(container_name: str, folder_path: str | None = None) -> str:
    """Delete all blobs in a container or folder.

    Args:
        container_name: Azure storage container name
        folder_path: Virtual folder path to clear. If None, clears entire container

    Returns:
        Summary of deletion results

    Warning:
        This operation is permanent and cannot be undone!
    """
    try:
        client = _get_blob_service_client()
        container_client = client.get_container_client(container_name)

        name_starts_with = folder_path if folder_path else None

        try:
            blobs = list(container_client.list_blobs(name_starts_with=name_starts_with))

            if not blobs:
                return f"""[WARNING] NOTHING TO CLEAR

[FOLDER] Container: {container_name}
[SEARCH] Folder: {folder_path or "Root"}
[CLIPBOARD] Status: Already empty"""

            # Delete all blobs
            deleted_count = 0
            failed_count = 0

            for blob in blobs:
                try:
                    blob_client = client.get_blob_client(
                        container=container_name, blob=blob.name
                    )
                    blob_client.delete_blob()
                    deleted_count += 1
                except Exception:
                    failed_count += 1

            return f"""[CLEANUP] CONTAINER CLEAR RESULTS

[FOLDER] Container: {container_name}
[SEARCH] Folder: {folder_path or "Root"}
[INFO] Results: {deleted_count} deleted, {failed_count} failed

[SUCCESS] Container/folder cleared successfully"""

        except ResourceNotFoundError:
            return f"[FAILED] Container not found: {container_name}"

    except Exception as e:
        return f"""[FAILED] CONTAINER CLEAR FAILED

Container: {container_name}
Error: {str(e)}"""


@mcp.tool()
def delete_container(container_name: str) -> str:
    """Delete an entire Azure Storage container and all its contents.

    Args:
        container_name: Name of the container to delete

    Returns:
        Success or error message

    Warning:
        This operation is permanent and cannot be undone!
        All blobs in the container will be permanently deleted.
    """
    try:
        client = _get_blob_service_client()

        try:
            client.delete_container(container_name)
            return f"[CLEANUP] Container successfully deleted: {container_name}\n[WARNING] All blobs in the container have been permanently deleted."
        except ResourceNotFoundError:
            return f"[WARNING] Container not found (may already be deleted): {container_name}"

    except Exception as e:
        return f"""[FAILED] CONTAINER DELETE FAILED

Container: {container_name}
Error: {str(e)}

[IDEA] SUGGESTIONS:
- Verify you have delete permissions
- Check if the container has a delete lock
- Ensure the container is not being used by other services"""


@mcp.tool()
def create_folder(
    folder_path: str,
    container_name: str | None = None,
    marker_file_name: str = ".keep",
) -> str:
    """Create an empty folder structure in Azure Blob Storage by creating a marker blob.

    Since Azure Blob Storage doesn't have true folders, this creates a small marker file
    to establish the folder structure. The folder will appear in storage explorers
    and can be used as a parent for other blobs.

    Args:
        folder_path: Virtual folder path to create (e.g., 'configs/', 'data/processed/')
        container_name: Azure storage container name. If None, uses 'default'
        marker_file_name: Name of the marker file to create (default: '.keep')

    Returns:
        Success message with the created folder structure
    """
    try:
        if container_name is None:
            container_name = _default_container

        # Ensure folder_path ends with '/'
        if not folder_path.endswith("/"):
            folder_path += "/"

        # Ensure container exists
        _ensure_container_exists(container_name)

        # Create marker blob in the folder
        full_blob_name = f"{folder_path}{marker_file_name}"

        client = _get_blob_service_client()
        blob_client = client.get_blob_client(
            container=container_name, blob=full_blob_name
        )

        # Create empty marker file with metadata indicating it's a folder marker
        marker_content = f"# Folder marker created at {folder_path}\n# This file maintains the folder structure in Azure Blob Storage\n"
        blob_client.upload_blob(
            marker_content,
            overwrite=True,
            encoding="utf-8",
            metadata={"folder_marker": "true", "created_by": "mcp_blob_service"},
        )

        blob_url = f"https://{client.account_name}.blob.core.windows.net/{container_name}/{full_blob_name}"

        return f"""[FOLDER] EMPTY FOLDER CREATED

[SUCCESS] Folder: {container_name}/{folder_path}
[DOCUMENT] Marker File: {marker_file_name}
[LINK] URL: {blob_url}

[IDEA] FOLDER READY FOR USE:
- You can now upload files to this folder path
- The folder will appear in Azure Storage Explorer
- Use folder_path='{folder_path}' in other blob operations"""

    except Exception as e:
        return f"""[FAILED] FOLDER CREATION FAILED

Folder: {container_name}/{folder_path}
Reason: {str(e)}

[IDEA] SUGGESTIONS:
- Verify Azure Storage credentials are configured
- Check if container name is valid (lowercase, no special chars)
- Ensure folder path doesn't contain invalid characters
- Try with a different folder path or marker file name"""


if __name__ == "__main__":
    mcp.run()
