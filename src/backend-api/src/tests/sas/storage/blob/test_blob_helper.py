"""
Tests for blob storage helper module.
"""

import os
import io
import pytest
from unittest.mock import MagicMock, patch, mock_open, call
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from azure.storage.blob import ContentSettings, StandardBlobTier

from libs.sas.storage.blob.helper import StorageBlobHelper
from libs.sas.storage.blob.config import create_config


class TestStorageBlobHelperInitialization:
    """Tests for StorageBlobHelper initialization."""

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_init_with_connection_string(self, mock_blob_client):
        """Test initialization with connection string."""
        mock_client_instance = MagicMock()
        mock_blob_client.from_connection_string.return_value = mock_client_instance
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        
        assert helper.blob_service_client == mock_client_instance
        mock_blob_client.from_connection_string.assert_called_once()

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_init_with_account_name_and_credential(self, mock_blob_client):
        """Test initialization with account name and credential."""
        mock_client_instance = MagicMock()
        mock_blob_client.return_value = mock_client_instance
        mock_credential = MagicMock()
        
        helper = StorageBlobHelper(
            account_name="testaccount",
            credential=mock_credential
        )
        
        assert helper.blob_service_client == mock_client_instance
        mock_blob_client.assert_called_once()

    @patch("libs.sas.storage.blob.helper.DefaultAzureCredential")
    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_init_with_account_name_only(self, mock_blob_client, mock_default_cred):
        """Test initialization with account name only (uses DefaultAzureCredential)."""
        mock_client_instance = MagicMock()
        mock_blob_client.return_value = mock_client_instance
        mock_cred_instance = MagicMock()
        mock_default_cred.return_value = mock_cred_instance
        
        helper = StorageBlobHelper(account_name="testaccount")
        
        assert helper.blob_service_client == mock_client_instance
        mock_default_cred.assert_called_once()

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_init_without_credentials_raises_error(self, mock_blob_client):
        """Test initialization without credentials raises ValueError."""
        with pytest.raises(ValueError, match="Either connection_string or account_name must be provided"):
            StorageBlobHelper()

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_init_with_custom_config_dict(self, mock_blob_client):
        """Test initialization with custom config dictionary."""
        mock_client_instance = MagicMock()
        mock_blob_client.from_connection_string.return_value = mock_client_instance
        custom_config = {"logging_level": "DEBUG"}
        
        helper = StorageBlobHelper(
            connection_string="DefaultEndpointsProtocol=https;...",
            config=custom_config
        )
        
        assert helper.config.get("logging_level") == "DEBUG"

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_init_with_config_object(self, mock_blob_client):
        """Test initialization with config object."""
        mock_client_instance = MagicMock()
        mock_blob_client.from_connection_string.return_value = mock_client_instance
        custom_config = create_config({"logging_level": "WARNING"})
        
        helper = StorageBlobHelper(
            connection_string="DefaultEndpointsProtocol=https;...",
            config=custom_config
        )
        
        assert helper.config == custom_config


class TestContainerOperations:
    """Tests for container operations."""

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_create_container_success(self, mock_blob_client):
        """Test successful container creation."""
        mock_container = MagicMock()
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.create_container("test-container")
        
        assert result is True
        mock_container.create_container.assert_called_once()

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_create_container_already_exists(self, mock_blob_client):
        """Test creating container that already exists."""
        mock_container = MagicMock()
        mock_container.create_container.side_effect = ResourceExistsError("already exists")
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.create_container("test-container")
        
        assert result is False

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_delete_container_success(self, mock_blob_client):
        """Test successful container deletion."""
        mock_container = MagicMock()
        mock_container.list_blobs.return_value = []
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.delete_container("test-container")
        
        assert result is True
        mock_container.delete_container.assert_called_once()

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_delete_container_not_found(self, mock_blob_client):
        """Test deleting non-existent container."""
        mock_container = MagicMock()
        mock_container.list_blobs.return_value = []
        mock_container.delete_container.side_effect = ResourceNotFoundError("not found")
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.delete_container("test-container")
        
        assert result is False

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_delete_container_with_blobs_fails_without_force(self, mock_blob_client):
        """Test deleting container with blobs fails without force_delete."""
        mock_blob = MagicMock()
        mock_blob.name = "blob1.txt"
        mock_container = MagicMock()
        mock_container.list_blobs.return_value = [mock_blob]
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        
        with pytest.raises(ValueError, match="Container .* is not empty"):
            helper.delete_container("test-container", force_delete=False)

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_delete_container_with_force_delete(self, mock_blob_client):
        """Test deleting container with force_delete=True removes blobs."""
        mock_blob = MagicMock()
        mock_blob.name = "blob1.txt"
        mock_blob_client_blob = MagicMock()
        mock_container = MagicMock()
        mock_container.list_blobs.return_value = [mock_blob]
        mock_container.get_blob_client.return_value = mock_blob_client_blob
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.delete_container("test-container", force_delete=True)
        
        assert result is True
        mock_blob_client_blob.delete_blob.assert_called_once()
        mock_container.delete_container.assert_called_once()

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_list_containers_success(self, mock_blob_client):
        """Test listing containers."""
        mock_container_prop = MagicMock()
        mock_container_prop.name = "container1"
        mock_container_prop.last_modified = "2024-01-01"
        mock_container_prop.etag = "abc123"
        mock_container_prop.public_access = None
        mock_container_prop.metadata = None
        
        mock_service = MagicMock()
        mock_service.list_containers.return_value = [mock_container_prop]
        mock_blob_client.from_connection_string.return_value = mock_service
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.list_containers()
        
        assert len(result) == 1
        assert result[0]["name"] == "container1"

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_container_exists_true(self, mock_blob_client):
        """Test checking if container exists."""
        mock_container = MagicMock()
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.container_exists("test-container")
        
        assert result is True
        mock_container.get_container_properties.assert_called_once()

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_container_exists_false(self, mock_blob_client):
        """Test checking for non-existent container."""
        mock_container = MagicMock()
        mock_container.get_container_properties.side_effect = ResourceNotFoundError("not found")
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.container_exists("test-container")
        
        assert result is False


class TestBlobUploadOperations:
    """Tests for blob upload operations."""

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_upload_blob_with_bytes(self, mock_blob_client):
        """Test uploading blob with bytes."""
        mock_blob = MagicMock()
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.upload_blob("container", "blob.txt", b"test data")
        
        assert result is True
        mock_blob.upload_blob.assert_called_once()

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_upload_blob_with_string(self, mock_blob_client):
        """Test uploading blob with string."""
        mock_blob = MagicMock()
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.upload_blob("container", "blob.txt", "test data")
        
        assert result is True
        mock_blob.upload_blob.assert_called_once()

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_upload_blob_with_file_object(self, mock_blob_client):
        """Test uploading blob with file object."""
        mock_blob = MagicMock()
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        file_obj = io.BytesIO(b"test data")
        result = helper.upload_blob("container", "blob.txt", file_obj)
        
        assert result is True

    @patch("builtins.open", new_callable=mock_open, read_data=b"file content")
    @patch("os.path.exists")
    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_upload_file_success(self, mock_blob_client, mock_exists, mock_file):
        """Test uploading file."""
        mock_exists.return_value = True
        mock_blob = MagicMock()
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.upload_file("container", "blob.txt", "/path/to/file.txt")
        
        assert result is True

    @patch("os.path.exists")
    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_upload_file_not_found(self, mock_blob_client, mock_exists):
        """Test uploading file that doesn't exist."""
        mock_exists.return_value = False
        mock_blob_client.from_connection_string.return_value = MagicMock()
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        
        with pytest.raises(FileNotFoundError):
            helper.upload_file("container", "blob.txt", "/path/to/nonexistent.txt")


class TestBlobDownloadOperations:
    """Tests for blob download operations."""

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_download_blob_success(self, mock_blob_client):
        """Test downloading blob."""
        mock_download_stream = MagicMock()
        mock_download_stream.readall.return_value = b"test data"
        mock_blob = MagicMock()
        mock_blob.download_blob.return_value = mock_download_stream
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.download_blob("container", "blob.txt")
        
        assert result == b"test data"

    @patch("builtins.open", new_callable=mock_open)
    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_download_blob_to_file_success(self, mock_blob_client, mock_file):
        """Test downloading blob to file."""
        mock_blob = MagicMock()
        mock_blob.readall.return_value = b"test data"
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.download_blob_to_file("container", "blob.txt", "/path/to/output.txt")
        
        assert result is True


class TestBlobDeleteOperations:
    """Tests for blob delete operations."""

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_delete_blob_success(self, mock_blob_client):
        """Test deleting blob."""
        mock_blob = MagicMock()
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.delete_blob("container", "blob.txt")
        
        assert result is True
        mock_blob.delete_blob.assert_called_once()

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_delete_blob_not_found(self, mock_blob_client):
        """Test deleting non-existent blob."""
        mock_blob = MagicMock()
        mock_blob.delete_blob.side_effect = ResourceNotFoundError("not found")
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.delete_blob("container", "blob.txt")
        
        assert result is False


class TestBlobPropertiesOperations:
    """Tests for blob properties operations."""

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_blob_exists_true(self, mock_blob_client):
        """Test checking if blob exists."""
        mock_blob = MagicMock()
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.blob_exists("container", "blob.txt")
        
        assert result is True

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_blob_exists_false(self, mock_blob_client):
        """Test checking for non-existent blob."""
        mock_blob = MagicMock()
        mock_blob.get_blob_properties.side_effect = ResourceNotFoundError("not found")
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.blob_exists("container", "blob.txt")
        
        assert result is False

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_blob_properties_success(self, mock_blob_client):
        """Test getting blob properties."""
        mock_properties = MagicMock()
        mock_properties.size = 1024
        mock_properties.content_settings.content_type = "text/plain"
        mock_blob = MagicMock()
        mock_blob.get_blob_properties.return_value = mock_properties
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.get_blob_properties("container", "blob.txt")
        
        assert result is not None

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_set_blob_metadata_success(self, mock_blob_client):
        """Test setting blob metadata."""
        mock_blob = MagicMock()
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.set_blob_metadata("container", "blob.txt", {"key": "value"})
        
        assert result is True


class TestBlobListingOperations:
    """Tests for blob listing operations."""

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_list_blobs_success(self, mock_blob_client):
        """Test listing blobs."""
        mock_blob_prop = MagicMock()
        mock_blob_prop.name = "blob1.txt"
        mock_blob_prop.size = 1024
        mock_container = MagicMock()
        mock_container.list_blobs.return_value = [mock_blob_prop]
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.list_blobs("container")
        
        assert len(result) > 0

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_list_blobs_hierarchical_success(self, mock_blob_client):
        """Test listing blobs hierarchically."""
        # walk_blobs returns items that are either BlobPrefix or blob properties
        mock_blob_prop = MagicMock()
        mock_blob_prop.name = "blob1.txt"
        mock_blob_prop.size = 1024
        mock_blob_prop.last_modified = "2024-01-01"
        mock_blob_prop.etag = "abc123"
        mock_blob_prop.content_settings = MagicMock(content_type="text/plain")
        mock_blob_prop.blob_tier = "Hot"
        mock_blob_prop.blob_type = "BlockBlob"
        
        mock_container = MagicMock()
        # walk_blobs is iterable and yields items
        mock_container.walk_blobs.return_value = iter([mock_blob_prop])
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.list_blobs_hierarchical("container")
        
        assert result is not None
        assert "blobs" in result
        assert "prefixes" in result


class TestBlobURLOperations:
    """Tests for blob URL operations."""

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_blob_url(self, mock_blob_client):
        """Test getting blob URL."""
        mock_service = MagicMock()
        mock_service.account_name = "testaccount"
        mock_blob_client.from_connection_string.return_value = mock_service
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        # Mock the internal _get_account_name method
        helper._get_account_name = MagicMock(return_value="testaccount")
        
        result = helper.get_blob_url("container", "blob.txt")
        
        assert "testaccount" in result
        assert "container" in result
        assert "blob.txt" in result

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_container_url(self, mock_blob_client):
        """Test getting container URL."""
        mock_service = MagicMock()
        mock_blob_client.from_connection_string.return_value = mock_service
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        helper._get_account_name = MagicMock(return_value="testaccount")
        
        result = helper.get_container_url("container")
        
        assert "container" in result


class TestBlobHelperContentType:
    """Tests for content type detection."""

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_content_type_text(self, mock_blob_client):
        """Test content type for text files."""
        mock_blob_client.from_connection_string.return_value = MagicMock()
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        
        content_type = helper._get_content_type("file.txt")
        assert content_type == "text/plain"

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_content_type_json(self, mock_blob_client):
        """Test content type for JSON files."""
        mock_blob_client.from_connection_string.return_value = MagicMock()
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        
        content_type = helper._get_content_type("file.json")
        assert content_type == "application/json"

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_content_type_image(self, mock_blob_client):
        """Test content type for image files."""
        mock_blob_client.from_connection_string.return_value = MagicMock()
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        
        content_type = helper._get_content_type("file.png")
        assert content_type == "image/png"

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_content_type_unknown(self, mock_blob_client):
        """Test content type for unknown files."""
        mock_blob_client.from_connection_string.return_value = MagicMock()
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        
        content_type = helper._get_content_type("file.xyz")
        assert content_type == "application/octet-stream"


class TestBlobMultipleOperations:
    """Tests for multiple blob operations."""

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_delete_multiple_blobs_success(self, mock_blob_client):
        """Test deleting multiple blobs."""
        mock_blob = MagicMock()
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob_client.from_connection_string.return_value = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        helper = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;...")
        result = helper.delete_multiple_blobs("container", ["blob1.txt", "blob2.txt"])
        
        assert "blob1.txt" in result
        assert "blob2.txt" in result
        assert len(result) == 2
