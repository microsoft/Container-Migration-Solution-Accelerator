"""
Unit tests for AsyncStorageQueueHelper class

This module contains comprehensive unit tests for the AsyncStorageQueueHelper class,
covering all queue operations, message handling, batch processing, and advanced features.
"""

import asyncio
import json
import pytest
import logging
from unittest.mock import Mock, AsyncMock, MagicMock, patch, call, PropertyMock
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Import the class under test
from app.libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

# Import Azure SDK exceptions for testing
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from azure.storage.queue.aio import QueueServiceClient
from azure.identity.aio import DefaultAzureCredential


def create_mock_queue_client():
    """Helper function to create a properly configured mock queue client"""
    mock_client = AsyncMock()
    mock_client.account_name = "test_account"
    
    # Configure all async methods with proper return values
    mock_client.create_queue = AsyncMock(return_value=None)
    mock_client.delete_queue = AsyncMock(return_value=None)
    mock_client.get_queue_client = Mock(return_value=mock_client)
    mock_client.list_queues = AsyncMock(return_value=[])
    mock_client.close = AsyncMock(return_value=None)
    
    return mock_client


def create_mock_queue_client_specific():
    """Helper function to create a mock for specific queue operations"""
    mock_client = AsyncMock()
    mock_client.send_message = AsyncMock(return_value=None)
    mock_client.receive_message = AsyncMock(return_value=None)
    mock_client.receive_messages = AsyncMock(return_value=[])
    mock_client.delete_message = AsyncMock(return_value=None)
    mock_client.update_message = AsyncMock(return_value=None)
    mock_client.send_messages = AsyncMock(return_value=None)
    mock_client.get_queue_properties = AsyncMock(return_value=AsyncMock())
    mock_client.set_queue_metadata = AsyncMock(return_value=None)
    mock_client.clear_messages = AsyncMock(return_value=None)
    mock_client.peek_messages = AsyncMock(return_value=[])
    mock_client.queue_exists = AsyncMock(return_value=True)
    mock_client.create_queue = AsyncMock(return_value=None)
    mock_client.delete_queue = AsyncMock(return_value=None)
    
    return mock_client


class TestAsyncStorageQueueHelperInitialization:
    """Test cases for AsyncStorageQueueHelper initialization"""

    @patch('app.libs.sas.storage.queue.async_helper.get_config')
    def test_init_with_connection_string(self, mock_get_config):
        """Test initialization with connection string"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        mock_get_config.return_value = mock_config
        
        helper = AsyncStorageQueueHelper(connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net")
        
        assert helper._connection_string == "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net"
        assert helper._account_name is None
        assert helper._credential is None

    @patch('app.libs.sas.storage.queue.async_helper.get_config')
    def test_init_with_account_name_and_credential(self, mock_get_config):
        """Test initialization with account name and credential"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        mock_get_config.return_value = mock_config
        
        mock_credential = Mock()
        
        helper = AsyncStorageQueueHelper(account_name="testaccount", credential=mock_credential)
        
        assert helper._account_name == "testaccount"
        assert helper._credential == mock_credential
        assert helper._connection_string is None

    @patch('app.libs.sas.storage.queue.async_helper.get_config')
    def test_init_with_account_name_only(self, mock_get_config):
        """Test initialization with account name only (uses DefaultAzureCredential)"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        mock_get_config.return_value = mock_config
        
        helper = AsyncStorageQueueHelper(account_name="testaccount")
        
        assert helper._account_name == "testaccount"
        assert helper._credential is None
        assert helper._connection_string is None

    @patch('app.libs.sas.storage.queue.async_helper.get_config')
    def test_init_with_config_dict(self, mock_get_config):
        """Test initialization with config dictionary"""
        config_dict = {"logging_level": "DEBUG"}
        
        helper = AsyncStorageQueueHelper(
            connection_string="test_conn_string", 
            config=config_dict
        )
        
        assert helper.config == config_dict

    @patch('app.libs.sas.storage.queue.async_helper.get_config')
    def test_init_with_config_object(self, mock_get_config):
        """Test initialization with config object"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        
        helper = AsyncStorageQueueHelper(
            connection_string="test_conn_string", 
            config=mock_config
        )
        
        assert helper.config == mock_config

    @patch('app.libs.sas.storage.queue.async_helper.get_config')
    def test_init_default_config(self, mock_get_config):
        """Test initialization with default config"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        mock_get_config.return_value = mock_config
        
        helper = AsyncStorageQueueHelper(connection_string="test_conn_string")
        
        assert helper.config == mock_config
        mock_get_config.assert_called_once()

    @patch('logging.basicConfig')
    @patch('app.libs.sas.storage.queue.async_helper.get_config')
    def test_logging_setup_debug(self, mock_get_config, mock_basic_config):
        """Test logging setup with DEBUG level"""
        mock_config = Mock()
        mock_config.get.return_value = "DEBUG"
        mock_get_config.return_value = mock_config
        
        helper = AsyncStorageQueueHelper(connection_string="test_conn_string")
        
        mock_basic_config.assert_called_with(level=10)  # DEBUG level


class TestAsyncStorageQueueHelperClientInitialization:
    """Test cases for client initialization and context management"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.queue.async_helper.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get.return_value = "INFO"
            mock_get_config.return_value = mock_config
            
            self.helper = AsyncStorageQueueHelper(connection_string="test_conn_string")

    @pytest.mark.asyncio
    @patch('app.libs.sas.storage.queue.async_helper.QueueServiceClient.from_connection_string')
    async def test_initialize_client_with_connection_string(self, mock_from_connection_string):
        """Test client initialization with connection string"""
        mock_client = AsyncMock()
        mock_from_connection_string.return_value = mock_client
        
        await self.helper._initialize_client()
        
        assert self.helper._queue_service_client == mock_client
        mock_from_connection_string.assert_called_once_with("test_conn_string")

    @pytest.mark.asyncio
    @patch('app.libs.sas.storage.queue.async_helper.QueueServiceClient')
    async def test_initialize_client_with_account_name_and_credential(self, mock_queue_service_client):
        """Test client initialization with account name and credential"""
        mock_client = AsyncMock()
        mock_queue_service_client.return_value = mock_client
        mock_credential = Mock()
        
        self.helper._account_name = "testaccount"
        self.helper._credential = mock_credential
        self.helper._connection_string = None
        
        await self.helper._initialize_client()
        
        assert self.helper._queue_service_client == mock_client
        mock_queue_service_client.assert_called_once_with(
            "https://testaccount.queue.core.windows.net", 
            credential=mock_credential
        )

    @pytest.mark.asyncio
    @patch('app.libs.sas.storage.queue.async_helper.QueueServiceClient')
    @patch('app.libs.sas.storage.queue.async_helper.DefaultAzureCredential')
    async def test_initialize_client_with_account_name_only(self, mock_default_cred, mock_queue_service_client):
        """Test client initialization with account name only"""
        mock_client = AsyncMock()
        mock_queue_service_client.return_value = mock_client
        mock_cred_instance = Mock()
        mock_default_cred.return_value = mock_cred_instance
        
        self.helper._account_name = "testaccount"
        self.helper._connection_string = None
        
        await self.helper._initialize_client()
        
        assert self.helper._queue_service_client == mock_client
        mock_default_cred.assert_called_once()
        mock_queue_service_client.assert_called_once_with(
            "https://testaccount.queue.core.windows.net", 
            credential=mock_cred_instance
        )

    @pytest.mark.asyncio
    async def test_initialize_client_no_parameters_raises_error(self):
        """Test client initialization with no parameters raises ValueError"""
        self.helper._connection_string = None
        self.helper._account_name = None
        
        with pytest.raises(ValueError, match="Either connection_string or account_name must be provided"):
            await self.helper._initialize_client()

    @pytest.mark.asyncio
    @patch('app.libs.sas.storage.queue.async_helper.QueueServiceClient.from_connection_string')
    async def test_initialize_client_exception_reraises(self, mock_from_connection_string):
        """Test that client initialization exception is re-raised"""
        mock_from_connection_string.side_effect = Exception("Failed to connect")
        
        with pytest.raises(Exception, match="Failed to connect"):
            await self.helper._initialize_client()

    def test_queue_service_client_not_initialized_raises_error(self):
        """Test accessing client before initialization raises RuntimeError"""
        with pytest.raises(RuntimeError, match="Client not initialized"):
            _ = self.helper.queue_service_client

    @pytest.mark.asyncio
    async def test_context_manager_entry_and_exit(self):
        """Test async context manager entry and exit"""
        with patch.object(self.helper, '_initialize_client') as mock_init:
            with patch.object(self.helper, 'close') as mock_close:
                async with self.helper as helper:
                    assert helper == self.helper
                    mock_init.assert_called_once()
                
                mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_method(self):
        """Test close method"""
        mock_client = AsyncMock()
        self.helper._queue_service_client = mock_client
        
        await self.helper.close()
        
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_method_no_client(self):
        """Test close method when no client is initialized"""
        await self.helper.close()  # Should not raise exception


class TestAsyncStorageQueueHelperQueueOperations:
    """Test cases for queue operations"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.queue.async_helper.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get.return_value = "INFO"
            mock_get_config.return_value = mock_config
            
            self.helper = AsyncStorageQueueHelper(connection_string="test_conn_string")
            
            # Create mock queue service client
            self.helper._queue_service_client = create_mock_queue_client()
            
            # Create a specific queue client for operations
            self.mock_queue_client = create_mock_queue_client_specific()
            self.helper._queue_service_client.get_queue_client.return_value = self.mock_queue_client

    @pytest.mark.asyncio
    async def test_create_queue_success(self):
        """Test successful queue creation"""
        queue_client = AsyncMock()
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.create_queue("test-queue", {"key": "value"})
        
        assert result is True
        self.helper._queue_service_client.get_queue_client.assert_called_once_with("test-queue")
        queue_client.create_queue.assert_called_once_with(metadata={"key": "value"})

    @pytest.mark.asyncio
    async def test_create_queue_already_exists(self):
        """Test queue creation when queue already exists"""
        queue_client = AsyncMock()
        queue_client.create_queue.side_effect = ResourceExistsError("Queue exists")
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.create_queue("test-queue")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_create_queue_exception(self):
        """Test queue creation with general exception"""
        queue_client = AsyncMock()
        queue_client.create_queue.side_effect = Exception("Network error")
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        with pytest.raises(Exception, match="Network error"):
            await self.helper.create_queue("test-queue")

    @pytest.mark.asyncio
    async def test_delete_queue_success(self):
        """Test successful queue deletion"""
        queue_client = AsyncMock()
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.delete_queue("test-queue")
        
        assert result is True
        queue_client.delete_queue.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_queue_not_found(self):
        """Test queue deletion when queue doesn't exist"""
        queue_client = AsyncMock()
        queue_client.delete_queue.side_effect = ResourceNotFoundError("Not found")
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.delete_queue("test-queue")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_queue_exception(self):
        """Test queue deletion with general exception"""
        queue_client = AsyncMock()
        queue_client.delete_queue.side_effect = Exception("Network error")
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        with pytest.raises(Exception, match="Network error"):
            await self.helper.delete_queue("test-queue")

    @pytest.mark.asyncio
    async def test_queue_exists_true(self):
        """Test queue exists returns True"""
        queue_client = AsyncMock()
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.queue_exists("test-queue")
        
        assert result is True
        queue_client.get_queue_properties.assert_called_once()

    @pytest.mark.asyncio
    async def test_queue_exists_false(self):
        """Test queue exists returns False"""
        queue_client = AsyncMock()
        queue_client.get_queue_properties.side_effect = ResourceNotFoundError("Not found")
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.queue_exists("test-queue")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_queue_exists_exception(self):
        """Test queue exists with general exception"""
        queue_client = AsyncMock()
        queue_client.get_queue_properties.side_effect = Exception("API error")
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        with pytest.raises(Exception, match="API error"):
            await self.helper.queue_exists("test-queue")

    @pytest.mark.asyncio
    async def test_list_queues_success(self):
        """Test successful queue listing"""
        mock_queue1 = Mock()
        mock_queue1.name = "queue1"
        mock_queue1.metadata = {"key": "value"}
        
        mock_queue2 = Mock()
        mock_queue2.name = "queue2"
        mock_queue2.metadata = None
        
        async def mock_list_queues(*args, **kwargs):
            for queue in [mock_queue1, mock_queue2]:
                yield queue
        
        self.helper._queue_service_client.list_queues = mock_list_queues
        
        result = await self.helper.list_queues()
        
        assert len(result) == 2
        assert result[0]["name"] == "queue1"
        assert result[0]["metadata"] == {"key": "value"}
        assert result[1]["name"] == "queue2"
        assert result[1]["metadata"] == {}

    @pytest.mark.asyncio
    async def test_list_queues_exception(self):
        """Test queue listing with exception"""
        async def mock_list_queues(*args, **kwargs):
            raise Exception("API error")
            yield  # This will never be reached
        
        self.helper._queue_service_client.list_queues = mock_list_queues
        
        with pytest.raises(Exception, match="API error"):
            await self.helper.list_queues()


class TestAsyncStorageQueueHelperMessageOperations:
    """Test cases for message operations"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.queue.async_helper.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get.return_value = "INFO"
            mock_get_config.return_value = mock_config
            
            self.helper = AsyncStorageQueueHelper(connection_string="test_conn_string")
            self.helper._queue_service_client = create_mock_queue_client()

    @pytest.mark.asyncio
    async def test_send_message_string_content(self):
        """Test sending a string message"""
        queue_client = create_mock_queue_client_specific()
        mock_message = Mock()
        mock_message.id = "msg123"
        mock_message.pop_receipt = "receipt123"
        mock_message.inserted_on = datetime.now()
        mock_message.expires_on = datetime.now() + timedelta(days=7)
        mock_message.next_visible_on = datetime.now()
        
        queue_client.send_message = AsyncMock(return_value=mock_message)
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.send_message("test-queue", "Hello, World!")
        
        assert result["message_id"] == "msg123"
        assert result["pop_receipt"] == "receipt123"
        queue_client.send_message.assert_called_once_with(
            "Hello, World!",
            visibility_timeout=None,
            time_to_live=None
        )

    @pytest.mark.asyncio
    async def test_send_message_dict_content(self):
        """Test sending a dictionary message"""
        queue_client = AsyncMock()
        mock_message = Mock()
        mock_message.id = "msg123"
        mock_message.pop_receipt = "receipt123"
        mock_message.inserted_on = None
        mock_message.expires_on = None
        mock_message.next_visible_on = None
        
        queue_client.send_message.return_value = mock_message
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        message_dict = {"type": "test", "data": {"value": 42}}
        result = await self.helper.send_message("test-queue", message_dict, visibility_timeout=30, time_to_live=3600)
        
        assert result["message_id"] == "msg123"
        assert result["inserted_on"] is None
        queue_client.send_message.assert_called_once_with(
            json.dumps(message_dict),
            visibility_timeout=30,
            time_to_live=3600
        )

    @pytest.mark.asyncio
    async def test_send_message_object_content(self):
        """Test sending a non-string, non-dict object"""
        queue_client = AsyncMock()
        mock_message = Mock()
        mock_message.id = "msg123"
        mock_message.pop_receipt = "receipt123"
        mock_message.inserted_on = datetime.now()
        mock_message.expires_on = datetime.now()
        mock_message.next_visible_on = datetime.now()
        
        queue_client.send_message.return_value = mock_message
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.send_message("test-queue", 42)
        
        queue_client.send_message.assert_called_once_with(
            "42",
            visibility_timeout=None,
            time_to_live=None
        )

    @pytest.mark.asyncio
    async def test_send_message_exception(self):
        """Test sending message with exception"""
        queue_client = AsyncMock()
        queue_client.send_message.side_effect = Exception("Send failed")
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        with pytest.raises(Exception, match="Send failed"):
            await self.helper.send_message("test-queue", "Hello")

    @pytest.mark.asyncio
    async def test_receive_message_success(self):
        """Test successful message receipt"""
        queue_client = AsyncMock()
        mock_message = Mock()
        mock_message.id = "msg123"
        mock_message.content = "Hello, World!"
        mock_message.pop_receipt = "receipt123"
        mock_message.inserted_on = datetime.now()
        mock_message.expires_on = datetime.now() + timedelta(days=7)
        mock_message.next_visible_on = datetime.now() + timedelta(seconds=30)
        mock_message.dequeue_count = 1
        
        async def mock_receive_messages(*args, **kwargs):
            yield mock_message
        
        queue_client.receive_messages = mock_receive_messages
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.receive_message("test-queue", visibility_timeout=60, timeout=30)
        
        assert result["id"] == "msg123"
        assert result["content"] == "Hello, World!"
        assert result["dequeue_count"] == 1

    @pytest.mark.asyncio
    async def test_receive_message_no_message(self):
        """Test receiving message when no messages available"""
        queue_client = AsyncMock()
        
        async def mock_receive_messages(*args, **kwargs):
            return
            yield  # This will never be reached
        
        queue_client.receive_messages = mock_receive_messages
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.receive_message("test-queue")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_receive_message_exception(self):
        """Test receiving message with exception"""
        queue_client = AsyncMock()
        
        async def mock_receive_messages(*args, **kwargs):
            raise Exception("Receive failed")
            yield  # This will never be reached
        
        queue_client.receive_messages = mock_receive_messages
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        with pytest.raises(Exception, match="Receive failed"):
            await self.helper.receive_message("test-queue")

    @pytest.mark.asyncio
    async def test_receive_messages_success(self):
        """Test successful multiple message receipt"""
        queue_client = AsyncMock()
        
        messages = []
        for i in range(3):
            mock_message = Mock()
            mock_message.id = f"msg{i}"
            mock_message.content = f"Message {i}"
            mock_message.pop_receipt = f"receipt{i}"
            mock_message.inserted_on = datetime.now()
            mock_message.expires_on = datetime.now() + timedelta(days=7)
            mock_message.next_visible_on = datetime.now() + timedelta(seconds=30)
            mock_message.dequeue_count = 1
            messages.append(mock_message)
        
        async def mock_receive_messages(*args, **kwargs):
            for message in messages:
                yield message
        
        queue_client.receive_messages = mock_receive_messages
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.receive_messages("test-queue", max_messages=5)
        
        assert len(result) == 3
        assert result[0]["id"] == "msg0"
        assert result[1]["id"] == "msg1"
        assert result[2]["id"] == "msg2"

    @pytest.mark.asyncio
    async def test_receive_messages_exception(self):
        """Test receiving multiple messages with exception"""
        queue_client = AsyncMock()
        
        async def mock_receive_messages(*args, **kwargs):
            raise Exception("Receive failed")
            yield  # This will never be reached
        
        queue_client.receive_messages = mock_receive_messages
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        with pytest.raises(Exception, match="Receive failed"):
            await self.helper.receive_messages("test-queue")

    @pytest.mark.asyncio
    async def test_delete_message_success(self):
        """Test successful message deletion"""
        queue_client = AsyncMock()
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.delete_message("test-queue", "msg123", "receipt123")
        
        assert result is True
        queue_client.delete_message.assert_called_once_with("msg123", "receipt123")

    @pytest.mark.asyncio
    async def test_delete_message_exception(self):
        """Test message deletion with exception"""
        queue_client = AsyncMock()
        queue_client.delete_message.side_effect = Exception("Delete failed")
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        with pytest.raises(Exception, match="Delete failed"):
            await self.helper.delete_message("test-queue", "msg123", "receipt123")

    @pytest.mark.asyncio
    async def test_update_message_string_content(self):
        """Test updating message with string content"""
        queue_client = AsyncMock()
        mock_result = Mock()
        mock_result.pop_receipt = "new_receipt123"
        mock_result.next_visible_on = datetime.now() + timedelta(seconds=60)
        
        queue_client.update_message.return_value = mock_result
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.update_message(
            "test-queue", "msg123", "receipt123", "Updated content", 30
        )
        
        assert result["pop_receipt"] == "new_receipt123"
        queue_client.update_message.assert_called_once_with(
            "msg123",
            pop_receipt="receipt123",
            content="Updated content",
            visibility_timeout=30
        )

    @pytest.mark.asyncio
    async def test_update_message_dict_content(self):
        """Test updating message with dict content"""
        queue_client = AsyncMock()
        mock_result = Mock()
        mock_result.pop_receipt = "new_receipt123"
        mock_result.next_visible_on = datetime.now()
        
        queue_client.update_message.return_value = mock_result
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        update_dict = {"status": "updated", "data": [1, 2, 3]}
        result = await self.helper.update_message(
            "test-queue", "msg123", "receipt123", update_dict
        )
        
        queue_client.update_message.assert_called_once_with(
            "msg123",
            pop_receipt="receipt123",
            content=json.dumps(update_dict),
            visibility_timeout=0
        )

    @pytest.mark.asyncio
    async def test_update_message_exception(self):
        """Test updating message with exception"""
        queue_client = AsyncMock()
        queue_client.update_message.side_effect = Exception("Update failed")
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        with pytest.raises(Exception, match="Update failed"):
            await self.helper.update_message("test-queue", "msg123", "receipt123", "content")


class TestAsyncStorageQueueHelperBatchOperations:
    """Test cases for batch operations"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.queue.async_helper.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get.return_value = "INFO"
            mock_get_config.return_value = mock_config
            
            self.helper = AsyncStorageQueueHelper(connection_string="test_conn_string")
            
            # Create mock queue service client
            self.helper._queue_service_client = create_mock_queue_client()
            
            # Create a specific queue client for operations
            self.mock_queue_client = create_mock_queue_client_specific()
            self.helper._queue_service_client.get_queue_client.return_value = self.mock_queue_client

    @pytest.mark.asyncio
    async def test_send_messages_batch_success(self):
        """Test successful batch message sending"""
        # Mock the send_message method to return successful results
        async def mock_send_message(queue_name, content):
            return {
                "message_id": f"msg_{hash(str(content))}",
                "pop_receipt": f"receipt_{hash(str(content))}",
                "inserted_on": datetime.now(),
                "expires_on": None,
                "next_visible_on": None
            }
        
        self.helper.send_message = mock_send_message
        
        messages = ["Message 1", "Message 2", "Message 3"]
        result = await self.helper.send_messages_batch("test-queue", messages, max_concurrency=2)
        
        assert len(result) == 3
        assert all("message_id" in msg for msg in result)

    @pytest.mark.asyncio
    async def test_send_messages_batch_with_failures(self):
        """Test batch message sending with some failures"""
        call_count = 0
        
        async def mock_send_message(queue_name, content):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Second call fails
                raise Exception(f"Failed to send: {content}")
            return {
                "message_id": f"msg_{call_count}",
                "pop_receipt": f"receipt_{call_count}",
                "inserted_on": datetime.now(),
                "expires_on": None,
                "next_visible_on": None
            }
        
        self.helper.send_message = mock_send_message
        
        messages = ["Message 1", "Message 2", "Message 3"]
        result = await self.helper.send_messages_batch("test-queue", messages)
        
        # Should return only successful sends
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_process_messages_batch_success(self):
        """Test successful batch message processing"""
        # Mock messages
        messages = [
            {
                "id": f"msg{i}",
                "content": f"Content {i}",
                "pop_receipt": f"receipt{i}",
                "inserted_on": datetime.now(),
                "expires_on": None,
                "next_visible_on": None,
                "dequeue_count": 1
            }
            for i in range(3)
        ]
        
        # Mock receive_messages to return our test messages
        self.helper.receive_messages = AsyncMock(return_value=messages)
        
        # Mock delete_message
        self.helper.delete_message = AsyncMock(return_value=True)
        
        # Mock processor function
        async def mock_processor(message):
            return f"Processed: {message['content']}"
        
        result = await self.helper.process_messages_batch(
            "test-queue", 
            mock_processor,
            max_messages=5,
            max_concurrency=2,
            delete_after_processing=True
        )
        
        assert len(result) == 3
        assert all(res["success"] for res in result)
        assert all("result" in res for res in result)
        
        # Verify delete_message was called for each message
        assert self.helper.delete_message.call_count == 3

    @pytest.mark.asyncio
    async def test_process_messages_batch_with_processing_failures(self):
        """Test batch message processing with processing failures"""
        messages = [
            {
                "id": "msg1",
                "content": "Content 1",
                "pop_receipt": "receipt1",
                "inserted_on": datetime.now(),
                "expires_on": None,
                "next_visible_on": None,
                "dequeue_count": 1
            },
            {
                "id": "msg2",
                "content": "Content 2",
                "pop_receipt": "receipt2",
                "inserted_on": datetime.now(),
                "expires_on": None,
                "next_visible_on": None,
                "dequeue_count": 1
            }
        ]
        
        self.helper.receive_messages = AsyncMock(return_value=messages)
        self.helper.delete_message = AsyncMock(return_value=True)
        
        # Mock processor that fails on second message
        async def mock_processor(message):
            if message["id"] == "msg2":
                raise Exception("Processing failed")
            return f"Processed: {message['content']}"
        
        result = await self.helper.process_messages_batch(
            "test-queue", 
            mock_processor,
            delete_after_processing=False
        )
        
        assert len(result) == 2
        assert result[0]["success"] is True
        assert result[1]["success"] is False
        assert "error" in result[1]
        
        # delete_message should not be called when delete_after_processing=False
        self.helper.delete_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_messages_batch_no_messages(self):
        """Test batch processing when no messages available"""
        self.helper.receive_messages = AsyncMock(return_value=[])
        
        async def mock_processor(message):
            return "Processed"
        
        result = await self.helper.process_messages_batch("test-queue", mock_processor)
        
        assert result == []


class TestAsyncStorageQueueHelperUtilityMethods:
    """Test cases for utility methods"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.queue.async_helper.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get.return_value = "INFO"
            mock_get_config.return_value = mock_config
            
            self.helper = AsyncStorageQueueHelper(connection_string="test_conn_string")
            
            # Create mock queue service client
            self.helper._queue_service_client = create_mock_queue_client()
            
            # Create a specific queue client for operations
            self.mock_queue_client = create_mock_queue_client_specific()
            self.helper._queue_service_client.get_queue_client.return_value = self.mock_queue_client

    @pytest.mark.asyncio
    async def test_get_queue_properties_success(self):
        """Test successful queue properties retrieval"""
        queue_client = AsyncMock()
        mock_properties = Mock()
        mock_properties.metadata = {"key": "value"}
        mock_properties.approximate_message_count = 5
        
        queue_client.get_queue_properties.return_value = mock_properties
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.get_queue_properties("test-queue")
        
        assert result["name"] == "test-queue"
        assert result["metadata"] == {"key": "value"}
        assert result["approximate_message_count"] == 5

    @pytest.mark.asyncio
    async def test_get_queue_properties_no_metadata(self):
        """Test queue properties retrieval with no metadata"""
        queue_client = AsyncMock()
        mock_properties = Mock()
        mock_properties.metadata = None
        mock_properties.approximate_message_count = 0
        
        queue_client.get_queue_properties.return_value = mock_properties
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.get_queue_properties("test-queue")
        
        assert result["metadata"] == {}

    @pytest.mark.asyncio
    async def test_get_queue_properties_exception(self):
        """Test queue properties retrieval with exception"""
        queue_client = AsyncMock()
        queue_client.get_queue_properties.side_effect = Exception("Properties failed")
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        with pytest.raises(Exception, match="Properties failed"):
            await self.helper.get_queue_properties("test-queue")

    @pytest.mark.asyncio
    async def test_set_queue_metadata_success(self):
        """Test successful queue metadata setting"""
        queue_client = AsyncMock()
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        metadata = {"category": "test", "environment": "dev"}
        result = await self.helper.set_queue_metadata("test-queue", metadata)
        
        assert result is True
        queue_client.set_queue_metadata.assert_called_once_with(metadata)

    @pytest.mark.asyncio
    async def test_set_queue_metadata_exception(self):
        """Test queue metadata setting with exception"""
        queue_client = AsyncMock()
        queue_client.set_queue_metadata.side_effect = Exception("Metadata failed")
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        with pytest.raises(Exception, match="Metadata failed"):
            await self.helper.set_queue_metadata("test-queue", {"key": "value"})

    @pytest.mark.asyncio
    async def test_clear_queue_success(self):
        """Test successful queue clearing"""
        queue_client = AsyncMock()
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.clear_queue("test-queue")
        
        assert result is True
        queue_client.clear_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_queue_exception(self):
        """Test queue clearing with exception"""
        queue_client = AsyncMock()
        queue_client.clear_messages.side_effect = Exception("Clear failed")
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        with pytest.raises(Exception, match="Clear failed"):
            await self.helper.clear_queue("test-queue")

    @pytest.mark.asyncio
    async def test_peek_messages_success(self):
        """Test successful message peeking"""
        queue_client = AsyncMock()
        
        mock_messages = []
        for i in range(3):
            mock_message = Mock()
            mock_message.id = f"msg{i}"
            mock_message.content = f"Content {i}"
            mock_message.inserted_on = datetime.now()
            mock_message.expires_on = datetime.now() + timedelta(days=7)
            mock_message.next_visible_on = datetime.now()
            mock_messages.append(mock_message)
        
        queue_client.peek_messages.return_value = mock_messages
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        result = await self.helper.peek_messages("test-queue", max_messages=5)
        
        assert len(result) == 3
        assert result[0]["id"] == "msg0"
        assert result[1]["id"] == "msg1"
        assert result[2]["id"] == "msg2"
        queue_client.peek_messages.assert_called_once_with(max_messages=5)

    @pytest.mark.asyncio
    async def test_peek_messages_exception(self):
        """Test message peeking with exception"""
        queue_client = AsyncMock()
        queue_client.peek_messages.side_effect = Exception("Peek failed")
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        with pytest.raises(Exception, match="Peek failed"):
            await self.helper.peek_messages("test-queue")


class TestAsyncStorageQueueHelperErrorHandling:
    """Test cases for error handling scenarios"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.queue.async_helper.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get.return_value = "INFO"
            mock_get_config.return_value = mock_config
            
            self.helper = AsyncStorageQueueHelper(connection_string="test_conn_string")
            
            # Create mock queue service client
            self.helper._queue_service_client = create_mock_queue_client()
            
            # Create a specific queue client for operations
            self.mock_queue_client = create_mock_queue_client_specific()
            self.helper._queue_service_client.get_queue_client.return_value = self.mock_queue_client

    @pytest.mark.asyncio
    async def test_concurrent_access_handling(self):
        """Test handling of concurrent access scenarios"""
        queue_client = AsyncMock()
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        # Simulate concurrent queue creation attempts
        async def create_queue_concurrent():
            try:
                return await self.helper.create_queue("test-queue")
            except ResourceExistsError:
                return False
        
        # Run multiple concurrent create attempts
        tasks = [create_queue_concurrent() for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # At least one should succeed or handle the conflict gracefully
        assert not all(isinstance(result, Exception) for result in results)

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling in operations"""
        queue_client = AsyncMock()
        queue_client.send_message.side_effect = asyncio.TimeoutError("Operation timed out")
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        with pytest.raises(asyncio.TimeoutError):
            await self.helper.send_message("test-queue", "test message")

    @pytest.mark.asyncio
    async def test_connection_failure_handling(self):
        """Test handling of connection failures"""
        # Simulate connection failure during queue client access
        self.mock_queue_client.create_queue = AsyncMock(side_effect=Exception("Connection failed"))
        
        with pytest.raises(Exception, match="Connection failed"):
            await self.helper.create_queue("test-queue")

    @pytest.mark.asyncio  
    async def test_large_message_handling(self):
        """Test handling of large messages that exceed limits"""
        queue_client = AsyncMock()
        queue_client.send_message.side_effect = Exception("Message too large")
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        large_message = "x" * 100000  # Simulate large message
        
        with pytest.raises(Exception, match="Message too large"):
            await self.helper.send_message("test-queue", large_message)

    @pytest.mark.asyncio
    async def test_invalid_queue_name_handling(self):
        """Test handling of invalid queue names"""
        queue_client = AsyncMock()
        queue_client.create_queue.side_effect = Exception("Invalid queue name")
        self.helper._queue_service_client.get_queue_client.return_value = queue_client
        
        with pytest.raises(Exception, match="Invalid queue name"):
            await self.helper.create_queue("Invalid-Queue-Name!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])