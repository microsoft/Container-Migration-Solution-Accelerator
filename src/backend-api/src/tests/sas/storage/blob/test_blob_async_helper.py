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
