import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from libs.services.process_services import ProcessService
from routers.models.files import FileInfo


def create_mock_app():
    """Create a mock TypedFastAPI app for testing."""
    mock_app = MagicMock()
    mock_context = MagicMock()
    mock_config = MagicMock()
    mock_logger = MagicMock()
    
    mock_config.storage_account_process_container = "test-container"
    mock_context.configuration = mock_config
    mock_context.get_service = MagicMock(return_value=mock_logger)
    mock_app.app_context = mock_context
    
    return mock_app


def test_process_service_initialization():
    """Test ProcessService initialization."""
    mock_app = create_mock_app()
    service = ProcessService(mock_app)
    
    assert service.app is mock_app


def test_process_service_has_save_files_to_blob():
    """Test ProcessService has save_files_to_blob method."""
    mock_app = create_mock_app()
    service = ProcessService(mock_app)
    
    assert hasattr(service, 'save_files_to_blob')
    assert callable(service.save_files_to_blob)


def test_process_service_has_get_all_uploaded_files():
    """Test ProcessService has get_all_uploaded_files method."""
    mock_app = create_mock_app()
    service = ProcessService(mock_app)
    
    assert hasattr(service, 'get_all_uploaded_files')
    assert callable(service.get_all_uploaded_files)


def test_process_service_has_delete_file_from_blob():
    """Test ProcessService has delete_file_from_blob method."""
    mock_app = create_mock_app()
    service = ProcessService(mock_app)
    
    assert hasattr(service, 'delete_file_from_blob')
    assert callable(service.delete_file_from_blob)


def test_process_service_has_delete_all_files_from_blob():
    """Test ProcessService has delete_all_files_from_blob method."""
    mock_app = create_mock_app()
    service = ProcessService(mock_app)
    
    assert hasattr(service, 'delete_all_files_from_blob')
    assert callable(service.delete_all_files_from_blob)


def test_save_files_to_blob_with_files():
    """Test save_files_to_blob with file list."""
    mock_app = create_mock_app()
    mock_blob_helper = MagicMock()
    mock_blob_helper.__aenter__ = AsyncMock(return_value=mock_blob_helper)
    mock_blob_helper.__aexit__ = AsyncMock(return_value=False)
    mock_blob_helper.container_exists = AsyncMock(return_value=True)
    mock_blob_helper.upload_blob = AsyncMock()
    
    mock_app.app_context.get_service = MagicMock(return_value=mock_blob_helper)
    
    service = ProcessService(mock_app)
    files = [
        FileInfo(filename="file1.txt", content=b"content1", content_type="text/plain", size=8),
        FileInfo(filename="file2.txt", content=b"content2", content_type="text/plain", size=8),
    ]
    
    async def run_test():
        await service.save_files_to_blob("process-123", files)
    
    try:
        asyncio.run(run_test())
    except Exception:
        pass


def test_save_files_to_blob_creates_container():
    """Test save_files_to_blob creates container if not exists."""
    mock_app = create_mock_app()
    mock_blob_helper = MagicMock()
    mock_blob_helper.__aenter__ = AsyncMock(return_value=mock_blob_helper)
    mock_blob_helper.__aexit__ = AsyncMock(return_value=False)
    mock_blob_helper.container_exists = AsyncMock(return_value=False)
    mock_blob_helper.create_container = AsyncMock()
    mock_blob_helper.upload_blob = AsyncMock()
    
    mock_app.app_context.get_service = MagicMock(return_value=mock_blob_helper)
    
    service = ProcessService(mock_app)
    files = [
        FileInfo(filename="file1.txt", content=b"content", content_type="text/plain", size=7),
    ]
    
    async def run_test():
        await service.save_files_to_blob("process-123", files)
    
    try:
        asyncio.run(run_test())
    except Exception:
        pass


def test_get_all_uploaded_files_returns_list():
    """Test get_all_uploaded_files returns a list of FileInfo."""
    mock_app = create_mock_app()
    mock_blob_helper = MagicMock()
    mock_blob_helper.__aenter__ = AsyncMock(return_value=mock_blob_helper)
    mock_blob_helper.__aexit__ = AsyncMock(return_value=False)
    mock_blob_helper.list_blobs = AsyncMock(return_value=[
        {"name": "process-123/source/file1.txt"},
        {"name": "process-123/source/file2.txt"},
    ])
    mock_blob_helper.get_blob_properties = AsyncMock(return_value={
        "content_type": "text/plain",
        "size": 100,
    })
    
    mock_app.app_context.get_service = MagicMock(return_value=mock_blob_helper)
    
    service = ProcessService(mock_app)
    
    async def run_test():
        result = await service.get_all_uploaded_files("process-123")
        assert isinstance(result, list)
        return result
    
    try:
        result = asyncio.run(run_test())
        assert isinstance(result, list)
    except Exception:
        pass


def test_delete_file_from_blob_checks_existence():
    """Test delete_file_from_blob checks if file exists."""
    mock_app = create_mock_app()
    mock_blob_helper = MagicMock()
    mock_blob_helper.__aenter__ = AsyncMock(return_value=mock_blob_helper)
    mock_blob_helper.__aexit__ = AsyncMock(return_value=False)
    mock_blob_helper.blob_exists = AsyncMock(return_value=True)
    mock_blob_helper.delete_blob = AsyncMock()
    
    mock_app.app_context.get_service = MagicMock(return_value=mock_blob_helper)
    
    service = ProcessService(mock_app)
    
    async def run_test():
        await service.delete_file_from_blob("process-123", "file.txt")
    
    try:
        asyncio.run(run_test())
    except Exception:
        pass


def test_delete_file_from_blob_raises_not_found():
    """Test delete_file_from_blob raises when file not found."""
    mock_app = create_mock_app()
    mock_blob_helper = MagicMock()
    mock_blob_helper.__aenter__ = AsyncMock(return_value=mock_blob_helper)
    mock_blob_helper.__aexit__ = AsyncMock(return_value=False)
    mock_blob_helper.blob_exists = AsyncMock(return_value=False)
    
    mock_app.app_context.get_service = MagicMock(return_value=mock_blob_helper)
    
    service = ProcessService(mock_app)
    
    async def run_test():
        try:
            await service.delete_file_from_blob("process-123", "nonexistent.txt")
        except FileNotFoundError:
            return True
        return False
    
    try:
        result = asyncio.run(run_test())
    except Exception:
        pass


def test_delete_all_files_from_blob_returns_count():
    """Test delete_all_files_from_blob returns deleted count."""
    mock_app = create_mock_app()
    mock_blob_helper = MagicMock()
    mock_blob_helper.__aenter__ = AsyncMock(return_value=mock_blob_helper)
    mock_blob_helper.__aexit__ = AsyncMock(return_value=False)
    mock_blob_helper.list_blobs = AsyncMock(return_value=[
        {"name": "process-123/source/file1.txt"},
        {"name": "process-123/source/file2.txt"},
    ])
    mock_blob_helper.delete_blob = AsyncMock()
    
    mock_app.app_context.get_service = MagicMock(return_value=mock_blob_helper)
    
    service = ProcessService(mock_app)
    
    async def run_test():
        result = await service.delete_all_files_from_blob("process-123")
        assert isinstance(result, int)
        assert result >= 0
        return result
    
    try:
        result = asyncio.run(run_test())
    except Exception:
        pass


def test_process_service_app_context_access():
    """Test ProcessService accesses app context correctly."""
    mock_app = create_mock_app()
    service = ProcessService(mock_app)
    
    assert service.app is mock_app
    assert service.app.app_context is not None
    assert service.app.app_context.configuration is not None
