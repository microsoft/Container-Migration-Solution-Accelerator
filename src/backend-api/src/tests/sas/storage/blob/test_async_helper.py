"""Tests for libs/sas/storage/blob/async_helper.py."""

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
def blob_service_mock():
    with patch(
        "libs.sas.storage.blob.async_helper.BlobServiceClient"
    ) as svc_cls:
        yield svc_cls


def _wire(svc_cls):
    """Wire BlobServiceClient -> container_client -> blob_client."""
    svc_instance = MagicMock()
    svc_cls.from_connection_string.return_value = svc_instance
    svc_cls.return_value = svc_instance
    svc_instance.close = AsyncMock()

    container_client = MagicMock()
    container_client.create_container = AsyncMock()
    container_client.delete_container = AsyncMock()
    container_client.get_container_properties = AsyncMock()
    blob_client = MagicMock()
    blob_client.upload_blob = AsyncMock(return_value={"etag": "e"})
    blob_client.download_blob = AsyncMock()
    blob_client.delete_blob = AsyncMock()
    blob_client.get_blob_properties = AsyncMock()
    blob_client.set_blob_metadata = AsyncMock()
    container_client.get_blob_client.return_value = blob_client
    svc_instance.get_container_client.return_value = container_client
    return svc_instance, container_client, blob_client


def _blob_obj(name="f.txt", metadata=None):
    b = MagicMock()
    b.name = name
    b.size = 5
    b.last_modified = None
    b.etag = "e"
    b.content_settings = None
    b.blob_tier = None
    b.blob_type = None
    b.metadata = metadata or {}
    return b


class TestInit:
    @pytest.mark.asyncio
    async def test_async_with_init_and_close(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        svc, _, _ = _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert h._blob_service_client is svc
        svc.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_init_with_account_and_credential(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(
            account_name="acct", credential=MagicMock()
        ):
            pass
        blob_service_mock.assert_called()

    @pytest.mark.asyncio
    async def test_init_with_account_only(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        with patch(
            "libs.sas.storage.blob.async_helper.DefaultAzureCredential"
        ) as cred:
            async with AsyncStorageBlobHelper(account_name="acct"):
                pass
            cred.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_no_args_raises(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        h = AsyncStorageBlobHelper()
        with pytest.raises(ValueError):
            await h._initialize_client()

    @pytest.mark.asyncio
    async def test_init_failure_propagates(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        blob_service_mock.from_connection_string.side_effect = RuntimeError("x")
        h = AsyncStorageBlobHelper(connection_string="c")
        with pytest.raises(RuntimeError):
            await h._initialize_client()

    @pytest.mark.asyncio
    async def test_property_raises_when_uninitialized(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        h = AsyncStorageBlobHelper(connection_string="c")
        with pytest.raises(RuntimeError):
            _ = h.blob_service_client

    def test_init_with_dict_config(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        with patch(
            "libs.sas.storage.blob.async_helper.create_config"
        ) as cc:
            cc.return_value = {"logging_level": "INFO"}
            AsyncStorageBlobHelper(connection_string="c", config={"x": 1})
            cc.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_client_noop(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        h = AsyncStorageBlobHelper(connection_string="c")
        await h.close()


class TestContainerOps:
    @pytest.mark.asyncio
    async def test_create_container(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.create_container("c") is True

    @pytest.mark.asyncio
    async def test_create_container_exists(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, cc, _ = _wire(blob_service_mock)
        cc.create_container.side_effect = ResourceExistsError("e")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.create_container("c") is False

    @pytest.mark.asyncio
    async def test_create_container_error(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, cc, _ = _wire(blob_service_mock)
        cc.create_container.side_effect = RuntimeError("x")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.create_container("c")

    @pytest.mark.asyncio
    async def test_delete_container_empty(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, cc, _ = _wire(blob_service_mock)
        cc.list_blobs = MagicMock(return_value=_AsyncIter([]))
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.delete_container("c") is True

    @pytest.mark.asyncio
    async def test_delete_container_nonempty_no_force(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, cc, _ = _wire(blob_service_mock)
        cc.list_blobs = MagicMock(return_value=_AsyncIter([_blob_obj("x")]))
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(ValueError):
                await h.delete_container("c")

    @pytest.mark.asyncio
    async def test_delete_container_force(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, cc, _ = _wire(blob_service_mock)
        # call 1: check empty (force=True; first list_blobs)
        # call 2: iterate blobs to delete
        cc.list_blobs = MagicMock(
            side_effect=[_AsyncIter([_blob_obj("x")]), _AsyncIter([_blob_obj("x")])]
        )
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.delete_container("c", force_delete=True) is True

    @pytest.mark.asyncio
    async def test_delete_container_not_found(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, cc, _ = _wire(blob_service_mock)
        cc.list_blobs = MagicMock(return_value=_AsyncIter([]))
        cc.delete_container.side_effect = ResourceNotFoundError("nf")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.delete_container("c") is False

    @pytest.mark.asyncio
    async def test_container_exists_true(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.container_exists("c") is True

    @pytest.mark.asyncio
    async def test_container_exists_false(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, cc, _ = _wire(blob_service_mock)
        cc.get_container_properties.side_effect = ResourceNotFoundError("nf")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.container_exists("c") is False

    @pytest.mark.asyncio
    async def test_container_exists_other_error(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, cc, _ = _wire(blob_service_mock)
        cc.get_container_properties.side_effect = RuntimeError("x")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.container_exists("c")

    @pytest.mark.asyncio
    async def test_list_containers(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        svc, _, _ = _wire(blob_service_mock)
        c = MagicMock()
        c.name = "x"
        c.last_modified = None
        c.metadata = {"k": "v"}
        c.lease = None
        c.public_access = None
        svc.list_containers = MagicMock(return_value=_AsyncIter([c]))
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            result = await h.list_containers()
        assert result[0]["name"] == "x"

    @pytest.mark.asyncio
    async def test_list_containers_error(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        svc, _, _ = _wire(blob_service_mock)
        svc.list_containers = MagicMock(side_effect=RuntimeError("x"))
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.list_containers()


class TestBlobOps:
    @pytest.mark.asyncio
    async def test_upload_blob_bytes(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            await h.upload_blob("c", "f.txt", b"x")
        bc.upload_blob.assert_awaited()

    @pytest.mark.asyncio
    async def test_upload_blob_string_converts(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, _ = _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            await h.upload_blob("c", "f.txt", "hi", content_type="text/plain")

    @pytest.mark.asyncio
    async def test_upload_blob_error(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)
        bc.upload_blob.side_effect = RuntimeError("x")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.upload_blob("c", "f.txt", b"x")

    @pytest.mark.asyncio
    async def test_download_blob(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)
        stream = MagicMock()
        stream.readall = AsyncMock(return_value=b"data")
        bc.download_blob.return_value = stream
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.download_blob("c", "f") == b"data"

    @pytest.mark.asyncio
    async def test_download_blob_error(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)
        bc.download_blob.side_effect = RuntimeError("x")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.download_blob("c", "f")

    @pytest.mark.asyncio
    async def test_download_blob_to_file(self, blob_service_mock, tmp_path):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)
        stream = MagicMock()
        stream.readall = AsyncMock(return_value=b"abc")
        bc.download_blob.return_value = stream
        out = tmp_path / "x.bin"
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.download_blob_to_file("c", "f", str(out)) is True
        assert out.read_bytes() == b"abc"

    @pytest.mark.asyncio
    async def test_download_blob_to_file_error(self, blob_service_mock, tmp_path):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)
        bc.download_blob.side_effect = RuntimeError("x")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.download_blob_to_file("c", "f", str(tmp_path / "x"))

    @pytest.mark.asyncio
    async def test_upload_blob_from_text(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            await h.upload_blob_from_text("c", "f", "hello")

    @pytest.mark.asyncio
    async def test_upload_blob_from_text_error(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)
        bc.upload_blob.side_effect = RuntimeError("x")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.upload_blob_from_text("c", "f", "hi")

    @pytest.mark.asyncio
    async def test_upload_file(self, blob_service_mock, tmp_path):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        f = tmp_path / "src.txt"
        f.write_text("hello")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.upload_file("c", "f.txt", str(f)) is True

    @pytest.mark.asyncio
    async def test_upload_file_error(self, blob_service_mock, tmp_path):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)
        bc.upload_blob.side_effect = RuntimeError("x")
        f = tmp_path / "src.txt"
        f.write_text("a")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.upload_file("c", "f.txt", str(f))

    @pytest.mark.asyncio
    async def test_download_file(self, blob_service_mock, tmp_path):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)

        class _Stream:
            def chunks(self):
                async def _gen():
                    for c in (b"a", b"b"):
                        yield c

                return _gen()

        bc.download_blob.return_value = _Stream()
        out = tmp_path / "sub" / "x.bin"
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.download_file("c", "f", str(out)) is True
        assert out.read_bytes() == b"ab"

    @pytest.mark.asyncio
    async def test_download_file_error(self, blob_service_mock, tmp_path):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)
        bc.download_blob.side_effect = RuntimeError("x")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.download_file("c", "f", str(tmp_path / "x"))

    @pytest.mark.asyncio
    async def test_blob_exists_true(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.blob_exists("c", "f") is True

    @pytest.mark.asyncio
    async def test_blob_exists_false(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)
        bc.get_blob_properties.side_effect = ResourceNotFoundError("nf")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.blob_exists("c", "f") is False

    @pytest.mark.asyncio
    async def test_blob_exists_error(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)
        bc.get_blob_properties.side_effect = RuntimeError("x")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.blob_exists("c", "f")

    @pytest.mark.asyncio
    async def test_delete_blob(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.delete_blob("c", "f") is True

    @pytest.mark.asyncio
    async def test_delete_blob_not_found(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)
        bc.delete_blob.side_effect = ResourceNotFoundError("nf")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.delete_blob("c", "f") is False

    @pytest.mark.asyncio
    async def test_delete_blob_error(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)
        bc.delete_blob.side_effect = RuntimeError("x")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.delete_blob("c", "f")

    @pytest.mark.asyncio
    async def test_list_blobs(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, cc, _ = _wire(blob_service_mock)
        cc.list_blobs = MagicMock(
            return_value=_AsyncIter([_blob_obj("a.txt", {"k": "v"})])
        )
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            result = await h.list_blobs("c", include_metadata=True)
        assert result[0]["name"] == "a.txt"

    @pytest.mark.asyncio
    async def test_list_blobs_error(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, cc, _ = _wire(blob_service_mock)
        cc.list_blobs = MagicMock(side_effect=RuntimeError("x"))
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.list_blobs("c")


class TestPropsAndSearch:
    @pytest.mark.asyncio
    async def test_get_blob_properties(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)
        props = MagicMock()
        props.size = 1
        props.last_modified = None
        props.etag = "e"
        props.content_settings = None
        props.metadata = {}
        props.blob_tier = None
        props.blob_type = "BlockBlob"
        props.lease = None
        props.creation_time = None
        bc.get_blob_properties.return_value = props
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            result = await h.get_blob_properties("c", "f")
        assert result["size"] == 1

    @pytest.mark.asyncio
    async def test_get_blob_properties_error(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)
        bc.get_blob_properties.side_effect = RuntimeError("x")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.get_blob_properties("c", "f")

    @pytest.mark.asyncio
    async def test_set_blob_metadata(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            assert await h.set_blob_metadata("c", "f", {"k": "v"}) is True

    @pytest.mark.asyncio
    async def test_set_blob_metadata_error(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _, _, bc = _wire(blob_service_mock)
        bc.set_blob_metadata.side_effect = RuntimeError("x")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            with pytest.raises(RuntimeError):
                await h.set_blob_metadata("c", "f", {})

    @pytest.mark.asyncio
    async def test_search_blobs_by_name(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            h.list_blobs = AsyncMock(
                return_value=[
                    {"name": "alpha.txt", "metadata": {"tag": "x"}},
                    {"name": "beta.txt", "metadata": {"tag": "alpha"}},
                ]
            )
            result = await h.search_blobs("c", "alpha", search_in_metadata=True)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_search_blobs_case_sensitive_no_match(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            h.list_blobs = AsyncMock(
                return_value=[{"name": "ALPHA.txt", "metadata": {}}]
            )
            result = await h.search_blobs("c", "alpha", case_sensitive=True)
        assert result == []

    @pytest.mark.asyncio
    async def test_search_blobs_error(self, blob_service_mock):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            h.list_blobs = AsyncMock(side_effect=RuntimeError("x"))
            with pytest.raises(RuntimeError):
                await h.search_blobs("c", "x")


class TestBatch:
    @pytest.mark.asyncio
    async def test_upload_multiple_files(self, blob_service_mock, tmp_path):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        f = tmp_path / "a.txt"
        f.write_text("x")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            h.upload_file = AsyncMock(return_value=True)
            results = await h.upload_multiple_files("c", [str(f)])
        assert results[str(f)] is True

    @pytest.mark.asyncio
    async def test_upload_multiple_files_with_failure(self, blob_service_mock, tmp_path):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        f = tmp_path / "a.txt"
        f.write_text("x")
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            h.upload_file = AsyncMock(side_effect=RuntimeError("x"))
            results = await h.upload_multiple_files("c", [str(f)])
        assert results[str(f)] is False

    @pytest.mark.asyncio
    async def test_download_multiple_blobs(self, blob_service_mock, tmp_path):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            h.download_file = AsyncMock(return_value=True)
            results = await h.download_multiple_blobs(
                "c", ["a.txt"], str(tmp_path)
            )
        assert results["a.txt"] is True

    @pytest.mark.asyncio
    async def test_download_multiple_blobs_failure(self, blob_service_mock, tmp_path):
        from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper

        _wire(blob_service_mock)
        async with AsyncStorageBlobHelper(connection_string="c") as h:
            h.download_file = AsyncMock(side_effect=RuntimeError("x"))
            results = await h.download_multiple_blobs(
                "c", ["a.txt"], str(tmp_path)
            )
        assert results["a.txt"] is False
