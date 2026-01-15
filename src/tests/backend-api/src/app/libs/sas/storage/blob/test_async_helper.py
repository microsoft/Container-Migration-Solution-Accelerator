#!/usr/bin/env python3
"""
Unit tests for AsyncStorageBlobHelper

This module provides comprehensive unit tests for the asynchronous Azure Storage Blob Helper class
covering all functionality including container operations, blob operations, batch processing, and SAS token generation.
"""

import asyncio
import json
import logging
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, mock_open, call
from typing import Dict, List, Any

from azure.storage.blob.aio import BlobServiceClient
from azure.storage.blob import ContentSettings
from azure.identity.aio import DefaultAzureCredential
from azure.core.exceptions import (
    ResourceNotFoundError,
    ResourceExistsError,
)

# Import the class under test
import sys
import os

# Add the src directory to the path so we can import the module
test_dir = Path(__file__).parent
src_dir = test_dir / ".." / ".." / ".." / ".." / ".." / "backend-api" / "src"
sys.path.insert(0, str(src_dir.resolve()))

from app.libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper


class TestAsyncStorageBlobHelper:
    """Test suite for AsyncStorageBlobHelper class"""

    def create_async_iterator(self, items):
        """Helper method to create async iterators for mocking"""
        async def async_iter():
            for item in items:
                yield item
        return async_iter()

    def create_async_file_mock(self):
        """Helper method to create async file context manager mock"""
        mock_file = mock_open()
        async_context = AsyncMock()
        async_context.write = AsyncMock()
        async_context.read = AsyncMock()
        mock_file.return_value.__aenter__ = AsyncMock(return_value=async_context)
        mock_file.return_value.__aexit__ = AsyncMock(return_value=None)
        return mock_file, async_context

    @pytest.fixture
    def mock_blob_service_client(self):
        """Mock BlobServiceClient for testing"""
        mock_client = AsyncMock(spec=BlobServiceClient)
        mock_client.account_name = "teststorageaccount"
        mock_client.close = AsyncMock()
        return mock_client

    @pytest.fixture
    def mock_container_client(self):
        """Mock container client for testing"""
        mock_container = AsyncMock()
        mock_container.create_container = AsyncMock()
        mock_container.delete_container = AsyncMock()
        mock_container.get_container_properties = AsyncMock()
        mock_container.list_blobs = AsyncMock()
        mock_container.get_blob_client = Mock()
        return mock_container

    @pytest.fixture
    def mock_blob_client(self):
        """Mock blob client for testing"""
        mock_blob = AsyncMock()
        mock_blob.upload_blob = AsyncMock()
        mock_blob.download_blob = AsyncMock()
        mock_blob.delete_blob = AsyncMock()
        mock_blob.get_blob_properties = AsyncMock()
        mock_blob.set_blob_metadata = AsyncMock()
        return mock_blob

    @pytest.fixture
    def helper(self, mock_blob_service_client):
        """Create AsyncStorageBlobHelper instance for testing"""
        with patch.object(AsyncStorageBlobHelper, '_initialize_client'):
            helper = AsyncStorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key")
            helper._blob_service_client = mock_blob_service_client
            return helper

    @pytest.mark.asyncio
    async def test_init_with_connection_string(self):
        """Test initialization with connection string"""
        connection_string = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key"
        
        with patch.object(AsyncStorageBlobHelper, '_initialize_client'):
            helper = AsyncStorageBlobHelper(connection_string=connection_string)
            assert helper._connection_string == connection_string
            assert helper._account_name is None
            assert helper._credential is None

    @pytest.mark.asyncio
    async def test_init_with_account_name(self):
        """Test initialization with account name and credential"""
        account_name = "testaccount"
        mock_credential = Mock(spec=DefaultAzureCredential)
        
        with patch.object(AsyncStorageBlobHelper, '_initialize_client'):
            helper = AsyncStorageBlobHelper(account_name=account_name, credential=mock_credential)
            assert helper._account_name == account_name
            assert helper._credential == mock_credential
            assert helper._connection_string is None

    @pytest.mark.asyncio
    async def test_init_with_config(self):
        """Test initialization with custom config"""
        config = {"logging_level": "DEBUG", "test_setting": "value"}
        
        with patch.object(AsyncStorageBlobHelper, '_initialize_client'):
            with patch('app.libs.sas.storage.blob.async_helper.create_config') as mock_create_config:
                mock_create_config.return_value = config
                helper = AsyncStorageBlobHelper(config=config)
                mock_create_config.assert_called_once_with(config)

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_blob_service_client):
        """Test async context manager functionality"""
        with patch.object(AsyncStorageBlobHelper, '_initialize_client') as mock_init:
            mock_init.return_value = None
            helper = AsyncStorageBlobHelper(connection_string="test_conn_string")
            helper._blob_service_client = mock_blob_service_client
            
            async with helper as h:
                assert h is helper
                mock_init.assert_called_once()
            
            mock_blob_service_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_client_with_connection_string(self):
        """Test client initialization with connection string"""
        connection_string = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key"
        
        with patch('app.libs.sas.storage.blob.async_helper.BlobServiceClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.from_connection_string.return_value = mock_client
            
            helper = AsyncStorageBlobHelper(connection_string=connection_string)
            await helper._initialize_client()
            
            mock_client_class.from_connection_string.assert_called_once_with(connection_string)
            assert helper._blob_service_client == mock_client

    @pytest.mark.asyncio
    async def test_initialize_client_with_account_name_and_credential(self):
        """Test client initialization with account name and credential"""
        account_name = "testaccount"
        mock_credential = Mock()
        
        with patch('app.libs.sas.storage.blob.async_helper.BlobServiceClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            helper = AsyncStorageBlobHelper(account_name=account_name, credential=mock_credential)
            await helper._initialize_client()
            
            expected_url = f"https://{account_name}.blob.core.windows.net"
            mock_client_class.assert_called_once_with(expected_url, credential=mock_credential)
            assert helper._blob_service_client == mock_client

    @pytest.mark.asyncio
    async def test_initialize_client_with_account_name_only(self):
        """Test client initialization with account name only (uses DefaultAzureCredential)"""
        account_name = "testaccount"
        
        with patch('app.libs.sas.storage.blob.async_helper.BlobServiceClient') as mock_client_class:
            with patch('app.libs.sas.storage.blob.async_helper.DefaultAzureCredential') as mock_cred_class:
                mock_client = AsyncMock()
                mock_credential = Mock()
                mock_client_class.return_value = mock_client
                mock_cred_class.return_value = mock_credential
                
                helper = AsyncStorageBlobHelper(account_name=account_name)
                await helper._initialize_client()
                
                expected_url = f"https://{account_name}.blob.core.windows.net"
                mock_client_class.assert_called_once_with(expected_url, credential=mock_credential)
                assert helper._blob_service_client == mock_client

    @pytest.mark.asyncio
    async def test_initialize_client_invalid_params(self):
        """Test client initialization with invalid parameters"""
        helper = AsyncStorageBlobHelper()
        
        with pytest.raises(ValueError, match="Either connection_string or account_name must be provided"):
            await helper._initialize_client()

    @pytest.mark.asyncio
    async def test_initialize_client_exception(self):
        """Test client initialization with exception"""
        connection_string = "invalid_connection_string"
        
        with patch('app.libs.sas.storage.blob.async_helper.BlobServiceClient') as mock_client_class:
            mock_client_class.from_connection_string.side_effect = Exception("Connection failed")
            
            helper = AsyncStorageBlobHelper(connection_string=connection_string)
            
            with pytest.raises(Exception, match="Connection failed"):
                await helper._initialize_client()

    @pytest.mark.asyncio
    async def test_blob_service_client_property_not_initialized(self):
        """Test accessing blob_service_client property when not initialized"""
        with patch.object(AsyncStorageBlobHelper, '_initialize_client'):
            helper = AsyncStorageBlobHelper(connection_string="test")
            helper._blob_service_client = None
            
            with pytest.raises(RuntimeError, match="Client not initialized"):
                _ = helper.blob_service_client

    @pytest.mark.asyncio
    async def test_blob_service_client_property_initialized(self, helper, mock_blob_service_client):
        """Test accessing blob_service_client property when initialized"""
        assert helper.blob_service_client == mock_blob_service_client

    # Container Operations Tests
    @pytest.mark.asyncio
    async def test_create_container_success(self, helper, mock_blob_service_client, mock_container_client):
        """Test successful container creation"""
        container_name = "test-container"
        public_access = "container"
        metadata = {"env": "test"}
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.create_container.return_value = None
        
        result = await helper.create_container(container_name, public_access, metadata)
        
        assert result is True
        mock_blob_service_client.get_container_client.assert_called_once_with(container_name)
        mock_container_client.create_container.assert_called_once_with(
            public_access=public_access, metadata=metadata
        )

    @pytest.mark.asyncio
    async def test_create_container_already_exists(self, helper, mock_blob_service_client, mock_container_client):
        """Test container creation when container already exists"""
        container_name = "existing-container"
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.create_container.side_effect = ResourceExistsError("Container exists")
        
        result = await helper.create_container(container_name)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_create_container_exception(self, helper, mock_blob_service_client, mock_container_client):
        """Test container creation with exception"""
        container_name = "test-container"
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.create_container.side_effect = Exception("Creation failed")
        
        with pytest.raises(Exception, match="Creation failed"):
            await helper.create_container(container_name)

    @pytest.mark.asyncio
    async def test_delete_container_success(self, helper, mock_blob_service_client, mock_container_client):
        """Test successful container deletion"""
        container_name = "test-container"
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.delete_container.return_value = None
        # Mock list_blobs to return an empty async iterator
        async def mock_list_blobs_empty():
            return
            yield  # This line never executes, making it an empty async generator
        mock_container_client.list_blobs = mock_list_blobs_empty
        
        result = await helper.delete_container(container_name, force_delete=False)
        
        assert result is True
        mock_container_client.delete_container.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_container_not_found(self, helper, mock_blob_service_client, mock_container_client):
        """Test container deletion when container not found"""
        container_name = "nonexistent-container"
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.delete_container.side_effect = ResourceNotFoundError("Container not found")
        # Mock list_blobs to return an empty async iterator
        async def mock_list_blobs_empty():
            return
            yield  # This line never executes, making it an empty async generator
        mock_container_client.list_blobs = mock_list_blobs_empty
        
        result = await helper.delete_container(container_name)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_container_with_blobs_no_force(self, helper, mock_blob_service_client, mock_container_client):
        """Test container deletion with blobs when force_delete=False"""
        container_name = "test-container"
        
        # Mock blob in container
        mock_blob = Mock()
        mock_blob.name = "test-blob.txt"
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        # Mock list_blobs to return an async iterator directly
        async def mock_list_blobs():
            yield mock_blob
        mock_container_client.list_blobs = mock_list_blobs
        
        with pytest.raises(ValueError, match="Container 'test-container' is not empty"):
            await helper.delete_container(container_name, force_delete=False)

    @pytest.mark.asyncio
    async def test_delete_container_with_force(self, helper, mock_blob_service_client, mock_container_client, mock_blob_client):
        """Test container deletion with force_delete=True"""
        container_name = "test-container"
        
        # Mock blob in container
        mock_blob = Mock()
        mock_blob.name = "test-blob.txt"
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        
        # Mock list_blobs to return the blob for both calls
        call_count = 0
        async def mock_list_blobs_with_blob():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # Return blob for first two calls
                yield mock_blob
        mock_container_client.list_blobs = mock_list_blobs_with_blob
        mock_container_client.delete_container.return_value = None
        mock_blob_client.delete_blob.return_value = None
        
        result = await helper.delete_container(container_name, force_delete=True)
        
        assert result is True
        mock_blob_client.delete_blob.assert_called_once()
        mock_container_client.delete_container.assert_called_once()

    @pytest.mark.asyncio
    async def test_container_exists_true(self, helper, mock_blob_service_client, mock_container_client):
        """Test container exists when container is found"""
        container_name = "existing-container"
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_container_properties.return_value = {}
        
        result = await helper.container_exists(container_name)
        
        assert result is True
        mock_container_client.get_container_properties.assert_called_once()

    @pytest.mark.asyncio
    async def test_container_exists_false(self, helper, mock_blob_service_client, mock_container_client):
        """Test container exists when container not found"""
        container_name = "nonexistent-container"
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_container_properties.side_effect = ResourceNotFoundError("Not found")
        
        result = await helper.container_exists(container_name)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_container_exists_exception(self, helper, mock_blob_service_client, mock_container_client):
        """Test container exists with exception"""
        container_name = "test-container"
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_container_properties.side_effect = Exception("Service error")
        
        with pytest.raises(Exception, match="Service error"):
            await helper.container_exists(container_name)

    @pytest.mark.asyncio
    async def test_list_containers(self, helper, mock_blob_service_client):
        """Test listing containers"""
        # Mock container data
        mock_container = Mock()
        mock_container.name = "test-container"
        mock_container.last_modified = datetime.now()
        mock_container.metadata = {"env": "test"}
        mock_container.lease = None
        mock_container.public_access = "blob"
        
        async def container_async_iter():
            yield mock_container
        mock_blob_service_client.list_containers.return_value = container_async_iter()
        
        result = await helper.list_containers()
        
        assert len(result) == 1
        assert result[0]["name"] == "test-container"
        assert result[0]["metadata"] == {"env": "test"}
        assert result[0]["public_access"] == "blob"
        mock_blob_service_client.list_containers.assert_called_once_with(include_metadata=True)

    @pytest.mark.asyncio
    async def test_list_containers_exception(self, helper, mock_blob_service_client):
        """Test listing containers with exception"""
        mock_blob_service_client.list_containers.side_effect = Exception("List failed")
        
        with pytest.raises(Exception, match="List failed"):
            await helper.list_containers()

    # Blob Operations Tests
    @pytest.mark.asyncio
    async def test_upload_blob_success(self, helper, mock_blob_service_client, mock_container_client, mock_blob_client):
        """Test successful blob upload"""
        container_name = "test-container"
        blob_name = "test-blob.txt"
        data = b"test data"
        content_type = "text/plain"
        metadata = {"source": "test"}
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.upload_blob.return_value = {"etag": "test-etag"}
        
        result = await helper.upload_blob(
            container_name, blob_name, data, content_type=content_type, metadata=metadata
        )
        
        assert result == {"etag": "test-etag"}
        mock_blob_client.upload_blob.assert_called_once()
        
        # Check the call arguments
        args, kwargs = mock_blob_client.upload_blob.call_args
        assert args[0] == data
        assert kwargs["overwrite"] is False
        assert kwargs["metadata"] == metadata
        assert kwargs["max_concurrency"] == 4

    @pytest.mark.asyncio
    async def test_upload_blob_string_data(self, helper, mock_blob_service_client, mock_container_client, mock_blob_client):
        """Test blob upload with string data"""
        container_name = "test-container"
        blob_name = "test-blob.txt"
        data = "test string data"
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.upload_blob.return_value = {}
        
        with patch.object(helper, '_get_content_type', return_value="text/plain"):
            result = await helper.upload_blob(container_name, blob_name, data)
        
        # Verify string was converted to bytes
        args, kwargs = mock_blob_client.upload_blob.call_args
        assert args[0] == data.encode("utf-8")

    @pytest.mark.asyncio
    async def test_upload_blob_exception(self, helper, mock_blob_service_client, mock_container_client, mock_blob_client):
        """Test blob upload with exception"""
        container_name = "test-container"
        blob_name = "test-blob.txt"
        data = b"test data"
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.upload_blob.side_effect = Exception("Upload failed")
        
        with pytest.raises(Exception, match="Upload failed"):
            await helper.upload_blob(container_name, blob_name, data)

    @pytest.mark.asyncio
    async def test_download_blob_success(self, helper, mock_blob_service_client, mock_container_client, mock_blob_client):
        """Test successful blob download"""
        container_name = "test-container"
        blob_name = "test-blob.txt"
        expected_data = b"downloaded data"
        
        mock_download_stream = AsyncMock()
        mock_download_stream.readall.return_value = expected_data
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.download_blob.return_value = mock_download_stream
        
        result = await helper.download_blob(container_name, blob_name)
        
        assert result == expected_data
        mock_blob_client.download_blob.assert_called_once()
        mock_download_stream.readall.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_blob_exception(self, helper, mock_blob_service_client, mock_container_client, mock_blob_client):
        """Test blob download with exception"""
        container_name = "test-container"
        blob_name = "test-blob.txt"
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.download_blob.side_effect = Exception("Download failed")
        
        with pytest.raises(Exception, match="Download failed"):
            await helper.download_blob(container_name, blob_name)

    @pytest.mark.asyncio
    async def test_download_blob_to_file(self, helper):
        """Test downloading blob to file"""
        container_name = "test-container"
        blob_name = "test-blob.txt"
        destination_file_path = "/tmp/test-file.txt"
        test_data = b"test file data"
        
        with patch.object(helper, 'download_blob', return_value=test_data) as mock_download:
            # Create a proper async file mock
            async_file_mock = AsyncMock()
            
            with patch('aiofiles.open') as mock_open:
                mock_open.return_value.__aenter__ = AsyncMock(return_value=async_file_mock)
                mock_open.return_value.__aexit__ = AsyncMock(return_value=None)
                
                result = await helper.download_blob_to_file(container_name, blob_name, destination_file_path)
                
                assert result is True
                mock_download.assert_called_once_with(container_name, blob_name)
                mock_open.assert_called_once_with(destination_file_path, "wb")

    @pytest.mark.asyncio
    async def test_upload_blob_from_text(self, helper):
        """Test uploading text as blob"""
        container_name = "test-container"
        blob_name = "test-blob.txt"
        text = "Hello, World!"
        
        with patch.object(helper, 'upload_blob', return_value={}) as mock_upload:
            result = await helper.upload_blob_from_text(container_name, blob_name, text)
            
            assert result == {}
            mock_upload.assert_called_once_with(
                container_name, blob_name, text.encode("utf-8"), content_type="text/plain"
            )

    @pytest.mark.asyncio
    async def test_upload_file(self, helper, mock_blob_service_client, mock_container_client, mock_blob_client):
        """Test file upload"""
        container_name = "test-container"
        blob_name = "test-blob.txt"
        file_path = "/tmp/test-file.txt"
        content_type = "text/plain"
        metadata = {"source": "file"}
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.upload_blob.return_value = None
        
        # Create a simple async file mock
        async_file_mock = AsyncMock()
        
        with patch('aiofiles.open') as mock_open:
            mock_open.return_value.__aenter__ = AsyncMock(return_value=async_file_mock)
            mock_open.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch.object(helper, '_get_content_type', return_value=content_type):
                result = await helper.upload_file(
                    container_name, blob_name, file_path, content_type=content_type, metadata=metadata
                )
                
                assert result is True
                mock_open.assert_called_once_with(file_path, "rb")
                mock_blob_client.upload_blob.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_file(self, helper, mock_blob_service_client, mock_container_client, mock_blob_client):
        """Test file download"""
        container_name = "test-container"
        blob_name = "test-blob.txt"
        file_path = "/tmp/downloaded-file.txt"
        
        mock_download_stream = AsyncMock()
        # Mock chunks method to return an async iterator
        async def mock_chunks():
            yield b"chunk1"
            yield b"chunk2"
        mock_download_stream.chunks = mock_chunks
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.download_blob.return_value = mock_download_stream
        
        # Create async file mock directly
        async_file_mock = AsyncMock()
        
        with patch('aiofiles.open') as mock_open:
            mock_open.return_value.__aenter__ = AsyncMock(return_value=async_file_mock)
            mock_open.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch('pathlib.Path.mkdir') as mock_mkdir:
                result = await helper.download_file(container_name, blob_name, file_path)
                
                assert result is True
                mock_open.assert_called_once_with(file_path, "wb")
                assert async_file_mock.write.call_count == 2

    @pytest.mark.asyncio
    async def test_blob_exists_true(self, helper, mock_blob_service_client, mock_container_client, mock_blob_client):
        """Test blob exists when blob is found"""
        container_name = "test-container"
        blob_name = "test-blob.txt"
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.get_blob_properties.return_value = {}
        
        result = await helper.blob_exists(container_name, blob_name)
        
        assert result is True
        mock_blob_client.get_blob_properties.assert_called_once()

    @pytest.mark.asyncio
    async def test_blob_exists_false(self, helper, mock_blob_service_client, mock_container_client, mock_blob_client):
        """Test blob exists when blob not found"""
        container_name = "test-container"
        blob_name = "nonexistent-blob.txt"
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.get_blob_properties.side_effect = ResourceNotFoundError("Not found")
        
        result = await helper.blob_exists(container_name, blob_name)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_blob_success(self, helper, mock_blob_service_client, mock_container_client, mock_blob_client):
        """Test successful blob deletion"""
        container_name = "test-container"
        blob_name = "test-blob.txt"
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.delete_blob.return_value = None
        
        result = await helper.delete_blob(container_name, blob_name)
        
        assert result is True
        mock_blob_client.delete_blob.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_blob_not_found(self, helper, mock_blob_service_client, mock_container_client, mock_blob_client):
        """Test blob deletion when blob not found"""
        container_name = "test-container"
        blob_name = "nonexistent-blob.txt"
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.delete_blob.side_effect = ResourceNotFoundError("Not found")
        
        result = await helper.delete_blob(container_name, blob_name)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_list_blobs(self, helper, mock_blob_service_client, mock_container_client):
        """Test listing blobs"""
        container_name = "test-container"
        prefix = "test-"
        
        # Mock blob data
        mock_blob = Mock()
        mock_blob.name = "test-blob.txt"
        mock_blob.size = 1024
        mock_blob.last_modified = datetime.now()
        mock_blob.etag = "test-etag"
        mock_blob.content_settings = Mock()
        mock_blob.content_settings.content_type = "text/plain"
        mock_blob.blob_tier = "Hot"
        mock_blob.blob_type = "BlockBlob"
        mock_blob.metadata = {"env": "test"}
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        # Mock list_blobs properly
        async def mock_list_blobs_generator(**kwargs):
            yield mock_blob
        mock_container_client.list_blobs = Mock(side_effect=lambda **kwargs: mock_list_blobs_generator(**kwargs))
        
        result = await helper.list_blobs(container_name, prefix, include_metadata=True)
        
        assert len(result) == 1
        assert result[0]["name"] == "test-blob.txt"
        assert result[0]["size"] == 1024
        assert result[0]["content_type"] == "text/plain"
        assert result[0]["metadata"] == {"env": "test"}
        
        mock_container_client.list_blobs.assert_called_once_with(
            name_starts_with=prefix, include=["metadata"]
        )

    # Batch Operations Tests
    @pytest.mark.asyncio
    async def test_upload_multiple_files(self, helper):
        """Test uploading multiple files concurrently"""
        container_name = "test-container"
        file_paths = ["/tmp/file1.txt", "/tmp/file2.txt"]
        blob_prefix = "uploads/"
        
        with patch.object(helper, 'upload_file') as mock_upload:
            mock_upload.side_effect = [True, True]
            
            result = await helper.upload_multiple_files(
                container_name, file_paths, blob_prefix, max_concurrency=2
            )
            
            assert result == {"/tmp/file1.txt": True, "/tmp/file2.txt": True}
            assert mock_upload.call_count == 2
            
            # Check calls were made with correct blob names
            expected_calls = [
                call(container_name, "uploads/file1.txt", "/tmp/file1.txt", overwrite=False),
                call(container_name, "uploads/file2.txt", "/tmp/file2.txt", overwrite=False)
            ]
            mock_upload.assert_has_calls(expected_calls, any_order=True)

    @pytest.mark.asyncio
    async def test_upload_multiple_files_with_failures(self, helper):
        """Test uploading multiple files with some failures"""
        container_name = "test-container"
        file_paths = ["/tmp/file1.txt", "/tmp/file2.txt"]
        
        with patch.object(helper, 'upload_file') as mock_upload:
            mock_upload.side_effect = [True, Exception("Upload failed")]
            
            result = await helper.upload_multiple_files(container_name, file_paths)
            
            assert result == {"/tmp/file1.txt": True, "/tmp/file2.txt": False}

    @pytest.mark.asyncio
    async def test_download_multiple_blobs(self, helper):
        """Test downloading multiple blobs concurrently"""
        container_name = "test-container"
        blob_names = ["blob1.txt", "blob2.txt"]
        download_dir = "/tmp/downloads"
        
        with patch.object(helper, 'download_file') as mock_download:
            mock_download.side_effect = [True, True]
            
            result = await helper.download_multiple_blobs(
                container_name, blob_names, download_dir, max_concurrency=2
            )
            
            assert result == {"blob1.txt": True, "blob2.txt": True}
            assert mock_download.call_count == 2
            
            # Check calls were made with correct file paths
            expected_calls = [
                call(container_name, "blob1.txt", str(Path("/tmp/downloads") / "blob1.txt")),
                call(container_name, "blob2.txt", str(Path("/tmp/downloads") / "blob2.txt"))
            ]
            mock_download.assert_has_calls(expected_calls, any_order=True)

    @pytest.mark.asyncio
    async def test_download_multiple_blobs_with_failures(self, helper):
        """Test downloading multiple blobs with some failures"""
        container_name = "test-container"
        blob_names = ["blob1.txt", "blob2.txt"]
        download_dir = "/tmp/downloads"
        
        with patch.object(helper, 'download_file') as mock_download:
            mock_download.side_effect = [True, Exception("Download failed")]
            
            result = await helper.download_multiple_blobs(container_name, blob_names, download_dir)
            
            assert result == {"blob1.txt": True, "blob2.txt": False}

    # Utility Methods Tests
    def test_get_content_type(self, helper):
        """Test content type detection"""
        assert helper._get_content_type("test.txt") == "text/plain"
        assert helper._get_content_type("test.json") == "application/json"
        assert helper._get_content_type("test.pdf") == "application/pdf"
        assert helper._get_content_type("test.unknown") == "application/octet-stream"

    @pytest.mark.asyncio
    async def test_get_blob_properties(self, helper, mock_blob_service_client, mock_container_client, mock_blob_client):
        """Test getting blob properties"""
        container_name = "test-container"
        blob_name = "test-blob.txt"
        
        # Mock blob properties
        mock_properties = Mock()
        mock_properties.size = 1024
        mock_properties.last_modified = datetime.now()
        mock_properties.etag = "test-etag"
        mock_properties.content_settings = Mock()
        mock_properties.content_settings.content_type = "text/plain"
        mock_properties.content_settings.content_encoding = None
        mock_properties.metadata = {"env": "test"}
        mock_properties.blob_tier = "Hot"
        mock_properties.blob_type = "BlockBlob"
        mock_properties.lease = Mock()
        mock_properties.lease.status = "unlocked"
        mock_properties.creation_time = datetime.now()
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.get_blob_properties.return_value = mock_properties
        
        result = await helper.get_blob_properties(container_name, blob_name)
        
        assert result["name"] == blob_name
        assert result["size"] == 1024
        assert result["content_type"] == "text/plain"
        assert result["metadata"] == {"env": "test"}
        assert result["blob_tier"] == "Hot"
        assert result["lease_status"] == "unlocked"

    @pytest.mark.asyncio
    async def test_set_blob_metadata(self, helper, mock_blob_service_client, mock_container_client, mock_blob_client):
        """Test setting blob metadata"""
        container_name = "test-container"
        blob_name = "test-blob.txt"
        metadata = {"env": "production", "version": "1.0"}
        
        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.set_blob_metadata.return_value = None
        
        result = await helper.set_blob_metadata(container_name, blob_name, metadata)
        
        assert result is True
        mock_blob_client.set_blob_metadata.assert_called_once_with(metadata)

    @pytest.mark.asyncio
    async def test_search_blobs_by_name(self, helper):
        """Test searching blobs by name"""
        container_name = "test-container"
        search_term = "test"
        
        # Mock blob list
        mock_blobs = [
            {"name": "test-file.txt", "size": 1024},
            {"name": "another-file.txt", "size": 2048},
            {"name": "test-image.png", "size": 512}
        ]
        
        with patch.object(helper, 'list_blobs', return_value=mock_blobs):
            result = await helper.search_blobs(container_name, search_term)
            
            assert len(result) == 2
            assert result[0]["name"] == "test-file.txt"
            assert result[1]["name"] == "test-image.png"

    @pytest.mark.asyncio
    async def test_search_blobs_case_sensitive(self, helper):
        """Test case-sensitive blob search"""
        container_name = "test-container"
        search_term = "Test"
        
        mock_blobs = [
            {"name": "Test-file.txt", "size": 1024},
            {"name": "test-file.txt", "size": 2048}
        ]
        
        with patch.object(helper, 'list_blobs', return_value=mock_blobs):
            result = await helper.search_blobs(container_name, search_term, case_sensitive=True)
            
            assert len(result) == 1
            assert result[0]["name"] == "Test-file.txt"

    @pytest.mark.asyncio
    async def test_search_blobs_in_metadata(self, helper):
        """Test searching blobs in metadata"""
        container_name = "test-container"
        search_term = "production"
        
        mock_blobs = [
            {
                "name": "file1.txt",
                "size": 1024,
                "metadata": {"env": "production", "version": "1.0"}
            },
            {
                "name": "file2.txt",
                "size": 2048,
                "metadata": {"env": "development", "version": "1.0"}
            }
        ]
        
        with patch.object(helper, 'list_blobs', return_value=mock_blobs):
            result = await helper.search_blobs(
                container_name, search_term, search_in_metadata=True
            )
            
            assert len(result) == 1
            assert result[0]["name"] == "file1.txt"

    # SAS Token Generation Tests
    @pytest.mark.asyncio
    async def test_generate_blob_sas_url_with_account_key(self, helper, mock_blob_service_client):
        """Test generating blob SAS URL with account key"""
        container_name = "test-container"
        blob_name = "test-blob.txt"
        account_name = "testaccount"
        account_key = "test-key"
        
        with patch.object(helper, '_get_account_name', return_value=account_name):
            with patch.object(helper, '_get_account_key', return_value=account_key):
                with patch.object(helper, '_get_credential_type', return_value="Storage Account Key"):
                    with patch('azure.storage.blob.generate_blob_sas', return_value="sas_token"):
                        result = await helper.generate_blob_sas_url(container_name, blob_name)
                        
                        expected_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?sas_token"
                        assert result == expected_url

    @pytest.mark.asyncio
    async def test_generate_blob_sas_url_with_user_delegation(self, helper, mock_blob_service_client):
        """Test generating blob SAS URL with user delegation"""
        container_name = "test-container"
        blob_name = "test-blob.txt"
        account_name = "testaccount"
        
        mock_delegation_key = Mock()
        mock_blob_service_client.get_user_delegation_key.return_value = mock_delegation_key
        
        with patch.object(helper, '_get_account_name', return_value=account_name):
            with patch.object(helper, '_get_account_key', return_value=None):
                with patch.object(helper, '_get_credential_type', return_value="DefaultAzureCredential"):
                    with patch('azure.storage.blob.generate_blob_sas', return_value="user_delegation_sas"):
                        result = await helper.generate_blob_sas_url(container_name, blob_name)
                        
                        expected_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?user_delegation_sas"
                        assert result == expected_url
                        mock_blob_service_client.get_user_delegation_key.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_container_sas_url_with_account_key(self, helper, mock_blob_service_client):
        """Test generating container SAS URL with account key"""
        container_name = "test-container"
        account_name = "testaccount"
        account_key = "test-key"
        
        with patch.object(helper, '_get_account_name', return_value=account_name):
            with patch.object(helper, '_get_account_key', return_value=account_key):
                with patch.object(helper, '_get_credential_type', return_value="Storage Account Key"):
                    with patch('azure.storage.blob.generate_container_sas', return_value="container_sas"):
                        result = await helper.generate_container_sas_url(container_name)
                        
                        expected_url = f"https://{account_name}.blob.core.windows.net/{container_name}?container_sas"
                        assert result == expected_url

    @pytest.mark.asyncio
    async def test_get_account_key_from_connection_string(self, helper):
        """Test extracting account key from connection string"""
        helper._connection_string = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test-key;EndpointSuffix=core.windows.net"
        
        result = await helper._get_account_key()
        assert result == "test-key"

    @pytest.mark.asyncio
    async def test_get_account_key_none(self, helper):
        """Test getting account key when not available"""
        helper._connection_string = None
        
        result = await helper._get_account_key()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_account_name(self, helper, mock_blob_service_client):
        """Test getting account name"""
        mock_blob_service_client.account_name = "testaccount"
        
        result = await helper._get_account_name()
        assert result == "testaccount"

    @pytest.mark.asyncio
    async def test_get_credential_type_default_azure_credential(self, helper, mock_blob_service_client):
        """Test getting credential type for DefaultAzureCredential"""
        mock_credential = Mock()
        mock_credential.__class__.__name__ = "DefaultAzureCredential"
        mock_blob_service_client.credential = mock_credential
        
        result = await helper._get_credential_type()
        assert result == "DefaultAzureCredential"

    @pytest.mark.asyncio
    async def test_get_credential_type_managed_identity(self, helper, mock_blob_service_client):
        """Test getting credential type for Managed Identity"""
        mock_credential = Mock()
        mock_credential.__class__.__name__ = "ManagedIdentityCredential"
        mock_blob_service_client.credential = mock_credential
        
        result = await helper._get_credential_type()
        assert result == "Managed Identity"

    @pytest.mark.asyncio
    async def test_get_credential_type_storage_key(self, helper, mock_blob_service_client):
        """Test getting credential type for storage account key"""
        mock_credential = Mock()
        mock_credential.__class__.__name__ = "StorageSharedKeyCredential"
        mock_blob_service_client.credential = mock_credential
        
        result = await helper._get_credential_type()
        assert result == "Storage Account Key"

    @pytest.mark.asyncio
    async def test_get_credential_type_unknown(self, helper, mock_blob_service_client):
        """Test getting credential type when unknown"""
        mock_blob_service_client.credential = None
        
        result = await helper._get_credential_type()
        assert result == "unknown"

    @pytest.mark.asyncio
    async def test_sas_generation_forbidden_error(self, helper, mock_blob_service_client):
        """Test SAS generation with forbidden error"""
        container_name = "test-container"
        blob_name = "test-blob.txt"
        
        mock_blob_service_client.get_user_delegation_key.side_effect = Exception("Forbidden")
        
        with patch.object(helper, '_get_account_name', return_value="testaccount"):
            with patch.object(helper, '_get_account_key', return_value=None):
                with patch.object(helper, '_get_credential_type', return_value="DefaultAzureCredential"):
                    with pytest.raises(ValueError, match="Access denied when requesting user delegation key"):
                        await helper.generate_blob_sas_url(container_name, blob_name)

    @pytest.mark.asyncio
    async def test_close_client(self, helper, mock_blob_service_client):
        """Test closing the blob service client"""
        await helper.close()
        mock_blob_service_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_client_none(self, helper):
        """Test closing when client is None"""
        helper._blob_service_client = None
        # Should not raise exception
        await helper.close()