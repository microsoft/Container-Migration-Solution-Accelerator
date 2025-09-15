"""
Queue-based Migration Service - Main service for processing migration requests from Azure Storage Queue.

Features:
- Azure Storage Queue integration with visibility timeout management
- Retry logic with exponential backoff (up to 5 attempts)
- Concurrent processing of multiple queue messages
- Dead letter queue for failed messages
- Comprehensive error handling and monitoring
"""

import asyncio
import base64
from dataclasses import dataclass
import json
import logging
import time
from typing import Any

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.storage.queue import QueueClient, QueueMessage, QueueServiceClient

from libs.application.application_context import AppContext
from services.migration_service import (
    MigrationEngineResult,
    create_migration_service,
)
from services.retry_manager import RetryManager
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
    output_file_folder: str = "converted",
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
        output_file_folder: Output folder for converted files (mandatory)

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
    dead_letter_queue_name: str = "process-queue-dead"
    visibility_timeout_minutes: int = 30  # Reduced for testing - was 30
    max_retry_count: int = (
        0  # it will be enabled in batch process. we don't allow retry
    )
    concurrent_workers: int = 1
    poll_interval_seconds: int = 5
    message_timeout_minutes: int = 25


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

    Processes migration requests from Azure Storage Queue with:
    - Visibility timeout management to prevent duplicate processing
    - Automatic retry with exponential backoff
    - Dead letter queue for permanently failed messages
    - Concurrent worker processing
    """

    # Class-level tracking to prevent multiple instances and detect ghost processes
    _instance_count = 0
    _active_instances = set()
    main_queue: QueueClient | None = None
    dlq_queue: QueueClient | None = None

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

        logger.info(f"🏗️ Creating QueueMigrationService instance #{self.instance_id}")
        logger.info(
            f"🔍 Active instances: {len(QueueMigrationService._active_instances)} - IDs: {list(QueueMigrationService._active_instances)}"
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
        self.dlq_queue = self.queue_service.get_queue_client(config.dead_letter_queue_name)

        # Initialize retry manager
        self.retry_manager = RetryManager(
            max_retries=config.max_retry_count,
            base_delay_seconds=30,  # Start with 30 seconds
            max_delay_seconds=300,  # Cap at 5 minutes
        )

        # Worker tracking
        self.active_workers = set()

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
            await self.process_message()

        except Exception as e:
            logger.error(f"Error starting queue service: {e}")
            raise
        finally:
            self.is_running = False

    async def stop_service(self):
        """Gracefully stop the service with ghost process prevention"""
        logger.info(
            f"🛑 STOPPING QueueMigrationService instance #{self.instance_id} - Setting is_running=False immediately"
        )

        # CRITICAL: Set is_running to False IMMEDIATELY to prevent ghost processes
        self.is_running = False
        logger.info(
            f"🔍 Queue service instance #{self.instance_id} is_running flag set to: {self.is_running}"
        )

        # Remove from active instances tracking
        if self.instance_id in QueueMigrationService._active_instances:
            QueueMigrationService._active_instances.remove(self.instance_id)
            logger.info(f"🗑️ Removed instance #{self.instance_id} from active instances")
            logger.info(
                f"🔍 Remaining active instances: {len(QueueMigrationService._active_instances)} - IDs: {list(QueueMigrationService._active_instances)}"
            )

        # Wait a moment for workers to finish current messages
        await asyncio.sleep(2)

    ######################################################
    # Queue message processing (Migration Process Start)
    ######################################################
    async def process_message(self):
        """Process a single queue message with retry logic"""
        start_time = time.time()

        # Additional ghost process check after try block starts
        while self.is_running:
            # Check whether Queue has a message
            if self.main_queue and not self.main_queue.peek_messages(max_messages=1):
                logger.info("No messages in main queue")
                await asyncio.sleep(5)
                continue

            # Message in the Queue
            if self.main_queue:
                for queue_message in self.main_queue.receive_messages(
                    max_messages=1,
                    visibility_timeout=self.config.visibility_timeout_minutes,
                ):  # type: ignore
                    logger.info(
                        f"Message dequeued from {self.main_queue.queue_name} - {queue_message.content}"
                    )  # type: ignore
                    # Initialize variables with default values
                    process_id: str = ""
                    user_id: str = ""
                    migration_request: dict[str, Any] = {}

                    if is_base64_encoded(queue_message.content):
                        queue_message.content = base64.b64decode(
                            queue_message.content
                        ).decode("utf-8")
                        json_queue_message_content = json.loads(queue_message.content)
                        # Get 2 Mandatory Fields
                        process_id = json_queue_message_content.get("process_id", "")
                        user_id = json_queue_message_content.get("user_id", "")
                        # Make up Message
                        migration_request = create_default_migration_request(
                            user_id=user_id, process_id=process_id
                        )
                    else:
                        # Handle non-base64 encoded content
                        json_queue_message_content = json.loads(queue_message.content)
                        process_id = json_queue_message_content.get("process_id", "")
                        user_id = json_queue_message_content.get("user_id", "")
                        migration_request = create_default_migration_request(
                            user_id=user_id, process_id=process_id
                        )

                    # Update RetryCount to MigrationRequest
                    # migration_request["retry_count"] = queue_message.dequeue_count + 1

                    # Create and execute migration engine
                    migration_engine = await create_migration_service(
                        app_context=self.app_context,
                        debug_mode=self.debug_mode,
                        timeout_minutes=self.config.message_timeout_minutes,
                    )

                    try:
                        # Execute migration process
                        #  update queue's visibility from here.
                        # self.main_queue.update_message(
                        #     queue_message,
                        #     visibility_timeout=self.config.visibility_timeout_minutes,
                        # )
                        migration_result: MigrationEngineResult = (
                            await migration_engine.execute_migration(
                                process_id=process_id,
                                user_id=user_id or "default-user",
                                migration_request=migration_request,
                            )
                        )

                        execution_time = time.time() - start_time

                        if migration_result.success:
                            # Success - delete message from queue
                            await self._handle_successful_processing(
                                queue_message, migration_result, execution_time
                            )
                        else:
                            # Failed - determine if retryable
                            await self._handle_failed_processing(
                                queue_message,
                                migration_result,
                                execution_time,
                            )

                            # Update
                    finally:
                        # Always cleanup engine resources
                        await migration_engine.cleanup()
                        migration_engine = None

    async def _handle_successful_processing(
        self,
        queue_message: QueueMessage,
        result: MigrationEngineResult,
        execution_time: float,
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
                        f"The message {queue_message.id} - Successfully processed {result.process_id} "
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

    async def _handle_failed_processing(
        self,
        queue_message: QueueMessage,
        result: MigrationEngineResult,
        execution_time: float,
    ):
        """Handle failed message processing with retry logic"""
        if (
            result.is_retryable
            and queue_message.dequeue_count < self.config.max_retry_count  # type: ignore
        ):
            # Retryable failure - increment retry count and requeue
            await self._retry_message(
                queue_message,
                result,
                result.error_message or "Unknown error",
            )
        else:
            # Non-retryable or max retries exceeded - move to DLQ
            failure_reason = (
                f"Max retries ({self.config.max_retry_count}) exceeded"
                if queue_message.dequeue_count >= self.config.max_retry_count
                else f"Non-retryable error: {result.error_message}"
            )

            await self._move_to_dead_letter_queue(queue_message, failure_reason, result)

    async def _handle_processing_exception(
        self,
        worker_id: int,
        queue_message: QueueMessage,
        result: MigrationEngineResult,
        error_message: str,
    ):
        """Handle unexpected processing exceptions"""
        if queue_message.dequeue_count < self.config.max_retry_count:
            await self._retry_message(queue_message, result, error_message)
        else:
            await self._move_to_dead_letter_queue(
                queue_message,
                f"Max retries exceeded - last error: {error_message}",
                result=result,
            )

    async def _retry_message(
        self,
        queue_message: QueueMessage,
        result: MigrationEngineResult,
        error_message: str,
    ):
        """Retry a failed message with exponential backoff or immediate retry for hard termination"""
        try:
            # NEW: Determine retry strategy based on immediate retry flag
            if (
                hasattr(result, "requires_immediate_retry")
                and result.requires_immediate_retry
            ):
                # Hard termination: Immediate retry with visibility_timeout=0
                visibility_timeout_minutes = 0  # Immediate retry
                retry_type = "IMMEDIATE"
                logger.info(
                    f"[IMMEDIATE_RETRY] Hard termination detected for message {queue_message.id} - "
                    f"using immediate retry (visibility_timeout=0)"
                )
            else:
                # Normal failure: Exponential backoff retry
                visibility_timeout_minutes = self.config.visibility_timeout_minutes
                retry_type = "EXPONENTIAL_BACKOFF"

                # Calculate retry delay for logging (actual delay is handled by visibility timeout)
                retry_delay = self.retry_manager.calculate_delay(
                    queue_message.dequeue_count  # type: ignore
                )

            # Update Message with appropriate visibility timeout
            if self.main_queue:
                self.main_queue.update_message(
                    message=queue_message,
                    visibility_timeout=visibility_timeout_minutes,
                )

            # Enhanced logging with retry type and telemetry
            if retry_type == "IMMEDIATE":
                logger.info(
                    f"[{retry_type}] Retrying message {queue_message.id} immediately "
                    f"(attempt {queue_message.dequeue_count}/{self.config.max_retry_count}) "
                    f"due to hard termination"
                )

                # NEW: Send telemetry for immediate retry scenarios
                await self._send_retry_telemetry(
                    queue_message, result, retry_type, visibility_timeout_minutes
                )
            else:
                retry_delay = self.retry_manager.calculate_delay(
                    queue_message.dequeue_count  # type: ignore
                )
                logger.info(
                    f"[{retry_type}] Retrying message {queue_message.id} "
                    f"(attempt {queue_message.dequeue_count}/{self.config.max_retry_count}) "
                    f"after {retry_delay}s delay (visibility_timeout={visibility_timeout_minutes}min)"
                )

                # NEW: Send telemetry for normal retry scenarios
                await self._send_retry_telemetry(
                    queue_message,
                    result,
                    retry_type,
                    visibility_timeout_minutes,
                    retry_delay,
                )

        except ResourceNotFoundError:
            # Message was already deleted or visibility timeout expired
            logger.debug(
                f"Cannot retry message {queue_message.id} - already processed "
                f"(visibility timeout expired or processed by another worker)"
            )
        except AzureError as e:
            logger.error(f"Failed to retry message: {e}")
            # If we can't retry, move to DLQ
            await self._move_to_dead_letter_queue(
                queue_message,
                f"Failed to retry message: {e}",
                result=result,
            )

    async def _send_retry_telemetry(
        self,
        queue_message: QueueMessage,
        result: MigrationEngineResult,
        retry_type: str,
        visibility_timeout_minutes: int,
        retry_delay: float = 0.0,
    ):
        """
        Send comprehensive telemetry information for retry scenarios.

        Covers all 3 behaviors: Immediate retry, exponential backoff, and dead letter queue.
        """
        try:
            # Extract process information
            process_id = result.process_id if result else "unknown"

            # Prepare telemetry data
            telemetry_data = {
                "event_type": "queue_retry_processing",
                "retry_strategy": retry_type,
                "process_id": process_id,
                "message_id": queue_message.id,
                "dequeue_count": queue_message.dequeue_count,
                "max_retry_count": self.config.max_retry_count,
                "visibility_timeout_minutes": visibility_timeout_minutes,
                "retry_delay_seconds": retry_delay,
                "error_classification": result.error_classification.value
                if result.error_classification
                else "unknown",
                "requires_immediate_retry": getattr(
                    result, "requires_immediate_retry", False
                ),
                "execution_time": result.execution_time if result else 0.0,
                "error_message": result.error_message if result else "Unknown error",
                "timestamp": time.time(),
            }

            # Add hard termination specific details for immediate retry
            if (
                retry_type == "IMMEDIATE"
                and hasattr(result, "final_state")
                and result.final_state
            ):
                termination_details = {}

                # Extract termination details from step states
                if hasattr(result.final_state, "steps"):
                    for step_index, step in enumerate(result.final_state.steps):
                        step_state = step.state.state
                        if (
                            step_state
                            and hasattr(step_state, "termination_details")
                            and step_state.termination_details
                        ):
                            step_name = getattr(
                                step_state, "name", f"Step_{step_index}"
                            )
                            termination_details[step_name] = (
                                step_state.termination_details
                            )

                telemetry_data["hard_termination_details"] = termination_details

            # Log telemetry information
            logger.info(
                f"[TELEMETRY] {retry_type} retry - Process: {process_id}, "
                f"Attempt: {queue_message.dequeue_count}/{self.config.max_retry_count}, "
                f"Visibility: {visibility_timeout_minutes}min, "
                f"Classification: {telemetry_data['error_classification']}"
            )

            # TODO: Send to actual telemetry system (Azure Application Insights, etc.)
            # For now, we log the comprehensive data
            if self.debug_mode:
                logger.debug(f"[TELEMETRY_DETAIL] {telemetry_data}")

        except Exception as e:
            logger.error(f"Failed to send retry telemetry: {e}")
            # Don't raise - telemetry failures shouldn't block retry processing

    async def _move_to_dead_letter_queue(
        self,
        queue_message: QueueMessage,
        failure_reason: str,
        result: MigrationEngineResult,
        is_poison_message: bool = False,
    ):
        """Move failed message to dead letter queue with comprehensive telemetry"""
        try:
            # Prepare DLQ message with failure details
            dlq_content = {
                "original_message": queue_message.content,
                "failure_reason": failure_reason,
                "failure_time": time.time(),
                "retry_count": queue_message.dequeue_count if result else 0,
                "process_id": result.process_id if result else "unknown",
                "is_poison_message": is_poison_message,
            }

            # Send to dead letter queue
            self.dlq_queue.send_message(json.dumps(dlq_content))

            # Delete from main queue
            self.main_queue.delete_message(queue_message)

            # NEW: Send comprehensive telemetry for dead letter queue scenarios
            await self._send_dlq_telemetry(
                queue_message, result, failure_reason, is_poison_message
            )

            logger.warning(
                f"Message moved to DLQ - Process: {dlq_content['process_id']}, "
                f"Reason: {failure_reason}"
            )

        except ResourceNotFoundError:
            # Message was already deleted or visibility timeout expired
            logger.debug(
                f"Cannot move message {queue_message.id} to DLQ - already processed "
                f"(visibility timeout expired or processed by another worker)"
            )
        except AzureError as e:
            logger.error(f"Failed to move message to DLQ: {e}")

    async def _send_dlq_telemetry(
        self,
        queue_message: QueueMessage,
        result: MigrationEngineResult,
        failure_reason: str,
        is_poison_message: bool,
    ):
        """
        Send comprehensive telemetry for dead letter queue scenarios.

        This represents the final failure case where no more retries will be attempted.
        """
        try:
            # Extract process information
            process_id = result.process_id if result else "unknown"

            # Prepare comprehensive DLQ telemetry
            dlq_telemetry = {
                "event_type": "queue_dead_letter_processing",
                "final_outcome": "DEAD_LETTER_QUEUE",
                "process_id": process_id,
                "message_id": queue_message.id,
                "total_retry_attempts": queue_message.dequeue_count,
                "max_retry_count": self.config.max_retry_count,
                "is_poison_message": is_poison_message,
                "failure_reason": failure_reason,
                "error_classification": result.error_classification.value
                if result.error_classification
                else "unknown",
                "requires_immediate_retry": getattr(
                    result, "requires_immediate_retry", False
                ),
                "execution_time": result.execution_time if result else 0.0,
                "error_message": result.error_message if result else "Unknown error",
                "dlq_timestamp": time.time(),
            }

            # Add failure analysis for different scenarios
            dequeue_count = queue_message.dequeue_count or 0  # Handle None case
            if dequeue_count >= self.config.max_retry_count:
                dlq_telemetry["dlq_reason"] = "MAX_RETRIES_EXCEEDED"
                if getattr(result, "requires_immediate_retry", False):
                    dlq_telemetry["retry_strategy_used"] = "IMMEDIATE_RETRY"
                else:
                    dlq_telemetry["retry_strategy_used"] = "EXPONENTIAL_BACKOFF"
            elif is_poison_message:
                dlq_telemetry["dlq_reason"] = "POISON_MESSAGE"
                dlq_telemetry["retry_strategy_used"] = "NONE"
            else:
                dlq_telemetry["dlq_reason"] = "NON_RETRYABLE_ERROR"
                dlq_telemetry["retry_strategy_used"] = "NONE"

            # Log comprehensive DLQ telemetry
            logger.warning(
                f"[TELEMETRY] DLQ processing - Process: {process_id}, "
                f"Reason: {dlq_telemetry['dlq_reason']}, "
                f"Attempts: {queue_message.dequeue_count}/{self.config.max_retry_count}, "
                f"Classification: {dlq_telemetry['error_classification']}"
            )

            # TODO: Send to actual telemetry system for DLQ analysis
            if self.debug_mode:
                logger.debug(f"[DLQ_TELEMETRY_DETAIL] {dlq_telemetry}")

        except Exception as e:
            logger.error(f"Failed to send DLQ telemetry: {e}")
            # Don't raise - telemetry failures shouldn't block DLQ processing

    async def _ensure_queues_exist(self):
        """Ensure required queues exist"""
        try:
            # Create main queue if it doesn't exist
            try:
                self.main_queue.create_queue()
                if self.debug_mode:
                    logger.info(f"Created main queue: {self.config.queue_name}")
            except Exception:
                pass  # Queue already exists

            # Create dead letter queue if it doesn't exist
            try:
                self.dlq_queue.create_queue()
                if self.debug_mode:
                    logger.info(f"Created DLQ: {self.config.dead_letter_queue_name}")
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
            "configured_workers": self.config.concurrent_workers,
            "queue_name": self.config.queue_name,
            "dead_letter_queue": self.config.dead_letter_queue_name,
            "max_retry_count": self.config.max_retry_count,
            "visibility_timeout_minutes": self.config.visibility_timeout_minutes,
        }

    async def get_queue_info(self) -> dict:
        """Get queue information for debugging"""
        try:
            # Get queue properties
            main_queue_props = self.main_queue.get_queue_properties()
            dlq_props = self.dlq_queue.get_queue_properties()

            return {
                "main_queue": {
                    "name": self.config.queue_name,
                    "approximate_message_count": main_queue_props.approximate_message_count,
                    "metadata": main_queue_props.metadata,
                },
                "dead_letter_queue": {
                    "name": self.config.dead_letter_queue_name,
                    "approximate_message_count": dlq_props.approximate_message_count,
                    "metadata": dlq_props.metadata,
                },
                "visibility_timeout_minutes": self.config.visibility_timeout_minutes,
                "poll_interval_seconds": self.config.poll_interval_seconds,
            }
        except Exception as e:
            return {"error": f"Failed to get queue info: {e}"}
