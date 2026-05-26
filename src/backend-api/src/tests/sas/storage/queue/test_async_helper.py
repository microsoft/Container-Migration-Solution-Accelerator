"""Tests for libs/sas/storage/queue/async_helper.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError


class _AsyncIter:
    def __init__(self, items):
        self._items = list(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


@pytest.fixture
def queue_service_mock():
    with patch("libs.sas.storage.queue.async_helper.QueueServiceClient") as svc_cls:
        yield svc_cls


def _make_message(
    id="m1", pop_receipt="pr", content="c", inserted_on=None, expires_on=None,
    next_visible_on=None, dequeue_count=0,
):
    m = MagicMock()
    m.id = id
    m.pop_receipt = pop_receipt
    m.content = content
    m.inserted_on = inserted_on
    m.expires_on = expires_on
    m.next_visible_on = next_visible_on
    m.dequeue_count = dequeue_count
    return m


def _wire_qc(svc_cls):
    """Wire QueueServiceClient -> queue_client mock with AsyncMock'd methods."""
    svc_instance = MagicMock()
    svc_cls.from_connection_string.return_value = svc_instance
    svc_cls.return_value = svc_instance
    svc_instance.close = AsyncMock()

    qc = MagicMock()
    qc.create_queue = AsyncMock()
    qc.delete_queue = AsyncMock()
    qc.get_queue_properties = AsyncMock()
    qc.send_message = AsyncMock()
    qc.delete_message = AsyncMock()
    qc.update_message = AsyncMock()
    qc.set_queue_metadata = AsyncMock()
    qc.clear_messages = AsyncMock()
    qc.peek_messages = AsyncMock()
    svc_instance.get_queue_client.return_value = qc
    return svc_instance, qc


async def _make_helper(queue_service_mock):
    from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

    return AsyncStorageQueueHelper(connection_string="conn-str")


class TestInitAndContext:
    @pytest.mark.asyncio
    async def test_async_with_initializes_and_closes(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        svc_instance, _ = _wire_qc(queue_service_mock)
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            assert h._queue_service_client is svc_instance
        svc_instance.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_init_with_account_and_credential(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        svc_instance, _ = _wire_qc(queue_service_mock)
        async with AsyncStorageQueueHelper(
            account_name="acct", credential=MagicMock()
        ):
            pass
        queue_service_mock.assert_called()

    @pytest.mark.asyncio
    async def test_init_with_account_only_uses_default_credential(
        self, queue_service_mock
    ):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        svc_instance, _ = _wire_qc(queue_service_mock)
        with patch(
            "libs.sas.storage.queue.async_helper.DefaultAzureCredential"
        ) as cred:
            async with AsyncStorageQueueHelper(account_name="acct"):
                pass
            cred.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_no_args_raises(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        h = AsyncStorageQueueHelper()
        with pytest.raises(ValueError):
            await h._initialize_client()

    @pytest.mark.asyncio
    async def test_init_failure_propagates(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        queue_service_mock.from_connection_string.side_effect = RuntimeError("boom")
        h = AsyncStorageQueueHelper(connection_string="c")
        with pytest.raises(RuntimeError):
            await h._initialize_client()

    @pytest.mark.asyncio
    async def test_property_raises_when_uninitialized(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        h = AsyncStorageQueueHelper(connection_string="c")
        with pytest.raises(RuntimeError):
            _ = h.queue_service_client

    def test_init_with_dict_config(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        h = AsyncStorageQueueHelper(connection_string="c", config={"logging_level": "INFO"})
        assert h.config == {"logging_level": "INFO"}


class TestQueueOps:
    @pytest.mark.asyncio
    async def test_create_queue_success(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _wire_qc(queue_service_mock)
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            assert await h.create_queue("q") is True

    @pytest.mark.asyncio
    async def test_create_queue_already_exists(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.create_queue.side_effect = ResourceExistsError("e")
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            assert await h.create_queue("q") is False

    @pytest.mark.asyncio
    async def test_create_queue_other_error(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.create_queue.side_effect = RuntimeError("x")
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.create_queue("q")

    @pytest.mark.asyncio
    async def test_delete_queue_success(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _wire_qc(queue_service_mock)
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            assert await h.delete_queue("q") is True

    @pytest.mark.asyncio
    async def test_delete_queue_not_found(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.delete_queue.side_effect = ResourceNotFoundError("nf")
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            assert await h.delete_queue("q") is False

    @pytest.mark.asyncio
    async def test_delete_queue_error(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.delete_queue.side_effect = RuntimeError("x")
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.delete_queue("q")

    @pytest.mark.asyncio
    async def test_queue_exists_true(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _wire_qc(queue_service_mock)
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            assert await h.queue_exists("q") is True

    @pytest.mark.asyncio
    async def test_queue_exists_false(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.get_queue_properties.side_effect = ResourceNotFoundError("nf")
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            assert await h.queue_exists("q") is False

    @pytest.mark.asyncio
    async def test_queue_exists_error(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.get_queue_properties.side_effect = RuntimeError("x")
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.queue_exists("q")

    @pytest.mark.asyncio
    async def test_list_queues(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        svc_instance, _ = _wire_qc(queue_service_mock)
        q = MagicMock()
        q.name = "x"
        q.metadata = {"k": "v"}
        svc_instance.list_queues = MagicMock(return_value=_AsyncIter([q]))
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            result = await h.list_queues()
        assert result[0]["name"] == "x"

    @pytest.mark.asyncio
    async def test_list_queues_error(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        svc_instance, _ = _wire_qc(queue_service_mock)

        def boom(**kw):
            raise RuntimeError("x")

        svc_instance.list_queues = MagicMock(side_effect=boom)
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.list_queues()


class TestMessageOps:
    @pytest.mark.asyncio
    async def test_send_message_dict(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.send_message.return_value = _make_message()
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            info = await h.send_message("q", {"k": "v"})
        assert info["message_id"] == "m1"

    @pytest.mark.asyncio
    async def test_send_message_string(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.send_message.return_value = _make_message()
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            await h.send_message("q", "hi")

    @pytest.mark.asyncio
    async def test_send_message_other_type(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.send_message.return_value = _make_message()
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            await h.send_message("q", 123)

    @pytest.mark.asyncio
    async def test_send_message_error(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.send_message.side_effect = RuntimeError("x")
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.send_message("q", "hi")

    @pytest.mark.asyncio
    async def test_receive_message_returns_one(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.receive_messages = MagicMock(return_value=_AsyncIter([_make_message()]))
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            msg = await h.receive_message("q")
        assert msg["id"] == "m1"

    @pytest.mark.asyncio
    async def test_receive_message_returns_none_when_empty(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.receive_messages = MagicMock(return_value=_AsyncIter([]))
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            assert await h.receive_message("q") is None

    @pytest.mark.asyncio
    async def test_receive_message_error(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.receive_messages = MagicMock(side_effect=RuntimeError("x"))
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.receive_message("q")

    @pytest.mark.asyncio
    async def test_receive_messages(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.receive_messages = MagicMock(
            return_value=_AsyncIter([_make_message(), _make_message("m2")])
        )
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            msgs = await h.receive_messages("q", max_messages=2)
        assert len(msgs) == 2

    @pytest.mark.asyncio
    async def test_receive_messages_error(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.receive_messages = MagicMock(side_effect=RuntimeError("x"))
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.receive_messages("q")

    @pytest.mark.asyncio
    async def test_delete_message(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _wire_qc(queue_service_mock)
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            assert await h.delete_message("q", "id", "pr") is True

    @pytest.mark.asyncio
    async def test_delete_message_error(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.delete_message.side_effect = RuntimeError("x")
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.delete_message("q", "id", "pr")

    @pytest.mark.asyncio
    async def test_update_message_dict(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.update_message.return_value = _make_message()
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            info = await h.update_message("q", "id", "pr", {"k": "v"})
        assert info["pop_receipt"] == "pr"

    @pytest.mark.asyncio
    async def test_update_message_string(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.update_message.return_value = _make_message()
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            await h.update_message("q", "id", "pr", "hi")

    @pytest.mark.asyncio
    async def test_update_message_other_type(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.update_message.return_value = _make_message()
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            await h.update_message("q", "id", "pr", 99)

    @pytest.mark.asyncio
    async def test_update_message_error(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.update_message.side_effect = RuntimeError("x")
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.update_message("q", "id", "pr", "hi")


class TestBatch:
    @pytest.mark.asyncio
    async def test_send_messages_batch(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.send_message.return_value = _make_message()
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            results = await h.send_messages_batch("q", ["a", "b"])
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_send_messages_batch_filters_failures(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.send_message.side_effect = [_make_message(), RuntimeError("x")]
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            results = await h.send_messages_batch("q", ["a", "b"])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_process_messages_batch_success(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.receive_messages = MagicMock(return_value=_AsyncIter([_make_message()]))

        async def proc(_msg):
            return "ok"

        async with AsyncStorageQueueHelper(connection_string="c") as h:
            results = await h.process_messages_batch("q", proc)
        assert results[0]["success"] is True

    @pytest.mark.asyncio
    async def test_process_messages_batch_no_messages(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.receive_messages = MagicMock(return_value=_AsyncIter([]))

        async def proc(_msg):
            return "ok"

        async with AsyncStorageQueueHelper(connection_string="c") as h:
            results = await h.process_messages_batch("q", proc)
        assert results == []

    @pytest.mark.asyncio
    async def test_process_messages_batch_processor_fails(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.receive_messages = MagicMock(return_value=_AsyncIter([_make_message()]))

        async def proc(_msg):
            raise RuntimeError("nope")

        async with AsyncStorageQueueHelper(connection_string="c") as h:
            results = await h.process_messages_batch("q", proc)
        assert results[0]["success"] is False


class TestPropsAndMisc:
    @pytest.mark.asyncio
    async def test_get_queue_properties(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        props = MagicMock()
        props.metadata = {"k": "v"}
        props.approximate_message_count = 5
        qc.get_queue_properties.return_value = props
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            result = await h.get_queue_properties("q")
        assert result["approximate_message_count"] == 5

    @pytest.mark.asyncio
    async def test_get_queue_properties_error(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.get_queue_properties.side_effect = RuntimeError("x")
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.get_queue_properties("q")

    @pytest.mark.asyncio
    async def test_set_queue_metadata(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _wire_qc(queue_service_mock)
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            assert await h.set_queue_metadata("q", {"k": "v"}) is True

    @pytest.mark.asyncio
    async def test_set_queue_metadata_error(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.set_queue_metadata.side_effect = RuntimeError("x")
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.set_queue_metadata("q", {})

    @pytest.mark.asyncio
    async def test_clear_queue(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _wire_qc(queue_service_mock)
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            assert await h.clear_queue("q") is True

    @pytest.mark.asyncio
    async def test_clear_queue_error(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.clear_messages.side_effect = RuntimeError("x")
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.clear_queue("q")

    @pytest.mark.asyncio
    async def test_peek_messages(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.peek_messages.return_value = [_make_message()]
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            result = await h.peek_messages("q")
        assert result[0]["id"] == "m1"

    @pytest.mark.asyncio
    async def test_peek_messages_error(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        _, qc = _wire_qc(queue_service_mock)
        qc.peek_messages.side_effect = RuntimeError("x")
        async with AsyncStorageQueueHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.peek_messages("q")

    @pytest.mark.asyncio
    async def test_close_no_client(self, queue_service_mock):
        from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper

        h = AsyncStorageQueueHelper(connection_string="c")
        # never initialized; close should be a no-op
        await h.close()
