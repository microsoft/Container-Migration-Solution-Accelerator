"""
Unit tests for StorageBlobHelper class

This module contains comprehensive unit tests for the StorageBlobHelper class,
covering all blob storage operations including container management, blob operations,
batch processing, and advanced features like SAS token generation.
"""

import os
import io
import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open, call
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Import the class under test
from app.libs.sas.storage.blob.helper import StorageBlobHelper

# Import Azure SDK exceptions for testing
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from azure.storage.blob import BlobServiceClient, ContentSettings, StandardBlobTier
from azure.identity import DefaultAzureCredential


class TestStorageBlobHelperInitialization:
    """Test cases for StorageBlobHelper initialization"""

    @patch('app.libs.sas.storage.blob.helper.BlobServiceClient.from_connection_string')
    @patch('app.libs.sas.storage.blob.helper.get_config')
    def test_init_with_connection_string(self, mock_get_config, mock_blob_client):
        """Test initialization with connection string"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        mock_get_config.return_value = mock_config
        
        mock_client = Mock()
        mock_blob_client.return_value = mock_client
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net")
        
        assert helper.blob_service_client == mock_client
        assert helper._connection_string == "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net"
        mock_blob_client.assert_called_once_with("DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net")

    @patch('app.libs.sas.storage.blob.helper.BlobServiceClient')
    @patch('app.libs.sas.storage.blob.helper.get_config')
    def test_init_with_account_name_and_credential(self, mock_get_config, mock_blob_client):
        """Test initialization with account name and credential"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        mock_get_config.return_value = mock_config
        
        mock_client = Mock()
        mock_blob_client.return_value = mock_client
        mock_credential = Mock()
        
        helper = StorageBlobHelper(account_name="testaccount", credential=mock_credential)
        
        assert helper.blob_service_client == mock_client
        mock_blob_client.assert_called_once_with(
            "https://testaccount.blob.core.windows.net", 
            credential=mock_credential
        )

    @patch('app.libs.sas.storage.blob.helper.BlobServiceClient')
    @patch('app.libs.sas.storage.blob.helper.DefaultAzureCredential')
    @patch('app.libs.sas.storage.blob.helper.get_config')
    def test_init_with_account_name_only(self, mock_get_config, mock_default_cred, mock_blob_client):
        """Test initialization with account name only (uses DefaultAzureCredential)"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        mock_get_config.return_value = mock_config
        
        mock_client = Mock()
        mock_blob_client.return_value = mock_client
        mock_cred_instance = Mock()
        mock_default_cred.return_value = mock_cred_instance
        
        helper = StorageBlobHelper(account_name="testaccount")
        
        assert helper.blob_service_client == mock_client
        mock_default_cred.assert_called_once()
        mock_blob_client.assert_called_once_with(
            "https://testaccount.blob.core.windows.net", 
            credential=mock_cred_instance
        )

    @patch('app.libs.sas.storage.blob.config.create_config')
    @patch('app.libs.sas.storage.blob.helper.get_config')
    def test_init_with_config_dict(self, mock_get_config, mock_create_config):
        """Test initialization with config dictionary"""
        config_dict = {"logging_level": "DEBUG"}
        mock_config = Mock()
        mock_config.get.return_value = "DEBUG"
        mock_create_config.return_value = mock_config
        
        with patch('app.libs.sas.storage.blob.helper.BlobServiceClient.from_connection_string'):
            helper = StorageBlobHelper(
                connection_string="test_conn_string", 
                config=config_dict
            )
        
        mock_create_config.assert_called_once_with(config_dict)
        assert helper.config == mock_config

    def test_init_with_config_object(self):
        """Test initialization with config object"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        
        with patch('app.libs.sas.storage.blob.helper.BlobServiceClient.from_connection_string'):
            helper = StorageBlobHelper(
                connection_string="test_conn_string", 
                config=mock_config
            )
        
        assert helper.config == mock_config

    @patch('app.libs.sas.storage.blob.helper.get_config')
    def test_init_no_parameters_raises_error(self, mock_get_config):
        """Test initialization with no parameters raises ValueError"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        mock_get_config.return_value = mock_config
        
        with pytest.raises(ValueError, match="Either connection_string or account_name must be provided"):
            StorageBlobHelper()

    @patch('app.libs.sas.storage.blob.helper.BlobServiceClient.from_connection_string')
    @patch('app.libs.sas.storage.blob.helper.get_config')
    def test_init_blob_client_exception_reraises(self, mock_get_config, mock_blob_client):
        """Test that BlobServiceClient initialization exception is re-raised"""
        mock_config = Mock()
        mock_config.get.return_value = "INFO"
        mock_get_config.return_value = mock_config
        
        mock_blob_client.side_effect = Exception("Failed to connect")
        
        with pytest.raises(Exception, match="Failed to connect"):
            StorageBlobHelper(connection_string="invalid_connection_string")


class TestStorageBlobHelperContainerOperations:
    """Test cases for container operations"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.blob.helper.BlobServiceClient.from_connection_string'):
            with patch('app.libs.sas.storage.blob.helper.get_config') as mock_get_config:
                mock_config = Mock()
                mock_config.get.return_value = "INFO"
                mock_get_config.return_value = mock_config
                
                self.helper = StorageBlobHelper(connection_string="test_conn_string")
                self.helper.blob_service_client = Mock()

    def test_create_container_success(self):
        """Test successful container creation"""
        container_client = Mock()
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.create_container("test-container", "blob", {"key": "value"})
        
        assert result is True
        self.helper.blob_service_client.get_container_client.assert_called_once_with("test-container")
        container_client.create_container.assert_called_once_with(
            public_access="blob", metadata={"key": "value"}
        )

    def test_create_container_already_exists(self):
        """Test container creation when container already exists"""
        container_client = Mock()
        container_client.create_container.side_effect = ResourceExistsError("Container exists")
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.create_container("test-container")
        
        assert result is False

    def test_create_container_exception(self):
        """Test container creation with general exception"""
        container_client = Mock()
        container_client.create_container.side_effect = Exception("Network error")
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        with pytest.raises(Exception, match="Network error"):
            self.helper.create_container("test-container")

    def test_delete_container_success(self):
        """Test successful container deletion"""
        container_client = Mock()
        container_client.list_blobs.return_value = []  # Empty container
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.delete_container("test-container")
        
        assert result is True
        container_client.delete_container.assert_called_once()

    def test_delete_container_not_found(self):
        """Test container deletion when container doesn't exist"""
        container_client = Mock()
        container_client.list_blobs.return_value = []  # Empty container
        container_client.delete_container.side_effect = ResourceNotFoundError("Not found")
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.delete_container("test-container")
        
        assert result is False

    def test_delete_container_force_delete_with_blobs(self):
        """Test force delete container with blobs"""
        container_client = Mock()
        blob_client = Mock()
        
        # Mock blobs in container
        mock_blob = Mock()
        mock_blob.name = "test-blob.txt"
        container_client.list_blobs.return_value = [mock_blob]
        container_client.get_blob_client.return_value = blob_client
        
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.delete_container("test-container", force_delete=True)
        
        assert result is True
        blob_client.delete_blob.assert_called_once()
        container_client.delete_container.assert_called_once()

    def test_delete_container_force_delete_with_blob_errors(self):
        """Test force delete container when blob deletion fails"""
        container_client = Mock()
        blob_client = Mock()
        
        # Mock blobs in container
        mock_blob = Mock()
        mock_blob.name = "test-blob.txt"
        container_client.list_blobs.return_value = [mock_blob]
        container_client.get_blob_client.return_value = blob_client
        
        # Make blob deletion fail
        blob_client.delete_blob.side_effect = Exception("Blob delete failed")
        
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.delete_container("test-container", force_delete=True)
        
        # Should still succeed at container level
        assert result is True
        blob_client.delete_blob.assert_called_once()
        container_client.delete_container.assert_called_once()

    def test_delete_container_error_with_container_being_deleted(self):
        """Test container deletion error with container being deleted"""
        container_client = Mock()
        container_client.list_blobs.return_value = []  # Empty container
        container_client.delete_container.side_effect = Exception("ContainerBeingDeleted")
        
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        with pytest.raises(ValueError, match="Set force_delete=True"):
            self.helper.delete_container("test-container")

    def test_delete_container_error_after_force_delete(self):
        """Test container deletion error after force delete attempt"""
        container_client = Mock()
        container_client.list_blobs.return_value = []  # Empty container 
        container_client.delete_container.side_effect = Exception("container has blobs")
        
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        with pytest.raises(Exception, match="container has blobs"):
            self.helper.delete_container("test-container", force_delete=True)

    def test_list_containers_success(self):
        """Test successful container listing"""
        mock_container = Mock()
        mock_container.name = "test-container"
        mock_container.last_modified = datetime.now()
        mock_container.etag = "etag123"
        mock_container.public_access = None
        mock_container.metadata = {"key": "value"}
        
        self.helper.blob_service_client.list_containers.return_value = [mock_container]
        
        result = self.helper.list_containers(name_starts_with="test", include_metadata=True)
        
        assert len(result) == 1
        assert result[0]["name"] == "test-container"
        assert result[0]["metadata"] == {"key": "value"}
        self.helper.blob_service_client.list_containers.assert_called_once_with(
            name_starts_with="test", include_metadata=True
        )

    def test_list_containers_exception(self):
        """Test container listing with exception"""
        self.helper.blob_service_client.list_containers.side_effect = Exception("API error")
        
        with pytest.raises(Exception, match="API error"):
            self.helper.list_containers()

    def test_container_exists_true(self):
        """Test container exists returns True"""
        container_client = Mock()
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.container_exists("test-container")
        
        assert result is True
        container_client.get_container_properties.assert_called_once()

    def test_container_exists_false(self):
        """Test container exists returns False"""
        container_client = Mock()
        container_client.get_container_properties.side_effect = ResourceNotFoundError("Not found")
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.container_exists("test-container")
        
        assert result is False

    def test_container_exists_exception(self):
        """Test container exists with general exception"""
        container_client = Mock()
        container_client.get_container_properties.side_effect = Exception("API error")
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        with pytest.raises(Exception, match="API error"):
            self.helper.container_exists("test-container")


class TestStorageBlobHelperUploadOperations:
    """Test cases for blob upload operations"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.blob.helper.BlobServiceClient.from_connection_string'):
            with patch('app.libs.sas.storage.blob.helper.get_config') as mock_get_config:
                mock_config = Mock()
                mock_config.get.return_value = "INFO"
                mock_get_config.return_value = mock_config
                
                self.helper = StorageBlobHelper(connection_string="test_conn_string")
                self.helper.blob_service_client = Mock()

    def test_upload_blob_success(self):
        """Test successful blob upload"""
        container_client = Mock()
        blob_client = Mock()
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        test_data = b"Hello, World!"
        result = self.helper.upload_blob(
            "test-container", 
            "test-blob.txt", 
            test_data,
            overwrite=True,
            metadata={"key": "value"},
            blob_tier=StandardBlobTier.Hot
        )
        
        assert result is True
        blob_client.upload_blob.assert_called_once_with(
            test_data,
            overwrite=True,
            metadata={"key": "value"},
            content_settings=None,
            standard_blob_tier=StandardBlobTier.Hot
        )

    def test_upload_blob_exception(self):
        """Test blob upload with exception"""
        container_client = Mock()
        blob_client = Mock()
        blob_client.upload_blob.side_effect = Exception("Upload failed")
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        with pytest.raises(Exception, match="Upload failed"):
            self.helper.upload_blob("test-container", "test-blob.txt", b"data")

    @patch('app.libs.sas.storage.blob.helper.os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data=b"file content")
    def test_upload_file_success(self, mock_file, mock_exists):
        """Test successful file upload"""
        mock_exists.return_value = True
        
        container_client = Mock()
        blob_client = Mock()
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        # Mock the _get_content_type method
        self.helper._get_content_type = Mock(return_value="text/plain")
        
        # Mock the upload_blob method to return True
        self.helper.upload_blob = Mock(return_value=True)
        
        result = self.helper.upload_file(
            "test-container", 
            "test-blob.txt", 
            "/path/to/file.txt",
            overwrite=True,
            metadata={"key": "value"}
        )
        
        assert result is True
        mock_file.assert_called_once_with("/path/to/file.txt", "rb")
        self.helper._get_content_type.assert_called_once_with("/path/to/file.txt")

    @patch('app.libs.sas.storage.blob.helper.os.path.exists')
    def test_upload_file_not_found(self, mock_exists):
        """Test file upload when file doesn't exist"""
        mock_exists.return_value = False
        
        with pytest.raises(FileNotFoundError, match="File not found: /path/to/nonexistent.txt"):
            self.helper.upload_file("test-container", "test-blob.txt", "/path/to/nonexistent.txt")

    @patch('app.libs.sas.storage.blob.helper.os.path.exists')
    @patch('builtins.open')
    def test_upload_file_exception(self, mock_open, mock_exists):
        """Test file upload with exception"""
        mock_exists.return_value = True
        mock_open.side_effect = Exception("File read error")
        
        with pytest.raises(Exception, match="File read error"):
            self.helper.upload_file("test-container", "test-blob.txt", "/path/to/file.txt")


class TestStorageBlobHelperDownloadOperations:
    """Test cases for blob download operations"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.blob.helper.BlobServiceClient.from_connection_string'):
            with patch('app.libs.sas.storage.blob.helper.get_config') as mock_get_config:
                mock_config = Mock()
                mock_config.get.return_value = "INFO"
                mock_get_config.return_value = mock_config
                
                self.helper = StorageBlobHelper(connection_string="test_conn_string")
                self.helper.blob_service_client = Mock()

    def test_download_blob_success(self):
        """Test successful blob download"""
        container_client = Mock()
        blob_client = Mock()
        download_stream = Mock()
        download_stream.readall.return_value = b"blob content"
        blob_client.download_blob.return_value = download_stream
        
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.download_blob("test-container", "test-blob.txt")
        
        assert result == b"blob content"
        blob_client.download_blob.assert_called_once()

    def test_download_blob_not_found(self):
        """Test blob download when blob doesn't exist"""
        container_client = Mock()
        blob_client = Mock()
        blob_client.download_blob.side_effect = ResourceNotFoundError("Blob not found")
        
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        with pytest.raises(ResourceNotFoundError, match="Blob not found"):
            self.helper.download_blob("test-container", "test-blob.txt")

    def test_download_blob_exception(self):
        """Test blob download with general exception"""
        container_client = Mock()
        blob_client = Mock()
        blob_client.download_blob.side_effect = Exception("Download failed")
        
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        with pytest.raises(Exception, match="Download failed"):
            self.helper.download_blob("test-container", "test-blob.txt")

    @patch('app.libs.sas.storage.blob.helper.os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_download_blob_to_file_success(self, mock_file, mock_makedirs):
        """Test successful blob download to file"""
        container_client = Mock()
        blob_client = Mock()
        download_stream = Mock()
        download_stream.readall.return_value = b"blob content"
        blob_client.download_blob.return_value = download_stream
        
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.download_blob_to_file(
            "test-container", 
            "test-blob.txt", 
            "/path/to/download.txt"
        )
        
        assert result is True
        mock_makedirs.assert_called_once()
        mock_file.assert_called_once_with("/path/to/download.txt", "wb")
        mock_file().write.assert_called_once_with(b"blob content")

    @patch('app.libs.sas.storage.blob.helper.os.makedirs')
    @patch('builtins.open')
    def test_download_blob_to_file_exception(self, mock_open, mock_makedirs):
        """Test blob download to file with exception"""
        mock_open.side_effect = Exception("File write error")
        
        with pytest.raises(Exception, match="File write error"):
            self.helper.download_blob_to_file("test-container", "test-blob.txt", "/path/to/download.txt")


class TestStorageBlobHelperBlobManagement:
    """Test cases for blob management operations"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.blob.helper.BlobServiceClient.from_connection_string'):
            with patch('app.libs.sas.storage.blob.helper.get_config') as mock_get_config:
                mock_config = Mock()
                mock_config.get.return_value = "INFO"
                mock_get_config.return_value = mock_config
                
                self.helper = StorageBlobHelper(connection_string="test_conn_string")
                self.helper.blob_service_client = Mock()

    def test_delete_blob_success(self):
        """Test successful blob deletion"""
        container_client = Mock()
        blob_client = Mock()
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.delete_blob("test-container", "test-blob.txt", "include")
        
        assert result is True
        blob_client.delete_blob.assert_called_once_with(delete_snapshots="include")

    def test_delete_blob_not_found(self):
        """Test blob deletion when blob doesn't exist"""
        container_client = Mock()
        blob_client = Mock()
        blob_client.delete_blob.side_effect = ResourceNotFoundError("Blob not found")
        
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.delete_blob("test-container", "test-blob.txt")
        
        assert result is False

    def test_delete_blob_exception(self):
        """Test blob deletion with general exception"""
        container_client = Mock()
        blob_client = Mock()
        blob_client.delete_blob.side_effect = Exception("Delete failed")
        
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        with pytest.raises(Exception, match="Delete failed"):
            self.helper.delete_blob("test-container", "test-blob.txt")

    def test_copy_blob_success(self):
        """Test successful blob copy"""
        source_blob_client = Mock()
        source_blob_client.url = "https://account.blob.core.windows.net/container/source.txt"
        
        dest_blob_client = Mock()
        dest_blob_client.start_copy_from_url.return_value = {"copy_status": "success"}
        
        self.helper.blob_service_client.get_blob_client.side_effect = [
            source_blob_client, dest_blob_client
        ]
        
        result = self.helper.copy_blob(
            "source-container", "source-blob.txt",
            "dest-container", "dest-blob.txt",
            {"key": "value"}
        )
        
        assert result is True
        dest_blob_client.start_copy_from_url.assert_called_once_with(source_blob_client.url)
        dest_blob_client.set_blob_metadata.assert_called_once_with({"key": "value"})

    def test_copy_blob_with_pending_status(self):
        """Test blob copy with pending status"""
        source_blob_client = Mock()
        source_blob_client.url = "https://account.blob.core.windows.net/container/source.txt"
        
        dest_blob_client = Mock()
        dest_blob_client.start_copy_from_url.return_value = {"copy_status": "pending"}
        
        self.helper.blob_service_client.get_blob_client.side_effect = [
            source_blob_client, dest_blob_client
        ]
        
        result = self.helper.copy_blob(
            "source-container", "source-blob.txt",
            "dest-container", "dest-blob.txt"
        )
        
        assert result is True

    def test_copy_blob_exception(self):
        """Test blob copy with exception"""
        self.helper.blob_service_client.get_blob_client.side_effect = Exception("Copy failed")
        
        with pytest.raises(Exception, match="Copy failed"):
            self.helper.copy_blob(
                "source-container", "source-blob.txt",
                "dest-container", "dest-blob.txt"
            )

    def test_move_blob_success(self):
        """Test successful blob move"""
        self.helper.copy_blob = Mock(return_value=True)
        self.helper.delete_blob = Mock(return_value=True)
        
        result = self.helper.move_blob(
            "source-container", "source-blob.txt",
            "dest-container", "dest-blob.txt",
            {"key": "value"}
        )
        
        assert result is True
        self.helper.copy_blob.assert_called_once_with(
            "source-container", "source-blob.txt",
            "dest-container", "dest-blob.txt",
            {"key": "value"}
        )
        self.helper.delete_blob.assert_called_once_with("source-container", "source-blob.txt")

    def test_move_blob_copy_fails(self):
        """Test blob move when copy fails"""
        self.helper.copy_blob = Mock(return_value=False)
        
        result = self.helper.move_blob(
            "source-container", "source-blob.txt",
            "dest-container", "dest-blob.txt"
        )
        
        assert result is False

    def test_move_blob_exception(self):
        """Test blob move with exception"""
        self.helper.copy_blob = Mock(side_effect=Exception("Move failed"))
        
        with pytest.raises(Exception, match="Move failed"):
            self.helper.move_blob(
                "source-container", "source-blob.txt",
                "dest-container", "dest-blob.txt"
            )

    def test_blob_exists_true(self):
        """Test blob exists returns True"""
        container_client = Mock()
        blob_client = Mock()
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.blob_exists("test-container", "test-blob.txt")
        
        assert result is True
        blob_client.get_blob_properties.assert_called_once()

    def test_blob_exists_false(self):
        """Test blob exists returns False"""
        container_client = Mock()
        blob_client = Mock()
        blob_client.get_blob_properties.side_effect = ResourceNotFoundError("Not found")
        
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.blob_exists("test-container", "test-blob.txt")
        
        assert result is False

    def test_blob_exists_exception(self):
        """Test blob exists with general exception"""
        container_client = Mock()
        blob_client = Mock()
        blob_client.get_blob_properties.side_effect = Exception("API error")
        
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        with pytest.raises(Exception, match="API error"):
            self.helper.blob_exists("test-container", "test-blob.txt")


class TestStorageBlobHelperListingOperations:
    """Test cases for blob listing operations"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.blob.helper.BlobServiceClient.from_connection_string'):
            with patch('app.libs.sas.storage.blob.helper.get_config') as mock_get_config:
                mock_config = Mock()
                mock_config.get.return_value = "INFO"
                mock_get_config.return_value = mock_config
                
                self.helper = StorageBlobHelper(connection_string="test_conn_string")
                self.helper.blob_service_client = Mock()

    def test_list_blobs_success(self):
        """Test successful blob listing"""
        container_client = Mock()
        
        # Mock blob object
        mock_blob = Mock()
        mock_blob.name = "test-blob.txt"
        mock_blob.size = 1024
        mock_blob.last_modified = datetime.now()
        mock_blob.etag = "etag123"
        mock_blob.content_settings = Mock()
        mock_blob.content_settings.content_type = "text/plain"
        mock_blob.blob_tier = "Hot"
        mock_blob.blob_type = "BlockBlob"
        mock_blob.metadata = {"key": "value"}
        
        container_client.list_blobs.return_value = [mock_blob]
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.list_blobs(
            "test-container", 
            prefix="test-", 
            include_metadata=True,
            include_snapshots=True
        )
        
        assert len(result) == 1
        assert result[0]["name"] == "test-blob.txt"
        assert result[0]["size"] == 1024
        assert result[0]["content_type"] == "text/plain"
        assert result[0]["metadata"] == {"key": "value"}
        
        container_client.list_blobs.assert_called_once_with(
            name_starts_with="test-",
            include=["metadata", "snapshots"]
        )

    def test_list_blobs_no_metadata(self):
        """Test blob listing without metadata"""
        container_client = Mock()
        
        mock_blob = Mock()
        mock_blob.name = "test-blob.txt"
        mock_blob.size = 1024
        mock_blob.last_modified = datetime.now()
        mock_blob.etag = "etag123"
        mock_blob.content_settings = None
        mock_blob.blob_tier = "Hot"
        mock_blob.blob_type = "BlockBlob"
        
        container_client.list_blobs.return_value = [mock_blob]
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.list_blobs("test-container", include_metadata=False)
        
        assert len(result) == 1
        assert result[0]["content_type"] is None
        assert "metadata" not in result[0]

    def test_list_blobs_exception(self):
        """Test blob listing with exception"""
        container_client = Mock()
        container_client.list_blobs.side_effect = Exception("List failed")
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        with pytest.raises(Exception, match="List failed"):
            self.helper.list_blobs("test-container")

    def test_list_blobs_hierarchical_success(self):
        """Test successful hierarchical blob listing"""
        from azure.storage.blob import BlobPrefix
        
        container_client = Mock()
        
        # Mock blob and prefix objects
        mock_blob = Mock()
        mock_blob.name = "folder/test-blob.txt"
        mock_blob.size = 1024
        mock_blob.last_modified = datetime.now()
        mock_blob.etag = "etag123"
        mock_blob.content_settings = Mock()
        mock_blob.content_settings.content_type = "text/plain"
        mock_blob.blob_tier = "Hot"
        mock_blob.blob_type = "BlockBlob"
        
        mock_prefix = Mock(spec=BlobPrefix)
        mock_prefix.name = "folder/"
        
        container_client.walk_blobs.return_value = [mock_prefix, mock_blob]
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.list_blobs_hierarchical("test-container", prefix="", delimiter="/")
        
        assert len(result["blobs"]) == 1
        assert len(result["prefixes"]) == 1
        assert result["prefixes"][0]["name"] == "folder/"
        assert result["blobs"][0]["name"] == "folder/test-blob.txt"

    def test_list_blobs_hierarchical_exception(self):
        """Test hierarchical blob listing with exception"""
        container_client = Mock()
        container_client.walk_blobs.side_effect = Exception("Walk failed")
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        with pytest.raises(Exception, match="Walk failed"):
            self.helper.list_blobs_hierarchical("test-container")


class TestStorageBlobHelperMetadataOperations:
    """Test cases for metadata and properties operations"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.blob.helper.BlobServiceClient.from_connection_string'):
            with patch('app.libs.sas.storage.blob.helper.get_config') as mock_get_config:
                mock_config = Mock()
                mock_config.get.return_value = "INFO"
                mock_get_config.return_value = mock_config
                
                self.helper = StorageBlobHelper(connection_string="test_conn_string")
                self.helper.blob_service_client = Mock()

    def test_get_blob_properties_success(self):
        """Test successful blob properties retrieval"""
        container_client = Mock()
        blob_client = Mock()
        
        # Mock blob properties
        mock_properties = Mock()
        mock_properties.size = 1024
        mock_properties.last_modified = datetime.now()
        mock_properties.etag = "etag123"
        mock_properties.content_settings = Mock()
        mock_properties.content_settings.content_type = "text/plain"
        mock_properties.content_settings.content_encoding = "utf-8"
        mock_properties.blob_tier = "Hot"
        mock_properties.blob_type = "BlockBlob"
        mock_properties.metadata = {"key": "value"}
        mock_properties.creation_time = datetime.now()
        mock_properties.lease = Mock()
        mock_properties.lease.status = "unlocked"
        mock_properties.lease.state = "available"
        
        blob_client.get_blob_properties.return_value = mock_properties
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        result = self.helper.get_blob_properties("test-container", "test-blob.txt")
        
        assert result["name"] == "test-blob.txt"
        assert result["size"] == 1024
        assert result["content_type"] == "text/plain"
        assert result["metadata"] == {"key": "value"}
        assert result["lease_status"] == "unlocked"

    def test_get_blob_properties_exception(self):
        """Test blob properties retrieval with exception"""
        container_client = Mock()
        blob_client = Mock()
        blob_client.get_blob_properties.side_effect = Exception("Properties failed")
        
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        with pytest.raises(Exception, match="Properties failed"):
            self.helper.get_blob_properties("test-container", "test-blob.txt")

    def test_set_blob_metadata_success(self):
        """Test successful blob metadata setting"""
        container_client = Mock()
        blob_client = Mock()
        
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        metadata = {"key": "value", "category": "test"}
        result = self.helper.set_blob_metadata("test-container", "test-blob.txt", metadata)
        
        assert result is True
        blob_client.set_blob_metadata.assert_called_once_with(metadata)

    def test_set_blob_metadata_exception(self):
        """Test blob metadata setting with exception"""
        container_client = Mock()
        blob_client = Mock()
        blob_client.set_blob_metadata.side_effect = Exception("Metadata failed")
        
        container_client.get_blob_client.return_value = blob_client
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        with pytest.raises(Exception, match="Metadata failed"):
            self.helper.set_blob_metadata("test-container", "test-blob.txt", {"key": "value"})


class TestStorageBlobHelperBatchOperations:
    """Test cases for batch operations"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.blob.helper.BlobServiceClient.from_connection_string'):
            with patch('app.libs.sas.storage.blob.helper.get_config') as mock_get_config:
                mock_config = Mock()
                mock_config.get.return_value = "INFO"
                mock_get_config.return_value = mock_config
                
                self.helper = StorageBlobHelper(connection_string="test_conn_string")
                self.helper.blob_service_client = Mock()

    @patch('app.libs.sas.storage.blob.helper.os.path.exists')
    @patch('app.libs.sas.storage.blob.helper.os.path.basename')
    def test_upload_multiple_files_success(self, mock_basename, mock_exists):
        """Test successful multiple file upload"""
        mock_exists.return_value = True
        mock_basename.side_effect = lambda x: x.split("/")[-1]
        
        self.helper.upload_file = Mock(return_value=True)
        
        file_paths = ["/path/to/file1.txt", "/path/to/file2.txt"]
        result = self.helper.upload_multiple_files(
            "test-container", 
            file_paths,
            blob_prefix="uploads/",
            overwrite=True
        )
        
        assert result["/path/to/file1.txt"] is True
        assert result["/path/to/file2.txt"] is True
        
        expected_calls = [
            call("test-container", "uploads/file1.txt", "/path/to/file1.txt", overwrite=True),
            call("test-container", "uploads/file2.txt", "/path/to/file2.txt", overwrite=True)
        ]
        self.helper.upload_file.assert_has_calls(expected_calls)

    @patch('app.libs.sas.storage.blob.helper.os.path.exists')
    def test_upload_multiple_files_file_not_found(self, mock_exists):
        """Test multiple file upload with non-existent file"""
        mock_exists.return_value = False
        
        file_paths = ["/path/to/nonexistent.txt"]
        result = self.helper.upload_multiple_files("test-container", file_paths)
        
        assert result["/path/to/nonexistent.txt"] is False

    @patch('app.libs.sas.storage.blob.helper.os.path.exists')
    @patch('app.libs.sas.storage.blob.helper.os.path.basename')
    def test_upload_multiple_files_upload_fails(self, mock_basename, mock_exists):
        """Test multiple file upload with upload failure"""
        mock_exists.return_value = True
        mock_basename.return_value = "file1.txt"
        
        self.helper.upload_file = Mock(side_effect=Exception("Upload failed"))
        
        file_paths = ["/path/to/file1.txt"]
        result = self.helper.upload_multiple_files("test-container", file_paths)
        
        assert result["/path/to/file1.txt"] is False

    @patch('app.libs.sas.storage.blob.helper.os.makedirs')
    @patch('app.libs.sas.storage.blob.helper.os.path.basename')
    @patch('app.libs.sas.storage.blob.helper.os.path.join')
    def test_download_multiple_blobs_success(self, mock_join, mock_basename, mock_makedirs):
        """Test successful multiple blob download"""
        mock_basename.side_effect = lambda x: x
        mock_join.side_effect = lambda x, y: f"{x}/{y}"
        
        self.helper.download_blob_to_file = Mock(return_value=True)
        
        blob_names = ["blob1.txt", "blob2.txt"]
        result = self.helper.download_multiple_blobs(
            "test-container", 
            blob_names,
            "/download/dir"
        )
        
        assert result["blob1.txt"] is True
        assert result["blob2.txt"] is True
        
        expected_calls = [
            call("test-container", "blob1.txt", "/download/dir/blob1.txt"),
            call("test-container", "blob2.txt", "/download/dir/blob2.txt")
        ]
        self.helper.download_blob_to_file.assert_has_calls(expected_calls)

    @patch('app.libs.sas.storage.blob.helper.os.makedirs')
    @patch('app.libs.sas.storage.blob.helper.os.path.basename')
    @patch('app.libs.sas.storage.blob.helper.os.path.join')
    def test_download_multiple_blobs_download_fails(self, mock_join, mock_basename, mock_makedirs):
        """Test multiple blob download with download failure"""
        mock_basename.return_value = "blob1.txt"
        mock_join.return_value = "/download/dir/blob1.txt"
        
        self.helper.download_blob_to_file = Mock(side_effect=Exception("Download failed"))
        
        blob_names = ["blob1.txt"]
        result = self.helper.download_multiple_blobs("test-container", blob_names, "/download/dir")
        
        assert result["blob1.txt"] is False

    def test_delete_multiple_blobs_success(self):
        """Test successful multiple blob deletion"""
        self.helper.delete_blob = Mock(return_value=True)
        
        blob_names = ["blob1.txt", "blob2.txt"]
        result = self.helper.delete_multiple_blobs("test-container", blob_names)
        
        assert result["blob1.txt"] is True
        assert result["blob2.txt"] is True
        
        expected_calls = [
            call("test-container", "blob1.txt"),
            call("test-container", "blob2.txt")
        ]
        self.helper.delete_blob.assert_has_calls(expected_calls)

    def test_delete_multiple_blobs_delete_fails(self):
        """Test multiple blob deletion with delete failure"""
        self.helper.delete_blob = Mock(side_effect=Exception("Delete failed"))
        
        blob_names = ["blob1.txt"]
        result = self.helper.delete_multiple_blobs("test-container", blob_names)
        
        assert result["blob1.txt"] is False


class TestStorageBlobHelperCoverageImprovements:
    """Test cases to improve coverage in missing areas"""

    def setup_method(self):
        """Setup test fixtures"""
        with patch('app.libs.sas.storage.blob.helper.BlobServiceClient.from_connection_string'):
            with patch('app.libs.sas.storage.blob.helper.get_config') as mock_get_config:
                mock_config = Mock()
                mock_config.get.return_value = "INFO"
                mock_get_config.return_value = mock_config
                
                self.helper = StorageBlobHelper(connection_string="test_conn_string")
                self.helper.blob_service_client = Mock()

    def test_init_with_invalid_config_type(self):
        """Test initialization with invalid config type (line 161-165 coverage)"""
        with patch('app.libs.sas.storage.blob.helper.BlobServiceClient.from_connection_string'):
            with patch('app.libs.sas.storage.blob.helper.get_config') as mock_get_config:
                # Mock default config
                mock_config = Mock()
                mock_config.get.return_value = "INFO"
                mock_get_config.return_value = mock_config
                
                # Test with invalid config that will cause AttributeError
                with pytest.raises(AttributeError, match="'str' object has no attribute 'get'"):
                    StorageBlobHelper(connection_string="test_conn_string", config="string_config")

    @patch('logging.basicConfig')
    def test_init_config_debug_level(self, mock_basic_config):
        """Test initialization with DEBUG log level (line 157-158 coverage)"""
        with patch('app.libs.sas.storage.blob.helper.BlobServiceClient.from_connection_string'):
            with patch('app.libs.sas.storage.blob.helper.get_config') as mock_get_config:
                mock_config = Mock()
                mock_config.get.return_value = "DEBUG"
                mock_get_config.return_value = mock_config
                
                helper = StorageBlobHelper(connection_string="test_conn_string")
                # Check that basicConfig was called with DEBUG level
                mock_basic_config.assert_called_with(level=10)  # DEBUG level

    def test_delete_container_with_exception_handling(self):
        """Test delete container exception handling (line 236 coverage)"""
        container_client = Mock()
        container_client.list_blobs.return_value = []
        container_client.delete_container.side_effect = Exception("Unexpected error")
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        # This should handle the exception and return False
        with pytest.raises(Exception, match="Unexpected error"):
            self.helper.delete_container("test-container")

    def test_generate_blob_sas_url_basic_functionality(self):
        """Test basic SAS URL generation without complex patching"""
        # Mock the helper methods to avoid complex datetime patching
        self.helper._get_account_name = Mock(return_value="testaccount")
        self.helper._get_account_key = Mock(return_value="test-key")
        self.helper._get_credential_type = Mock(return_value="Storage Account Key")
        
        # Mock the Azure SAS generation
        with patch('azure.storage.blob.generate_blob_sas') as mock_gen_sas:
            with patch('azure.storage.blob.BlobSasPermissions'):
                mock_gen_sas.return_value = "mock_sas_token"
                
                result = self.helper.generate_blob_sas_url("container", "blob.txt")
                
                assert "testaccount.blob.core.windows.net" in result
                assert "mock_sas_token" in result

    def test_generate_blob_sas_url_no_account_name(self):
        """Test SAS URL generation when account name cannot be determined"""
        self.helper._get_account_name = Mock(return_value=None)
        
        with pytest.raises(ValueError, match="Unable to determine storage account name"):
            self.helper.generate_blob_sas_url("container", "blob.txt")

    def test_generate_container_sas_url_basic_functionality(self):
        """Test basic container SAS URL generation"""
        self.helper._get_account_name = Mock(return_value="testaccount")
        self.helper._get_account_key = Mock(return_value="test-key")  
        self.helper._get_credential_type = Mock(return_value="Storage Account Key")
        
        with patch('azure.storage.blob.generate_container_sas') as mock_gen_sas:
            with patch('azure.storage.blob.ContainerSasPermissions'):
                mock_gen_sas.return_value = "mock_container_sas"
                
                result = self.helper.generate_container_sas_url("container")
                
                assert "testaccount.blob.core.windows.net/container" in result
                assert "mock_container_sas" in result

    @patch('os.path.exists')
    def test_sync_directory_path_not_found(self, mock_exists):
        """Test sync_directory when local path doesn't exist"""
        mock_exists.return_value = False
        
        with pytest.raises(FileNotFoundError, match="Local directory not found"):
            self.helper.sync_directory("/nonexistent", "container")

    @patch('os.walk')
    @patch('os.path.exists') 
    @patch('os.path.relpath')
    def test_sync_directory_basic_success(self, mock_relpath, mock_exists, mock_walk):
        """Test basic sync_directory functionality"""
        mock_exists.return_value = True
        mock_walk.return_value = [('/test', [], ['file1.txt'])]
        mock_relpath.return_value = 'file1.txt'
        
        # Mock helper methods
        self.helper.blob_exists = Mock(return_value=False)
        self.helper.upload_file = Mock(return_value=True)
        
        result = self.helper.sync_directory('/test', 'container')
        
        assert 'uploaded' in result
        assert 'skipped' in result
        assert 'errors' in result
        assert 'total_files' in result

    def test_azure_error_handling(self):
        """Test handling of Azure-specific exceptions"""
        from azure.core.exceptions import AzureError
        
        container_client = Mock()
        container_client.get_container_properties.side_effect = AzureError("Azure service error")
        self.helper.blob_service_client.get_container_client.return_value = container_client
        
        # The Azure error should be caught and re-raised - this is the actual behavior
        with pytest.raises(Exception, match="Azure service error"):
            self.helper.container_exists('test-container')

    def test_connection_error_handling(self):
        """Test edge cases in connection handling"""
        # Test with malformed connection strings
        with patch('app.libs.sas.storage.blob.helper.BlobServiceClient.from_connection_string') as mock_client:
            mock_client.side_effect = Exception("Invalid connection string")
            
            with pytest.raises(Exception):
                StorageBlobHelper(connection_string="invalid_format")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])