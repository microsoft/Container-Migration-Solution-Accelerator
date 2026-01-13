"""Queue-based Migration Service.

This worker consumes migration requests from a single Azure Storage Queue and
executes the step-based workflow runner in `src/steps/migration_processor.py`.

Policy:
- Single queue only
- No retry
- No dead-letter queue

If a job fails, the message is deleted and the failure is surfaced via logs and
telemetry/artifacts.
"""

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.storage.queue import QueueClient, QueueMessage, QueueServiceClient
from sas.storage import StorageBlobHelper

from libs.application.application_context import AppContext
from services.process_control import ProcessControlManager
from steps.analysis.models.step_param import Analysis_TaskParam
from steps.migration_processor import (
    MigrationProcessor as WorkflowMigrationProcessor,
)
from steps.migration_processor import (
    WorkflowExecutorFailedException,
)
from utils.agent_telemetry import TelemetryManager
from utils.credential_util import get_azure_credential

# Import comprehensive logging suppression
from utils.logging_utils import configure_application_logging

# Apply comprehensive verbose logging suppression
configure_application_logging(debug_mode=False)  # Default to production mode

logger = logging.getLogger(__name__)


def is_base64_encoded(data: str) -> bool:
    try:
        # Try to decode the string
        decoded_data = base64.b64decode(data, validate=True)
        # Check if the decoded data can be encoded back to the original string
        return base64.b64encode(decoded_data).decode("utf-8") == data
    except Exception:
        return False


def create_default_migration_request(
    process_id: str | None = None,
    user_id: str | None = None,
    container_name: str = "processes",
    source_file_folder: str = "source",
    workspace_file_folder: str = "workspace",
    output_file_folder: str = "output",
) -> dict[str, Any]:
    """
    Create a default migration_request with all mandatory fields.

    This utility function ensures all required fields are present and provides
    sensible defaults for Kubernetes migration processing.

    Args:
        process_id: Process identifier (optional, shipped in request)
        user_id: User identifier (optional, shipped in request)
        container_name: Azure storage container name (mandatory)
        source_file_folder: Source folder for K8s files (mandatory)
        workspace_file_folder: Workspace folder for processing (mandatory)
        output_file_folder: Output folder for generated artifacts (mandatory)

    Returns:
        Complete migration_request dictionary with all mandatory fields
    """
    migration_request = {
        # Mandatory fields for migration processing
        "process_id": process_id,
        "user_id": user_id,
        "container_name": container_name,
        "source_file_folder": f"{process_id}/{source_file_folder}",
        "workspace_file_folder": f"{process_id}/{workspace_file_folder}",
        "output_file_folder": f"{process_id}/{output_file_folder}",
    }

    return migration_request


@dataclass
class QueueServiceConfig:
    """Configuration for queue service using Azure Default Credential"""

    use_entra_id: bool = True
    storage_account_name: str = ""  # Storage account name for default credential auth
    queue_name: str = "processes-queue"
    visibility_timeout_minutes: int = 30  # Reduced for testing - was 30
    concurrent_workers: int = 1
    poll_interval_seconds: int = 5
    message_timeout_minutes: int = 25
    control_poll_interval_seconds: int = 2


@dataclass
class MigrationQueueMessage:
    """Structured migration queue message"""

    process_id: str
    migration_request: dict[str, Any]
    user_id: str | None = None  # Optional user id
    retry_count: int = 0
    created_time: str | None = None
    priority: str = "normal"

    def __post_init__(self):
        """Validate mandatory fields in migration_request after initialization"""
        # Mandatory fields for migration processing
        required_fields = [
            "container_name",
            "source_file_folder",
            "workspace_file_folder",
            "output_file_folder",
            "process_id",
            "user_id",
        ]

        # Optional fields that can be shipped in migration_request
        optional_fields = []

        missing_fields = []
        for field in required_fields:
            if field not in self.migration_request:
                missing_fields.append(field)

        if missing_fields:
            raise ValueError(
                f"migration_request missing mandatory fields: {missing_fields}. "
                f"Required fields: {required_fields}. "
                f"Optional fields: {optional_fields}"
            )

    @classmethod
    def from_queue_message(cls, queue_message: QueueMessage) -> "MigrationQueueMessage":
        """Create from Azure Queue message with Base64 decoding and auto-completion of missing fields"""
        import base64
        import binascii

        try:
            # Step 1: Handle Azure Queue Base64 encoding = Text Encoding format
            raw_content = queue_message.content

            # Azure Storage Queue may Base64 encode message content
            if isinstance(raw_content, str):
                try:
                    # Try to decode as Base64 first (common in Azure Storage Queue)
                    decoded_bytes = base64.b64decode(raw_content)
                    content = decoded_bytes.decode("utf-8")
                except (binascii.Error, UnicodeDecodeError):
                    # If Base64 decode fails, treat as plain string
                    content = raw_content
            elif isinstance(raw_content, bytes):
                content = raw_content.decode("utf-8")
            else:
                raise TypeError(f"Unexpected message content type: {type(raw_content)}")

            # Step 2: Parse JSON with encoding-safe content
            data = json.loads(content)

            # Step 3: Auto-complete missing fields if only process_id is provided
            if "process_id" in data and "migration_request" not in data:
                # Extract optional fields
                user_id = data.get("user_id")

                # Create complete message using utility function
                data["migration_request"] = create_default_migration_request(
                    process_id=data["process_id"], user_id=user_id
                )

                # Set optional fields with defaults if not present
                if "user_id" not in data and user_id:
                    data["user_id"] = user_id
                if "retry_count" not in data:
                    data["retry_count"] = 0
                if "priority" not in data:
                    data["priority"] = "normal"

            # Filter data to only include expected dataclass fields
            expected_fields = {
                "process_id",
                "migration_request",
                "user_id",
                "retry_count",
                "created_time",
                "priority",
            }
            filtered_data = {k: v for k, v in data.items() if k in expected_fields}

            # Log unexpected fields for debugging
            unexpected_fields = set(data.keys()) - expected_fields
            if unexpected_fields:
                logger.warning(
                    f"Queue message contains unexpected fields (ignoring): {unexpected_fields}"
                )
                logger.debug(f"Full message data: {data}")

            return cls(**filtered_data)
        except (json.JSONDecodeError, TypeError) as e:
            raise ValueError(f"Invalid queue message format: {e}") from e
        except (binascii.Error, UnicodeDecodeError) as e:
            raise ValueError(f"Message encoding error: {e}") from e
        except ValueError as e:
            # Re-raise validation errors from __post_init__
            raise ValueError(f"Queue message validation failed: {e}") from e


class QueueMigrationService:
    """
    Main queue-based migration service.

    Processes migration requests from Azure Storage Queue with visibility timeout
    management to reduce duplicate processing.

    No retry and no dead-letter queue are used.
    """

    # Class-level tracking to prevent multiple instances and detect ghost processes
    _instance_count = 0
    _active_instances = set()
    main_queue: QueueClient | None = None

    def __init__(
        self,
        config: QueueServiceConfig,
        app_context: AppContext | None = None,
        debug_mode: bool = False,
    ):
        # Increment instance counter and track this instance
        QueueMigrationService._instance_count += 1
        self.instance_id = QueueMigrationService._instance_count
        QueueMigrationService._active_instances.add(self.instance_id)

        logger.info(f"Creating QueueMigrationService instance #{self.instance_id}")
        logger.info(
            f"Active instances: {len(QueueMigrationService._active_instances)} - IDs: {list(QueueMigrationService._active_instances)}"
        )

        self.config = config
        self.app_context: AppContext = app_context
        # Use the explicit debug_mode parameter instead of configuration override
        # This allows main_service.py to control debug mode explicitly
        self.debug_mode = debug_mode
        self.is_running = False

        # Initialize Azure Queue Service with Default Credential
        credential = get_azure_credential()
        storage_account_url = (
            f"https://{config.storage_account_name}.queue.core.windows.net"
        )
        self.queue_service = QueueServiceClient(
            account_url=storage_account_url, credential=credential
        )

        # Initialize queues
        self.main_queue = self.queue_service.get_queue_client(config.queue_name)

        # No retry / no DLQ: failures are deleted and surfaced via telemetry/logs.

        # Worker tracking
        self.active_workers = set()
        self._worker_tasks: dict[int, asyncio.Task] = {}

        # Best-effort: track the currently running process_id per worker for observability.
        self._worker_inflight: dict[int, str] = {}

        # Best-effort: track the in-flight queue message per worker so we can delete it on kill.
        self._worker_inflight_message: dict[int, tuple[str, str]] = {}

        # Track the in-flight workflow input per worker (used for resource cleanup).
        self._worker_inflight_task_param: dict[int, Analysis_TaskParam] = {}

        # Track the in-flight job task per worker so we can cancel only the job (not the worker).
        self._worker_inflight_task: dict[int, asyncio.Task] = {}

        # Process control (kill requests) watcher task.
        self._control_watcher_task: asyncio.Task | None = None

    async def start_service(self):
        """Start the queue processing service with multiple workers"""
        if self.is_running:
            logger.warning("Service is already running")
            return

        self.is_running = True
        logger.info(
            f"Starting Queue Migration Service with {self.config.concurrent_workers} workers"
        )

        try:
            # Ensure queues exist
            await self._ensure_queues_exist()

            # Start control watcher (best-effort). This watches shared kill requests
            # and triggers stop_process locally for any in-flight matches.
            self._control_watcher_task = asyncio.create_task(
                self._control_watcher_loop(),
                name=f"process-control-watcher-{self.instance_id}",
            )

            worker_count = max(1, int(self.config.concurrent_workers or 1))
            logger.info("Spawning %s queue worker(s)", worker_count)

            self._worker_tasks = {
                worker_id: asyncio.create_task(
                    self._worker_loop(worker_id),
                    name=f"queue-worker-{worker_id}",
                )
                for worker_id in range(1, worker_count + 1)
            }

            results = await asyncio.gather(
                *self._worker_tasks.values(), return_exceptions=True
            )
            for result in results:
                if isinstance(result, Exception):
                    logger.error("Queue worker exited with error: %s", result)
                    raise result

        except Exception as e:
            logger.error(f"Error starting queue service: {e}")
            raise
        finally:
            self.is_running = False

            if self._control_watcher_task:
                self._control_watcher_task.cancel()
                try:
                    await asyncio.gather(
                        self._control_watcher_task, return_exceptions=True
                    )
                except Exception:
                    pass
                self._control_watcher_task = None

            self._worker_tasks.clear()

    async def stop_service(self):
        """Gracefully stop the service with ghost process prevention"""
        logger.info(
            f"STOPPING QueueMigrationService instance #{self.instance_id} - Setting is_running=False immediately"
        )

        # CRITICAL: Set is_running to False IMMEDIATELY to prevent ghost processes
        self.is_running = False
        logger.info(
            f"Queue service instance #{self.instance_id} is_running flag set to: {self.is_running}"
        )

        # Remove from active instances tracking
        if self.instance_id in QueueMigrationService._active_instances:
            QueueMigrationService._active_instances.remove(self.instance_id)
            logger.info(f"Removed instance #{self.instance_id} from active instances")
            logger.info(
                f"Remaining active instances: {len(QueueMigrationService._active_instances)} - IDs: {list(QueueMigrationService._active_instances)}"
            )

        # Cancel any active worker tasks (best-effort)
        if self._worker_tasks:
            logger.info(
                "Cancelling %s worker task(s) for instance #%s",
                len(self._worker_tasks),
                self.instance_id,
            )
            for task in self._worker_tasks.values():
                task.cancel()
            await asyncio.gather(*self._worker_tasks.values(), return_exceptions=True)
            self._worker_tasks.clear()

        # Cancel control watcher task (best-effort)
        if self._control_watcher_task:
            self._control_watcher_task.cancel()
            try:
                await asyncio.gather(self._control_watcher_task, return_exceptions=True)
            except Exception:
                pass
            self._control_watcher_task = None

        # Clear inflight tracking
        self._worker_inflight.clear()
        self._worker_inflight_message.clear()
        self._worker_inflight_task_param.clear()
        self._worker_inflight_task.clear()

        # Close queue clients (best-effort)
        try:
            if self.main_queue:
                self.main_queue.close()
        except Exception:
            pass

        try:
            self.queue_service.close()
        except Exception:
            pass

    async def stop_process(
        self, process_id: str, timeout_seconds: float = 10.0
    ) -> bool:
        """Hard-kill an in-flight process by process_id.

        Behavior:
        - Deletes the in-flight queue message so it won't be retried
        - Best-effort deletes generated artifacts (blobs) for the process
        - Cancels only the in-flight job task (the worker continues polling)

        If the process_id is not currently being processed, returns False.
        """

        target_worker_id = None
        for worker_id, inflight_process_id in self._worker_inflight.items():
            if inflight_process_id == process_id:
                target_worker_id = worker_id
                break

        if not target_worker_id:
            logger.warning(
                "Requested kill for process_id=%s but no worker is inflight",
                process_id,
            )
            return False

        logger.warning(
            "Hard-kill requested for process_id=%s (worker_id=%s)",
            process_id,
            target_worker_id,
        )

        # 1) Delete the queue message (best-effort). This prevents re-processing.
        await self._delete_inflight_queue_message(target_worker_id)

        # 2) Delete generated artifacts/logs for this process (best-effort).
        task_param = self._worker_inflight_task_param.get(target_worker_id)
        if task_param:
            await self._cleanup_process_blobs(task_param)
        else:
            logger.warning(
                "No task_param tracked for worker_id=%s; skipping blob cleanup",
                target_worker_id,
            )

        # 2b) Delete telemetry for this process (best-effort).
        await self._cleanup_process_telemetry(process_id)

        # 3) Cancel only the in-flight job task (worker loop continues).
        job_task = self._worker_inflight_task.get(target_worker_id)
        if job_task:
            job_task.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.shield(job_task), timeout=timeout_seconds
                )
            except asyncio.CancelledError:
                # Expected: we intentionally cancelled the in-flight job.
                pass
            except asyncio.TimeoutError:
                logger.warning(
                    "Timed out waiting for job cancellation process_id=%s worker_id=%s",
                    process_id,
                    target_worker_id,
                )
            except Exception:
                pass

        return True

    async def _control_watcher_loop(self):
        """Watch shared control records and execute kill locally when owned.

        This loop is replica-agnostic: it only checks kill requests for process_ids
        that are currently in-flight on this instance.
        """

        poll_s = max(
            1, int(getattr(self.config, "control_poll_interval_seconds", 2) or 2)
        )
        instance_tag = f"instance-{self.instance_id}"

        try:
            control: ProcessControlManager = await self.app_context.get_service_async(
                ProcessControlManager
            )
        except Exception:
            # Fallback: construct directly (still best-effort)
            control = ProcessControlManager(self.app_context)

        while self.is_running:
            try:
                inflight_process_ids = set(self._worker_inflight.values())
                if not inflight_process_ids:
                    await asyncio.sleep(poll_s)
                    continue

                for process_id in inflight_process_ids:
                    record = await control.get(process_id)
                    if not record or not record.kill_requested:
                        continue
                    if record.kill_state in {"executed", "executing"}:
                        continue

                    logger.warning(
                        "Control watcher: kill requested process_id=%s state=%s",
                        process_id,
                        record.kill_state,
                    )

                    await control.ack_executing(process_id, instance_tag)
                    ok = await self.stop_process(process_id)
                    if ok:
                        await control.mark_executed(process_id, instance_tag)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Control watcher loop error")

            await asyncio.sleep(poll_s)

    async def stop_worker(self, worker_id: int, timeout_seconds: float = 5.0) -> bool:
        """Stop a specific worker (processor) by cancelling its task.

        Prefer `stop_process(process_id)` unless you already know the worker id.

        Notes:
        - If the worker is mid-message, it may stop without deleting the message.
          The message will reappear after the visibility timeout.
        - This is best-effort cleanup; it primarily prevents the worker from
          dequeuing more messages.
        """

        task = self._worker_tasks.get(worker_id)
        if not task:
            logger.warning("Requested stop for missing worker_id=%s", worker_id)
            return False

        inflight = self._worker_inflight.get(worker_id)
        if inflight:
            logger.info(
                "Stopping worker %s (inflight process_id=%s)", worker_id, inflight
            )
        else:
            logger.info("Stopping worker %s", worker_id)

        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(
                "Timed out waiting for worker %s to stop; task will remain cancelled",
                worker_id,
            )
        except Exception:
            # Cancellation typically raises CancelledError which is fine.
            pass
        finally:
            self._worker_tasks.pop(worker_id, None)
            self._worker_inflight.pop(worker_id, None)
            self._worker_inflight_message.pop(worker_id, None)
            self._worker_inflight_task_param.pop(worker_id, None)
            self._worker_inflight_task.pop(worker_id, None)
            self.active_workers.discard(worker_id)

        return True

    def _storage_account_name(self) -> str:
        """Extract a storage account name from config (handles account name or URL)."""

        raw = (self.config.storage_account_name or "").strip()
        if not raw:
            return raw

        if raw.startswith("http://") or raw.startswith("https://"):
            host = urlparse(raw).netloc
            return host.split(".")[0] if host else raw

        # If user passed a hostname like "mystorage.queue.core.windows.net"
        if "." in raw:
            return raw.split(".")[0]

        return raw

    async def _delete_inflight_queue_message(self, worker_id: int):
        """Best-effort delete of the queue message currently held by a worker."""

        msg = self._worker_inflight_message.get(worker_id)
        if not msg:
            logger.warning(
                "No inflight queue message tracked for worker_id=%s", worker_id
            )
            return

        message_id, pop_receipt = msg
        try:
            if self.main_queue:
                self.main_queue.delete_message(message_id, pop_receipt)
                logger.info(
                    "Deleted inflight queue message worker_id=%s message_id=%s",
                    worker_id,
                    message_id,
                )
        except ResourceNotFoundError:
            # Message was already deleted or pop_receipt expired.
            logger.info(
                "Inflight queue message already gone worker_id=%s message_id=%s",
                worker_id,
                message_id,
            )
        except AzureError as e:
            logger.error(
                "Failed to delete inflight queue message worker_id=%s message_id=%s err=%s",
                worker_id,
                message_id,
                e,
            )

    async def _cleanup_process_blobs(self, task_param: Analysis_TaskParam):
        """Best-effort delete of blobs for a process (generated files/logs)."""

        # Avoid blocking the event loop during large deletes.
        await asyncio.to_thread(self._cleanup_process_blobs_sync, task_param)

    async def _cleanup_output_blobs(self, task_param: Analysis_TaskParam):
        """Best-effort delete of only the output folder blobs for a process."""

        await asyncio.to_thread(self._cleanup_output_blobs_sync, task_param)

    def _cleanup_process_blobs_sync(self, task_param: Analysis_TaskParam):
        account = self._storage_account_name()
        if not account:
            logger.warning("No storage account configured; skipping blob cleanup")
            return

        credential = get_azure_credential()

        process_prefix = f"{task_param.process_id}/"
        container_name = task_param.container_name

        def _is_directory_entry(entry: dict) -> bool:
            try:
                # Support multiple shapes from helper implementations.
                if entry.get("is_directory") is True:
                    return True
                if str(entry.get("is_directory", "")).strip().lower() in {
                    "true",
                    "1",
                    "yes",
                }:
                    return True

                kind = (
                    str(entry.get("type", "") or entry.get("resource_type", ""))
                    .strip()
                    .lower()
                )
                if kind in {"directory", "dir", "folder"}:
                    return True
            except Exception:
                return False
            return False

        try:
            helper = StorageBlobHelper(account_name=account, credential=credential)
            blobs = helper.list_blobs(container_name, prefix=process_prefix)

            # Storage accounts with hierarchical namespace (ADLS Gen2) can surface
            # directory entries (e.g., '<pid>/output') which cannot be deleted via
            # blob delete APIs.
            blob_names: list[str] = []
            for b in blobs:
                name = (b.get("name") or "").strip()
                if not name:
                    continue
                if _is_directory_entry(b):
                    continue
                # Additional safeguard: skip common directory placeholders even if helper
                # doesn't expose directory metadata.
                if name.rstrip("/") in {
                    task_param.process_id,
                    f"{task_param.process_id}/output",
                    f"{task_param.process_id}/source",
                }:
                    continue
                blob_names.append(name)
            if not blob_names:
                logger.warning(
                    "Blob cleanup: no blobs found process_id=%s container=%s prefix=%s",
                    task_param.process_id,
                    container_name,
                    process_prefix,
                )
                return

            results = helper.delete_multiple_blobs(container_name, blob_names)
            deleted = sum(1 for ok in results.values() if ok)

            # ADLS Gen2 (HNS) can retain directory entries even after all files are deleted.
            # Best-effort: remove the process directory recursively via the DFS endpoint.
            try:
                import importlib

                dl_mod = importlib.import_module("azure.storage.filedatalake")
                DataLakeServiceClient = getattr(dl_mod, "DataLakeServiceClient")

                dl = DataLakeServiceClient(
                    account_url=f"https://{account}.dfs.core.windows.net",
                    credential=credential,
                )
                fs = dl.get_file_system_client(container_name)
                dir_client = fs.get_directory_client(task_param.process_id)
                try:
                    dir_client.delete_directory(recursive=True)
                except TypeError as te:
                    # Some SDK versions surface an internal PathClient._delete signature
                    # mismatch where `recursive` is passed twice. If the directory is
                    # already empty (we just deleted blobs), retry without recursive.
                    if "recursive" in str(te) and "multiple values" in str(te):
                        dir_client.delete_directory()
                    else:
                        raise
            except Exception as e:
                logger.info(
                    "Process directory delete skipped/failed process_id=%s container=%s err=%s",
                    task_param.process_id,
                    container_name,
                    e,
                )

            logger.warning(
                "Blob cleanup complete process_id=%s container=%s deleted=%s",
                task_param.process_id,
                container_name,
                deleted,
            )
        except Exception as e:
            logger.error(
                "Blob cleanup failed process_id=%s container=%s err=%s",
                task_param.process_id,
                container_name,
                e,
            )

    def _cleanup_output_blobs_sync(self, task_param: Analysis_TaskParam):
        account = self._storage_account_name()
        if not account:
            logger.warning(
                "No storage account configured; skipping output blob cleanup"
            )
            return

        credential = get_azure_credential()

        # Prefer the explicit output_file_folder passed in the queue payload.
        output_prefix = (getattr(task_param, "output_file_folder", None) or "").strip()
        if not output_prefix:
            output_prefix = f"{task_param.process_id}/output"

        # Normalize to a folder-like prefix.
        output_prefix = output_prefix.strip("/") + "/"

        # Safety: never allow an output cleanup call to delete the entire process prefix.
        if output_prefix == f"{task_param.process_id}/":
            logger.error(
                "Refusing output cleanup with broad prefix process_id=%s container=%s prefix=%s",
                task_param.process_id,
                task_param.container_name,
                output_prefix,
            )
            return

        container_name = task_param.container_name

        def _is_directory_entry(entry: dict) -> bool:
            try:
                if entry.get("is_directory") is True:
                    return True
                if str(entry.get("is_directory", "")).strip().lower() in {
                    "true",
                    "1",
                    "yes",
                }:
                    return True

                kind = (
                    str(entry.get("type", "") or entry.get("resource_type", ""))
                    .strip()
                    .lower()
                )
                if kind in {"directory", "dir", "folder"}:
                    return True
            except Exception:
                return False
            return False

        try:
            helper = StorageBlobHelper(account_name=account, credential=credential)
            blobs = helper.list_blobs(container_name, prefix=output_prefix)

            blob_names: list[str] = []
            output_dir_name = output_prefix.rstrip("/")
            for b in blobs:
                name = (b.get("name") or "").strip()
                if not name:
                    continue
                if _is_directory_entry(b):
                    continue
                # Some helpers may return the directory itself (without trailing '/').
                if name.rstrip("/") == output_dir_name:
                    continue
                blob_names.append(name)
            if not blob_names:
                logger.info(
                    "Output cleanup: no blobs found process_id=%s container=%s prefix=%s",
                    task_param.process_id,
                    container_name,
                    output_prefix,
                )
                return

            results = helper.delete_multiple_blobs(container_name, blob_names)
            deleted = sum(1 for ok in results.values() if ok)

            # Best-effort: remove the output directory entry itself for ADLS Gen2 (HNS).
            try:
                import importlib

                dl_mod = importlib.import_module("azure.storage.filedatalake")
                DataLakeServiceClient = getattr(dl_mod, "DataLakeServiceClient")

                dl = DataLakeServiceClient(
                    account_url=f"https://{account}.dfs.core.windows.net",
                    credential=credential,
                )
                fs = dl.get_file_system_client(container_name)
                dir_client = fs.get_directory_client(output_dir_name)
                try:
                    dir_client.delete_directory(recursive=True)
                except TypeError as te:
                    if "recursive" in str(te) and "multiple values" in str(te):
                        dir_client.delete_directory()
                    else:
                        raise
            except Exception as e:
                logger.info(
                    "Output directory delete skipped/failed process_id=%s container=%s dir=%s err=%s",
                    task_param.process_id,
                    container_name,
                    output_dir_name,
                    e,
                )

            logger.warning(
                "Output cleanup complete process_id=%s container=%s prefix=%s deleted=%s",
                task_param.process_id,
                container_name,
                output_prefix,
                deleted,
            )
        except Exception as e:
            logger.error(
                "Output cleanup failed process_id=%s container=%s prefix=%s err=%s",
                task_param.process_id,
                container_name,
                output_prefix,
                e,
            )

    async def _cleanup_process_telemetry(self, process_id: str):
        """Best-effort delete of telemetry records for a process."""

        if not self.app_context:
            logger.warning(
                "No app_context configured; skipping telemetry delete process_id=%s",
                process_id,
            )
            return

        try:
            telemetry: TelemetryManager = await self.app_context.get_service_async(
                TelemetryManager
            )
        except Exception:
            # Fallback: construct directly (still best-effort)
            telemetry = TelemetryManager(self.app_context)

        try:
            await telemetry.delete_process(process_id)
            logger.info("Telemetry deleted for process_id=%s", process_id)
        except Exception:
            logger.exception(
                "Failed to delete telemetry for process_id=%s",
                process_id,
            )

    ######################################################
    # Queue message processing (Migration Process Start)
    ######################################################
    async def process_message(self):
        """Backward-compatible entrypoint: process messages with a single worker."""

        await self._worker_loop(worker_id=1)

    async def _worker_loop(self, worker_id: int):
        """Poll and process queue messages for a single worker."""

        self.active_workers.add(worker_id)
        logger.info("[worker %s] started", worker_id)

        try:
            while self.is_running:
                if not self.main_queue:
                    await asyncio.sleep(self.config.poll_interval_seconds)
                    continue

                received_any = False
                try:
                    for queue_message in self.main_queue.receive_messages(
                        max_messages=1,
                        visibility_timeout=self.config.visibility_timeout_minutes * 60,
                    ):
                        received_any = True
                        job_task = asyncio.create_task(
                            self._process_queue_message(worker_id, queue_message),
                            name=f"queue-job-{worker_id}",
                        )
                        self._worker_inflight_task[worker_id] = job_task

                        try:
                            await job_task
                        except asyncio.CancelledError:
                            # Cancelled intentionally via stop_process/stop_service.
                            logger.warning(
                                "[worker %s] in-flight job cancelled", worker_id
                            )
                        except Exception:
                            # Defensive: a job should never crash the worker.
                            logger.exception(
                                "[worker %s] job task crashed unexpectedly", worker_id
                            )

                            # Best-effort: if the job task crashed before it could record failure,
                            # ensure telemetry is marked failed and the message is deleted (no-retry).
                            try:
                                inflight_pid = self._worker_inflight.get(
                                    worker_id, "<unknown>"
                                )
                                inflight_task_param = (
                                    self._worker_inflight_task_param.get(worker_id)
                                )
                                task_param_for_cleanup = (
                                    inflight_task_param
                                    if isinstance(
                                        inflight_task_param, Analysis_TaskParam
                                    )
                                    else None
                                )
                                await self._handle_failed_no_retry(
                                    queue_message=queue_message,
                                    process_id=inflight_pid,
                                    failure_reason="Job task crashed unexpectedly",
                                    execution_time=0.0,
                                    task_param=task_param_for_cleanup,
                                )
                            except Exception:
                                logger.exception(
                                    "[worker %s] failed to handle crashed job task",
                                    worker_id,
                                )
                        finally:
                            self._worker_inflight_task.pop(worker_id, None)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # Defensive: queue receive can fail transiently (network/storage).
                    # Don't exit the worker; log and continue polling.
                    logger.exception(
                        "[worker %s] queue receive loop error (will continue)",
                        worker_id,
                    )
                    await asyncio.sleep(self.config.poll_interval_seconds)

                if not received_any:
                    await asyncio.sleep(self.config.poll_interval_seconds)
        except asyncio.CancelledError:
            # Task was cancelled intentionally (stop_service/stop_worker).
            raise
        finally:
            self._worker_inflight.pop(worker_id, None)
            self.active_workers.discard(worker_id)
            logger.info("[worker %s] stopped", worker_id)

    async def _process_queue_message(self, worker_id: int, queue_message: QueueMessage):
        """Execute one queue message through the step-based workflow runner."""

        message_start_time = time.time()

        # Ensure this function never raises (except CancelledError), so a single
        # bad message can't crash the entire service.
        process_id: str = "<unknown>"

        try:
            logger.info(
                "[worker %s] Message dequeued from %s - %s",
                worker_id,
                getattr(self.main_queue, "queue_name", "<unknown>"),
                getattr(queue_message, "content", "<no-content>"),
            )

            # Parse queue payload into the workflow input model.
            try:
                task_param = self._build_task_param(queue_message)
                process_id = task_param.process_id
            except Exception as e:
                execution_time = time.time() - message_start_time
                reason = f"Invalid queue message: {e}"

                logger.error(
                    "[worker %s] %s message_id=%s raw=%s",
                    worker_id,
                    reason,
                    getattr(queue_message, "id", "<unknown>"),
                    getattr(queue_message, "content", "<no-content>"),
                )

                # No process_id available; still enforce no-retry by deleting message.
                await self._handle_failed_no_retry(
                    queue_message,
                    process_id,
                    reason,
                    execution_time,
                    task_param=None,
                )
                return

            self._worker_inflight[worker_id] = process_id
            self._worker_inflight_task_param[worker_id] = task_param
            if getattr(queue_message, "id", None) and getattr(
                queue_message, "pop_receipt", None
            ):
                self._worker_inflight_message[worker_id] = (
                    queue_message.id,
                    queue_message.pop_receipt,
                )

            # Use the step-based workflow runner (src/steps/migration_processor.py).
            migration_processor = self.app_context.get_service(
                WorkflowMigrationProcessor
            )

            try:
                result = await migration_processor.run(task_param)

                execution_time = time.time() - message_start_time
                is_hard_terminated = bool(getattr(result, "is_hard_terminated", False))

                # Single-queue, no-retry policy:
                # - Success: delete message.
                # - Failure (exception, None output, or hard-termination): delete message.
                if result is not None and not is_hard_terminated:
                    await self._handle_successful_processing(
                        queue_message, process_id, execution_time
                    )
                else:
                    if is_hard_terminated:
                        blocking_issues = getattr(result, "blocking_issues", None) or []
                        blocking_suffix = (
                            f" ({', '.join(blocking_issues)})"
                            if blocking_issues
                            else ""
                        )
                        reason = (
                            (getattr(result, "reason", None) or "Hard terminated")
                            + blocking_suffix
                            + "\n\nCLEANUP NOTE: This run was hard-terminated. The uploaded resource files for this process will be cleared from blob storage."
                        )
                    else:
                        reason = "Workflow output is None"
                    await self._handle_failed_no_retry(
                        queue_message,
                        process_id,
                        reason,
                        execution_time,
                        task_param=task_param,
                        cleanup_scope="process" if is_hard_terminated else "output",
                    )

            except WorkflowExecutorFailedException as e:
                execution_time = time.time() - message_start_time
                await self._handle_failed_no_retry(
                    queue_message,
                    process_id,
                    str(e),
                    execution_time,
                    task_param=task_param,
                )
            except Exception as e:
                execution_time = time.time() - message_start_time
                await self._handle_failed_no_retry(
                    queue_message,
                    process_id,
                    f"Unhandled exception: {e}",
                    execution_time,
                    task_param=task_param,
                )
            finally:
                migration_processor = None

        except asyncio.CancelledError:
            # When cancelled, we assume stop_process has already deleted the message
            # (hard-kill). If it hasn't, the message may become visible again after
            # visibility timeout.
            logger.warning(
                "[worker %s] cancelled while processing process_id=%s message_id=%s",
                worker_id,
                process_id,
                getattr(queue_message, "id", "<unknown>"),
            )
            raise
        except Exception:
            # Last resort: don't let unexpected errors kill the worker.
            execution_time = time.time() - message_start_time
            logger.exception(
                "[worker %s] unexpected error while processing message_id=%s",
                worker_id,
                getattr(queue_message, "id", "<unknown>"),
            )
            try:
                await self._handle_failed_no_retry(
                    queue_message,
                    process_id,
                    "Worker crashed while processing message",
                    execution_time,
                    task_param=None,
                )
            except Exception:
                pass
        finally:
            self._worker_inflight.pop(worker_id, None)
            self._worker_inflight_message.pop(worker_id, None)
            self._worker_inflight_task_param.pop(worker_id, None)

    async def _handle_successful_processing(
        self, queue_message: QueueMessage, process_id: str, execution_time: float
    ):
        """Handle successful message processing"""

        try:
            # Delete message from queue
            if self.main_queue:
                self.main_queue.delete_message(
                    queue_message.id, queue_message.pop_receipt
                )

                if self.debug_mode:
                    logger.info(
                        f"The message {queue_message.id} - Successfully processed {process_id} "
                        f"in {execution_time:.2f}s"
                    )

        except ResourceNotFoundError:
            # Message was already deleted or visibility timeout expired - this is okay
            logger.debug(
                f"The message {queue_message.id} already processed "
                f"(visibility timeout expired or processed by another worker)"
            )
        except AzureError as e:
            logger.error(f"Failed to delete processed message: {e}")

    async def _handle_failed_no_retry(
        self,
        queue_message: QueueMessage,
        process_id: str,
        failure_reason: str,
        execution_time: float,
        task_param: Analysis_TaskParam | None = None,
        cleanup_scope: str = "output",
    ):
        """No-retry policy: delete the message even on failure."""

        logger.error(
            "Job failed (no-retry). Deleting message. process_id=%s message_id=%s reason=%s elapsed=%.2fs",
            process_id,
            queue_message.id,
            failure_reason,
            execution_time,
        )

        # Best-effort: reflect failure in telemetry so status won't remain "running"
        # when a job crashes before the workflow records its own failure.
        if (
            self.app_context
            and process_id
            and process_id != "<unknown>"
            and (process_id or "").strip()
        ):
            try:
                telemetry: TelemetryManager = await self.app_context.get_service_async(
                    TelemetryManager
                )

                # Use the latest known step from telemetry if possible.
                failed_step = "unknown"
                try:
                    current = await telemetry.get_current_process(process_id)
                    if current and getattr(current, "step", None):
                        failed_step = current.step
                except Exception:
                    failed_step = "unknown"

                await telemetry.record_failure_outcome(
                    process_id=process_id,
                    error_message=failure_reason,
                    failed_step=failed_step,
                    failure_details={
                        "source": "queue_service",
                        "message_id": getattr(queue_message, "id", None),
                        "elapsed_seconds": execution_time,
                    },
                    execution_time_seconds=execution_time,
                )
            except Exception:
                logger.exception(
                    "Failed to write failure telemetry (process_id=%s)", process_id
                )

        # Best-effort cleanup:
        # - Default: clear output folder only (avoids stale artifacts while preserving inputs).
        # - Hard termination: clear the entire process folder (includes uploaded resources).
        if task_param is not None:
            try:
                scope = (cleanup_scope or "output").strip().lower()
                if scope == "process":
                    await self._cleanup_process_blobs(task_param)
                elif scope == "output":
                    await self._cleanup_output_blobs(task_param)
            except Exception:
                logger.exception(
                    "Failed to cleanup blobs (process_id=%s scope=%s)",
                    process_id,
                    cleanup_scope,
                )

        try:
            if self.main_queue:
                self.main_queue.delete_message(
                    queue_message.id, queue_message.pop_receipt
                )
        except AzureError as e:
            logger.error("Failed to delete failed message: %s", e)

    def _build_task_param(self, queue_message: QueueMessage) -> Analysis_TaskParam:
        """Convert Azure Queue message -> Analysis_TaskParam for the step-based workflow."""

        parsed = MigrationQueueMessage.from_queue_message(queue_message)
        req = parsed.migration_request
        return Analysis_TaskParam(
            process_id=req["process_id"],
            container_name=req["container_name"],
            source_file_folder=req["source_file_folder"],
            workspace_file_folder=req["workspace_file_folder"],
            output_file_folder=req["output_file_folder"],
        )

    async def _ensure_queues_exist(self):
        """Ensure required queue exists."""
        try:
            # Create main queue if it doesn't exist
            try:
                self.main_queue.create_queue()
                if self.debug_mode:
                    logger.info(f"Created main queue: {self.config.queue_name}")
            except Exception:
                pass  # Queue already exists

        except AzureError as e:
            logger.error(f"Failed to ensure queues exist: {e}")
            raise

    def get_service_status(self) -> dict:
        """Get current service status"""
        return {
            "is_running": self.is_running,
            "active_workers": len(self.active_workers),
            "active_worker_ids": sorted(self.active_workers),
            "inflight": dict(self._worker_inflight),
            "configured_workers": self.config.concurrent_workers,
            "queue_name": self.config.queue_name,
            "visibility_timeout_minutes": self.config.visibility_timeout_minutes,
        }

    async def get_queue_info(self) -> dict:
        """Get queue information for debugging"""
        try:
            # Get queue properties
            main_queue_props = self.main_queue.get_queue_properties()

            return {
                "main_queue": {
                    "name": self.config.queue_name,
                    "approximate_message_count": main_queue_props.approximate_message_count,
                    "metadata": main_queue_props.metadata,
                },
                "visibility_timeout_minutes": self.config.visibility_timeout_minutes,
                "poll_interval_seconds": self.config.poll_interval_seconds,
            }
        except Exception as e:
            return {"error": f"Failed to get queue info: {e}"}
