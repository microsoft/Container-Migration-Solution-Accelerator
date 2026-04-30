"""
Tests for async blob storage helper module.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError

from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper
from libs.sas.storage.blob.config import create_config


class TestAsyncStorageBlobHelperInitialization:
    """Tests for AsyncStorageBlobHelper initialization."""

    def test_init_with_connection_string(self):
        """Test initialization with connection string."""
        helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        assert helper._connection_string == "DefaultEndpointsProtocol=https;..."
        assert helper._account_name is None
        assert helper._credential is None

    def test_init_with_account_name_and_credential(self):
        """Test initialization with account name and credential."""
        mock_credential = MagicMock()
        helper = AsyncStorageBlobHelper(
            account_name="testaccount",
            credential=mock_credential
        )
        assert helper._account_name == "testaccount"
        assert helper._credential == mock_credential

    def test_init_with_account_name_only(self):
        """Test initialization with account name only."""
        helper = AsyncStorageBlobHelper(account_name="testaccount")
        assert helper._account_name == "testaccount"
        assert helper._credential is None

    def test_init_with_custom_config_dict(self):
        """Test initialization with custom config dictionary."""
        custom_config = {"logging_level": "DEBUG"}
        helper = AsyncStorageBlobHelper(
            connection_string="DefaultEndpointsProtocol=https;...",
            config=custom_config
        )
        assert helper.config.get("logging_level") == "DEBUG"

    def test_init_with_config_object(self):
        """Test initialization with config object."""
        custom_config = create_config({"logging_level": "WARNING"})
        helper = AsyncStorageBlobHelper(
            connection_string="DefaultEndpointsProtocol=https;...",
            config=custom_config
        )
        assert helper.config == custom_config

    def test_init_without_credentials(self):
        """Test initialization without any credentials."""
        helper = AsyncStorageBlobHelper()
        assert helper._connection_string is None
        assert helper._account_name is None
        assert helper._credential is None
        assert helper._blob_service_client is None


class TestAsyncInitializeClient:
    """Tests for async client initialization."""

    def test_initialize_client_with_connection_string(self):
        """Test async client initialization with connection string."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient") as mock_blob_client:
                mock_client_instance = MagicMock()
                mock_blob_client.from_connection_string.return_value = mock_client_instance
                
                helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
                await helper._initialize_client()
                
                assert helper._blob_service_client == mock_client_instance
                mock_blob_client.from_connection_string.assert_called_once()
        
        asyncio.run(_run())

    def test_initialize_client_with_account_name_and_credential(self):
        """Test async client initialization with account name and credential."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient") as mock_blob_client:
                mock_client_instance = MagicMock()
                mock_blob_client.return_value = mock_client_instance
                mock_credential = MagicMock()
                
                helper = AsyncStorageBlobHelper(
                    account_name="testaccount",
                    credential=mock_credential
                )
                await helper._initialize_client()
                
                assert helper._blob_service_client == mock_client_instance
        
        asyncio.run(_run())

    def test_initialize_client_without_credentials_raises_error(self):
        """Test async client initialization without credentials raises error."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient"):
                helper = AsyncStorageBlobHelper()
                
                with pytest.raises(ValueError, match="Either connection_string or account_name must be provided"):
                    await helper._initialize_client()
        
        asyncio.run(_run())


class TestAsyncCreateContainer:
    """Tests for async container creation."""

    def test_create_container_success(self):
        """Test successful async container creation."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient"):
                mock_container = AsyncMock()
                mock_container.create_container = AsyncMock(return_value=None)
                
                helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
                helper._blob_service_client = MagicMock()
                helper._blob_service_client.get_container_client.return_value = mock_container
                
                result = await helper.create_container("test-container")
                
                assert result is True
                mock_container.create_container.assert_called_once()
        
        asyncio.run(_run())

    def test_create_container_already_exists(self):
        """Test creating container that already exists."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient"):
                mock_container = AsyncMock()
                mock_container.create_container = AsyncMock(side_effect=ResourceExistsError("already exists"))
                
                helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
                helper._blob_service_client = MagicMock()
                helper._blob_service_client.get_container_client.return_value = mock_container
                
                result = await helper.create_container("test-container")
                
                assert result is False
        
        asyncio.run(_run())


class TestAsyncContainerExists:
    """Tests for async container exists check."""

    def test_container_exists_true(self):
        """Test checking if container exists."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient"):
                mock_container = AsyncMock()
                mock_container.get_container_properties = AsyncMock(return_value={"name": "test"})
                
                helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
                helper._blob_service_client = MagicMock()
                helper._blob_service_client.get_container_client.return_value = mock_container
                
                result = await helper.container_exists("test-container")
                
                assert result is True
        
        asyncio.run(_run())

    def test_container_exists_false(self):
        """Test checking for non-existent container."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient"):
                mock_container = AsyncMock()
                mock_container.get_container_properties = AsyncMock(side_effect=ResourceNotFoundError("not found"))
                
                helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
                helper._blob_service_client = MagicMock()
                helper._blob_service_client.get_container_client.return_value = mock_container
                
                result = await helper.container_exists("test-container")
                
                assert result is False
        
        asyncio.run(_run())


class TestAsyncBlobExists:
    """Tests for async blob exists check."""

    def test_blob_exists_true(self):
        """Test checking if blob exists."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient"):
                mock_blob = AsyncMock()
                mock_blob.get_blob_properties = AsyncMock(return_value={"size": 1024})
                mock_container = MagicMock()
                mock_container.get_blob_client.return_value = mock_blob
                
                helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
                helper._blob_service_client = MagicMock()
                helper._blob_service_client.get_container_client.return_value = mock_container
                
                result = await helper.blob_exists("container", "blob.txt")
                
                assert result is True
        
        asyncio.run(_run())

    def test_blob_exists_false(self):
        """Test checking for non-existent blob."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient"):
                mock_blob = AsyncMock()
                mock_blob.get_blob_properties = AsyncMock(side_effect=ResourceNotFoundError("not found"))
                mock_container = MagicMock()
                mock_container.get_blob_client.return_value = mock_blob
                
                helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
                helper._blob_service_client = MagicMock()
                helper._blob_service_client.get_container_client.return_value = mock_container
                
                result = await helper.blob_exists("container", "blob.txt")
                
                assert result is False
        
        asyncio.run(_run())


class TestAsyncDeleteBlob:
    """Tests for async blob deletion."""

    def test_delete_blob_success(self):
        """Test deleting blob asynchronously."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient"):
                mock_blob = AsyncMock()
                mock_blob.delete_blob = AsyncMock(return_value=None)
                mock_container = MagicMock()
                mock_container.get_blob_client.return_value = mock_blob
                
                helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
                helper._blob_service_client = MagicMock()
                helper._blob_service_client.get_container_client.return_value = mock_container
                
                result = await helper.delete_blob("container", "blob.txt")
                
                assert result is True
                mock_blob.delete_blob.assert_called_once()
        
        asyncio.run(_run())

    def test_delete_blob_not_found(self):
        """Test deleting non-existent blob."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient"):
                mock_blob = AsyncMock()
                mock_blob.delete_blob = AsyncMock(side_effect=ResourceNotFoundError("not found"))
                mock_container = MagicMock()
                mock_container.get_blob_client.return_value = mock_blob
                
                helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
                helper._blob_service_client = MagicMock()
                helper._blob_service_client.get_container_client.return_value = mock_container
                
                result = await helper.delete_blob("container", "blob.txt")
                
                assert result is False
        
        asyncio.run(_run())


class TestAsyncClose:
    """Tests for async close operation."""

    def test_close_with_client(self):
        """Test closing async client when client exists."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient"):
                mock_client = AsyncMock()
                mock_client.close = AsyncMock(return_value=None)
                
                helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
                helper._blob_service_client = mock_client
                
                await helper.close()
                
                mock_client.close.assert_called_once()
        
        asyncio.run(_run())

    def test_close_without_client(self):
        """Test closing when no client has been initialized."""
        async def _run():
            helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
            helper._blob_service_client = None
            
            # Should not raise an error
            await helper.close()
        
        asyncio.run(_run())


class TestAsyncGetBlobProperties:
    """Tests for async blob properties."""

    def test_get_blob_properties_success(self):
        """Test getting blob properties asynchronously."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient"):
                mock_properties = MagicMock()
                mock_properties.size = 1024
                mock_blob = AsyncMock()
                mock_blob.get_blob_properties = AsyncMock(return_value=mock_properties)
                mock_container = MagicMock()
                mock_container.get_blob_client.return_value = mock_blob
                
                helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
                helper._blob_service_client = MagicMock()
                helper._blob_service_client.get_container_client.return_value = mock_container
                
                result = await helper.get_blob_properties("container", "blob.txt")
                
                assert result is not None
        
        asyncio.run(_run())


class TestAsyncSetBlobMetadata:
    """Tests for async set blob metadata."""

    def test_set_blob_metadata_success(self):
        """Test setting blob metadata asynchronously."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient"):
                mock_blob = AsyncMock()
                mock_blob.set_blob_metadata = AsyncMock(return_value=None)
                mock_container = MagicMock()
                mock_container.get_blob_client.return_value = mock_blob
                
                helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
                helper._blob_service_client = MagicMock()
                helper._blob_service_client.get_container_client.return_value = mock_container
                
                result = await helper.set_blob_metadata("container", "blob.txt", {"key": "value"})
                
                assert result is True
                mock_blob.set_blob_metadata.assert_called_once()
        
        asyncio.run(_run())


class TestAsyncSearchBlobs:
    """Tests for async blob search."""

    def test_search_blobs_returns_list(self):
        """Test searching blobs returns a list."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient"):
                mock_blob_prop1 = MagicMock()
                mock_blob_prop1.name = "test_blob.txt"
                mock_blob_prop2 = MagicMock()
                mock_blob_prop2.name = "other_file.txt"
                
                mock_container = MagicMock()
                
                async def async_gen():
                    yield mock_blob_prop1
                    yield mock_blob_prop2
                
                mock_container.list_blobs.return_value = async_gen()
                
                helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
                helper._blob_service_client = MagicMock()
                helper._blob_service_client.get_container_client.return_value = mock_container
                
                result = await helper.search_blobs("container", "test")
                
                assert isinstance(result, list)
        
        asyncio.run(_run())


class TestAsyncContextManager:
    """Tests for async context manager operations."""

    def test_aenter_initializes_client(self):
        """Test __aenter__ initializes the client."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient") as mock_blob_client:
                mock_client_instance = MagicMock()
                mock_blob_client.from_connection_string.return_value = mock_client_instance
                
                helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
                result = await helper.__aenter__()
                
                assert result == helper
                assert helper._blob_service_client == mock_client_instance
        
        asyncio.run(_run())

    def test_aexit_closes_client(self):
        """Test __aexit__ closes the client."""
        async def _run():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient"):
                mock_client = AsyncMock()
                mock_client.close = AsyncMock(return_value=None)
                
                helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
                helper._blob_service_client = mock_client
                
                await helper.__aexit__(None, None, None)
                
                mock_client.close.assert_called_once()
        
        asyncio.run(_run())



# ---------------------------------------------------------------------------
# Additional coverage tests for AsyncStorageBlobHelper
# ---------------------------------------------------------------------------
import os as _os


def _async_iter(items):
    async def gen():
        for it in items:
            yield it
    return gen()


def _make_async_helper(client_mock=None):
    """Helper: create AsyncStorageBlobHelper with stubbed _blob_service_client."""
    h = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
    h._blob_service_client = client_mock or MagicMock()
    return h


def _run(coro):
    return asyncio.run(coro)


class TestAsyncInitErrors:
    def test_initialize_account_name_only(self):
        async def go():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient") as mc, \
                 patch("libs.sas.storage.blob.async_helper.DefaultAzureCredential") as md:
                mc.return_value = MagicMock()
                md.return_value = MagicMock()
                h = AsyncStorageBlobHelper(account_name="acct")
                await h._initialize_client()
                assert h._blob_service_client is not None
                md.assert_called_once()
        _run(go())

    def test_initialize_failure(self):
        async def go():
            with patch("libs.sas.storage.blob.async_helper.BlobServiceClient") as mc:
                mc.from_connection_string.side_effect = RuntimeError("boom")
                h = AsyncStorageBlobHelper(connection_string="x")
                with pytest.raises(RuntimeError):
                    await h._initialize_client()
        _run(go())

    def test_blob_service_client_property_uninit_raises(self):
        h = AsyncStorageBlobHelper(connection_string="x")
        with pytest.raises(RuntimeError):
            _ = h.blob_service_client


class TestAsyncCreateContainerErrors:
    def test_create_container_unexpected_error(self):
        async def go():
            mc = AsyncMock()
            mc.create_container = AsyncMock(side_effect=RuntimeError("err"))
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(RuntimeError):
                await h.create_container("c")
        _run(go())


class TestAsyncDeleteContainer:
    def test_delete_container_empty_then_delete(self):
        async def go():
            mc = MagicMock()
            mc.list_blobs.return_value = _async_iter([])
            mc.delete_container = AsyncMock(return_value=None)
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            assert await h.delete_container("c") is True
            mc.delete_container.assert_called_once()
        _run(go())

    def test_delete_container_with_blobs_no_force(self):
        async def go():
            b = MagicMock(); b.name = "x"
            mc = MagicMock()
            mc.list_blobs.return_value = _async_iter([b])
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(ValueError, match="not empty"):
                await h.delete_container("c", force_delete=False)
        _run(go())

    def test_delete_container_force_delete_with_blobs(self):
        async def go():
            b1 = MagicMock(); b1.name = "a"
            b2 = MagicMock(); b2.name = "b"
            # Need three calls: check, check-again, iterate-to-delete
            mc = MagicMock()
            iter_seq = [
                _async_iter([b1]),
                _async_iter([b1, b2]),
            ]
            mc.list_blobs.side_effect = iter_seq
            blob_client = AsyncMock()
            blob_client.delete_blob = AsyncMock(return_value=None)
            mc.get_blob_client.return_value = blob_client
            mc.delete_container = AsyncMock(return_value=None)
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            assert await h.delete_container("c", force_delete=True) is True
        _run(go())

    def test_delete_container_force_delete_inner_failure(self):
        async def go():
            b1 = MagicMock(); b1.name = "a"
            mc = MagicMock()
            mc.list_blobs.side_effect = [
                _async_iter([b1]),
                _async_iter([b1]),
            ]
            blob_client = AsyncMock()
            blob_client.delete_blob = AsyncMock(side_effect=RuntimeError("nope"))
            mc.get_blob_client.return_value = blob_client
            mc.delete_container = AsyncMock(return_value=None)
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            assert await h.delete_container("c", force_delete=True) is True
        _run(go())

    def test_delete_container_force_delete_empty(self):
        async def go():
            mc = MagicMock()
            mc.list_blobs.return_value = _async_iter([])
            mc.delete_container = AsyncMock(return_value=None)
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            assert await h.delete_container("c", force_delete=True) is True
        _run(go())

    def test_delete_container_not_found_returns_false(self):
        async def go():
            mc = MagicMock()
            mc.list_blobs.return_value = _async_iter([])
            mc.delete_container = AsyncMock(side_effect=ResourceNotFoundError("nf"))
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            assert await h.delete_container("c") is False
        _run(go())

    def test_delete_container_error_has_blobs_message(self):
        async def go():
            mc = MagicMock()
            mc.list_blobs.return_value = _async_iter([])
            mc.delete_container = AsyncMock(side_effect=RuntimeError("Container has blobs"))
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(ValueError, match="not empty"):
                await h.delete_container("c", force_delete=False)
        _run(go())

    def test_delete_container_error_being_deleted_force(self):
        async def go():
            mc = MagicMock()
            mc.list_blobs.return_value = _async_iter([])
            mc.delete_container = AsyncMock(side_effect=RuntimeError("Container being deleted now"))
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(RuntimeError):
                await h.delete_container("c", force_delete=True)
        _run(go())

    def test_delete_container_other_error(self):
        async def go():
            mc = MagicMock()
            mc.list_blobs.return_value = _async_iter([])
            mc.delete_container = AsyncMock(side_effect=RuntimeError("network"))
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(RuntimeError):
                await h.delete_container("c")
        _run(go())


class TestAsyncContainerExistsAndList:
    def test_container_exists_unexpected_error(self):
        async def go():
            mc = AsyncMock()
            mc.get_container_properties = AsyncMock(side_effect=RuntimeError("err"))
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(RuntimeError):
                await h.container_exists("c")
        _run(go())

    def test_list_containers_success(self):
        async def go():
            c = MagicMock()
            c.name = "x"; c.last_modified = "t"; c.metadata = {"k": "v"}
            c.lease = "lease"; c.public_access = None
            h = _make_async_helper()
            h._blob_service_client.list_containers.return_value = _async_iter([c])
            out = await h.list_containers()
            assert out and out[0]["name"] == "x"
        _run(go())

    def test_list_containers_failure(self):
        async def go():
            h = _make_async_helper()
            h._blob_service_client.list_containers.side_effect = RuntimeError("err")
            with pytest.raises(RuntimeError):
                await h.list_containers()
        _run(go())


class TestAsyncUploadDownload:
    def test_upload_blob_string_data(self):
        async def go():
            mc = MagicMock()
            bc = AsyncMock()
            bc.upload_blob = AsyncMock(return_value={"etag": "1"})
            mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            res = await h.upload_blob("c", "b.txt", "hello")
            assert res == {"etag": "1"}
        _run(go())

    def test_upload_blob_failure(self):
        async def go():
            mc = MagicMock()
            bc = AsyncMock()
            bc.upload_blob = AsyncMock(side_effect=RuntimeError("err"))
            mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(RuntimeError):
                await h.upload_blob("c", "b.txt", b"data", content_type="text/plain")
        _run(go())

    def test_download_blob_success(self):
        async def go():
            mc = MagicMock()
            stream = AsyncMock()
            stream.readall = AsyncMock(return_value=b"data")
            bc = AsyncMock()
            bc.download_blob = AsyncMock(return_value=stream)
            mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            assert await h.download_blob("c", "b") == b"data"
        _run(go())

    def test_download_blob_failure(self):
        async def go():
            mc = MagicMock()
            bc = AsyncMock(); bc.download_blob = AsyncMock(side_effect=RuntimeError("err"))
            mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(RuntimeError):
                await h.download_blob("c", "b")
        _run(go())

    def test_download_blob_to_file_success(self, tmp_path):
        async def go():
            target = tmp_path / "out.bin"
            mc = MagicMock()
            stream = AsyncMock(); stream.readall = AsyncMock(return_value=b"hi")
            bc = AsyncMock(); bc.download_blob = AsyncMock(return_value=stream)
            mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            assert await h.download_blob_to_file("c", "b", str(target)) is True
            assert target.read_bytes() == b"hi"
        _run(go())

    def test_download_blob_to_file_failure(self):
        async def go():
            mc = MagicMock()
            bc = AsyncMock(); bc.download_blob = AsyncMock(side_effect=RuntimeError("err"))
            mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(RuntimeError):
                await h.download_blob_to_file("c", "b", "/no/where/out.bin")
        _run(go())

    def test_upload_blob_from_text_success(self):
        async def go():
            mc = MagicMock()
            bc = AsyncMock(); bc.upload_blob = AsyncMock(return_value={"etag": "1"})
            mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            res = await h.upload_blob_from_text("c", "b", "hello")
            assert res == {"etag": "1"}
        _run(go())

    def test_upload_blob_from_text_failure(self):
        async def go():
            mc = MagicMock()
            bc = AsyncMock(); bc.upload_blob = AsyncMock(side_effect=RuntimeError("err"))
            mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(RuntimeError):
                await h.upload_blob_from_text("c", "b", "x")
        _run(go())

    def test_upload_file_success(self, tmp_path):
        async def go():
            f = tmp_path / "a.txt"; f.write_text("hello")
            mc = MagicMock()
            bc = AsyncMock(); bc.upload_blob = AsyncMock(return_value={"etag": "1"})
            mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            assert await h.upload_file("c", "b.txt", str(f)) is True
        _run(go())

    def test_upload_file_failure(self, tmp_path):
        async def go():
            f = tmp_path / "a.txt"; f.write_text("x")
            mc = MagicMock()
            bc = AsyncMock(); bc.upload_blob = AsyncMock(side_effect=RuntimeError("err"))
            mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(RuntimeError):
                await h.upload_file("c", "b", str(f), content_type="text/plain")
        _run(go())

    def test_download_file_success(self, tmp_path):
        async def go():
            target = tmp_path / "sub" / "out.bin"
            mc = MagicMock()
            stream = MagicMock()
            stream.chunks = lambda: _async_iter([b"hel", b"lo"])
            bc = AsyncMock(); bc.download_blob = AsyncMock(return_value=stream)
            mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            assert await h.download_file("c", "b", str(target)) is True
            assert target.read_bytes() == b"hello"
        _run(go())

    def test_download_file_failure(self, tmp_path):
        async def go():
            mc = MagicMock()
            bc = AsyncMock(); bc.download_blob = AsyncMock(side_effect=RuntimeError("err"))
            mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(RuntimeError):
                await h.download_file("c", "b", str(tmp_path / "x.bin"))
        _run(go())


class TestAsyncBlobOpsErrors:
    def test_blob_exists_unexpected_error(self):
        async def go():
            bc = AsyncMock()
            bc.get_blob_properties = AsyncMock(side_effect=RuntimeError("err"))
            mc = MagicMock(); mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(RuntimeError):
                await h.blob_exists("c", "b")
        _run(go())

    def test_delete_blob_unexpected_error(self):
        async def go():
            bc = AsyncMock(); bc.delete_blob = AsyncMock(side_effect=RuntimeError("err"))
            mc = MagicMock(); mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(RuntimeError):
                await h.delete_blob("c", "b")
        _run(go())


class TestAsyncListBlobs:
    def test_list_blobs_success(self):
        async def go():
            b = MagicMock()
            b.name = "x"; b.size = 1; b.last_modified = "t"; b.etag = "e"
            b.content_settings = MagicMock(content_type="text/plain")
            b.blob_tier = "Hot"; b.blob_type = "BlockBlob"; b.metadata = {"k": "v"}
            mc = MagicMock(); mc.list_blobs.return_value = _async_iter([b])
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            out = await h.list_blobs("c", include_metadata=True)
            assert out[0]["metadata"] == {"k": "v"}
        _run(go())

    def test_list_blobs_no_content_settings(self):
        async def go():
            b = MagicMock()
            b.name = "x"; b.size = 1; b.last_modified = "t"; b.etag = "e"
            b.content_settings = None
            b.blob_tier = "Hot"; b.blob_type = "BlockBlob"; b.metadata = None
            mc = MagicMock(); mc.list_blobs.return_value = _async_iter([b])
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            out = await h.list_blobs("c")
            assert out[0]["content_type"] is None
        _run(go())

    def test_list_blobs_failure(self):
        async def go():
            mc = MagicMock(); mc.list_blobs.side_effect = RuntimeError("err")
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(RuntimeError):
                await h.list_blobs("c")
        _run(go())


class TestAsyncBatch:
    def test_upload_multiple_files_success(self, tmp_path):
        async def go():
            f1 = tmp_path / "a.txt"; f1.write_text("a")
            f2 = tmp_path / "b.txt"; f2.write_text("b")
            h = _make_async_helper()
            h.upload_file = AsyncMock(return_value=True)
            res = await h.upload_multiple_files("c", [str(f1), str(f2)], blob_prefix="p/")
            assert res[str(f1)] is True
        _run(go())

    def test_upload_multiple_files_inner_failure(self, tmp_path):
        async def go():
            f1 = tmp_path / "a.txt"; f1.write_text("a")
            h = _make_async_helper()
            h.upload_file = AsyncMock(side_effect=RuntimeError("err"))
            res = await h.upload_multiple_files("c", [str(f1)])
            assert res[str(f1)] is False
        _run(go())

    def test_download_multiple_blobs_success(self, tmp_path):
        async def go():
            h = _make_async_helper()
            h.download_file = AsyncMock(return_value=True)
            res = await h.download_multiple_blobs("c", ["a.txt", "b.txt"], str(tmp_path))
            assert all(res.values())
        _run(go())

    def test_download_multiple_blobs_inner_failure(self, tmp_path):
        async def go():
            h = _make_async_helper()
            h.download_file = AsyncMock(side_effect=RuntimeError("err"))
            res = await h.download_multiple_blobs("c", ["a.txt"], str(tmp_path))
            assert res["a.txt"] is False
        _run(go())


class TestAsyncProperties:
    def test_get_content_type_known(self):
        h = AsyncStorageBlobHelper(connection_string="x")
        assert h._get_content_type("file.txt").startswith("text/")

    def test_get_content_type_unknown(self):
        h = AsyncStorageBlobHelper(connection_string="x")
        assert h._get_content_type("file.unknownext") == "application/octet-stream"

    def test_get_blob_properties_full(self):
        async def go():
            p = MagicMock()
            p.size = 5; p.last_modified = "t"; p.etag = "e"
            p.content_settings = MagicMock(content_type="text/plain", content_encoding="utf-8")
            p.metadata = {"k": "v"}
            p.blob_tier = "Hot"; p.blob_type = "BlockBlob"
            p.lease = MagicMock(status="unlocked")
            p.creation_time = "now"
            bc = AsyncMock(); bc.get_blob_properties = AsyncMock(return_value=p)
            mc = MagicMock(); mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            out = await h.get_blob_properties("c", "b")
            assert out["lease_status"] == "unlocked"
        _run(go())

    def test_get_blob_properties_no_settings_no_lease(self):
        async def go():
            p = MagicMock()
            p.size = 5; p.last_modified = "t"; p.etag = "e"
            p.content_settings = None; p.metadata = None
            p.blob_tier = None; p.blob_type = "BlockBlob"; p.lease = None
            p.creation_time = "now"
            bc = AsyncMock(); bc.get_blob_properties = AsyncMock(return_value=p)
            mc = MagicMock(); mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            out = await h.get_blob_properties("c", "b")
            assert out["lease_status"] is None and out["content_type"] is None
        _run(go())

    def test_get_blob_properties_failure(self):
        async def go():
            bc = AsyncMock(); bc.get_blob_properties = AsyncMock(side_effect=RuntimeError("err"))
            mc = MagicMock(); mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(RuntimeError):
                await h.get_blob_properties("c", "b")
        _run(go())

    def test_set_blob_metadata_failure(self):
        async def go():
            bc = AsyncMock(); bc.set_blob_metadata = AsyncMock(side_effect=RuntimeError("err"))
            mc = MagicMock(); mc.get_blob_client.return_value = bc
            h = _make_async_helper()
            h._blob_service_client.get_container_client.return_value = mc
            with pytest.raises(RuntimeError):
                await h.set_blob_metadata("c", "b", {})
        _run(go())


class TestAsyncSearch:
    def test_search_blobs_metadata_match(self):
        async def go():
            h = _make_async_helper()
            h.list_blobs = AsyncMock(return_value=[
                {"name": "FOO", "metadata": {"k": "VALUE"}},
                {"name": "skip", "metadata": {"k": "nope"}},
            ])
            out = await h.search_blobs("c", "value", search_in_metadata=True)
            assert any(b["name"] == "FOO" for b in out)
        _run(go())

    def test_search_blobs_case_sensitive(self):
        async def go():
            h = _make_async_helper()
            h.list_blobs = AsyncMock(return_value=[
                {"name": "lower"}, {"name": "UPPER"},
            ])
            out = await h.search_blobs("c", "lower", case_sensitive=True)
            assert len(out) == 1 and out[0]["name"] == "lower"
        _run(go())

    def test_search_blobs_failure(self):
        async def go():
            h = _make_async_helper()
            h.list_blobs = AsyncMock(side_effect=RuntimeError("err"))
            with pytest.raises(RuntimeError):
                await h.search_blobs("c", "x")
        _run(go())


class TestAsyncSAS:
    def test_generate_blob_sas_url_no_account_name(self):
        async def go():
            h = _make_async_helper()
            h._get_account_name = AsyncMock(return_value=None)
            with pytest.raises(ValueError, match="account name"):
                await h.generate_blob_sas_url("c", "b")
        _run(go())

    def test_generate_blob_sas_url_account_key(self):
        async def go():
            with patch("azure.storage.blob.generate_blob_sas") as gen:
                gen.return_value = "sas=tok"
                h = _make_async_helper()
                h._get_account_name = AsyncMock(return_value="acct")
                h._get_account_key = AsyncMock(return_value="key")
                h._get_credential_type = AsyncMock(return_value="Storage Account Key")
                url = await h.generate_blob_sas_url("c", "b", permissions="rwdl")
                assert "sas=tok" in url and "acct.blob.core.windows.net" in url
        _run(go())

    def test_generate_blob_sas_url_user_delegation(self):
        async def go():
            with patch("azure.storage.blob.generate_blob_sas") as gen:
                gen.return_value = "udk=tok"
                h = _make_async_helper()
                h._get_account_name = AsyncMock(return_value="acct")
                h._get_account_key = AsyncMock(return_value=None)
                h._get_credential_type = AsyncMock(return_value="DefaultAzureCredential")
                h._blob_service_client.get_user_delegation_key = AsyncMock(return_value=MagicMock())
                url = await h.generate_blob_sas_url("c", "b")
                assert "udk=tok" in url
        _run(go())

    def test_generate_blob_sas_url_unknown_credential(self):
        async def go():
            h = _make_async_helper()
            h._get_account_name = AsyncMock(return_value="acct")
            h._get_account_key = AsyncMock(return_value=None)
            h._get_credential_type = AsyncMock(return_value="unknown")
            with pytest.raises(ValueError, match="Cannot generate user delegation SAS"):
                await h.generate_blob_sas_url("c", "b")
        _run(go())

    def test_generate_blob_sas_url_delegation_403(self):
        async def go():
            h = _make_async_helper()
            h._get_account_name = AsyncMock(return_value="acct")
            h._get_account_key = AsyncMock(return_value=None)
            h._get_credential_type = AsyncMock(return_value="DefaultAzureCredential")
            h._blob_service_client.get_user_delegation_key = AsyncMock(side_effect=RuntimeError("403 Forbidden"))
            with pytest.raises(ValueError, match="Access denied"):
                await h.generate_blob_sas_url("c", "b")
        _run(go())

    def test_generate_blob_sas_url_delegation_401(self):
        async def go():
            h = _make_async_helper()
            h._get_account_name = AsyncMock(return_value="acct")
            h._get_account_key = AsyncMock(return_value=None)
            h._get_credential_type = AsyncMock(return_value="DefaultAzureCredential")
            h._blob_service_client.get_user_delegation_key = AsyncMock(side_effect=RuntimeError("401 Unauthorized"))
            with pytest.raises(ValueError, match="Authentication failed"):
                await h.generate_blob_sas_url("c", "b")
        _run(go())

    def test_generate_blob_sas_url_delegation_other(self):
        async def go():
            h = _make_async_helper()
            h._get_account_name = AsyncMock(return_value="acct")
            h._get_account_key = AsyncMock(return_value=None)
            h._get_credential_type = AsyncMock(return_value="DefaultAzureCredential")
            h._blob_service_client.get_user_delegation_key = AsyncMock(side_effect=RuntimeError("network"))
            with pytest.raises(ValueError, match="Failed to get user delegation key"):
                await h.generate_blob_sas_url("c", "b")
        _run(go())

    def test_generate_container_sas_url_no_account_name(self):
        async def go():
            h = _make_async_helper()
            h._get_account_name = AsyncMock(return_value=None)
            with pytest.raises(ValueError, match="account name"):
                await h.generate_container_sas_url("c")
        _run(go())

    def test_generate_container_sas_url_account_key(self):
        async def go():
            with patch("azure.storage.blob.generate_container_sas") as gen:
                gen.return_value = "sas=tok"
                h = _make_async_helper()
                h._get_account_name = AsyncMock(return_value="acct")
                h._get_account_key = AsyncMock(return_value="key")
                h._get_credential_type = AsyncMock(return_value="Storage Account Key")
                url = await h.generate_container_sas_url("c", permissions="rwdl")
                assert "sas=tok" in url
        _run(go())

    def test_generate_container_sas_url_user_delegation(self):
        async def go():
            with patch("azure.storage.blob.generate_container_sas") as gen:
                gen.return_value = "udk=tok"
                h = _make_async_helper()
                h._get_account_name = AsyncMock(return_value="acct")
                h._get_account_key = AsyncMock(return_value=None)
                h._get_credential_type = AsyncMock(return_value="DefaultAzureCredential")
                h._blob_service_client.get_user_delegation_key = AsyncMock(return_value=MagicMock())
                url = await h.generate_container_sas_url("c")
                assert "udk=tok" in url
        _run(go())

    def test_generate_container_sas_url_unknown_credential(self):
        async def go():
            h = _make_async_helper()
            h._get_account_name = AsyncMock(return_value="acct")
            h._get_account_key = AsyncMock(return_value=None)
            h._get_credential_type = AsyncMock(return_value="unknown")
            with pytest.raises(ValueError, match="Cannot generate user delegation SAS"):
                await h.generate_container_sas_url("c")
        _run(go())

    def test_generate_container_sas_url_delegation_403(self):
        async def go():
            h = _make_async_helper()
            h._get_account_name = AsyncMock(return_value="acct")
            h._get_account_key = AsyncMock(return_value=None)
            h._get_credential_type = AsyncMock(return_value="DefaultAzureCredential")
            h._blob_service_client.get_user_delegation_key = AsyncMock(side_effect=RuntimeError("403 Forbidden"))
            with pytest.raises(ValueError, match="Access denied"):
                await h.generate_container_sas_url("c")
        _run(go())

    def test_generate_container_sas_url_delegation_401(self):
        async def go():
            h = _make_async_helper()
            h._get_account_name = AsyncMock(return_value="acct")
            h._get_account_key = AsyncMock(return_value=None)
            h._get_credential_type = AsyncMock(return_value="DefaultAzureCredential")
            h._blob_service_client.get_user_delegation_key = AsyncMock(side_effect=RuntimeError("401 Unauthorized"))
            with pytest.raises(ValueError, match="Authentication failed"):
                await h.generate_container_sas_url("c")
        _run(go())

    def test_generate_container_sas_url_delegation_other(self):
        async def go():
            h = _make_async_helper()
            h._get_account_name = AsyncMock(return_value="acct")
            h._get_account_key = AsyncMock(return_value=None)
            h._get_credential_type = AsyncMock(return_value="DefaultAzureCredential")
            h._blob_service_client.get_user_delegation_key = AsyncMock(side_effect=RuntimeError("oops"))
            with pytest.raises(ValueError, match="Failed to get user delegation key"):
                await h.generate_container_sas_url("c")
        _run(go())


class TestAsyncInternals:
    def test_get_account_key_from_credential(self):
        async def go():
            h = _make_async_helper()
            cred = MagicMock(); cred.account_key = "abc"
            h._blob_service_client.credential = cred
            assert await h._get_account_key() == "abc"
        _run(go())

    def test_get_account_key_from_connection_string(self):
        async def go():
            h = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;AccountKey=mykey;Foo=bar")
            client = MagicMock(spec=[])
            h._blob_service_client = client
            assert await h._get_account_key() == "mykey"
        _run(go())

    def test_get_account_key_returns_none(self):
        async def go():
            h = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;Foo=bar")
            h._blob_service_client = MagicMock(spec=[])
            assert await h._get_account_key() is None
        _run(go())

    def test_get_account_name_success(self):
        async def go():
            h = _make_async_helper()
            h._blob_service_client.account_name = "acct"
            assert await h._get_account_name() == "acct"
        _run(go())

    def test_get_account_name_failure(self):
        async def go():
            h = AsyncStorageBlobHelper(connection_string="x")
            svc = MagicMock()
            type(svc).account_name = property(lambda self: (_ for _ in ()).throw(RuntimeError("x")))
            h._blob_service_client = svc
            assert await h._get_account_name() is None
        _run(go())

    def test_get_credential_type_variants(self):
        async def go():
            h = _make_async_helper()
            for cls_name, expected in [
                ("StorageSharedKeyCredential", "Storage Account Key"),
                ("DefaultAzureCredential", "DefaultAzureCredential"),
                ("ManagedIdentityCredential", "Managed Identity"),
                ("AzureCliCredential", "Azure CLI"),
                ("EnvironmentCredential", "Environment Variables"),
                ("WorkloadIdentityCredential", "Workload Identity"),
                ("ChainedTokenCredential", "Chained Token Credential"),
            ]:
                cred = MagicMock(); type(cred).__name__ = cls_name
                h._blob_service_client.credential = cred
                assert await h._get_credential_type() == expected
        _run(go())

    def test_get_credential_type_unknown(self):
        async def go():
            h = _make_async_helper()
            h._blob_service_client.credential = None
            assert await h._get_credential_type() == "unknown"
        _run(go())

    def test_get_credential_type_other(self):
        async def go():
            h = _make_async_helper()
            cred = MagicMock(); type(cred).__name__ = "FooCredential"
            h._blob_service_client.credential = cred
            assert "Azure AD" in await h._get_credential_type()
        _run(go())
