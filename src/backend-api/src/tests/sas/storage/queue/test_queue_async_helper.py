"""Tests for src/app/libs/sas/storage/queue/async_helper.py"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper


def test_async_storage_queue_helper_init_with_connection_string():
    """Test AsyncStorageQueueHelper initialization with connection string"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service_instance = MagicMock()
            mock_queue_service.from_connection_string.return_value = mock_service_instance
            
            helper = AsyncStorageQueueHelper(connection_string="test_connection_string")
            assert helper is not None
            assert helper._connection_string == "test_connection_string"
    
    asyncio.run(_run())


def test_async_storage_queue_helper_init_with_account_name():
    """Test AsyncStorageQueueHelper initialization with account name"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient"):
            helper = AsyncStorageQueueHelper(account_name="test_account")
            assert helper is not None
            assert helper._account_name == "test_account"
    
    asyncio.run(_run())


def test_async_storage_queue_helper_init_no_params_raises_error():
    """Test AsyncStorageQueueHelper initialization without required params raises ValueError"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient"):
            try:
                helper = AsyncStorageQueueHelper()
                await helper._initialize_client()
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "connection_string" in str(e) or "account_name" in str(e)
    
    asyncio.run(_run())


def test_async_storage_queue_helper_context_manager():
    """Test AsyncStorageQueueHelper as async context manager"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service_instance = AsyncMock()
            mock_service_instance.close = AsyncMock()
            mock_queue_service.from_connection_string.return_value = mock_service_instance
            
            async with AsyncStorageQueueHelper(connection_string="test_conn") as helper:
                assert helper is not None
                assert helper._queue_service_client is not None
    
    asyncio.run(_run())


def test_async_create_queue_success():
    """Test create_queue returns True on success"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.create_queue("test_queue", metadata={"key": "value"})
            
            assert result is True
            mock_queue_client.create_queue.assert_called_once()
    
    asyncio.run(_run())


def test_async_create_queue_already_exists():
    """Test create_queue returns False when queue already exists"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_queue_client.create_queue.side_effect = ResourceExistsError("Queue exists")
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.create_queue("test_queue")
            
            assert result is False
    
    asyncio.run(_run())


def test_async_delete_queue_success():
    """Test delete_queue returns True on success"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.delete_queue("test_queue")
            
            assert result is True
            mock_queue_client.delete_queue.assert_called_once()
    
    asyncio.run(_run())


def test_async_delete_queue_not_found():
    """Test delete_queue returns False when queue not found"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_queue_client.delete_queue.side_effect = ResourceNotFoundError("Not found")
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.delete_queue("test_queue")
            
            assert result is False
    
    asyncio.run(_run())


def test_async_queue_exists_true():
    """Test queue_exists returns True when queue exists"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.queue_exists("test_queue")
            
            assert result is True
            mock_queue_client.get_queue_properties.assert_called_once()
    
    asyncio.run(_run())


def test_async_queue_exists_false():
    """Test queue_exists returns False when queue not found"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_queue_client.get_queue_properties.side_effect = ResourceNotFoundError(
                "Not found"
            )
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.queue_exists("test_queue")
            
            assert result is False
    
    asyncio.run(_run())


def test_async_list_queues_success():
    """Test list_queues returns list of queues"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            
            mock_queue1 = MagicMock()
            mock_queue1.name = "queue1"
            mock_queue1.metadata = {"env": "test"}
            
            mock_queue2 = MagicMock()
            mock_queue2.name = "queue2"
            mock_queue2.metadata = None
            
            async def async_list_queues(*args, **kwargs):
                for q in [mock_queue1, mock_queue2]:
                    yield q
            
            mock_service.list_queues.return_value = async_list_queues()
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.list_queues()
            
            assert len(result) == 2
            assert result[0]["name"] == "queue1"
            assert result[0]["metadata"] == {"env": "test"}
    
    asyncio.run(_run())


def test_async_send_message_string():
    """Test send_message with string content"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            
            mock_result = MagicMock()
            mock_result.id = "msg_id_1"
            mock_result.pop_receipt = "receipt_1"
            mock_result.inserted_on = "2024-01-01T00:00:00"
            mock_result.expires_on = "2024-01-08T00:00:00"
            mock_result.next_visible_on = "2024-01-01T00:10:00"
            
            mock_queue_client.create_queue = AsyncMock()
            mock_queue_client.send_message = AsyncMock(return_value=mock_result)
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.send_message("test_queue", "test message")
            
            assert result["message_id"] == "msg_id_1"
            mock_queue_client.send_message.assert_called_once()
    
    asyncio.run(_run())


def test_async_send_message_dict():
    """Test send_message with dict content"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            
            mock_result = MagicMock()
            mock_result.id = "msg_id_2"
            mock_result.pop_receipt = "receipt_2"
            mock_result.inserted_on = "2024-01-01T00:00:00"
            mock_result.expires_on = "2024-01-08T00:00:00"
            mock_result.next_visible_on = "2024-01-01T00:10:00"
            
            mock_queue_client.send_message = AsyncMock(return_value=mock_result)
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            msg_dict = {"key": "value", "number": 42}
            result = await helper.send_message("test_queue", msg_dict)
            
            assert result["message_id"] == "msg_id_2"
            call_args = mock_queue_client.send_message.call_args
            assert json.loads(call_args[0][0]) == msg_dict
    
    asyncio.run(_run())


def test_async_receive_messages_success():
    """Test receive_messages returns list of messages"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
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
            
            async def async_iter():
                yield mock_msg1
            
            mock_queue_client.receive_messages = MagicMock(return_value=async_iter())
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.receive_messages("test_queue", max_messages=5)
            
            assert len(result) == 1
            assert result[0]["id"] == "msg_1"
            assert result[0]["content"] == "content 1"
    
    asyncio.run(_run())


def test_async_peek_messages_success():
    """Test peek_messages returns list of messages"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            
            mock_msg1 = MagicMock()
            mock_msg1.id = "msg_1"
            mock_msg1.content = "peeked content"
            mock_msg1.inserted_on = "2024-01-01T00:00:00"
            mock_msg1.expires_on = "2024-01-08T00:00:00"
            mock_msg1.next_visible_on = "2024-01-01T00:10:00"
            mock_msg1.dequeue_count = 0
            
            mock_queue_client.peek_messages = AsyncMock(return_value=[mock_msg1])
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.peek_messages("test_queue", max_messages=1)
            
            assert len(result) == 1
            assert result[0]["content"] == "peeked content"
    
    asyncio.run(_run())


def test_async_delete_message_success():
    """Test delete_message returns True on success"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.delete_message("test_queue", "msg_id", "receipt")
            
            assert result is True
            mock_queue_client.delete_message.assert_called_once()
    
    asyncio.run(_run())


def test_async_send_messages_batch_success():
    """Test send_messages_batch sends all messages"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            
            mock_result = MagicMock()
            mock_result.id = "msg_id"
            mock_result.pop_receipt = "receipt"
            mock_result.inserted_on = "2024-01-01T00:00:00"
            mock_result.expires_on = "2024-01-08T00:00:00"
            mock_result.next_visible_on = "2024-01-01T00:10:00"
            
            mock_queue_client.send_message = AsyncMock(return_value=mock_result)
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            messages = ["msg1", "msg2", "msg3"]
            result = await helper.send_messages_batch("test_queue", messages)
            
            assert len(result) == 3
            assert all("message_id" in r for r in result)
    
    asyncio.run(_run())


def test_async_send_messages_batch_with_failures():
    """Test send_messages_batch handles failures gracefully"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            
            mock_result = MagicMock()
            mock_result.id = "msg_id"
            mock_result.pop_receipt = "receipt"
            mock_result.inserted_on = "2024-01-01T00:00:00"
            mock_result.expires_on = "2024-01-08T00:00:00"
            mock_result.next_visible_on = "2024-01-01T00:10:00"
            
            mock_queue_client.send_message = AsyncMock(side_effect=[
                mock_result,
                Exception("Send failed"),
                mock_result,
            ])
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            messages = ["msg1", "msg2", "msg3"]
            result = await helper.send_messages_batch("test_queue", messages)
            
            # Only successful messages are returned, failed ones are logged
            assert len(result) == 2
            assert all("message_id" in r for r in result)
    
    asyncio.run(_run())


def test_async_process_messages_batch_success():
    """Test process_messages_batch with successful processing"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
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
            
            async def async_iter():
                yield mock_msg
            
            mock_queue_client.receive_messages = MagicMock(return_value=async_iter())
            mock_queue_client.delete_message = AsyncMock()
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            async def processor(msg):
                return {"success": True, "processed": msg["id"]}
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.process_messages_batch("test_queue", processor, delete_after_processing=True)
            
            assert len(result) == 1
            assert result[0]["success"] is True
            assert result[0]["message_id"] == "msg_1"
            mock_queue_client.delete_message.assert_called_once()
    
    asyncio.run(_run())


def test_async_get_queue_properties():
    """Test get_queue_properties returns queue properties"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            
            mock_props = MagicMock()
            mock_props.metadata = {"env": "test"}
            mock_props.approximate_message_count = 42
            
            mock_queue_client.get_queue_properties = AsyncMock(return_value=mock_props)
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.get_queue_properties("test_queue")
            
            assert result["name"] == "test_queue"
            assert result["metadata"] == {"env": "test"}
            assert result["approximate_message_count"] == 42
    
    asyncio.run(_run())


def test_async_set_queue_metadata():
    """Test set_queue_metadata returns True on success"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.set_queue_metadata("test_queue", {"key": "value"})
            
            assert result is True
            mock_queue_client.set_queue_metadata.assert_called_once()
    
    asyncio.run(_run())


def test_async_client_not_initialized_raises_error():
    """Test accessing queue_service_client without initialization raises RuntimeError"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient"):
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            
            try:
                _ = helper.queue_service_client
                assert False, "Should have raised RuntimeError"
            except RuntimeError as e:
                assert "Client not initialized" in str(e)
    
    asyncio.run(_run())


def test_async_close_client():
    """Test close method closes the client"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = AsyncMock()
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            await helper.close()
            
            mock_service.close.assert_called_once()
    
    asyncio.run(_run())


def test_async_receive_message_single():
    """Test receive_message returns single message"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = MagicMock()
            
            mock_msg = MagicMock()
            mock_msg.id = "msg_1"
            mock_msg.pop_receipt = "receipt_1"
            mock_msg.content = "content"
            mock_msg.inserted_on = "2024-01-01T00:00:00"
            mock_msg.expires_on = "2024-01-08T00:00:00"
            mock_msg.next_visible_on = "2024-01-01T00:10:00"
            mock_msg.dequeue_count = 0
            
            async def async_iter():
                yield mock_msg
            
            mock_queue_client.receive_messages = MagicMock(return_value=async_iter())
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.receive_message("test_queue")
            
            assert result is not None
            assert result["id"] == "msg_1"
            assert result["content"] == "content"
    
    asyncio.run(_run())


def test_async_receive_message_empty():
    """Test receive_message returns None when no messages"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = MagicMock()
            
            async def async_iter():
                return
                yield
            
            mock_queue_client.receive_messages = MagicMock(return_value=async_iter())
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.receive_message("test_queue")
            
            assert result is None
    
    asyncio.run(_run())


def test_async_update_message():
    """Test update_message with new content"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            
            mock_result = MagicMock()
            mock_result.pop_receipt = "new_receipt"
            mock_result.next_visible_on = "2024-01-01T00:10:00"
            
            mock_queue_client.update_message = AsyncMock(return_value=mock_result)
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.update_message(
                "test_queue",
                "msg_id",
                "receipt",
                content="updated",
            )
            
            assert result["pop_receipt"] == "new_receipt"
    
    asyncio.run(_run())


def test_async_clear_queue():
    """Test clear_queue returns True on success"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.clear_queue("test_queue")
            
            assert result is True
            mock_queue_client.clear_messages.assert_called_once()
    
    asyncio.run(_run())


def test_async_peek_messages_success():
    """Test peek_messages returns list"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            
            mock_msg = MagicMock()
            mock_msg.id = "msg_1"
            mock_msg.content = "content"
            mock_msg.inserted_on = "2024-01-01T00:00:00"
            mock_msg.expires_on = "2024-01-08T00:00:00"
            mock_msg.next_visible_on = "2024-01-01T00:10:00"
            
            mock_queue_client.peek_messages = AsyncMock(return_value=[mock_msg])
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            result = await helper.peek_messages("test_queue")
            
            assert len(result) == 1
            assert result[0]["id"] == "msg_1"
    
    asyncio.run(_run())


def test_async_send_message_error():
    """Test send_message error handling"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_queue_client.send_message = AsyncMock(side_effect=Exception("Send error"))
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            
            try:
                await helper.send_message("test_queue", "message")
                assert False, "Should raise exception"
            except Exception as e:
                assert "Send error" in str(e)
    
    asyncio.run(_run())


def test_async_create_queue_error():
    """Test create_queue error handling"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_queue_client.create_queue = AsyncMock(side_effect=Exception("Create error"))
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            
            try:
                await helper.create_queue("test_queue")
                assert False, "Should raise exception"
            except Exception as e:
                assert "Create error" in str(e)
    
    asyncio.run(_run())


def test_async_delete_queue_error():
    """Test delete_queue error handling"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_queue_client.delete_queue = AsyncMock(side_effect=Exception("Delete error"))
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            
            try:
                await helper.delete_queue("test_queue")
                assert False, "Should raise exception"
            except Exception as e:
                assert "Delete error" in str(e)
    
    asyncio.run(_run())


def test_async_queue_exists_error():
    """Test queue_exists error handling"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_queue_client.get_queue_properties = AsyncMock(side_effect=Exception("Props error"))
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            
            try:
                await helper.queue_exists("test_queue")
                assert False, "Should raise exception"
            except Exception as e:
                assert "Props error" in str(e)
    
    asyncio.run(_run())


def test_async_receive_messages_error():
    """Test receive_messages error handling"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = MagicMock()
            
            async def async_iter():
                raise Exception("Receive error")
                yield
            
            mock_queue_client.receive_messages = MagicMock(return_value=async_iter())
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            
            try:
                await helper.receive_messages("test_queue")
                assert False, "Should raise exception"
            except Exception as e:
                assert "Receive error" in str(e)
    
    asyncio.run(_run())


def test_async_delete_message_error():
    """Test delete_message error handling"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_queue_client.delete_message = AsyncMock(side_effect=Exception("Delete error"))
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            
            try:
                await helper.delete_message("test_queue", "msg_id", "receipt")
                assert False, "Should raise exception"
            except Exception as e:
                assert "Delete error" in str(e)
    
    asyncio.run(_run())


def test_async_update_message_error():
    """Test update_message error handling"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_queue_client.update_message = AsyncMock(side_effect=Exception("Update error"))
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            
            try:
                await helper.update_message("test_queue", "msg_id", "receipt", "new content")
                assert False, "Should raise exception"
            except Exception as e:
                assert "Update error" in str(e)
    
    asyncio.run(_run())


def test_async_clear_queue_error():
    """Test clear_queue error handling"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_queue_client.clear_messages = AsyncMock(side_effect=Exception("Clear error"))
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            
            try:
                await helper.clear_queue("test_queue")
                assert False, "Should raise exception"
            except Exception as e:
                assert "Clear error" in str(e)
    
    asyncio.run(_run())


def test_async_peek_messages_error():
    """Test peek_messages error handling"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_queue_client.peek_messages = AsyncMock(side_effect=Exception("Peek error"))
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            
            try:
                await helper.peek_messages("test_queue")
                assert False, "Should raise exception"
            except Exception as e:
                assert "Peek error" in str(e)
    
    asyncio.run(_run())


def test_async_get_queue_properties_error():
    """Test get_queue_properties error handling"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_queue_client.get_queue_properties = AsyncMock(side_effect=Exception("Props error"))
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            
            try:
                await helper.get_queue_properties("test_queue")
                assert False, "Should raise exception"
            except Exception as e:
                assert "Props error" in str(e)
    
    asyncio.run(_run())


def test_async_set_queue_metadata_error():
    """Test set_queue_metadata error handling"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = AsyncMock()
            mock_queue_client.set_queue_metadata = AsyncMock(side_effect=Exception("Metadata error"))
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            
            try:
                await helper.set_queue_metadata("test_queue", {"key": "value"})
                assert False, "Should raise exception"
            except Exception as e:
                assert "Metadata error" in str(e)
    
    asyncio.run(_run())


def test_async_receive_message_error():
    """Test receive_message error handling"""
    async def _run():
        with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as mock_queue_service:
            mock_service = MagicMock()
            mock_queue_client = MagicMock()
            
            async def async_iter():
                raise Exception("Receive error")
                yield
            
            mock_queue_client.receive_messages = MagicMock(return_value=async_iter())
            mock_service.get_queue_client.return_value = mock_queue_client
            mock_queue_service.from_connection_string.return_value = mock_service
            
            helper = AsyncStorageQueueHelper(connection_string="test_conn")
            await helper._initialize_client()
            
            try:
                await helper.receive_message("test_queue")
                assert False, "Should raise exception"
            except Exception as e:
                assert "Receive error" in str(e)
    
    asyncio.run(_run())
