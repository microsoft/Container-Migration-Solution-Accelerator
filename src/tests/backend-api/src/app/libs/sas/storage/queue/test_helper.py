"""
Unit tests for StorageQueueHelper class

This module contains comprehensive unit tests for the StorageQueueHelper class,
covering all queue operations, message handling, batch processing, and utility methods.
"""

import json
import pytest
import logging
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Import the class under test
from app.libs.sas.storage.queue.helper import StorageQueueHelper

# Import Azure SDK exceptions for testing
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from azure.storage.queue import QueueServiceClient, TextBase64EncodePolicy, TextBase64DecodePolicy
from azure.identity import DefaultAzureCredential


def create_mock_queue_client():
    """Helper function to create a properly configured mock queue client"""
    mock_client = Mock()
    mock_client.account_name = "test_account"
    
    # Configure all methods with proper return values
    mock_client.create_queue = Mock(return_value=None)
    mock_client.delete_queue = Mock(return_value=None)
    mock_client.get_queue_client = Mock(return_value=mock_client)
    mock_client.list_queues = Mock(return_value=[])
    
    return mock_client


def create_mock_queue_client_specific():
    """Helper function to create a mock for specific queue operations"""
    mock_client = Mock()
    mock_client.send_message = Mock(return_value=None)
    mock_client.receive_messages = Mock(return_value=[])
    mock_client.peek_messages = Mock(return_value=[])
    mock_client.delete_message = Mock(return_value=None)
    mock_client.update_message = Mock(return_value=None)
    mock_client.get_queue_properties = Mock(return_value=Mock())
    mock_client.set_queue_metadata = Mock(return_value=None)
    mock_client.clear_messages = Mock(return_value=None)
    mock_client.create_queue = Mock(return_value=None)
    mock_client.delete_queue = Mock(return_value=None)
    
    return mock_client


class TestStorageQueueHelperInitialization:
    """Test cases for StorageQueueHelper initialization"""

    @patch('app.libs.sas.storage.queue.helper.get_config')
    def test_init_with_connection_string(self, mock_get_config):
        """Test initialization with connection string"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        mock_get_config.return_value = mock_config
        
        with patch('app.libs.sas.storage.queue.helper.QueueServiceClient.from_connection_string') as mock_from_conn:
            mock_client = Mock()
            mock_from_conn.return_value = mock_client
            
            helper = StorageQueueHelper(connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net")
            
            assert helper._connection_string == "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net"
            assert helper.queue_service_client == mock_client
            mock_from_conn.assert_called_once()

    @patch('app.libs.sas.storage.queue.helper.get_config')
    def test_init_with_account_name_and_credential(self, mock_get_config):
        """Test initialization with account name and credential"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        mock_get_config.return_value = mock_config
        
        with patch('app.libs.sas.storage.queue.helper.QueueServiceClient') as mock_queue_service_client:
            mock_client = Mock()
            mock_queue_service_client.return_value = mock_client
            mock_credential = Mock()
            
            helper = StorageQueueHelper(account_name="testaccount", credential=mock_credential)
            
            assert helper.queue_service_client == mock_client
            mock_queue_service_client.assert_called_once_with(
                "https://testaccount.queue.core.windows.net",
                credential=mock_credential,
                message_encode_policy=helper.message_encode_policy,
                message_decode_policy=helper.message_decode_policy
            )

    @patch('app.libs.sas.storage.queue.helper.get_config')
    def test_init_with_account_name_only(self, mock_get_config):
        """Test initialization with account name only (uses DefaultAzureCredential)"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        mock_get_config.return_value = mock_config
        
        with patch('app.libs.sas.storage.queue.helper.QueueServiceClient') as mock_queue_service_client:
            with patch('app.libs.sas.storage.queue.helper.DefaultAzureCredential') as mock_default_cred:
                mock_client = Mock()
                mock_queue_service_client.return_value = mock_client
                mock_credential = Mock()
                mock_default_cred.return_value = mock_credential
                
                helper = StorageQueueHelper(account_name="testaccount")
                
                assert helper.queue_service_client == mock_client
                mock_default_cred.assert_called_once()

    @patch('app.libs.sas.storage.queue.helper.get_config')
    def test_init_with_custom_config(self, mock_get_config):
        """Test initialization with custom config"""
        custom_config = {"logging_level": "DEBUG"}
        
        with patch('app.libs.sas.storage.queue.helper.QueueServiceClient.from_connection_string'):
            mock_created_config = Mock()
            mock_created_config.get.return_value = "DEBUG"
            
            # Test with dictionary config - it should call the shared_config.create_config
            helper = StorageQueueHelper(connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net", config=mock_created_config)
            
            assert helper.config == mock_created_config

    @patch('app.libs.sas.storage.queue.helper.get_config')
    def test_init_with_custom_encoding_policies(self, mock_get_config):
        """Test initialization with custom encoding/decoding policies"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        mock_get_config.return_value = mock_config
        
        encode_policy = Mock()
        decode_policy = Mock()
        
        with patch('app.libs.sas.storage.queue.helper.QueueServiceClient.from_connection_string'):
            helper = StorageQueueHelper(
                connection_string="test_conn",
                message_encode_policy=encode_policy,
                message_decode_policy=decode_policy
            )
            
            assert helper.message_encode_policy == encode_policy
            assert helper.message_decode_policy == decode_policy

    @patch('app.libs.sas.storage.queue.helper.get_config')
    def test_init_no_connection_info_raises_error(self, mock_get_config):
        """Test that initialization without connection info raises ValueError"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        mock_get_config.return_value = mock_config
        
        with pytest.raises(ValueError, match="Either connection_string or account_name must be provided"):
            StorageQueueHelper()

    @patch('app.libs.sas.storage.queue.helper.get_config')
    def test_init_client_creation_failure(self, mock_get_config):
        """Test initialization failure when client creation fails"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        mock_get_config.return_value = mock_config
        
        with patch('app.libs.sas.storage.queue.helper.QueueServiceClient.from_connection_string') as mock_from_conn:
            mock_from_conn.side_effect = Exception("Connection failed")
            
            with pytest.raises(Exception, match="Connection failed"):
                StorageQueueHelper(connection_string="test_conn")


class TestStorageQueueHelperQueueManagement:
    """Test cases for queue management operations"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.queue.helper.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get.return_value = "INFO"
            mock_get_config.return_value = mock_config
            
            with patch('app.libs.sas.storage.queue.helper.QueueServiceClient.from_connection_string') as mock_from_conn:
                mock_client = Mock()
                mock_from_conn.return_value = mock_client
                
                self.helper = StorageQueueHelper(connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net")
                
                # Create mock queue service client
                self.helper.queue_service_client = create_mock_queue_client()
                
                # Create a specific queue client for operations
                self.mock_queue_client = create_mock_queue_client_specific()
                self.helper.queue_service_client.get_queue_client.return_value = self.mock_queue_client

    def test_create_queue_success(self):
        """Test successful queue creation"""
        result = self.helper.create_queue("test-queue", metadata={"key": "value"})
        
        assert result is True
        self.mock_queue_client.create_queue.assert_called_once_with(
            metadata={"key": "value"},
            timeout=None
        )

    def test_create_queue_already_exists(self):
        """Test queue creation when queue already exists"""
        self.mock_queue_client.create_queue.side_effect = ResourceExistsError()
        
        result = self.helper.create_queue("test-queue")
        
        assert result is False

    def test_create_queue_exception(self):
        """Test queue creation with unexpected exception"""
        self.mock_queue_client.create_queue.side_effect = Exception("API error")
        
        with pytest.raises(Exception, match="API error"):
            self.helper.create_queue("test-queue")

    def test_delete_queue_success(self):
        """Test successful queue deletion"""
        result = self.helper.delete_queue("test-queue")
        
        assert result is True
        self.mock_queue_client.delete_queue.assert_called_once_with(timeout=None)

    def test_delete_queue_not_found(self):
        """Test queue deletion when queue doesn't exist"""
        self.mock_queue_client.delete_queue.side_effect = ResourceNotFoundError()
        
        result = self.helper.delete_queue("test-queue")
        
        assert result is False

    def test_delete_queue_exception(self):
        """Test queue deletion with unexpected exception"""
        self.mock_queue_client.delete_queue.side_effect = Exception("API error")
        
        with pytest.raises(Exception, match="API error"):
            self.helper.delete_queue("test-queue")

    def test_queue_exists_true(self):
        """Test queue existence check when queue exists"""
        mock_properties = Mock()
        self.mock_queue_client.get_queue_properties.return_value = mock_properties
        
        result = self.helper.queue_exists("test-queue")
        
        assert result is True
        self.mock_queue_client.get_queue_properties.assert_called_once_with(timeout=None)

    def test_queue_exists_false(self):
        """Test queue existence check when queue doesn't exist"""
        self.mock_queue_client.get_queue_properties.side_effect = ResourceNotFoundError()
        
        result = self.helper.queue_exists("test-queue")
        
        assert result is False

    def test_queue_exists_exception(self):
        """Test queue existence check with unexpected exception"""
        self.mock_queue_client.get_queue_properties.side_effect = Exception("API error")
        
        with pytest.raises(Exception, match="API error"):
            self.helper.queue_exists("test-queue")

    def test_list_queues_success(self):
        """Test successful queue listing"""
        mock_queue1 = Mock()
        mock_queue1.name = "queue1"
        mock_queue1.metadata = {"key": "value"}
        
        mock_queue2 = Mock()
        mock_queue2.name = "queue2"
        mock_queue2.metadata = None
        
        self.helper.queue_service_client.list_queues.return_value = [mock_queue1, mock_queue2]
        
        result = self.helper.list_queues(include_metadata=True)
        
        assert len(result) == 2
        assert result[0]["name"] == "queue1"
        assert result[0]["metadata"] == {"key": "value"}
        assert result[1]["name"] == "queue2"
        assert result[1]["metadata"] is None

    def test_list_queues_with_filters(self):
        """Test queue listing with filters"""
        mock_queue = Mock()
        mock_queue.name = "test-queue"
        mock_queue.metadata = {}
        
        self.helper.queue_service_client.list_queues.return_value = [mock_queue]
        
        result = self.helper.list_queues(
            name_starts_with="test",
            include_metadata=True,
            results_per_page=10,
            timeout=30
        )
        
        assert len(result) == 1
        self.helper.queue_service_client.list_queues.assert_called_once_with(
            name_starts_with="test",
            include_metadata=True,
            results_per_page=10,
            timeout=30
        )

    def test_list_queues_exception(self):
        """Test queue listing with exception"""
        self.helper.queue_service_client.list_queues.side_effect = Exception("API error")
        
        with pytest.raises(Exception, match="API error"):
            self.helper.list_queues()

    def test_clear_queue_success(self):
        """Test successful queue clearing"""
        result = self.helper.clear_queue("test-queue")
        
        assert result is True
        self.mock_queue_client.clear_messages.assert_called_once_with(timeout=None)

    def test_clear_queue_exception(self):
        """Test queue clearing with exception"""
        self.mock_queue_client.clear_messages.side_effect = Exception("API error")
        
        with pytest.raises(Exception, match="API error"):
            self.helper.clear_queue("test-queue")


class TestStorageQueueHelperMessageOperations:
    """Test cases for message operations"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.queue.helper.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get.return_value = "INFO"
            mock_get_config.return_value = mock_config
            
            with patch('app.libs.sas.storage.queue.helper.QueueServiceClient.from_connection_string') as mock_from_conn:
                mock_client = Mock()
                mock_from_conn.return_value = mock_client
                
                self.helper = StorageQueueHelper(connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net")
                
                # Create mock queue service client
                self.helper.queue_service_client = create_mock_queue_client()
                
                # Create a specific queue client for operations
                self.mock_queue_client = create_mock_queue_client_specific()
                self.helper.queue_service_client.get_queue_client.return_value = self.mock_queue_client

    def test_send_message_string_content(self):
        """Test sending a string message"""
        mock_message = Mock()
        mock_message.id = "msg123"
        mock_message.pop_receipt = "receipt123"
        mock_message.inserted_on = datetime.now()
        mock_message.expires_on = datetime.now() + timedelta(days=7)
        mock_message.next_visible_on = datetime.now()
        
        self.mock_queue_client.send_message.return_value = mock_message
        
        result = self.helper.send_message("test-queue", "Hello, World!")
        
        assert result["message_id"] == "msg123"
        assert result["pop_receipt"] == "receipt123"
        self.mock_queue_client.send_message.assert_called_once_with(
            "Hello, World!",
            visibility_timeout=None,
            time_to_live=None,
            timeout=None
        )

    def test_send_message_dict_content(self):
        """Test sending a dictionary message"""
        mock_message = Mock()
        mock_message.id = "msg123"
        mock_message.pop_receipt = "receipt123"
        mock_message.inserted_on = datetime.now()
        mock_message.expires_on = datetime.now() + timedelta(days=7)
        mock_message.next_visible_on = datetime.now()
        
        self.mock_queue_client.send_message.return_value = mock_message
        
        message_dict = {"key": "value", "number": 42}
        result = self.helper.send_message("test-queue", message_dict)
        
        assert result["message_id"] == "msg123"
        self.mock_queue_client.send_message.assert_called_once_with(
            json.dumps(message_dict),
            visibility_timeout=None,
            time_to_live=None,
            timeout=None
        )

    def test_send_message_bytes_content(self):
        """Test sending bytes content"""
        mock_message = Mock()
        mock_message.id = "msg123"
        mock_message.pop_receipt = "receipt123"
        mock_message.inserted_on = datetime.now()
        mock_message.expires_on = datetime.now() + timedelta(days=7)
        mock_message.next_visible_on = datetime.now()
        
        self.mock_queue_client.send_message.return_value = mock_message
        
        bytes_content = b"binary data"
        result = self.helper.send_message("test-queue", bytes_content)
        
        assert result["message_id"] == "msg123"
        self.mock_queue_client.send_message.assert_called_once_with(
            bytes_content,
            visibility_timeout=None,
            time_to_live=None,
            timeout=None
        )

    def test_send_message_with_options(self):
        """Test sending message with visibility timeout and TTL"""
        mock_message = Mock()
        mock_message.id = "msg123"
        mock_message.pop_receipt = "receipt123"
        mock_message.inserted_on = datetime.now()
        mock_message.expires_on = datetime.now() + timedelta(days=7)
        mock_message.next_visible_on = datetime.now()
        
        self.mock_queue_client.send_message.return_value = mock_message
        
        result = self.helper.send_message(
            "test-queue", 
            "Hello!", 
            visibility_timeout=30,
            time_to_live=3600,
            timeout=10
        )
        
        assert result["message_id"] == "msg123"
        self.mock_queue_client.send_message.assert_called_once_with(
            "Hello!",
            visibility_timeout=30,
            time_to_live=3600,
            timeout=10
        )

    def test_send_message_exception(self):
        """Test send message with exception"""
        self.mock_queue_client.send_message.side_effect = Exception("Send failed")
        
        with pytest.raises(Exception, match="Send failed"):
            self.helper.send_message("test-queue", "Hello!")

    def test_receive_messages_success(self):
        """Test successful message receiving"""
        mock_message1 = Mock()
        mock_message1.id = "msg1"
        mock_message1.pop_receipt = "receipt1"
        mock_message1.content = "Hello 1"
        mock_message1.inserted_on = datetime.now()
        mock_message1.expires_on = datetime.now() + timedelta(days=7)
        mock_message1.next_visible_on = datetime.now()
        mock_message1.dequeue_count = 1
        
        mock_message2 = Mock()
        mock_message2.id = "msg2"
        mock_message2.pop_receipt = "receipt2"
        mock_message2.content = "Hello 2"
        mock_message2.inserted_on = datetime.now()
        mock_message2.expires_on = datetime.now() + timedelta(days=7)
        mock_message2.next_visible_on = datetime.now()
        mock_message2.dequeue_count = 1
        
        self.mock_queue_client.receive_messages.return_value = [mock_message1, mock_message2]
        
        result = self.helper.receive_messages("test-queue", max_messages=2)
        
        assert len(result) == 2
        assert result[0]["message_id"] == "msg1"
        assert result[0]["content"] == "Hello 1"
        assert result[1]["message_id"] == "msg2"
        assert result[1]["content"] == "Hello 2"

    def test_receive_messages_with_options(self):
        """Test receiving messages with options"""
        self.mock_queue_client.receive_messages.return_value = []
        
        self.helper.receive_messages(
            "test-queue",
            max_messages=10,
            visibility_timeout=60,
            timeout=30
        )
        
        self.mock_queue_client.receive_messages.assert_called_once_with(
            max_messages=10,
            visibility_timeout=60,
            timeout=30
        )

    def test_receive_messages_exception(self):
        """Test receive messages with exception"""
        self.mock_queue_client.receive_messages.side_effect = Exception("Receive failed")
        
        with pytest.raises(Exception, match="Receive failed"):
            self.helper.receive_messages("test-queue")

    def test_peek_messages_success(self):
        """Test successful message peeking"""
        mock_message = Mock()
        mock_message.id = "msg1"
        mock_message.content = "Hello peek"
        mock_message.inserted_on = datetime.now()
        mock_message.expires_on = datetime.now() + timedelta(days=7)
        mock_message.next_visible_on = datetime.now()
        mock_message.dequeue_count = 0
        
        self.mock_queue_client.peek_messages.return_value = [mock_message]
        
        result = self.helper.peek_messages("test-queue")
        
        assert len(result) == 1
        assert result[0]["message_id"] == "msg1"
        assert result[0]["content"] == "Hello peek"
        assert "pop_receipt" not in result[0]  # peek doesn't include pop_receipt

    def test_peek_messages_with_options(self):
        """Test peek messages with options"""
        self.mock_queue_client.peek_messages.return_value = []
        
        self.helper.peek_messages("test-queue", max_messages=5, timeout=20)
        
        self.mock_queue_client.peek_messages.assert_called_once_with(
            max_messages=5,
            timeout=20
        )

    def test_peek_messages_exception(self):
        """Test peek messages with exception"""
        self.mock_queue_client.peek_messages.side_effect = Exception("Peek failed")
        
        with pytest.raises(Exception, match="Peek failed"):
            self.helper.peek_messages("test-queue")

    def test_delete_message_success(self):
        """Test successful message deletion"""
        result = self.helper.delete_message("test-queue", "msg123", "receipt123")
        
        assert result is True
        self.mock_queue_client.delete_message.assert_called_once_with(
            "msg123", "receipt123", timeout=None
        )

    def test_delete_message_exception(self):
        """Test delete message with exception"""
        self.mock_queue_client.delete_message.side_effect = Exception("Delete failed")
        
        with pytest.raises(Exception, match="Delete failed"):
            self.helper.delete_message("test-queue", "msg123", "receipt123")

    def test_update_message_with_content(self):
        """Test message update with new content"""
        mock_result = Mock()
        mock_result.pop_receipt = "new_receipt123"
        mock_result.next_visible_on = datetime.now()
        
        self.mock_queue_client.update_message.return_value = mock_result
        
        result = self.helper.update_message(
            "test-queue", 
            "msg123", 
            "receipt123", 
            content={"updated": "content"},
            visibility_timeout=60
        )
        
        assert result["pop_receipt"] == "new_receipt123"
        self.mock_queue_client.update_message.assert_called_once_with(
            "msg123",
            "receipt123",
            content=json.dumps({"updated": "content"}),
            visibility_timeout=60,
            timeout=None
        )

    def test_update_message_without_content(self):
        """Test message update without new content (just visibility timeout)"""
        mock_result = Mock()
        mock_result.pop_receipt = "new_receipt123"
        mock_result.next_visible_on = datetime.now()
        
        self.mock_queue_client.update_message.return_value = mock_result
        
        result = self.helper.update_message(
            "test-queue", 
            "msg123", 
            "receipt123", 
            visibility_timeout=60
        )
        
        assert result["pop_receipt"] == "new_receipt123"
        self.mock_queue_client.update_message.assert_called_once_with(
            "msg123",
            "receipt123",
            content=None,
            visibility_timeout=60,
            timeout=None
        )

    def test_update_message_bytes_content(self):
        """Test message update with bytes content"""
        mock_result = Mock()
        mock_result.pop_receipt = "new_receipt123"
        mock_result.next_visible_on = datetime.now()
        
        self.mock_queue_client.update_message.return_value = mock_result
        
        bytes_content = b"updated binary data"
        result = self.helper.update_message(
            "test-queue", 
            "msg123", 
            "receipt123", 
            content=bytes_content
        )
        
        assert result["pop_receipt"] == "new_receipt123"
        self.mock_queue_client.update_message.assert_called_once_with(
            "msg123",
            "receipt123",
            content=bytes_content,
            visibility_timeout=None,
            timeout=None
        )

    def test_update_message_exception(self):
        """Test update message with exception"""
        self.mock_queue_client.update_message.side_effect = Exception("Update failed")
        
        with pytest.raises(Exception, match="Update failed"):
            self.helper.update_message("test-queue", "msg123", "receipt123")


class TestStorageQueueHelperBatchOperations:
    """Test cases for batch operations"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.queue.helper.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get.return_value = "INFO"
            mock_get_config.return_value = mock_config
            
            with patch('app.libs.sas.storage.queue.helper.QueueServiceClient.from_connection_string') as mock_from_conn:
                mock_client = Mock()
                mock_from_conn.return_value = mock_client
                
                self.helper = StorageQueueHelper(connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net")
                
                # Create mock queue service client
                self.helper.queue_service_client = create_mock_queue_client()
                
                # Create a specific queue client for operations
                self.mock_queue_client = create_mock_queue_client_specific()
                self.helper.queue_service_client.get_queue_client.return_value = self.mock_queue_client

    def test_send_multiple_messages_success(self):
        """Test successful batch message sending"""
        messages = ["Hello 1", {"key": "value"}, b"binary data"]
        
        # Mock successful send_message calls
        mock_results = [
            {"message_id": "msg1", "pop_receipt": "receipt1"},
            {"message_id": "msg2", "pop_receipt": "receipt2"},
            {"message_id": "msg3", "pop_receipt": "receipt3"}
        ]
        
        with patch.object(self.helper, 'send_message', side_effect=mock_results) as mock_send:
            result = self.helper.send_multiple_messages("test-queue", messages)
            
            assert len(result) == 3
            assert all(r["success"] for r in result)
            assert result[0]["message_info"]["message_id"] == "msg1"
            assert mock_send.call_count == 3

    def test_send_multiple_messages_partial_failure(self):
        """Test batch message sending with partial failures"""
        messages = ["Hello 1", "Hello 2", "Hello 3"]
        
        def side_effect(*args, **kwargs):
            if "Hello 2" in args:
                raise Exception("Send failed")
            return {"message_id": "msg123", "pop_receipt": "receipt123"}
        
        with patch.object(self.helper, 'send_message', side_effect=side_effect):
            result = self.helper.send_multiple_messages("test-queue", messages)
            
            assert len(result) == 3
            assert result[0]["success"] is True
            assert result[1]["success"] is False
            assert "Send failed" in result[1]["error"]
            assert result[2]["success"] is True

    def test_process_messages_success(self):
        """Test successful message processing"""
        # Mock received messages
        mock_messages = [
            {
                "message_id": "msg1",
                "pop_receipt": "receipt1", 
                "content": "Hello 1",
                "inserted_on": datetime.now(),
                "expires_on": datetime.now() + timedelta(days=7),
                "next_visible_on": datetime.now(),
                "dequeue_count": 1
            }
        ]
        
        def processor_function(message):
            return {"result": f"Processed: {message['content']}"}
        
        with patch.object(self.helper, 'receive_messages', return_value=mock_messages) as mock_receive:
            with patch.object(self.helper, 'delete_message', return_value=True) as mock_delete:
                result = self.helper.process_messages("test-queue", processor_function)
                
                assert len(result) == 1
                assert result[0]["message_id"] == "msg1"
                assert result[0]["deleted"] is True
                assert "Processed: Hello 1" in str(result[0]["processing_result"])
                mock_delete.assert_called_once_with("test-queue", "msg1", "receipt1", timeout=None)

    def test_process_messages_no_delete_after_processing(self):
        """Test message processing without deleting after processing"""
        mock_messages = [
            {
                "message_id": "msg1",
                "pop_receipt": "receipt1", 
                "content": "Hello 1",
                "inserted_on": datetime.now(),
                "expires_on": datetime.now() + timedelta(days=7),
                "next_visible_on": datetime.now(),
                "dequeue_count": 1
            }
        ]
        
        def processor_function(message):
            return {"result": "processed"}
        
        with patch.object(self.helper, 'receive_messages', return_value=mock_messages):
            with patch.object(self.helper, 'delete_message') as mock_delete:
                result = self.helper.process_messages(
                    "test-queue", 
                    processor_function,
                    delete_after_processing=False
                )
                
                assert len(result) == 1
                assert result[0]["deleted"] is False
                mock_delete.assert_not_called()

    def test_process_messages_processing_failure(self):
        """Test message processing with processing failure"""
        mock_messages = [
            {
                "message_id": "msg1",
                "pop_receipt": "receipt1", 
                "content": "Hello 1",
                "inserted_on": datetime.now(),
                "expires_on": datetime.now() + timedelta(days=7),
                "next_visible_on": datetime.now(),
                "dequeue_count": 1
            }
        ]
        
        def processor_function(message):
            raise Exception("Processing failed")
        
        with patch.object(self.helper, 'receive_messages', return_value=mock_messages):
            with patch.object(self.helper, 'delete_message') as mock_delete:
                result = self.helper.process_messages("test-queue", processor_function)
                
                assert len(result) == 1
                assert result[0]["deleted"] is False
                assert "Processing failed" in result[0]["processing_result"]["error"]
                mock_delete.assert_not_called()

    def test_process_messages_with_options(self):
        """Test message processing with custom options"""
        mock_messages = []
        
        def processor_function(message):
            return {"result": "processed"}
        
        with patch.object(self.helper, 'receive_messages', return_value=mock_messages) as mock_receive:
            self.helper.process_messages(
                "test-queue",
                processor_function,
                max_messages=10,
                visibility_timeout=60,
                timeout=30
            )
            
            mock_receive.assert_called_once_with(
                "test-queue",
                max_messages=10,
                visibility_timeout=60,
                timeout=30
            )

    def test_process_messages_receive_exception(self):
        """Test message processing when receiving messages fails"""
        def processor_function(message):
            return {"result": "processed"}
        
        with patch.object(self.helper, 'receive_messages', side_effect=Exception("Receive failed")):
            with pytest.raises(Exception, match="Receive failed"):
                self.helper.process_messages("test-queue", processor_function)


class TestStorageQueueHelperPropertiesAndMetadata:
    """Test cases for queue properties, metadata, and statistics"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.queue.helper.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get.return_value = "INFO"
            mock_get_config.return_value = mock_config
            
            with patch('app.libs.sas.storage.queue.helper.QueueServiceClient.from_connection_string') as mock_from_conn:
                mock_client = Mock()
                mock_from_conn.return_value = mock_client
                
                self.helper = StorageQueueHelper(connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net")
                
                # Create mock queue service client
                self.helper.queue_service_client = create_mock_queue_client()
                
                # Create a specific queue client for operations
                self.mock_queue_client = create_mock_queue_client_specific()
                self.helper.queue_service_client.get_queue_client.return_value = self.mock_queue_client

    def test_get_queue_properties_success(self):
        """Test successful queue properties retrieval"""
        mock_properties = Mock()
        mock_properties.metadata = {"key1": "value1", "key2": "value2"}
        mock_properties.approximate_message_count = 42
        
        self.mock_queue_client.get_queue_properties.return_value = mock_properties
        
        result = self.helper.get_queue_properties("test-queue")
        
        assert result["name"] == "test-queue"
        assert result["metadata"] == {"key1": "value1", "key2": "value2"}
        assert result["approximate_message_count"] == 42
        self.mock_queue_client.get_queue_properties.assert_called_once_with(timeout=None)

    def test_get_queue_properties_with_timeout(self):
        """Test queue properties retrieval with timeout"""
        mock_properties = Mock()
        mock_properties.metadata = {}
        mock_properties.approximate_message_count = 0
        
        self.mock_queue_client.get_queue_properties.return_value = mock_properties
        
        self.helper.get_queue_properties("test-queue", timeout=30)
        
        self.mock_queue_client.get_queue_properties.assert_called_once_with(timeout=30)

    def test_get_queue_properties_exception(self):
        """Test queue properties retrieval with exception"""
        self.mock_queue_client.get_queue_properties.side_effect = Exception("API error")
        
        with pytest.raises(Exception, match="API error"):
            self.helper.get_queue_properties("test-queue")

    def test_set_queue_metadata_success(self):
        """Test successful queue metadata setting"""
        metadata = {"key1": "value1", "environment": "test"}
        
        result = self.helper.set_queue_metadata("test-queue", metadata)
        
        assert result is True
        self.mock_queue_client.set_queue_metadata.assert_called_once_with(metadata, timeout=None)

    def test_set_queue_metadata_with_timeout(self):
        """Test queue metadata setting with timeout"""
        metadata = {"key": "value"}
        
        self.helper.set_queue_metadata("test-queue", metadata, timeout=20)
        
        self.mock_queue_client.set_queue_metadata.assert_called_once_with(metadata, timeout=20)

    def test_set_queue_metadata_exception(self):
        """Test queue metadata setting with exception"""
        self.mock_queue_client.set_queue_metadata.side_effect = Exception("API error")
        
        with pytest.raises(Exception, match="API error"):
            self.helper.set_queue_metadata("test-queue", {"key": "value"})

    def test_get_queue_statistics_success(self):
        """Test successful queue statistics retrieval"""
        with patch.object(self.helper, 'get_queue_properties') as mock_get_props:
            mock_get_props.return_value = {
                "name": "test-queue",
                "metadata": {"env": "test"},
                "approximate_message_count": 10
            }
            
            result = self.helper.get_queue_statistics("test-queue")
            
            assert result["queue_name"] == "test-queue"
            assert result["approximate_message_count"] == 10
            assert result["metadata"] == {"env": "test"}
            assert "last_updated" in result

    def test_get_queue_statistics_exception(self):
        """Test queue statistics retrieval with exception"""
        with patch.object(self.helper, 'get_queue_properties', side_effect=Exception("API error")):
            with pytest.raises(Exception, match="API error"):
                self.helper.get_queue_statistics("test-queue")


class TestStorageQueueHelperUtilityMethods:
    """Test cases for utility methods"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.queue.helper.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get.return_value = "INFO"
            mock_get_config.return_value = mock_config
            
            with patch('app.libs.sas.storage.queue.helper.QueueServiceClient.from_connection_string') as mock_from_conn:
                mock_client = Mock()
                mock_from_conn.return_value = mock_client
                
                self.helper = StorageQueueHelper(connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net")
                
                # Create mock queue service client
                self.helper.queue_service_client = create_mock_queue_client()

    def test_get_queue_url_success(self):
        """Test successful queue URL generation"""
        self.helper.queue_service_client.account_name = "testaccount"
        
        result = self.helper.get_queue_url("test-queue")
        
        assert result == "https://testaccount.queue.core.windows.net/test-queue"

    def test_get_queue_url_no_account_name(self):
        """Test queue URL generation when account name is not available"""
        with patch.object(self.helper, '_get_account_name', return_value=None):
            result = self.helper.get_queue_url("test-queue")
            
            assert result == "https://None.queue.core.windows.net/test-queue"

    def test_get_account_name_success(self):
        """Test successful account name extraction"""
        self.helper.queue_service_client.account_name = "testaccount"
        
        result = self.helper._get_account_name()
        
        assert result == "testaccount"

    def test_get_account_name_exception(self):
        """Test account name extraction with exception"""
        del self.helper.queue_service_client.account_name  # Remove the attribute
        
        result = self.helper._get_account_name()
        
        assert result is None

    def test_encode_message_dict(self):
        """Test message encoding with dictionary"""
        message = {"key": "value", "number": 42}
        
        result = self.helper.encode_message(message)
        
        assert result == json.dumps(message)

    def test_encode_message_string(self):
        """Test message encoding with string"""
        message = "Hello, World!"
        
        result = self.helper.encode_message(message)
        
        assert result == "Hello, World!"

    def test_encode_message_other_type(self):
        """Test message encoding with other types"""
        message = 123
        
        result = self.helper.encode_message(message)
        
        assert result == "123"

    def test_decode_message_json(self):
        """Test message decoding with valid JSON"""
        message_content = '{"key": "value", "number": 42}'
        
        result = self.helper.decode_message(message_content)
        
        assert result == {"key": "value", "number": 42}

    def test_decode_message_invalid_json(self):
        """Test message decoding with invalid JSON"""
        message_content = "Not JSON content"
        
        result = self.helper.decode_message(message_content)
        
        assert result == "Not JSON content"

    def test_decode_message_none(self):
        """Test message decoding with None"""
        result = self.helper.decode_message(None)
        
        assert result is None

    def test_create_message_processor_success(self):
        """Test message processor creation with successful processing"""
        def user_processor(message):
            return f"Processed: {message['content']}"
        
        wrapper = self.helper.create_message_processor(user_processor)
        
        # Mock message from queue
        queue_message = {
            "message_id": "msg123",
            "content": '{"data": "test"}',
            "insertion_time": datetime.now(),
            "expiration_time": datetime.now() + timedelta(days=7),
            "dequeue_count": 1,
            "pop_receipt": "receipt123"
        }
        
        result = wrapper(queue_message)
        
        assert result["success"] is True
        assert "Processed:" in str(result["result"])

    def test_create_message_processor_exception(self):
        """Test message processor creation with processing exception"""
        def user_processor(message):
            raise Exception("Processing failed")
        
        wrapper = self.helper.create_message_processor(user_processor)
        
        # Mock message from queue
        queue_message = {
            "message_id": "msg123",
            "content": "test content",
            "insertion_time": datetime.now(),
            "expiration_time": datetime.now() + timedelta(days=7),
            "dequeue_count": 1,
            "pop_receipt": "receipt123"
        }
        
        result = wrapper(queue_message)
        
        assert result["success"] is False
        assert "Processing failed" in result["error"]

    def test_create_message_processor_json_decode(self):
        """Test message processor with JSON content decoding"""
        def user_processor(message):
            return message["content"]["key"]
        
        wrapper = self.helper.create_message_processor(user_processor)
        
        # Mock message with JSON content
        queue_message = {
            "message_id": "msg123",
            "content": '{"key": "decoded_value"}',
            "insertion_time": datetime.now(),
            "expiration_time": datetime.now() + timedelta(days=7),
            "dequeue_count": 1,
            "pop_receipt": "receipt123"
        }
        
        result = wrapper(queue_message)
        
        assert result["success"] is True
        assert result["result"] == "decoded_value"


class TestStorageQueueHelperErrorHandling:
    """Test cases for error handling scenarios"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.queue.helper.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get.return_value = "INFO"
            mock_get_config.return_value = mock_config
            
            with patch('app.libs.sas.storage.queue.helper.QueueServiceClient.from_connection_string') as mock_from_conn:
                mock_client = Mock()
                mock_from_conn.return_value = mock_client
                
                self.helper = StorageQueueHelper(connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net")
                
                # Create mock queue service client
                self.helper.queue_service_client = create_mock_queue_client()
                
                # Create a specific queue client for operations
                self.mock_queue_client = create_mock_queue_client_specific()
                self.helper.queue_service_client.get_queue_client.return_value = self.mock_queue_client

    def test_large_message_handling(self):
        """Test handling of large messages"""
        # Create a large message (over 64KB when encoded)
        large_message = "x" * 100000
        
        self.mock_queue_client.send_message.side_effect = Exception("Message too large")
        
        with pytest.raises(Exception, match="Message too large"):
            self.helper.send_message("test-queue", large_message)

    def test_invalid_queue_name_handling(self):
        """Test handling of invalid queue names"""
        self.mock_queue_client.create_queue.side_effect = Exception("Invalid queue name")
        
        with pytest.raises(Exception, match="Invalid queue name"):
            self.helper.create_queue("invalid-queue-name!")

    def test_connection_failure_handling(self):
        """Test handling of connection failures"""
        self.mock_queue_client.send_message.side_effect = Exception("Connection failed")
        
        with pytest.raises(Exception, match="Connection failed"):
            self.helper.send_message("test-queue", "Hello!")

    def test_timeout_handling(self):
        """Test handling of timeout scenarios"""
        self.mock_queue_client.receive_messages.side_effect = Exception("Operation timed out")
        
        with pytest.raises(Exception, match="Operation timed out"):
            self.helper.receive_messages("test-queue", timeout=1)

    def test_resource_not_found_handling(self):
        """Test handling of resource not found scenarios"""
        self.mock_queue_client.get_queue_properties.side_effect = ResourceNotFoundError()
        
        result = self.helper.queue_exists("non-existent-queue")
        
        assert result is False

    def test_resource_exists_handling(self):
        """Test handling of resource exists scenarios"""
        self.mock_queue_client.create_queue.side_effect = ResourceExistsError()
        
        result = self.helper.create_queue("existing-queue")
        
        assert result is False