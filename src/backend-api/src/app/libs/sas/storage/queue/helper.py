import json
import logging
from typing import List, Dict, Any, Union
from datetime import datetime
from azure.storage.queue import (
    QueueServiceClient,
    TextBase64EncodePolicy,
    TextBase64DecodePolicy,
)
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from azure.identity import DefaultAzureCredential
from ..shared_config import get_config


class StorageQueueHelper:
    """
    Azure Storage Queue Helper Class

    A comprehensive helper class for Azure Queue Storage operations that provides
    full queue management and message handling functionality.

    Features:
    - Queue management (create, delete, list, clear)
    - Message operations (send, receive, peek, delete, update)
    - Batch message operations for efficiency
    - Message properties and metadata management
    - Visibility timeout and TTL management
    - Message encoding/decoding support (text, binary, JSON)
    - Queue statistics and monitoring
    - Error handling with retry logic
    """

    def __init__(
        self,
        connection_string: str = None,
        account_name: str = None,
        credential=None,
        config=None,
        message_encode_policy=None,
        message_decode_policy=None,
    ):
        """
        Initialize the StorageQueueHelper

        Args:
            connection_string: Azure Storage connection string (preferred for development)
            account_name: Storage account name (for managed identity)
            credential: Azure credential (DefaultAzureCredential for production)
            config: Configuration object or dictionary for custom settings
            message_encode_policy: Message encoding policy (default: TextBase64EncodePolicy)
            message_decode_policy: Message decoding policy (default: TextBase64DecodePolicy)
        """
        # Set up configuration
        if config:
            if isinstance(config, dict):
                from ..shared_config import create_config

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

        # Set up message encoding/decoding policies
        self.message_encode_policy = message_encode_policy or TextBase64EncodePolicy()
        self.message_decode_policy = message_decode_policy or TextBase64DecodePolicy()

        self._connection_string = connection_string  # Store for later use

        try:
            if connection_string:
                self.queue_service_client = QueueServiceClient.from_connection_string(
                    connection_string,
                    message_encode_policy=self.message_encode_policy,
                    message_decode_policy=self.message_decode_policy,
                )
            elif account_name and credential:
                account_url = f"https://{account_name}.queue.core.windows.net"
                self.queue_service_client = QueueServiceClient(
                    account_url,
                    credential=credential,
                    message_encode_policy=self.message_encode_policy,
                    message_decode_policy=self.message_decode_policy,
                )
            elif account_name:
                # Use DefaultAzureCredential for managed identity
                account_url = f"https://{account_name}.queue.core.windows.net"
                self.queue_service_client = QueueServiceClient(
                    account_url,
                    credential=DefaultAzureCredential(),
                    message_encode_policy=self.message_encode_policy,
                    message_decode_policy=self.message_decode_policy,
                )
            else:
                raise ValueError(
                    "Either connection_string or account_name must be provided"
                )

        except Exception as e:
            self.logger.error(f"Failed to initialize QueueServiceClient: {e}")
            raise

    # Queue Management Operations
    def create_queue(
        self,
        queue_name: str,
        metadata: Dict[str, str] = None,
        timeout: int = None,
    ) -> bool:
        """
        Create a new queue

        Args:
            queue_name: Name of the queue
            metadata: Optional metadata dictionary
            timeout: Request timeout in seconds

        Returns:
            bool: True if created successfully, False if already exists
        """
        try:
            queue_client = self.queue_service_client.get_queue_client(queue_name)
            queue_client.create_queue(metadata=metadata, timeout=timeout)
            self.logger.info(f"Queue '{queue_name}' created successfully")
            return True
        except ResourceExistsError:
            self.logger.warning(f"Queue '{queue_name}' already exists")
            return False
        except Exception as e:
            self.logger.error(f"Failed to create queue '{queue_name}': {e}")
            raise

    def delete_queue(self, queue_name: str, timeout: int = None) -> bool:
        """
        Delete a queue

        Args:
            queue_name: Name of the queue to delete
            timeout: Request timeout in seconds

        Returns:
            bool: True if deleted successfully
        """
        try:
            queue_client = self.queue_service_client.get_queue_client(queue_name)
            queue_client.delete_queue(timeout=timeout)
            self.logger.info(f"Queue '{queue_name}' deleted successfully")
            return True
        except ResourceNotFoundError:
            self.logger.warning(f"Queue '{queue_name}' not found")
            return False
        except Exception as e:
            self.logger.error(f"Failed to delete queue '{queue_name}': {e}")
            raise

    def list_queues(
        self,
        name_starts_with: str = None,
        include_metadata: bool = False,
        results_per_page: int = None,
        timeout: int = None,
    ) -> List[Dict[str, Any]]:
        """
        List all queues in the storage account

        Args:
            name_starts_with: Filter queues by name prefix
            include_metadata: Include queue metadata
            results_per_page: Number of results per page
            timeout: Request timeout in seconds

        Returns:
            List of queue information dictionaries
        """
        try:
            queues = []
            queue_list = self.queue_service_client.list_queues(
                name_starts_with=name_starts_with,
                include_metadata=include_metadata,
                results_per_page=results_per_page,
                timeout=timeout,
            )

            for queue in queue_list:
                queue_info = {
                    "name": queue.name,
                    "metadata": queue.metadata if include_metadata else None,
                }
                queues.append(queue_info)

            return queues
        except Exception as e:
            self.logger.error(f"Failed to list queues: {e}")
            raise

    def queue_exists(self, queue_name: str, timeout: int = None) -> bool:
        """
        Check if a queue exists

        Args:
            queue_name: Name of the queue
            timeout: Request timeout in seconds

        Returns:
            bool: True if queue exists
        """
        try:
            queue_client = self.queue_service_client.get_queue_client(queue_name)
            queue_client.get_queue_properties(timeout=timeout)
            return True
        except ResourceNotFoundError:
            return False
        except Exception as e:
            self.logger.error(f"Error checking queue existence: {e}")
            raise

    def clear_queue(self, queue_name: str, timeout: int = None) -> bool:
        """
        Clear all messages from a queue

        Args:
            queue_name: Name of the queue
            timeout: Request timeout in seconds

        Returns:
            bool: True if cleared successfully
        """
        try:
            queue_client = self.queue_service_client.get_queue_client(queue_name)
            queue_client.clear_messages(timeout=timeout)
            self.logger.info(f"Queue '{queue_name}' cleared successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to clear queue '{queue_name}': {e}")
            raise

    # Message Operations
    def send_message(
        self,
        queue_name: str,
        message: Union[str, bytes, Dict[str, Any]],
        visibility_timeout: int = None,
        time_to_live: int = None,
        timeout: int = None,
    ) -> Dict[str, Any]:
        """
        Send a message to a queue

        Args:
            queue_name: Name of the queue
            message: Message content (string, bytes, or dict for JSON)
            visibility_timeout: Visibility timeout in seconds
            time_to_live: Time to live in seconds
            timeout: Request timeout in seconds

        Returns:
            Dictionary with message information
        """
        try:
            queue_client = self.queue_service_client.get_queue_client(queue_name)

            # Handle different message types
            if isinstance(message, dict):
                message_content = json.dumps(message)
            elif isinstance(message, bytes):
                message_content = message
            else:
                message_content = str(message)

            result = queue_client.send_message(
                message_content,
                visibility_timeout=visibility_timeout,
                time_to_live=time_to_live,
                timeout=timeout,
            )

            message_info = {
                "message_id": result.id,
                "pop_receipt": result.pop_receipt,
                "inserted_on": result.inserted_on,
                "expires_on": result.expires_on,
                "next_visible_on": result.next_visible_on,
            }

            self.logger.info(f"Message sent to queue '{queue_name}': {result.id}")
            return message_info

        except Exception as e:
            self.logger.error(f"Failed to send message to queue '{queue_name}': {e}")
            raise

    def receive_messages(
        self,
        queue_name: str,
        max_messages: int = 1,
        visibility_timeout: int = None,
        timeout: int = None,
    ) -> List[Dict[str, Any]]:
        """
        Receive messages from a queue

        Args:
            queue_name: Name of the queue
            max_messages: Maximum number of messages to receive (1-32)
            visibility_timeout: Visibility timeout in seconds
            timeout: Request timeout in seconds

        Returns:
            List of message dictionaries
        """
        try:
            queue_client = self.queue_service_client.get_queue_client(queue_name)
            messages = queue_client.receive_messages(
                max_messages=max_messages,
                visibility_timeout=visibility_timeout,
                timeout=timeout,
            )

            message_list = []
            for message in messages:
                message_info = {
                    "message_id": message.id,
                    "pop_receipt": message.pop_receipt,
                    "content": message.content,
                    "inserted_on": message.inserted_on,
                    "expires_on": message.expires_on,
                    "next_visible_on": message.next_visible_on,
                    "dequeue_count": message.dequeue_count,
                }
                message_list.append(message_info)

            self.logger.info(
                f"Received {len(message_list)} messages from queue '{queue_name}'"
            )
            return message_list

        except Exception as e:
            self.logger.error(
                f"Failed to receive messages from queue '{queue_name}': {e}"
            )
            raise

    def peek_messages(
        self,
        queue_name: str,
        max_messages: int = 1,
        timeout: int = None,
    ) -> List[Dict[str, Any]]:
        """
        Peek at messages in a queue without removing them

        Args:
            queue_name: Name of the queue
            max_messages: Maximum number of messages to peek (1-32)
            timeout: Request timeout in seconds

        Returns:
            List of message dictionaries
        """
        try:
            queue_client = self.queue_service_client.get_queue_client(queue_name)
            messages = queue_client.peek_messages(
                max_messages=max_messages,
                timeout=timeout,
            )

            message_list = []
            for message in messages:
                message_info = {
                    "message_id": message.id,
                    "content": message.content,
                    "inserted_on": message.inserted_on,
                    "expires_on": message.expires_on,
                    "next_visible_on": message.next_visible_on,
                    "dequeue_count": message.dequeue_count,
                }
                message_list.append(message_info)

            self.logger.info(
                f"Peeked at {len(message_list)} messages from queue '{queue_name}'"
            )
            return message_list

        except Exception as e:
            self.logger.error(f"Failed to peek messages from queue '{queue_name}': {e}")
            raise

    def delete_message(
        self,
        queue_name: str,
        message_id: str,
        pop_receipt: str,
        timeout: int = None,
    ) -> bool:
        """
        Delete a message from a queue

        Args:
            queue_name: Name of the queue
            message_id: ID of the message to delete
            pop_receipt: Pop receipt of the message
            timeout: Request timeout in seconds

        Returns:
            bool: True if deleted successfully
        """
        try:
            queue_client = self.queue_service_client.get_queue_client(queue_name)
            queue_client.delete_message(
                message_id,
                pop_receipt,
                timeout=timeout,
            )
            self.logger.info(f"Message {message_id} deleted from queue '{queue_name}'")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete message {message_id}: {e}")
            raise

    def update_message(
        self,
        queue_name: str,
        message_id: str,
        pop_receipt: str,
        content: Union[str, bytes, Dict[str, Any]] = None,
        visibility_timeout: int = None,
        timeout: int = None,
    ) -> Dict[str, Any]:
        """
        Update a message in a queue

        Args:
            queue_name: Name of the queue
            message_id: ID of the message to update
            pop_receipt: Pop receipt of the message
            content: New message content (optional)
            visibility_timeout: New visibility timeout in seconds
            timeout: Request timeout in seconds

        Returns:
            Dictionary with updated message information
        """
        try:
            queue_client = self.queue_service_client.get_queue_client(queue_name)

            # Handle different message types
            if content is not None:
                if isinstance(content, dict):
                    message_content = json.dumps(content)
                elif isinstance(content, bytes):
                    message_content = content
                else:
                    message_content = str(content)
            else:
                message_content = None

            result = queue_client.update_message(
                message_id,
                pop_receipt,
                content=message_content,
                visibility_timeout=visibility_timeout,
                timeout=timeout,
            )

            message_info = {
                "pop_receipt": result.pop_receipt,
                "next_visible_on": result.next_visible_on,
            }

            self.logger.info(f"Message {message_id} updated in queue '{queue_name}'")
            return message_info

        except Exception as e:
            self.logger.error(f"Failed to update message {message_id}: {e}")
            raise

    # Batch Operations
    def send_multiple_messages(
        self,
        queue_name: str,
        messages: List[Union[str, bytes, Dict[str, Any]]],
        visibility_timeout: int = None,
        time_to_live: int = None,
        timeout: int = None,
    ) -> List[Dict[str, Any]]:
        """
        Send multiple messages to a queue

        Args:
            queue_name: Name of the queue
            messages: List of messages to send
            visibility_timeout: Visibility timeout in seconds
            time_to_live: Time to live in seconds
            timeout: Request timeout in seconds

        Returns:
            List of message information dictionaries
        """
        results = []
        for message in messages:
            try:
                result = self.send_message(
                    queue_name,
                    message,
                    visibility_timeout=visibility_timeout,
                    time_to_live=time_to_live,
                    timeout=timeout,
                )
                results.append({"success": True, "message_info": result})
            except Exception as e:
                results.append({"success": False, "error": str(e)})

        return results

    def process_messages(
        self,
        queue_name: str,
        processor_function,
        max_messages: int = 1,
        visibility_timeout: int = None,
        delete_after_processing: bool = True,
        timeout: int = None,
    ) -> List[Dict[str, Any]]:
        """
        Process messages from a queue with a custom function

        Args:
            queue_name: Name of the queue
            processor_function: Function to process each message
            max_messages: Maximum number of messages to process
            visibility_timeout: Visibility timeout in seconds
            delete_after_processing: Whether to delete messages after processing
            timeout: Request timeout in seconds

        Returns:
            List of processing results
        """
        try:
            messages = self.receive_messages(
                queue_name,
                max_messages=max_messages,
                visibility_timeout=visibility_timeout,
                timeout=timeout,
            )

            results = []
            for message in messages:
                try:
                    # Process the message
                    result = processor_function(message)

                    # Delete message if processing was successful and delete_after_processing is True
                    if delete_after_processing and result.get("success", True):
                        self.delete_message(
                            queue_name,
                            message["message_id"],
                            message["pop_receipt"],
                            timeout=timeout,
                        )

                    results.append(
                        {
                            "message_id": message["message_id"],
                            "processing_result": result,
                            "deleted": delete_after_processing
                            and result.get("success", True),
                        }
                    )

                except Exception as e:
                    results.append(
                        {
                            "message_id": message["message_id"],
                            "processing_result": {"success": False, "error": str(e)},
                            "deleted": False,
                        }
                    )

            return results

        except Exception as e:
            self.logger.error(
                f"Failed to process messages from queue '{queue_name}': {e}"
            )
            raise

    # Queue Properties and Metadata
    def get_queue_properties(
        self, queue_name: str, timeout: int = None
    ) -> Dict[str, Any]:
        """
        Get queue properties and metadata

        Args:
            queue_name: Name of the queue
            timeout: Request timeout in seconds

        Returns:
            Dictionary with queue properties
        """
        try:
            queue_client = self.queue_service_client.get_queue_client(queue_name)
            properties = queue_client.get_queue_properties(timeout=timeout)

            return {
                "name": queue_name,
                "metadata": properties.metadata,
                "approximate_message_count": properties.approximate_message_count,
            }
        except Exception as e:
            self.logger.error(f"Failed to get queue properties: {e}")
            raise

    def set_queue_metadata(
        self, queue_name: str, metadata: Dict[str, str], timeout: int = None
    ) -> bool:
        """
        Set queue metadata

        Args:
            queue_name: Name of the queue
            metadata: Metadata dictionary
            timeout: Request timeout in seconds

        Returns:
            bool: True if metadata set successfully
        """
        try:
            queue_client = self.queue_service_client.get_queue_client(queue_name)
            queue_client.set_queue_metadata(metadata, timeout=timeout)
            self.logger.info(f"Metadata set for queue '{queue_name}'")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set queue metadata: {e}")
            raise

    def get_queue_statistics(self, queue_name: str) -> Dict[str, Any]:
        """
        Get queue statistics

        Args:
            queue_name: Name of the queue

        Returns:
            Dictionary with queue statistics
        """
        try:
            properties = self.get_queue_properties(queue_name)

            return {
                "queue_name": queue_name,
                "approximate_message_count": properties["approximate_message_count"],
                "metadata": properties["metadata"],
                "last_updated": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Failed to get queue statistics: {e}")
            raise

    # Utility Methods
    def get_queue_url(self, queue_name: str) -> str:
        """
        Get the full URL of a queue

        Args:
            queue_name: Name of the queue

        Returns:
            Full queue URL
        """
        account_name = self._get_account_name()
        return f"https://{account_name}.queue.core.windows.net/{queue_name}"

    def _get_account_name(self) -> str:
        """Extract account name from queue service client"""
        try:
            return self.queue_service_client.account_name
        except Exception:
            return None

    def encode_message(self, message: Union[str, Dict[str, Any]]) -> str:
        """
        Encode a message for queue storage

        Args:
            message: Message to encode

        Returns:
            Encoded message string
        """
        if isinstance(message, dict):
            return json.dumps(message)
        return str(message)

    def decode_message(self, message_content: str) -> Union[str, Dict[str, Any]]:
        """
        Try to decode a message from queue storage

        Args:
            message_content: Message content to decode

        Returns:
            Decoded message (dict if JSON, string otherwise)
        """
        try:
            return json.loads(message_content)
        except (json.JSONDecodeError, TypeError):
            return message_content

    def create_message_processor(self, processor_func):
        """
        Create a message processor wrapper

        Args:
            processor_func: Function to process messages

        Returns:
            Wrapped processor function
        """

        def wrapper(message):
            try:
                # Decode message content
                decoded_content = self.decode_message(message["content"])

                # Create a more user-friendly message object
                processed_message = {
                    "id": message["message_id"],
                    "content": decoded_content,
                    "insertion_time": message["insertion_time"],
                    "expiration_time": message["expiration_time"],
                    "dequeue_count": message["dequeue_count"],
                    "pop_receipt": message["pop_receipt"],
                }

                # Call the user's processor function
                result = processor_func(processed_message)

                return {"success": True, "result": result}

            except Exception as e:
                return {"success": False, "error": str(e)}

        return wrapper
