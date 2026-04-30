"""Tests for src/app/libs/sas/storage/queue/helper.py"""

import json
from unittest.mock import (
    MagicMock,
    patch,
    PropertyMock,
    call,
)
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from libs.sas.storage.queue.helper import StorageQueueHelper


# Fixtures for mocking Azure SDK objects
@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_storage_queue_helper_init_with_connection_string(mock_queue_service):
    """Test StorageQueueHelper initialization with connection string"""
    mock_service_instance = MagicMock()
    mock_queue_service.from_connection_string.return_value = mock_service_instance
    
    helper = StorageQueueHelper(connection_string="test_connection_string")
    
    assert helper is not None
    assert helper.queue_service_client == mock_service_instance
    mock_queue_service.from_connection_string.assert_called_once()


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_storage_queue_helper_init_with_account_name_and_credential(mock_queue_service):
    """Test StorageQueueHelper initialization with account name and credential"""
    mock_service_instance = MagicMock()
    mock_queue_service.return_value = mock_service_instance
    mock_credential = MagicMock()
    
    helper = StorageQueueHelper(account_name="test_account", credential=mock_credential)
    
    assert helper is not None
    mock_queue_service.assert_called_once()
    call_args = mock_queue_service.call_args
    assert "https://test_account.queue.core.windows.net" in call_args[0][0]


@patch("libs.sas.storage.queue.helper.DefaultAzureCredential")
@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_storage_queue_helper_init_with_account_name_only(mock_queue_service, mock_cred):
    """Test StorageQueueHelper initialization with account name only (uses DefaultAzureCredential)"""
    mock_service_instance = MagicMock()
    mock_queue_service.return_value = mock_service_instance
    mock_default_cred = MagicMock()
    mock_cred.return_value = mock_default_cred
    
    helper = StorageQueueHelper(account_name="test_account")
    
    assert helper is not None
    mock_cred.assert_called_once()
    mock_queue_service.assert_called_once()


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_storage_queue_helper_init_no_params_raises_error(mock_queue_service):
    """Test StorageQueueHelper initialization without required params raises ValueError"""
    try:
        helper = StorageQueueHelper()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "connection_string" in str(e) or "account_name" in str(e)


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_storage_queue_helper_init_with_config_dict(mock_queue_service):
    """Test StorageQueueHelper initialization with config dictionary"""
    mock_service_instance = MagicMock()
    mock_queue_service.from_connection_string.return_value = mock_service_instance
    
    custom_config = {"retry_attempts": 5, "timeout_seconds": 60}
    helper = StorageQueueHelper(
        connection_string="test_conn",
        config=custom_config,
    )
    
    assert helper.config.get("retry_attempts") == 5
    assert helper.config.get("timeout_seconds") == 60


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_create_queue_success(mock_queue_service):
    """Test create_queue returns True on success"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.create_queue("test_queue", metadata={"key": "value"})
    
    assert result is True
    mock_queue_client.create_queue.assert_called_once()


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_create_queue_already_exists(mock_queue_service):
    """Test create_queue returns False when queue already exists"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_queue_client.create_queue.side_effect = ResourceExistsError("Queue exists")
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.create_queue("test_queue")
    
    assert result is False


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_create_queue_error(mock_queue_service):
    """Test create_queue raises exception on error"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_queue_client.create_queue.side_effect = Exception("Connection error")
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    
    try:
        helper.create_queue("test_queue")
        assert False, "Should have raised exception"
    except Exception as e:
        assert "Connection error" in str(e)


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_delete_queue_success(mock_queue_service):
    """Test delete_queue returns True on success"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.delete_queue("test_queue")
    
    assert result is True
    mock_queue_client.delete_queue.assert_called_once()


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_delete_queue_not_found(mock_queue_service):
    """Test delete_queue returns False when queue not found"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_queue_client.delete_queue.side_effect = ResourceNotFoundError("Queue not found")
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.delete_queue("test_queue")
    
    assert result is False


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_queue_exists_true(mock_queue_service):
    """Test queue_exists returns True when queue exists"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.queue_exists("test_queue")
    
    assert result is True
    mock_queue_client.get_queue_properties.assert_called_once()


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_queue_exists_false(mock_queue_service):
    """Test queue_exists returns False when queue not found"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_queue_client.get_queue_properties.side_effect = ResourceNotFoundError(
        "Queue not found"
    )
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.queue_exists("test_queue")
    
    assert result is False


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_list_queues_success(mock_queue_service):
    """Test list_queues returns list of queues"""
    mock_service = MagicMock()
    mock_queue1 = MagicMock()
    mock_queue1.name = "queue1"
    mock_queue1.metadata = {"env": "test"}
    
    mock_queue2 = MagicMock()
    mock_queue2.name = "queue2"
    mock_queue2.metadata = None
    
    mock_service.list_queues.return_value = [mock_queue1, mock_queue2]
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.list_queues(include_metadata=True)
    
    assert len(result) == 2
    assert result[0]["name"] == "queue1"
    assert result[0]["metadata"] == {"env": "test"}
    assert result[1]["name"] == "queue2"


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_clear_queue_success(mock_queue_service):
    """Test clear_queue returns True on success"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.clear_queue("test_queue")
    
    assert result is True
    mock_queue_client.clear_messages.assert_called_once()


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_send_message_string(mock_queue_service):
    """Test send_message with string content"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_result = MagicMock()
    mock_result.id = "msg_id_1"
    mock_result.pop_receipt = "receipt_1"
    mock_result.inserted_on = "2024-01-01T00:00:00"
    mock_result.expires_on = "2024-01-08T00:00:00"
    mock_result.next_visible_on = "2024-01-01T00:10:00"
    
    mock_queue_client.send_message.return_value = mock_result
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.send_message("test_queue", "test message")
    
    assert result["message_id"] == "msg_id_1"
    assert result["pop_receipt"] == "receipt_1"
    mock_queue_client.send_message.assert_called_once()


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_send_message_dict(mock_queue_service):
    """Test send_message with dict content (JSON serialization)"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_result = MagicMock()
    mock_result.id = "msg_id_2"
    mock_result.pop_receipt = "receipt_2"
    mock_result.inserted_on = "2024-01-01T00:00:00"
    mock_result.expires_on = "2024-01-08T00:00:00"
    mock_result.next_visible_on = "2024-01-01T00:10:00"
    
    mock_queue_client.send_message.return_value = mock_result
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    msg_dict = {"key": "value", "number": 42}
    result = helper.send_message("test_queue", msg_dict)
    
    assert result["message_id"] == "msg_id_2"
    # Verify the message was JSON serialized
    call_args = mock_queue_client.send_message.call_args
    assert json.loads(call_args[0][0]) == msg_dict


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_send_message_bytes(mock_queue_service):
    """Test send_message with bytes content"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_result = MagicMock()
    mock_result.id = "msg_id_3"
    mock_result.pop_receipt = "receipt_3"
    mock_result.inserted_on = "2024-01-01T00:00:00"
    mock_result.expires_on = "2024-01-08T00:00:00"
    mock_result.next_visible_on = "2024-01-01T00:10:00"
    
    mock_queue_client.send_message.return_value = mock_result
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.send_message("test_queue", b"binary data")
    
    assert result["message_id"] == "msg_id_3"


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_receive_messages_success(mock_queue_service):
    """Test receive_messages returns list of messages"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_msg1 = MagicMock()
    mock_msg1.id = "msg_1"
    mock_msg1.pop_receipt = "receipt_1"
    mock_msg1.content = "content 1"
    mock_msg1.inserted_on = "2024-01-01T00:00:00"
    mock_msg1.expires_on = "2024-01-08T00:00:00"
    mock_msg1.next_visible_on = "2024-01-01T00:10:00"
    mock_msg1.dequeue_count = 1
    
    mock_queue_client.receive_messages.return_value = [mock_msg1]
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.receive_messages("test_queue", max_messages=5)
    
    assert len(result) == 1
    assert result[0]["message_id"] == "msg_1"
    assert result[0]["content"] == "content 1"
    assert result[0]["dequeue_count"] == 1


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_peek_messages_success(mock_queue_service):
    """Test peek_messages returns list of messages"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_msg1 = MagicMock()
    mock_msg1.id = "msg_1"
    mock_msg1.content = "peeked content"
    mock_msg1.inserted_on = "2024-01-01T00:00:00"
    mock_msg1.expires_on = "2024-01-08T00:00:00"
    mock_msg1.next_visible_on = "2024-01-01T00:10:00"
    mock_msg1.dequeue_count = 0
    
    mock_queue_client.peek_messages.return_value = [mock_msg1]
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.peek_messages("test_queue", max_messages=1)
    
    assert len(result) == 1
    assert result[0]["content"] == "peeked content"
    assert "pop_receipt" not in result[0]  # peek doesn't return pop_receipt


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_delete_message_success(mock_queue_service):
    """Test delete_message returns True on success"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.delete_message("test_queue", "msg_id", "receipt")
    
    assert result is True
    mock_queue_client.delete_message.assert_called_once_with("msg_id", "receipt", timeout=None)


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_update_message_with_content(mock_queue_service):
    """Test update_message with new content"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_result = MagicMock()
    mock_result.pop_receipt = "new_receipt"
    mock_result.next_visible_on = "2024-01-01T00:10:00"
    
    mock_queue_client.update_message.return_value = mock_result
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.update_message(
        "test_queue",
        "msg_id",
        "receipt",
        content="updated content",
    )
    
    assert result["pop_receipt"] == "new_receipt"
    mock_queue_client.update_message.assert_called_once()


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_update_message_with_dict_content(mock_queue_service):
    """Test update_message with dict content"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_result = MagicMock()
    mock_result.pop_receipt = "new_receipt"
    mock_result.next_visible_on = "2024-01-01T00:10:00"
    
    mock_queue_client.update_message.return_value = mock_result
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    new_content = {"status": "updated", "value": 100}
    result = helper.update_message(
        "test_queue",
        "msg_id",
        "receipt",
        content=new_content,
    )
    
    assert result["pop_receipt"] == "new_receipt"
    call_args = mock_queue_client.update_message.call_args
    assert json.loads(call_args[1]["content"]) == new_content


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_send_multiple_messages_success(mock_queue_service):
    """Test send_multiple_messages sends all messages"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_result = MagicMock()
    mock_result.id = "msg_id"
    mock_result.pop_receipt = "receipt"
    mock_result.inserted_on = "2024-01-01T00:00:00"
    mock_result.expires_on = "2024-01-08T00:00:00"
    mock_result.next_visible_on = "2024-01-01T00:10:00"
    
    mock_queue_client.send_message.return_value = mock_result
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    messages = ["msg1", "msg2", "msg3"]
    result = helper.send_multiple_messages("test_queue", messages)
    
    assert len(result) == 3
    assert all(r["success"] for r in result)


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_send_multiple_messages_with_failures(mock_queue_service):
    """Test send_multiple_messages handles failures gracefully"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_result = MagicMock()
    mock_result.id = "msg_id"
    mock_result.pop_receipt = "receipt"
    mock_result.inserted_on = "2024-01-01T00:00:00"
    mock_result.expires_on = "2024-01-08T00:00:00"
    mock_result.next_visible_on = "2024-01-01T00:10:00"
    
    mock_queue_client.send_message.side_effect = [
        mock_result,
        Exception("Send failed"),
        mock_result,
    ]
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    messages = ["msg1", "msg2", "msg3"]
    result = helper.send_multiple_messages("test_queue", messages)
    
    assert len(result) == 3
    assert result[0]["success"] is True
    assert result[1]["success"] is False
    assert result[2]["success"] is True


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_process_messages_success(mock_queue_service):
    """Test process_messages with successful processing"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_msg = MagicMock()
    mock_msg.id = "msg_1"
    mock_msg.pop_receipt = "receipt_1"
    mock_msg.content = "content"
    mock_msg.inserted_on = "2024-01-01T00:00:00"
    mock_msg.expires_on = "2024-01-08T00:00:00"
    mock_msg.next_visible_on = "2024-01-01T00:10:00"
    mock_msg.dequeue_count = 1
    
    mock_queue_client.receive_messages.return_value = [mock_msg]
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    def processor(msg):
        return {"success": True, "processed": msg["message_id"]}
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.process_messages("test_queue", processor, delete_after_processing=True)
    
    assert len(result) == 1
    assert result[0]["processing_result"]["success"] is True
    assert result[0]["deleted"] is True
    mock_queue_client.delete_message.assert_called_once()


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_process_messages_no_delete(mock_queue_service):
    """Test process_messages with delete_after_processing=False"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_msg = MagicMock()
    mock_msg.id = "msg_1"
    mock_msg.pop_receipt = "receipt_1"
    mock_msg.content = "content"
    mock_msg.inserted_on = "2024-01-01T00:00:00"
    mock_msg.expires_on = "2024-01-08T00:00:00"
    mock_msg.next_visible_on = "2024-01-01T00:10:00"
    mock_msg.dequeue_count = 1
    
    mock_queue_client.receive_messages.return_value = [mock_msg]
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    def processor(msg):
        return {"success": True}
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.process_messages("test_queue", processor, delete_after_processing=False)
    
    assert result[0]["deleted"] is False
    mock_queue_client.delete_message.assert_not_called()


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_get_queue_properties(mock_queue_service):
    """Test get_queue_properties returns queue properties"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_props = MagicMock()
    mock_props.metadata = {"env": "test"}
    mock_props.approximate_message_count = 42
    
    mock_queue_client.get_queue_properties.return_value = mock_props
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.get_queue_properties("test_queue")
    
    assert result["name"] == "test_queue"
    assert result["metadata"] == {"env": "test"}
    assert result["approximate_message_count"] == 42


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_set_queue_metadata(mock_queue_service):
    """Test set_queue_metadata returns True on success"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.set_queue_metadata("test_queue", {"key": "value"})
    
    assert result is True
    mock_queue_client.set_queue_metadata.assert_called_once()


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_send_message_error_handling(mock_queue_service):
    """Test send_message raises exception on error"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_queue_client.send_message.side_effect = Exception("Network error")
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    
    try:
        helper.send_message("test_queue", "message")
        assert False, "Should have raised exception"
    except Exception as e:
        assert "Network error" in str(e)


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_receive_messages_empty(mock_queue_service):
    """Test receive_messages with no messages"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_queue_client.receive_messages.return_value = []
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.receive_messages("test_queue")
    
    assert result == []


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_list_queues_with_filter(mock_queue_service):
    """Test list_queues with name prefix filter"""
    mock_service = MagicMock()
    
    mock_queue = MagicMock()
    mock_queue.name = "myqueue"
    mock_queue.metadata = None
    
    mock_service.list_queues.return_value = [mock_queue]
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.list_queues(name_starts_with="myq", results_per_page=10)
    
    assert len(result) == 1
    mock_service.list_queues.assert_called_once()
    call_kwargs = mock_service.list_queues.call_args[1]
    assert call_kwargs["name_starts_with"] == "myq"
    assert call_kwargs["results_per_page"] == 10


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_get_queue_properties_error(mock_queue_service):
    """Test get_queue_properties raises exception on error"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_queue_client.get_queue_properties.side_effect = Exception("Service error")
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    
    try:
        helper.get_queue_properties("test_queue")
        assert False, "Should have raised exception"
    except Exception as e:
        assert "Service error" in str(e)


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_delete_message_error(mock_queue_service):
    """Test delete_message raises exception on error"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_queue_client.delete_message.side_effect = Exception("Delete failed")
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    
    try:
        helper.delete_message("test_queue", "msg_id", "receipt")
        assert False, "Should have raised exception"
    except Exception as e:
        assert "Delete failed" in str(e)


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_update_message_without_content(mock_queue_service):
    """Test update_message without content (only timeout)"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_result = MagicMock()
    mock_result.pop_receipt = "new_receipt"
    mock_result.next_visible_on = "2024-01-01T00:10:00"
    
    mock_queue_client.update_message.return_value = mock_result
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.update_message(
        "test_queue",
        "msg_id",
        "receipt",
        visibility_timeout=300,
    )
    
    assert result["pop_receipt"] == "new_receipt"
    call_kwargs = mock_queue_client.update_message.call_args[1]
    assert call_kwargs["content"] is None


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_update_message_with_bytes_content(mock_queue_service):
    """Test update_message with bytes content"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_result = MagicMock()
    mock_result.pop_receipt = "new_receipt"
    mock_result.next_visible_on = "2024-01-01T00:10:00"
    
    mock_queue_client.update_message.return_value = mock_result
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.update_message(
        "test_queue",
        "msg_id",
        "receipt",
        content=b"binary content",
    )
    
    assert result["pop_receipt"] == "new_receipt"


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_process_messages_processor_failure(mock_queue_service):
    """Test process_messages when processor raises exception"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_msg = MagicMock()
    mock_msg.id = "msg_1"
    mock_msg.pop_receipt = "receipt_1"
    mock_msg.content = "content"
    mock_msg.inserted_on = "2024-01-01T00:00:00"
    mock_msg.expires_on = "2024-01-08T00:00:00"
    mock_msg.next_visible_on = "2024-01-01T00:10:00"
    mock_msg.dequeue_count = 1
    
    mock_queue_client.receive_messages.return_value = [mock_msg]
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    def failing_processor(msg):
        raise ValueError("Processing error")
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.process_messages("test_queue", failing_processor)
    
    assert len(result) == 1
    assert result[0]["processing_result"]["success"] is False
    assert "Processing error" in result[0]["processing_result"]["error"]


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_process_messages_delete_failed(mock_queue_service):
    """Test process_messages when delete fails after processing"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_msg = MagicMock()
    mock_msg.id = "msg_1"
    mock_msg.pop_receipt = "receipt_1"
    mock_msg.content = "content"
    mock_msg.inserted_on = "2024-01-01T00:00:00"
    mock_msg.expires_on = "2024-01-08T00:00:00"
    mock_msg.next_visible_on = "2024-01-01T00:10:00"
    mock_msg.dequeue_count = 1
    
    mock_queue_client.receive_messages.return_value = [mock_msg]
    mock_queue_client.delete_message.side_effect = Exception("Delete failed")
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    def processor(msg):
        return {"success": True}
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.process_messages("test_queue", processor, delete_after_processing=True)
    
    assert len(result) == 1
    assert result[0]["deleted"] is False


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_send_message_with_int(mock_queue_service):
    """Test send_message with integer content"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    
    mock_result = MagicMock()
    mock_result.id = "msg_id"
    mock_result.pop_receipt = "receipt"
    mock_result.inserted_on = "2024-01-01T00:00:00"
    mock_result.expires_on = "2024-01-08T00:00:00"
    mock_result.next_visible_on = "2024-01-01T00:10:00"
    
    mock_queue_client.send_message.return_value = mock_result
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    result = helper.send_message("test_queue", 12345)
    
    assert result["message_id"] == "msg_id"
    call_args = mock_queue_client.send_message.call_args
    assert call_args[0][0] == "12345"


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_clear_queue_error(mock_queue_service):
    """Test clear_queue error handling"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_queue_client.clear_messages.side_effect = Exception("Clear failed")
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    
    try:
        helper.clear_queue("test_queue")
        assert False, "Should have raised exception"
    except Exception as e:
        assert "Clear failed" in str(e)


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_queue_exists_error(mock_queue_service):
    """Test queue_exists error handling"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_queue_client.get_queue_properties.side_effect = Exception("API error")
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    
    try:
        helper.queue_exists("test_queue")
        assert False, "Should have raised exception"
    except Exception as e:
        assert "API error" in str(e)


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_list_queues_error(mock_queue_service):
    """Test list_queues error handling"""
    mock_service = MagicMock()
    mock_service.list_queues.side_effect = Exception("List failed")
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    
    try:
        helper.list_queues()
        assert False, "Should have raised exception"
    except Exception as e:
        assert "List failed" in str(e)


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_receive_messages_error(mock_queue_service):
    """Test receive_messages error handling"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_queue_client.receive_messages.side_effect = Exception("Receive failed")
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    
    try:
        helper.receive_messages("test_queue")
        assert False, "Should have raised exception"
    except Exception as e:
        assert "Receive failed" in str(e)


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_peek_messages_error(mock_queue_service):
    """Test peek_messages error handling"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_queue_client.peek_messages.side_effect = Exception("Peek failed")
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    
    try:
        helper.peek_messages("test_queue")
        assert False, "Should have raised exception"
    except Exception as e:
        assert "Peek failed" in str(e)


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_process_messages_error_on_receive(mock_queue_service):
    """Test process_messages when receive_messages fails"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_queue_client.receive_messages.side_effect = Exception("Receive error")
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    def processor(msg):
        return {"success": True}
    
    helper = StorageQueueHelper(connection_string="test_conn")
    
    try:
        helper.process_messages("test_queue", processor)
        assert False, "Should have raised exception"
    except Exception as e:
        assert "Receive error" in str(e)


@patch("libs.sas.storage.queue.helper.QueueServiceClient")
def test_set_queue_metadata_error(mock_queue_service):
    """Test set_queue_metadata error handling"""
    mock_service = MagicMock()
    mock_queue_client = MagicMock()
    mock_queue_client.set_queue_metadata.side_effect = Exception("Metadata error")
    mock_service.get_queue_client.return_value = mock_queue_client
    mock_queue_service.from_connection_string.return_value = mock_service
    
    helper = StorageQueueHelper(connection_string="test_conn")
    
    try:
        helper.set_queue_metadata("test_queue", {"key": "value"})
        assert False, "Should have raised exception"
    except Exception as e:
        assert "Metadata error" in str(e)
