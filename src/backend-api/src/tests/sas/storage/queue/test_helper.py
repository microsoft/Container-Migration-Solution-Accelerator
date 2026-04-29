"""Tests for libs/sas/storage/queue/helper.py."""

from unittest.mock import MagicMock, patch

import pytest
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError


@pytest.fixture
def queue_service_mock():
    with patch(
        "libs.sas.storage.queue.helper.QueueServiceClient"
    ) as svc_cls:
        yield svc_cls


def _make_helper(queue_service_mock, **kwargs):
    from libs.sas.storage.queue.helper import StorageQueueHelper

    helper = StorageQueueHelper(connection_string="conn-str", **kwargs)
    return helper


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


class TestInit:
    def test_init_with_connection_string(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        queue_service_mock.from_connection_string.assert_called_once()
        assert h._connection_string == "conn-str"

    def test_init_with_account_name_and_credential(self, queue_service_mock):
        from libs.sas.storage.queue.helper import StorageQueueHelper

        cred = MagicMock()
        StorageQueueHelper(account_name="acct", credential=cred)
        queue_service_mock.assert_called()

    def test_init_with_account_name_only_uses_default_credential(
        self, queue_service_mock
    ):
        from libs.sas.storage.queue.helper import StorageQueueHelper

        with patch(
            "libs.sas.storage.queue.helper.DefaultAzureCredential"
        ) as cred_cls:
            StorageQueueHelper(account_name="acct")
            cred_cls.assert_called_once()

    def test_init_no_args_raises(self, queue_service_mock):
        from libs.sas.storage.queue.helper import StorageQueueHelper

        with pytest.raises(ValueError):
            StorageQueueHelper()

    def test_init_with_dict_config(self, queue_service_mock):
        from libs.sas.storage.queue.helper import StorageQueueHelper

        with patch("libs.sas.storage.shared_config.create_config") as cc:
            cc.return_value = {"logging_level": "INFO"}
            StorageQueueHelper(connection_string="c", config={"x": 1})
            cc.assert_called_once()

    def test_init_failure_propagates(self, queue_service_mock):
        from libs.sas.storage.queue.helper import StorageQueueHelper

        queue_service_mock.from_connection_string.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            StorageQueueHelper(connection_string="c")


class TestQueueOperations:
    def test_create_queue_success(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        h.queue_service_client.get_queue_client.return_value = qc
        assert h.create_queue("q") is True

    def test_create_queue_already_exists(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.create_queue.side_effect = ResourceExistsError("exists")
        h.queue_service_client.get_queue_client.return_value = qc
        assert h.create_queue("q") is False

    def test_create_queue_other_error_raises(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.create_queue.side_effect = RuntimeError("x")
        h.queue_service_client.get_queue_client.return_value = qc
        with pytest.raises(RuntimeError):
            h.create_queue("q")

    def test_delete_queue_success(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        h.queue_service_client.get_queue_client.return_value = qc
        assert h.delete_queue("q") is True

    def test_delete_queue_not_found(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.delete_queue.side_effect = ResourceNotFoundError("nf")
        h.queue_service_client.get_queue_client.return_value = qc
        assert h.delete_queue("q") is False

    def test_delete_queue_error_raises(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.delete_queue.side_effect = RuntimeError("x")
        h.queue_service_client.get_queue_client.return_value = qc
        with pytest.raises(RuntimeError):
            h.delete_queue("q")

    def test_list_queues(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        q1 = MagicMock()
        q1.name = "a"
        q1.metadata = {"k": "v"}
        h.queue_service_client.list_queues.return_value = iter([q1])
        result = h.list_queues(include_metadata=True)
        assert result[0]["name"] == "a"
        assert result[0]["metadata"] == {"k": "v"}

    def test_list_queues_error(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        h.queue_service_client.list_queues.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            h.list_queues()

    def test_queue_exists_true(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        h.queue_service_client.get_queue_client.return_value = qc
        assert h.queue_exists("q") is True

    def test_queue_exists_false(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.get_queue_properties.side_effect = ResourceNotFoundError("nf")
        h.queue_service_client.get_queue_client.return_value = qc
        assert h.queue_exists("q") is False

    def test_queue_exists_other_error(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.get_queue_properties.side_effect = RuntimeError("x")
        h.queue_service_client.get_queue_client.return_value = qc
        with pytest.raises(RuntimeError):
            h.queue_exists("q")

    def test_clear_queue(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        h.queue_service_client.get_queue_client.return_value = qc
        assert h.clear_queue("q") is True

    def test_clear_queue_error(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.clear_messages.side_effect = RuntimeError("x")
        h.queue_service_client.get_queue_client.return_value = qc
        with pytest.raises(RuntimeError):
            h.clear_queue("q")


class TestMessageOperations:
    def test_send_message_dict(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.send_message.return_value = _make_message()
        h.queue_service_client.get_queue_client.return_value = qc
        info = h.send_message("q", {"key": "val"})
        assert info["message_id"] == "m1"

    def test_send_message_bytes(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.send_message.return_value = _make_message()
        h.queue_service_client.get_queue_client.return_value = qc
        info = h.send_message("q", b"bytes-data")
        assert info["message_id"] == "m1"

    def test_send_message_string(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.send_message.return_value = _make_message()
        h.queue_service_client.get_queue_client.return_value = qc
        h.send_message("q", "hello")
        qc.send_message.assert_called_once()

    def test_send_message_failure(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.send_message.side_effect = RuntimeError("x")
        h.queue_service_client.get_queue_client.return_value = qc
        with pytest.raises(RuntimeError):
            h.send_message("q", "msg")

    def test_receive_messages(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.receive_messages.return_value = iter([_make_message(), _make_message("m2")])
        h.queue_service_client.get_queue_client.return_value = qc
        msgs = h.receive_messages("q", max_messages=2)
        assert len(msgs) == 2
        assert msgs[0]["message_id"] == "m1"

    def test_receive_messages_error(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.receive_messages.side_effect = RuntimeError("x")
        h.queue_service_client.get_queue_client.return_value = qc
        with pytest.raises(RuntimeError):
            h.receive_messages("q")

    def test_peek_messages(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.peek_messages.return_value = iter([_make_message()])
        h.queue_service_client.get_queue_client.return_value = qc
        msgs = h.peek_messages("q")
        assert msgs[0]["message_id"] == "m1"

    def test_peek_messages_error(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.peek_messages.side_effect = RuntimeError("x")
        h.queue_service_client.get_queue_client.return_value = qc
        with pytest.raises(RuntimeError):
            h.peek_messages("q")

    def test_delete_message(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        h.queue_service_client.get_queue_client.return_value = qc
        assert h.delete_message("q", "id", "pr") is True

    def test_delete_message_error(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.delete_message.side_effect = RuntimeError("x")
        h.queue_service_client.get_queue_client.return_value = qc
        with pytest.raises(RuntimeError):
            h.delete_message("q", "id", "pr")

    def test_update_message_dict(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.update_message.return_value = _make_message()
        h.queue_service_client.get_queue_client.return_value = qc
        info = h.update_message("q", "id", "pr", {"a": 1})
        assert info["pop_receipt"] == "pr"

    def test_update_message_bytes(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.update_message.return_value = _make_message()
        h.queue_service_client.get_queue_client.return_value = qc
        h.update_message("q", "id", "pr", b"bytes")

    def test_update_message_no_content(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.update_message.return_value = _make_message()
        h.queue_service_client.get_queue_client.return_value = qc
        h.update_message("q", "id", "pr", content=None)

    def test_update_message_error(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.update_message.side_effect = RuntimeError("x")
        h.queue_service_client.get_queue_client.return_value = qc
        with pytest.raises(RuntimeError):
            h.update_message("q", "id", "pr", "msg")


class TestBatchAndProcessing:
    def test_send_multiple_messages_mixed_results(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.send_message.side_effect = [_make_message(), RuntimeError("x")]
        h.queue_service_client.get_queue_client.return_value = qc
        results = h.send_multiple_messages("q", ["a", "b"])
        assert results[0]["success"] is True
        assert results[1]["success"] is False

    def test_process_messages_success_with_delete(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.receive_messages.return_value = iter([_make_message()])
        h.queue_service_client.get_queue_client.return_value = qc
        results = h.process_messages("q", lambda m: {"success": True})
        assert results[0]["deleted"] is True

    def test_process_messages_processor_raises(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.receive_messages.return_value = iter([_make_message()])
        h.queue_service_client.get_queue_client.return_value = qc

        def boom(_):
            raise RuntimeError("nope")

        results = h.process_messages("q", boom)
        assert results[0]["processing_result"]["success"] is False

    def test_process_messages_top_level_failure(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.receive_messages.side_effect = RuntimeError("x")
        h.queue_service_client.get_queue_client.return_value = qc
        with pytest.raises(RuntimeError):
            h.process_messages("q", lambda m: {"success": True})


class TestProperties:
    def test_get_queue_properties(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        props = MagicMock()
        props.metadata = {"k": "v"}
        props.approximate_message_count = 7
        qc.get_queue_properties.return_value = props
        h.queue_service_client.get_queue_client.return_value = qc
        result = h.get_queue_properties("q")
        assert result["approximate_message_count"] == 7

    def test_get_queue_properties_error(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.get_queue_properties.side_effect = RuntimeError("x")
        h.queue_service_client.get_queue_client.return_value = qc
        with pytest.raises(RuntimeError):
            h.get_queue_properties("q")

    def test_set_queue_metadata(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        h.queue_service_client.get_queue_client.return_value = qc
        assert h.set_queue_metadata("q", {"k": "v"}) is True

    def test_set_queue_metadata_error(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.set_queue_metadata.side_effect = RuntimeError("x")
        h.queue_service_client.get_queue_client.return_value = qc
        with pytest.raises(RuntimeError):
            h.set_queue_metadata("q", {})

    def test_get_queue_statistics(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        props = MagicMock()
        props.metadata = {}
        props.approximate_message_count = 3
        qc.get_queue_properties.return_value = props
        h.queue_service_client.get_queue_client.return_value = qc
        stats = h.get_queue_statistics("q")
        assert stats["approximate_message_count"] == 3
        assert "last_updated" in stats

    def test_get_queue_statistics_error(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        qc = MagicMock()
        qc.get_queue_properties.side_effect = RuntimeError("x")
        h.queue_service_client.get_queue_client.return_value = qc
        with pytest.raises(RuntimeError):
            h.get_queue_statistics("q")


class TestUtilities:
    def test_get_queue_url(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        h.queue_service_client.account_name = "acct"
        url = h.get_queue_url("q")
        assert "acct" in url and "q" in url

    def test_get_account_name_returns_none_on_error(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        type(h.queue_service_client).account_name = property(
            lambda s: (_ for _ in ()).throw(RuntimeError("x"))
        )
        assert h._get_account_name() is None

    def test_encode_message_dict(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        out = h.encode_message({"a": 1})
        assert "a" in out

    def test_encode_message_string(self, queue_service_mock):
        h = _make_helper(queue_service_mock)
        assert h.encode_message("plain") == "plain"
