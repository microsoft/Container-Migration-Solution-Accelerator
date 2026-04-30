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



# ---------------------------------------------------------------------------
# Additional coverage tests
# ---------------------------------------------------------------------------
import datetime as _dt
from libs.sas.storage.blob.helper import StorageBlobHelper as _Helper


def _make_helper(mock_cls, service=None):
    svc = service or MagicMock()
    mock_cls.from_connection_string.return_value = svc
    return _Helper(connection_string="DefaultEndpointsProtocol=https;..."), svc


class TestExtraInitAndContainer:
    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_init_blob_service_client_failure_raises(self, mock_cls):
        mock_cls.from_connection_string.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            StorageBlobHelper(connection_string="x")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_create_container_unexpected_error_reraises(self, mock_cls):
        mock_container = MagicMock()
        mock_container.create_container.side_effect = RuntimeError("bad")
        svc = MagicMock(); svc.get_container_client.return_value = mock_container
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.create_container("c")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_delete_container_force_delete_inner_blob_failure_continues(self, mock_cls):
        b1 = MagicMock(); b1.name = "a.txt"
        b2 = MagicMock(); b2.name = "b.txt"
        bc = MagicMock(); bc.delete_blob.side_effect = [RuntimeError("x"), None]
        mc = MagicMock()
        mc.list_blobs.return_value = [b1, b2]
        mc.get_blob_client.return_value = bc
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        assert h.delete_container("c", force_delete=True) is True
        mc.delete_container.assert_called_once()

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_delete_container_force_delete_empty_logs_already_empty(self, mock_cls):
        mc = MagicMock(); mc.list_blobs.return_value = []
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        assert h.delete_container("c", force_delete=True) is True

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_delete_container_error_path_container_has_blobs_string(self, mock_cls):
        mc = MagicMock()
        mc.list_blobs.return_value = []
        mc.delete_container.side_effect = RuntimeError("Container has blobs in it")
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(ValueError, match="not empty"):
            h.delete_container("c", force_delete=False)

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_delete_container_error_path_container_being_deleted_force(self, mock_cls):
        mc = MagicMock()
        mc.list_blobs.return_value = []
        mc.delete_container.side_effect = RuntimeError("ContainerBeingDeleted occurred")
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.delete_container("c", force_delete=True)

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_delete_container_other_error_reraises(self, mock_cls):
        mc = MagicMock()
        mc.list_blobs.return_value = []
        mc.delete_container.side_effect = RuntimeError("network down")
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.delete_container("c")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_list_containers_with_metadata(self, mock_cls):
        c = MagicMock()
        c.name = "x"; c.last_modified = "t"; c.etag = "e"; c.public_access = None
        c.metadata = {"a": "b"}
        svc = MagicMock(); svc.list_containers.return_value = [c]
        h, _ = _make_helper(mock_cls, svc)
        out = h.list_containers(include_metadata=True)
        assert out[0]["metadata"] == {"a": "b"}

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_list_containers_failure(self, mock_cls):
        svc = MagicMock(); svc.list_containers.side_effect = RuntimeError("nope")
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.list_containers()

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_container_exists_unexpected_error(self, mock_cls):
        mc = MagicMock(); mc.get_container_properties.side_effect = RuntimeError("bad")
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.container_exists("c")


class TestExtraBlobOps:
    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_upload_blob_failure(self, mock_cls):
        bc = MagicMock(); bc.upload_blob.side_effect = RuntimeError("err")
        mc = MagicMock(); mc.get_blob_client.return_value = bc
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.upload_blob("c", "b", b"d")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_download_blob_not_found(self, mock_cls):
        bc = MagicMock(); bc.download_blob.side_effect = ResourceNotFoundError("nf")
        mc = MagicMock(); mc.get_blob_client.return_value = bc
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(ResourceNotFoundError):
            h.download_blob("c", "b")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_download_blob_other_failure(self, mock_cls):
        bc = MagicMock(); bc.download_blob.side_effect = RuntimeError("oops")
        mc = MagicMock(); mc.get_blob_client.return_value = bc
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.download_blob("c", "b")

    def test_download_blob_to_file_success(self, tmp_path):
        with patch("libs.sas.storage.blob.helper.BlobServiceClient") as mock_cls:
            stream = MagicMock(); stream.readall.return_value = b"hi"
            bc = MagicMock(); bc.download_blob.return_value = stream
            mc = MagicMock(); mc.get_blob_client.return_value = bc
            svc = MagicMock(); svc.get_container_client.return_value = mc
            h, _ = _make_helper(mock_cls, svc)
            target = tmp_path / "sub" / "out.bin"
            assert h.download_blob_to_file("c", "b", str(target)) is True
            assert target.read_bytes() == b"hi"

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_download_blob_to_file_failure(self, mock_cls):
        bc = MagicMock(); bc.download_blob.side_effect = RuntimeError("err")
        mc = MagicMock(); mc.get_blob_client.return_value = bc
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with patch("os.makedirs"), patch("builtins.open", mock_open()):
            with pytest.raises(RuntimeError):
                h.download_blob_to_file("c", "b", "/tmpx/out.bin")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_delete_blob_unexpected_error(self, mock_cls):
        bc = MagicMock(); bc.delete_blob.side_effect = RuntimeError("err")
        mc = MagicMock(); mc.get_blob_client.return_value = bc
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.delete_blob("c", "b")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_copy_blob_success_no_metadata(self, mock_cls):
        src = MagicMock(); src.url = "https://x/c/s"
        dst = MagicMock()
        dst.start_copy_from_url.return_value = {"copy_status": "success"}
        svc = MagicMock(); svc.get_blob_client.side_effect = [src, dst]
        h, _ = _make_helper(mock_cls, svc)
        assert h.copy_blob("c1", "s", "c2", "d") is True
        dst.set_blob_metadata.assert_not_called()

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_copy_blob_pending_with_metadata(self, mock_cls):
        src = MagicMock(); src.url = "https://x/c/s"
        dst = MagicMock()
        dst.start_copy_from_url.return_value = {"copy_status": "pending"}
        svc = MagicMock(); svc.get_blob_client.side_effect = [src, dst]
        h, _ = _make_helper(mock_cls, svc)
        assert h.copy_blob("c1", "s", "c2", "d", metadata={"k": "v"}) is True
        dst.set_blob_metadata.assert_called_once_with({"k": "v"})

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_copy_blob_failure(self, mock_cls):
        svc = MagicMock(); svc.get_blob_client.side_effect = RuntimeError("err")
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.copy_blob("c1", "s", "c2", "d")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_move_blob_success(self, mock_cls):
        src = MagicMock(); src.url = "u"
        dst = MagicMock(); dst.start_copy_from_url.return_value = {"copy_status": "success"}
        del_bc = MagicMock()
        mc = MagicMock(); mc.get_blob_client.return_value = del_bc
        svc = MagicMock()
        svc.get_blob_client.side_effect = [src, dst]
        svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        assert h.move_blob("c1", "s", "c2", "d") is True
        del_bc.delete_blob.assert_called_once()

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_move_blob_failure(self, mock_cls):
        svc = MagicMock(); svc.get_blob_client.side_effect = RuntimeError("err")
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.move_blob("c1", "s", "c2", "d")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_blob_exists_unexpected_error(self, mock_cls):
        bc = MagicMock(); bc.get_blob_properties.side_effect = RuntimeError("err")
        mc = MagicMock(); mc.get_blob_client.return_value = bc
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.blob_exists("c", "b")


class TestExtraListing:
    def _blob(self, name, meta=None):
        b = MagicMock()
        b.name = name; b.size = 10; b.last_modified = "t"; b.etag = "e"
        b.content_settings = MagicMock(content_type="text/plain")
        b.blob_tier = "Hot"; b.blob_type = "BlockBlob"; b.metadata = meta
        b.snapshot = None
        return b

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_list_blobs_with_metadata_and_snapshots(self, mock_cls):
        b = self._blob("x", meta={"k": "v"})
        mc = MagicMock(); mc.list_blobs.return_value = [b]
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        out = h.list_blobs("c", include_metadata=True, include_snapshots=True)
        assert out[0]["metadata"] == {"k": "v"}
        # Verify include list contains both
        kwargs = mc.list_blobs.call_args.kwargs
        assert "metadata" in kwargs["include"] and "snapshots" in kwargs["include"]

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_list_blobs_no_content_settings(self, mock_cls):
        b = self._blob("x"); b.content_settings = None
        mc = MagicMock(); mc.list_blobs.return_value = [b]
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        out = h.list_blobs("c")
        assert out[0]["content_type"] is None

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_list_blobs_failure(self, mock_cls):
        mc = MagicMock(); mc.list_blobs.side_effect = RuntimeError("err")
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.list_blobs("c")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_list_blobs_hierarchical_with_prefix(self, mock_cls):
        from libs.sas.storage.blob import helper as helper_mod
        # Create real BlobPrefix subclass instance to satisfy isinstance check
        class _MyPrefix(helper_mod.BlobPrefix):
            pass
        prefix = _MyPrefix()
        prefix.name = "dir/"
        b = MagicMock(spec=[]); b.name = "f.txt"; b.size = 1; b.last_modified = "t"; b.etag = "e"
        b.content_settings = MagicMock(content_type="text/plain")
        b.blob_tier = "Hot"; b.blob_type = "BlockBlob"
        mc = MagicMock(); mc.walk_blobs.return_value = iter([prefix, b])
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        result = h.list_blobs_hierarchical("c", prefix="d")
        assert len(result["prefixes"]) == 1 and result["prefixes"][0]["name"] == "dir/"
        assert len(result["blobs"]) == 1

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_list_blobs_hierarchical_failure(self, mock_cls):
        mc = MagicMock(); mc.walk_blobs.side_effect = RuntimeError("err")
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.list_blobs_hierarchical("c")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_list_blobs_hierarchical_blob_no_content_settings(self, mock_cls):
        b = MagicMock(); b.name = "f.txt"; b.size = 1; b.last_modified = "t"; b.etag = "e"
        b.content_settings = None
        b.blob_tier = "Hot"; b.blob_type = "BlockBlob"
        mc = MagicMock(); mc.walk_blobs.return_value = iter([b])
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        result = h.list_blobs_hierarchical("c")
        assert result["blobs"][0]["content_type"] is None


class TestExtraProperties:
    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_blob_properties_full(self, mock_cls):
        p = MagicMock()
        p.size = 5; p.last_modified = "t"; p.etag = "e"
        p.content_settings = MagicMock(content_type="text/plain", content_encoding="utf-8")
        p.blob_tier = "Hot"; p.blob_type = "BlockBlob"; p.metadata = {"a": "b"}
        p.creation_time = "now"
        p.lease = MagicMock(status="unlocked", state="available")
        bc = MagicMock(); bc.get_blob_properties.return_value = p
        mc = MagicMock(); mc.get_blob_client.return_value = bc
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        out = h.get_blob_properties("c", "b")
        assert out["lease_status"] == "unlocked"
        assert out["content_encoding"] == "utf-8"

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_blob_properties_no_lease_no_settings(self, mock_cls):
        p = MagicMock()
        p.size = 5; p.last_modified = "t"; p.etag = "e"
        p.content_settings = None
        p.blob_tier = "Hot"; p.blob_type = "BlockBlob"; p.metadata = {}
        p.creation_time = "now"; p.lease = None
        bc = MagicMock(); bc.get_blob_properties.return_value = p
        mc = MagicMock(); mc.get_blob_client.return_value = bc
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        out = h.get_blob_properties("c", "b")
        assert out["content_type"] is None and out["lease_status"] is None

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_blob_properties_failure(self, mock_cls):
        bc = MagicMock(); bc.get_blob_properties.side_effect = RuntimeError("err")
        mc = MagicMock(); mc.get_blob_client.return_value = bc
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.get_blob_properties("c", "b")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_set_blob_metadata_failure(self, mock_cls):
        bc = MagicMock(); bc.set_blob_metadata.side_effect = RuntimeError("err")
        mc = MagicMock(); mc.get_blob_client.return_value = bc
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.set_blob_metadata("c", "b", {})


class TestExtraBatch:
    def test_upload_multiple_files(self, tmp_path):
        f1 = tmp_path / "a.txt"; f1.write_text("a")
        f2 = tmp_path / "b.txt"; f2.write_text("b")
        missing = str(tmp_path / "missing.txt")
        with patch("libs.sas.storage.blob.helper.BlobServiceClient") as mock_cls:
            bc = MagicMock(); mc = MagicMock(); mc.get_blob_client.return_value = bc
            svc = MagicMock(); svc.get_container_client.return_value = mc
            h, _ = _make_helper(mock_cls, svc)
            results = h.upload_multiple_files("c", [str(f1), str(f2), missing], blob_prefix="p/")
            assert results[str(f1)] is True
            assert results[missing] is False

    def test_upload_multiple_files_inner_exception(self, tmp_path):
        f1 = tmp_path / "a.txt"; f1.write_text("a")
        with patch("libs.sas.storage.blob.helper.BlobServiceClient") as mock_cls:
            bc = MagicMock(); bc.upload_blob.side_effect = RuntimeError("bad")
            mc = MagicMock(); mc.get_blob_client.return_value = bc
            svc = MagicMock(); svc.get_container_client.return_value = mc
            h, _ = _make_helper(mock_cls, svc)
            results = h.upload_multiple_files("c", [str(f1)])
            assert results[str(f1)] is False

    def test_download_multiple_blobs(self, tmp_path):
        with patch("libs.sas.storage.blob.helper.BlobServiceClient") as mock_cls:
            stream = MagicMock(); stream.readall.return_value = b"x"
            bc = MagicMock(); bc.download_blob.return_value = stream
            mc = MagicMock(); mc.get_blob_client.return_value = bc
            svc = MagicMock(); svc.get_container_client.return_value = mc
            h, _ = _make_helper(mock_cls, svc)
            res = h.download_multiple_blobs("c", ["a.txt", "b.txt"], str(tmp_path))
            assert res["a.txt"] is True and res["b.txt"] is True

    def test_download_multiple_blobs_inner_exception(self, tmp_path):
        with patch("libs.sas.storage.blob.helper.BlobServiceClient") as mock_cls:
            bc = MagicMock(); bc.download_blob.side_effect = RuntimeError("bad")
            mc = MagicMock(); mc.get_blob_client.return_value = bc
            svc = MagicMock(); svc.get_container_client.return_value = mc
            h, _ = _make_helper(mock_cls, svc)
            res = h.download_multiple_blobs("c", ["a.txt"], str(tmp_path))
            assert res["a.txt"] is False

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_delete_multiple_blobs_inner_exception(self, mock_cls):
        bc = MagicMock(); bc.delete_blob.side_effect = RuntimeError("bad")
        mc = MagicMock(); mc.get_blob_client.return_value = bc
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        out = h.delete_multiple_blobs("c", ["a.txt"])
        assert out["a.txt"] is False


class TestExtraSAS:
    @patch("azure.storage.blob.generate_blob_sas")
    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_generate_blob_sas_url_account_key(self, mock_cls, mock_gen):
        svc = MagicMock(); svc.account_name = "acct"
        cred = MagicMock(); cred.account_key = "key"
        svc.credential = cred
        mock_gen.return_value = "sas=token"
        h, _ = _make_helper(mock_cls, svc)
        url = h.generate_blob_sas_url("c", "b", expiry_hours=2, permissions="rwdl")
        assert "acct.blob.core.windows.net" in url and "sas=token" in url

    @patch("azure.storage.blob.generate_blob_sas")
    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_generate_blob_sas_url_user_delegation(self, mock_cls, mock_gen):
        svc = MagicMock(); svc.account_name = "acct"
        cred = MagicMock(spec=[])  # no account_key attr
        type(cred).__name__ = "DefaultAzureCredential"
        svc.credential = cred
        svc.get_user_delegation_key.return_value = MagicMock()
        mock_gen.return_value = "udk=tok"
        h, _ = _make_helper(mock_cls, svc)
        url = h.generate_blob_sas_url("c", "b")
        assert "udk=tok" in url

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_generate_blob_sas_url_no_account_name(self, mock_cls):
        svc = MagicMock(); svc.account_name = None
        cred = MagicMock(spec=[]); svc.credential = cred
        h, _ = _make_helper(mock_cls, svc)
        h._get_account_name = MagicMock(return_value=None)
        with pytest.raises(ValueError, match="account name"):
            h.generate_blob_sas_url("c", "b")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_generate_blob_sas_url_unknown_credential(self, mock_cls):
        svc = MagicMock(); svc.account_name = "acct"; svc.credential = None
        h, _ = _make_helper(mock_cls, svc)
        h._get_account_key = MagicMock(return_value=None)
        h._get_credential_type = MagicMock(return_value="unknown")
        with pytest.raises(ValueError, match="Cannot generate user delegation SAS"):
            h.generate_blob_sas_url("c", "b")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_generate_blob_sas_url_delegation_key_403(self, mock_cls):
        svc = MagicMock(); svc.account_name = "acct"
        cred = MagicMock(spec=[]); svc.credential = cred
        svc.get_user_delegation_key.side_effect = RuntimeError("403 Forbidden")
        h, _ = _make_helper(mock_cls, svc)
        h._get_account_key = MagicMock(return_value=None)
        h._get_credential_type = MagicMock(return_value="DefaultAzureCredential")
        with pytest.raises(ValueError, match="Access denied"):
            h.generate_blob_sas_url("c", "b")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_generate_blob_sas_url_delegation_key_401(self, mock_cls):
        svc = MagicMock(); svc.account_name = "acct"
        cred = MagicMock(spec=[]); svc.credential = cred
        svc.get_user_delegation_key.side_effect = RuntimeError("401 Unauthorized")
        h, _ = _make_helper(mock_cls, svc)
        h._get_account_key = MagicMock(return_value=None)
        h._get_credential_type = MagicMock(return_value="DefaultAzureCredential")
        with pytest.raises(ValueError, match="Authentication failed"):
            h.generate_blob_sas_url("c", "b")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_generate_blob_sas_url_delegation_key_other(self, mock_cls):
        svc = MagicMock(); svc.account_name = "acct"
        cred = MagicMock(spec=[]); svc.credential = cred
        svc.get_user_delegation_key.side_effect = RuntimeError("network")
        h, _ = _make_helper(mock_cls, svc)
        h._get_account_key = MagicMock(return_value=None)
        h._get_credential_type = MagicMock(return_value="DefaultAzureCredential")
        with pytest.raises(ValueError, match="Failed to get user delegation key"):
            h.generate_blob_sas_url("c", "b")

    @patch("azure.storage.blob.generate_container_sas")
    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_generate_container_sas_url_account_key(self, mock_cls, mock_gen):
        svc = MagicMock(); svc.account_name = "acct"
        cred = MagicMock(); cred.account_key = "key"; svc.credential = cred
        mock_gen.return_value = "sas=tok"
        h, _ = _make_helper(mock_cls, svc)
        url = h.generate_container_sas_url("c", permissions="rwdl")
        assert "sas=tok" in url

    @patch("azure.storage.blob.generate_container_sas")
    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_generate_container_sas_url_user_delegation(self, mock_cls, mock_gen):
        svc = MagicMock(); svc.account_name = "acct"
        cred = MagicMock(spec=[]); svc.credential = cred
        svc.get_user_delegation_key.return_value = MagicMock()
        mock_gen.return_value = "udk=tok"
        h, _ = _make_helper(mock_cls, svc)
        url = h.generate_container_sas_url("c")
        assert "udk=tok" in url

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_generate_container_sas_url_no_account_name(self, mock_cls):
        h, _ = _make_helper(mock_cls)
        h._get_account_name = MagicMock(return_value=None)
        with pytest.raises(ValueError, match="account name"):
            h.generate_container_sas_url("c")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_generate_container_sas_url_unknown_credential(self, mock_cls):
        svc = MagicMock(); svc.account_name = "acct"; svc.credential = None
        h, _ = _make_helper(mock_cls, svc)
        h._get_account_key = MagicMock(return_value=None)
        h._get_credential_type = MagicMock(return_value="unknown")
        with pytest.raises(ValueError, match="Cannot generate user delegation SAS"):
            h.generate_container_sas_url("c")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_generate_container_sas_url_delegation_403(self, mock_cls):
        svc = MagicMock(); svc.account_name = "acct"
        cred = MagicMock(spec=[]); svc.credential = cred
        svc.get_user_delegation_key.side_effect = RuntimeError("403 Forbidden")
        h, _ = _make_helper(mock_cls, svc)
        h._get_account_key = MagicMock(return_value=None)
        h._get_credential_type = MagicMock(return_value="DefaultAzureCredential")
        with pytest.raises(ValueError, match="Access denied"):
            h.generate_container_sas_url("c")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_generate_container_sas_url_delegation_401(self, mock_cls):
        svc = MagicMock(); svc.account_name = "acct"
        cred = MagicMock(spec=[]); svc.credential = cred
        svc.get_user_delegation_key.side_effect = RuntimeError("401 Unauthorized")
        h, _ = _make_helper(mock_cls, svc)
        h._get_account_key = MagicMock(return_value=None)
        h._get_credential_type = MagicMock(return_value="DefaultAzureCredential")
        with pytest.raises(ValueError, match="Authentication failed"):
            h.generate_container_sas_url("c")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_generate_container_sas_url_delegation_other(self, mock_cls):
        svc = MagicMock(); svc.account_name = "acct"
        cred = MagicMock(spec=[]); svc.credential = cred
        svc.get_user_delegation_key.side_effect = RuntimeError("oops")
        h, _ = _make_helper(mock_cls, svc)
        h._get_account_key = MagicMock(return_value=None)
        h._get_credential_type = MagicMock(return_value="DefaultAzureCredential")
        with pytest.raises(ValueError, match="Failed to get user delegation key"):
            h.generate_container_sas_url("c")


class TestExtraTierSnapshotSearch:
    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_set_blob_tier_success(self, mock_cls):
        bc = MagicMock(); mc = MagicMock(); mc.get_blob_client.return_value = bc
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        assert h.set_blob_tier("c", "b", StandardBlobTier.Cool) is True
        bc.set_standard_blob_tier.assert_called_once_with(StandardBlobTier.Cool)

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_set_blob_tier_failure(self, mock_cls):
        bc = MagicMock(); bc.set_standard_blob_tier.side_effect = RuntimeError("err")
        mc = MagicMock(); mc.get_blob_client.return_value = bc
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.set_blob_tier("c", "b", StandardBlobTier.Cool)

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_create_snapshot_success(self, mock_cls):
        bc = MagicMock(); bc.create_snapshot.return_value = {"snapshot": "2024-01-01"}
        mc = MagicMock(); mc.get_blob_client.return_value = bc
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        assert h.create_snapshot("c", "b") == "2024-01-01"

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_create_snapshot_failure(self, mock_cls):
        bc = MagicMock(); bc.create_snapshot.side_effect = RuntimeError("err")
        mc = MagicMock(); mc.get_blob_client.return_value = bc
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.create_snapshot("c", "b")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_list_blob_snapshots_success(self, mock_cls):
        b1 = MagicMock(); b1.name = "b"; b1.snapshot = "2024-01-01"
        b1.last_modified = "t"; b1.etag = "e"; b1.size = 1
        b2 = MagicMock(); b2.name = "b"; b2.snapshot = None  # current blob
        b3 = MagicMock(); b3.name = "other"; b3.snapshot = "x"
        mc = MagicMock(); mc.list_blobs.return_value = [b1, b2, b3]
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        out = h.list_blob_snapshots("c", "b")
        assert len(out) == 1 and out[0]["snapshot"] == "2024-01-01"

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_list_blob_snapshots_failure(self, mock_cls):
        mc = MagicMock(); mc.list_blobs.side_effect = RuntimeError("err")
        svc = MagicMock(); svc.get_container_client.return_value = mc
        h, _ = _make_helper(mock_cls, svc)
        with pytest.raises(RuntimeError):
            h.list_blob_snapshots("c", "b")

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_search_blobs_by_name_and_metadata(self, mock_cls):
        h, _ = _make_helper(mock_cls)
        h.list_blobs = MagicMock(return_value=[
            {"name": "FooBar", "metadata": {"k": "VALUE"}},
            {"name": "other", "metadata": {"k": "matched-value"}},
            {"name": "skip", "metadata": {"k": "nope"}},
        ])
        out = h.search_blobs("c", "value", search_in_metadata=True)
        names = {b["name"] for b in out}
        assert "other" in names

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_search_blobs_failure(self, mock_cls):
        h, _ = _make_helper(mock_cls)
        h.list_blobs = MagicMock(side_effect=RuntimeError("err"))
        with pytest.raises(RuntimeError):
            h.search_blobs("c", "x")


class TestExtraSyncDirectory:
    def test_sync_directory_missing_source(self):
        with patch("libs.sas.storage.blob.helper.BlobServiceClient") as mock_cls:
            h, _ = _make_helper(mock_cls)
            with pytest.raises(FileNotFoundError):
                h.sync_directory("/no/such/dir", "c")

    def test_sync_directory_uploads_and_skips(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "skip.tmp").write_text("s")
        with patch("libs.sas.storage.blob.helper.BlobServiceClient") as mock_cls:
            h, _ = _make_helper(mock_cls)
            h.blob_exists = MagicMock(return_value=False)
            h.upload_file = MagicMock(return_value=True)
            out = h.sync_directory(str(tmp_path), "c", exclude_patterns=["*.tmp"])
            assert "a.txt" in out["uploaded"]
            assert "skip.tmp" in out["skipped"]

    def test_sync_directory_existing_blob_newer_skips(self, tmp_path):
        f = tmp_path / "a.txt"; f.write_text("a")
        with patch("libs.sas.storage.blob.helper.BlobServiceClient") as mock_cls:
            h, _ = _make_helper(mock_cls)
            future = _dt.datetime.utcnow() + _dt.timedelta(days=10)
            h.blob_exists = MagicMock(return_value=True)
            h.get_blob_properties = MagicMock(return_value={"last_modified": future})
            h.upload_file = MagicMock(return_value=True)
            out = h.sync_directory(str(tmp_path), "c")
            assert "a.txt" in out["skipped"]

    def test_sync_directory_upload_fail(self, tmp_path):
        f = tmp_path / "a.txt"; f.write_text("a")
        with patch("libs.sas.storage.blob.helper.BlobServiceClient") as mock_cls:
            h, _ = _make_helper(mock_cls)
            h.blob_exists = MagicMock(return_value=False)
            h.upload_file = MagicMock(return_value=False)
            out = h.sync_directory(str(tmp_path), "c")
            assert any("Failed" in e for e in out["errors"])

    def test_sync_directory_inner_exception(self, tmp_path):
        f = tmp_path / "a.txt"; f.write_text("a")
        with patch("libs.sas.storage.blob.helper.BlobServiceClient") as mock_cls:
            h, _ = _make_helper(mock_cls)
            h.blob_exists = MagicMock(side_effect=RuntimeError("err"))
            out = h.sync_directory(str(tmp_path), "c")
            assert any("Error" in e for e in out["errors"])


class TestExtraInternals:
    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_account_key_from_credential(self, mock_cls):
        svc = MagicMock()
        svc.credential = MagicMock(); svc.credential.account_key = "abc"
        h, _ = _make_helper(mock_cls, svc)
        assert h._get_account_key() == "abc"

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_account_key_from_connection_string(self, mock_cls):
        svc = MagicMock(spec=[])  # no credential
        mock_cls.from_connection_string.return_value = svc
        h = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;AccountKey=mykey;Foo=bar")
        assert h._get_account_key() == "mykey"

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_account_key_returns_none_when_no_match(self, mock_cls):
        svc = MagicMock(spec=[])
        mock_cls.from_connection_string.return_value = svc
        h = StorageBlobHelper(connection_string="DefaultEndpointsProtocol=https;Foo=bar")
        # spec=[] means hasattr credential is False; no AccountKey in conn str -> None
        assert h._get_account_key() is None

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_account_name_failure_returns_none(self, mock_cls):
        svc = MagicMock()
        type(svc).account_name = property(lambda self: (_ for _ in ()).throw(RuntimeError("x")))
        mock_cls.from_connection_string.return_value = svc
        h = StorageBlobHelper(connection_string="x")
        assert h._get_account_name() is None

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_credential_type_variants(self, mock_cls):
        svc = MagicMock(); h, _ = _make_helper(mock_cls, svc)
        for cls_name, expected in [
            ("StorageSharedKeyCredential", "Storage Account Key"),
            ("DefaultAzureCredential", "DefaultAzureCredential"),
            ("ManagedIdentityCredential", "Managed Identity"),
            ("AzureCliCredential", "Azure CLI"),
            ("EnvironmentCredential", "Environment Variables"),
            ("WorkloadIdentityCredential", "Workload Identity"),
            ("ChainedTokenCredential", "Chained Token Credential"),
        ]:
            cred = MagicMock()
            type(cred).__name__ = cls_name
            svc.credential = cred
            assert h._get_credential_type() == expected

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_credential_type_other_known(self, mock_cls):
        svc = MagicMock(); h, _ = _make_helper(mock_cls, svc)
        cred = MagicMock(); type(cred).__name__ = "WeirdCredential"
        svc.credential = cred
        assert "Azure AD" in h._get_credential_type()

    @patch("libs.sas.storage.blob.helper.BlobServiceClient")
    def test_get_credential_type_no_credential(self, mock_cls):
        svc = MagicMock(); svc.credential = None
        h, _ = _make_helper(mock_cls, svc)
        assert h._get_credential_type() == "unknown"
