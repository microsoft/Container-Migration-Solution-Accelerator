"""
Unit tests for the router_process module.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import UUID
from fastapi import HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
import zipfile
import io

from app.routers.router_process import (
    create, status, render_status, upload_files, delete_file,
    delete_process, start_processing, download_process_files,
    get_process_summary, get_file_content
)
from libs.models.entities import Process
from routers.models.processes import ProcessCreateResponse
from routers.models.files import FileInfo
from libs.services.interfaces import ILoggerService
from libs.services.process_services import ProcessService
from libs.repositories.process_repository import ProcessRepository


class TestRouterProcessBase:
    """Base test class with common fixtures and setup."""

    @pytest.fixture(autouse=True)
    def setup_common_mocks(self):
        """Setup common mocks for all tests."""
        with patch('app.routers.router_process.get_authenticated_user') as mock_auth:
            # Setup authenticated user
            self.authenticated_user = Mock()
            self.authenticated_user.user_principal_id = "test-user-123"
            mock_auth.return_value = self.authenticated_user
            yield

    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request with mocked services."""
        request = Mock(spec=Request)
        request.app = Mock()
        request.app.app_context = Mock()
        
        # Mock logger service
        self.logger_service = Mock(spec=ILoggerService)
        
        # Mock process service
        self.process_service = Mock(spec=ProcessService)
        self.process_service.render_current_process = AsyncMock()
        self.process_service.process_enqueue = AsyncMock()
        
        # Mock process repository  
        self.process_repository = Mock(spec=ProcessRepository)
        self.process_repository.add_async = AsyncMock()
        
        # Setup get_service to return our mocks
        def get_service_mock(service_type):
            if service_type == ILoggerService or str(service_type).endswith('ILoggerService'):
                return self.logger_service
            elif service_type == ProcessService or str(service_type).endswith('ProcessService'):
                return self.process_service
            elif service_type == ProcessRepository or str(service_type).endswith('ProcessRepository'):
                return self.process_repository
            return Mock()
        
        request.app.app_context.get_service.side_effect = get_service_mock
        
        # Setup scope for create endpoint with proper context manager mocking
        async def create_mock_scope():
            return self.process_repository
            
        mock_scope = Mock()
        mock_scope.__aenter__ = AsyncMock(return_value=mock_scope)  
        mock_scope.__aexit__ = AsyncMock(return_value=None)
        mock_scope.get_service = Mock(return_value=self.process_repository)
        request.app.app_context.create_scope.return_value = mock_scope
        
        return request

    @pytest.fixture
    def mock_response(self):
        """Create a mock FastAPI response."""
        response = Mock(spec=Response)
        response.headers = {}  # Make headers assignable
        return response

    @pytest.fixture
    def sample_upload_file(self):
        """Create a sample upload file mock."""
        file_mock = Mock(spec=UploadFile)
        file_mock.filename = "test.yaml"
        file_mock.content_type = "text/yaml"
        file_mock.read = AsyncMock(return_value=b"test content")
        file_mock.seek = AsyncMock()
        return file_mock


class TestCreateEndpoint(TestRouterProcessBase):
    """Test cases for the create endpoint."""

    @pytest.mark.asyncio
    async def test_create_success(self, mock_request):
        """Test successful process creation."""
        with patch('app.routers.router_process.uuid4', return_value=UUID('12345678-1234-5678-9012-123456789012')):
            result = await create(mock_request)

        # Verify result
        assert isinstance(result, ProcessCreateResponse)
        assert result.process_id == '12345678-1234-5678-9012-123456789012'
        
        # Verify repository was called
        self.process_repository.add_async.assert_called_once()
        added_process = self.process_repository.add_async.call_args[0][0]
        assert isinstance(added_process, Process)
        assert added_process.user_id == "test-user-123"

    @pytest.mark.asyncio
    async def test_create_user_not_authenticated(self, mock_request):
        """Test create endpoint when user is not authenticated."""
        with patch('app.routers.router_process.get_authenticated_user') as mock_auth:
            mock_auth.return_value.user_principal_id = None
            
            with pytest.raises(HTTPException) as exc_info:
                await create(mock_request)
            
            assert exc_info.value.status_code == 401
            assert "User not authenticated" in str(exc_info.value.detail)

    @pytest.mark.asyncio 
    async def test_create_exception_handling(self, mock_request):
        """Test create endpoint exception handling."""
        # Mock scope that raises exception
        mock_request.app.app_context.create_scope.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await create(mock_request)
        
        assert exc_info.value.status_code == 500
        assert "Internal server error" in str(exc_info.value.detail)


class TestStatusEndpoint(TestRouterProcessBase):
    """Test cases for the status endpoint."""

    @pytest.mark.asyncio
    async def test_status_success(self, mock_request):
        """Test successful status retrieval."""
        process_id = "test-process-123"
        expected_status = {"status": "running", "phase": "migration"}
        
        self.process_service.get_current_process.return_value = expected_status

        result = await status(process_id, mock_request)

        assert result == expected_status
        self.logger_service.log_info.assert_called_with(
            f"Process router status endpoint called for process_id: {process_id}"
        )
        self.process_service.get_current_process.assert_called_once_with(process_id)


class TestRenderStatusEndpoint(TestRouterProcessBase):
    """Test cases for the render status endpoint."""

    @pytest.mark.asyncio
    async def test_render_status_success(self, mock_request):
        """Test successful render status retrieval."""
        process_id = "test-render-123"
        expected_html = "<html><body>Status content</body></html>"
        
        self.process_service.render_current_process.return_value = expected_html

        result = await render_status(process_id, mock_request)

        assert result == expected_html
        self.logger_service.log_info.assert_called()
        self.process_service.render_current_process.assert_called_once_with(process_id)


class TestUploadFilesEndpoint(TestRouterProcessBase):
    """Test cases for the upload files endpoint."""

    @pytest.mark.asyncio
    async def test_upload_files_success(self, mock_request, mock_response, sample_upload_file):
        """Test successful file upload."""
        process_id = "test-upload-process"
        files = [sample_upload_file]

        # Mock get_all_uploaded_files to return uploaded files
        self.process_service.get_all_uploaded_files.return_value = [
            FileInfo(filename="test.yaml", content=b"test content", content_type="text/yaml", size=12)
        ]

        result = await upload_files(process_id, files, mock_request, mock_response)

        assert result.message == "Files uploaded successfully"
        assert result.process_id == process_id
        assert len(result.files) == 1
        self.logger_service.log_info.assert_called()

    @pytest.mark.asyncio
    async def test_upload_files_skip_unnamed_files(self, mock_request, mock_response):
        """Test that files without names are skipped."""
        process_id = "test-process"

        # Create file without filename
        unnamed_file = Mock(spec=UploadFile)
        unnamed_file.filename = None

        named_file = Mock(spec=UploadFile)
        named_file.filename = "test.yaml"
        named_file.content_type = "text/yaml"
        named_file.read = AsyncMock(return_value=b"content")
        named_file.seek = AsyncMock()
    
        files = [unnamed_file, named_file]
        self.process_service.get_all_uploaded_files.return_value = []

        await upload_files(process_id, files, mock_request, mock_response)

        # Verify only named file was processed (read called)
        unnamed_file.read.assert_not_called()
        named_file.read.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_files_no_files_provided(self, mock_request, mock_response):
        """Test upload files with no files provided."""
        process_id = "test-process"
        files = []

        with pytest.raises(HTTPException) as exc_info:
            await upload_files(process_id, files, mock_request, mock_response)
        
        assert exc_info.value.status_code == 500
        assert "Error uploading files: 400: No files provided" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_upload_files_no_process_id(self, mock_request, mock_response, sample_upload_file):
        """Test upload files with no process_id provided."""
        process_id = ""
        files = [sample_upload_file]

        with pytest.raises(HTTPException) as exc_info:
            await upload_files(process_id, files, mock_request, mock_response)
        
        assert exc_info.value.status_code == 500
        assert "Error uploading files: 400: Process ID is required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_upload_files_user_not_authenticated(self, mock_request, mock_response, sample_upload_file):
        """Test upload files when user is not authenticated."""
        process_id = "test-process"
        files = [sample_upload_file]

        with patch('app.routers.router_process.get_authenticated_user') as mock_auth:
            mock_auth.return_value.user_principal_id = None
            
            with pytest.raises(HTTPException) as exc_info:
                await upload_files(process_id, files, mock_request, mock_response)
            
            assert exc_info.value.status_code == 500
            assert "Error uploading files: 401: User not authenticated" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_upload_files_exception_handling(self, mock_request, mock_response, sample_upload_file):
        """Test upload files general exception handling."""
        process_id = "test-process"
        files = [sample_upload_file]

        # Mock service to raise exception
        self.process_service.save_files_to_blob.side_effect = Exception("Storage error")
        
        with pytest.raises(HTTPException) as exc_info:
            await upload_files(process_id, files, mock_request, mock_response)
        
        assert exc_info.value.status_code == 500
        assert "Error uploading files" in str(exc_info.value.detail)


class TestDeleteFileEndpoint(TestRouterProcessBase):
    """Test cases for the delete file endpoint."""

    @pytest.mark.asyncio
    async def test_delete_file_success(self, mock_request, mock_response):
        """Test successful file deletion."""
        file_name = "test.yaml"
        process_id = "test-process"

        # Mock remaining files after deletion
        self.process_service.get_all_uploaded_files.return_value = []

        result = await delete_file(file_name, process_id, mock_request, mock_response)

        assert result.message == "File deleted successfully"
        assert result.process_id == process_id
        assert len(result.files) == 0
        self.logger_service.log_info.assert_called()

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, mock_request, mock_response):
        """Test delete file when file not found."""
        file_name = "nonexistent.yaml"
        process_id = "test-process"

        # Mock service to raise FileNotFoundError
        self.process_service.delete_file_from_blob.side_effect = FileNotFoundError()
        
        with pytest.raises(HTTPException) as exc_info:
            await delete_file(file_name, process_id, mock_request, mock_response)
        
        assert exc_info.value.status_code == 404
        assert "nonexistent.yaml' not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_delete_file_no_process_id(self, mock_request, mock_response):
        """Test delete file with no process_id provided."""
        file_name = "test.yaml"
        process_id = ""

        with pytest.raises(HTTPException) as exc_info:
            await delete_file(file_name, process_id, mock_request, mock_response)
        
        assert exc_info.value.status_code == 500
        assert "Error deleting file: 400: Process ID is required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_file_no_file_name(self, mock_request, mock_response):
        """Test delete file with no file_name provided."""
        file_name = ""
        process_id = "test-process"

        with pytest.raises(HTTPException) as exc_info:
            await delete_file(file_name, process_id, mock_request, mock_response)
        
        assert exc_info.value.status_code == 500
        assert "Error deleting file: 400: File name is required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_file_user_not_authenticated(self, mock_request, mock_response):
        """Test delete file when user is not authenticated."""
        file_name = "test.yaml"
        process_id = "test-process"

        with patch('app.routers.router_process.get_authenticated_user') as mock_auth:
            mock_auth.return_value.user_principal_id = None
            
            with pytest.raises(HTTPException) as exc_info:
                await delete_file(file_name, process_id, mock_request, mock_response)
            
            assert exc_info.value.status_code == 500
            assert "Error deleting file: 401: User not authenticated" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_file_general_exception(self, mock_request, mock_response):
        """Test delete file general exception handling."""
        file_name = "test.yaml"
        process_id = "test-process"

        # Mock service to raise general exception
        self.process_service.delete_file_from_blob.side_effect = Exception("Storage error")
        
        with pytest.raises(HTTPException) as exc_info:
            await delete_file(file_name, process_id, mock_request, mock_response)
        
        assert exc_info.value.status_code == 500
        assert "Error deleting file" in str(exc_info.value.detail)


class TestDeleteProcessEndpoint(TestRouterProcessBase):
    """Test cases for the delete process endpoint."""

    @pytest.mark.asyncio
    async def test_delete_process_success(self, mock_request, mock_response):
        """Test successful process deletion."""
        process_id = "test-process"

        # Mock deletion count
        self.process_service.delete_all_files_from_blob.return_value = 3

        result = await delete_process(process_id, mock_request, mock_response)

        assert "All files deleted successfully" in result.message
        assert result.process_id == process_id
        self.logger_service.log_info.assert_called()

    @pytest.mark.asyncio
    async def test_delete_process_no_process_id(self, mock_request, mock_response):
        """Test delete process with no process_id provided."""
        process_id = ""

        with pytest.raises(HTTPException) as exc_info:
            await delete_process(process_id, mock_request, mock_response)
        
        assert exc_info.value.status_code == 500
        assert "Error deleting process: 400: Process ID is required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_process_user_not_authenticated(self, mock_request, mock_response):
        """Test delete process when user is not authenticated."""
        process_id = "test-process"

        with patch('app.routers.router_process.get_authenticated_user') as mock_auth:
            mock_auth.return_value.user_principal_id = None
            
            with pytest.raises(HTTPException) as exc_info:
                await delete_process(process_id, mock_request, mock_response)
            
            assert exc_info.value.status_code == 500
            assert "Error deleting process: 401: User not authenticated" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_process_general_exception(self, mock_request, mock_response):
        """Test delete process general exception handling."""
        process_id = "test-process"

        # Mock service to raise exception
        self.process_service.delete_all_files_from_blob.side_effect = Exception("Storage error")
        
        with pytest.raises(HTTPException) as exc_info:
            await delete_process(process_id, mock_request, mock_response)
        
        assert exc_info.value.status_code == 500
        assert "Error deleting process" in str(exc_info.value.detail)


class TestStartProcessingEndpoint(TestRouterProcessBase):
    """Test cases for the start processing endpoint."""

    @pytest.mark.asyncio
    async def test_start_processing_success(self, mock_request, mock_response):
        """Test successful processing start."""
        process_id = "test-process"

        result = await start_processing(process_id, mock_request, mock_response)

        assert result["message"] == "Processing started successfully"
        assert result["process_id"] == process_id
        assert result["status"] == "queued"
        self.logger_service.log_info.assert_called()
        self.process_service.process_enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_processing_no_process_id(self, mock_request, mock_response):
        """Test start processing with no process_id provided."""
        process_id = ""

        with pytest.raises(HTTPException) as exc_info:
            await start_processing(process_id, mock_request, mock_response)
        
        assert exc_info.value.status_code == 500
        assert "Error starting processing: 400: Process ID is required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_start_processing_user_not_authenticated(self, mock_request, mock_response):
        """Test start processing when user is not authenticated."""
        process_id = "test-process"

        with patch('app.routers.router_process.get_authenticated_user') as mock_auth:
            mock_auth.return_value.user_principal_id = None
            
            with pytest.raises(HTTPException) as exc_info:
                await start_processing(process_id, mock_request, mock_response)
            
            assert exc_info.value.status_code == 500
            assert "Error starting processing: 401: User not authenticated" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_start_processing_general_exception(self, mock_request, mock_response):
        """Test start processing general exception handling."""
        process_id = "test-process"

        # Mock service to raise exception
        self.process_service.process_enqueue.side_effect = Exception("Queue error")
        
        with pytest.raises(HTTPException) as exc_info:
            await start_processing(process_id, mock_request, mock_response)
        
        assert exc_info.value.status_code == 500
        assert "Error starting processing" in str(exc_info.value.detail)


class TestDownloadProcessFilesEndpoint(TestRouterProcessBase):
    """Test cases for the download process files endpoint."""

    @pytest.mark.asyncio
    async def test_download_process_files_success(self, mock_request):
        """Test successful file download."""
        process_id = "test-process"

        # Mock converted files
        mock_files = [
            FileInfo(filename="converted1.yaml", content=b"converted content 1", content_type="text/yaml", size=18),
            FileInfo(filename="converted2.yaml", content=b"converted content 2", content_type="text/yaml", size=18),
        ]
        self.process_service.get_converted_files.return_value = mock_files

        result = await download_process_files(process_id, mock_request)

        assert isinstance(result, StreamingResponse)
        assert result.headers["content-disposition"] == f"attachment; filename=process_{process_id}_converted.zip"

    @pytest.mark.asyncio
    async def test_download_process_files_no_files(self, mock_request):
        """Test download when no converted files exist."""
        process_id = "empty-process"

        # Mock no converted files
        self.process_service.get_converted_files.return_value = []

        with pytest.raises(HTTPException) as exc_info:
            await download_process_files(process_id, mock_request)
        
        assert exc_info.value.status_code == 404
        assert "No converted files found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_download_process_files_user_not_authenticated(self, mock_request):
        """Test download when user is not authenticated."""
        process_id = "test-process"

        with patch('app.routers.router_process.get_authenticated_user') as mock_auth:
            mock_auth.return_value.user_principal_id = None
            
            with pytest.raises(HTTPException) as exc_info:
                await download_process_files(process_id, mock_request)
            
            assert exc_info.value.status_code == 401
            assert "User not authenticated" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_download_process_files_general_exception(self, mock_request):
        """Test download general exception handling."""
        process_id = "test-process"

        # Mock service to raise exception
        self.process_service.get_converted_files.side_effect = Exception("Storage error")
        
        with pytest.raises(HTTPException) as exc_info:
            await download_process_files(process_id, mock_request)
        
        assert exc_info.value.status_code == 500
        assert "Error downloading files" in str(exc_info.value.detail)


class TestGetProcessSummaryEndpoint(TestRouterProcessBase):
    """Test cases for the get process summary endpoint."""

    @pytest.mark.asyncio
    async def test_get_process_summary_success(self, mock_request):
        """Test successful process summary retrieval."""
        process_id = "test-process"

        # Mock process entity and filenames
        mock_process = Mock()
        mock_process.id = process_id
        mock_process.created_at = "2024-01-01T10:00:00Z"

        mock_filenames = ["file1.yaml", "file2.yaml"]
        self.process_service.get_process_summary.return_value = (mock_process, mock_filenames)
        
        result = await get_process_summary(process_id, mock_request)

        assert result.Process.process_id == process_id
        assert len(result.files) == len(mock_filenames)
        self.logger_service.log_info.assert_called()

    @pytest.mark.asyncio
    async def test_get_process_summary_user_not_authenticated(self, mock_request):
        """Test get process summary when user is not authenticated."""
        process_id = "test-process"

        with patch('app.routers.router_process.get_authenticated_user') as mock_auth:
            mock_auth.return_value.user_principal_id = None
            
            with pytest.raises(HTTPException) as exc_info:
                await get_process_summary(process_id, mock_request)
            
            assert exc_info.value.status_code == 401
            assert "User not authenticated" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_process_summary_general_exception(self, mock_request):
        """Test get process summary general exception handling."""
        process_id = "test-process"

        # Mock service to raise exception
        self.process_service.get_process_summary.side_effect = Exception("Database error")
        
        with pytest.raises(HTTPException) as exc_info:
            await get_process_summary(process_id, mock_request)
        
        assert exc_info.value.status_code == 500
        assert "Error retrieving process summary" in str(exc_info.value.detail)


class TestGetFileContentEndpoint(TestRouterProcessBase):
    """Test cases for the get file content endpoint."""

    @pytest.mark.asyncio
    async def test_get_file_content_success(self, mock_request):
        """Test successful file content retrieval."""
        process_id = "test-process"
        filename = "test.yaml"
        expected_content = "test file content"

        self.process_service.get_converted_file_content.return_value = expected_content
        
        result = await get_file_content(process_id, filename, mock_request)

        assert result.content == expected_content
        self.logger_service.log_info.assert_called()

    @pytest.mark.asyncio
    async def test_get_file_content_file_not_found(self, mock_request):
        """Test get file content when file not found."""
        process_id = "test-process"
        filename = "nonexistent.yaml"

        self.process_service.get_converted_file_content.side_effect = FileNotFoundError()
        
        with pytest.raises(HTTPException) as exc_info:
            await get_file_content(process_id, filename, mock_request)
        
        assert exc_info.value.status_code == 404
        assert "nonexistent.yaml' not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_file_content_unicode_decode_error(self, mock_request):
        """Test get file content with unicode decode error."""
        process_id = "test-process"  
        filename = "binary.bin"

        self.process_service.get_converted_file_content.side_effect = UnicodeDecodeError(
            'utf-8', b'', 0, 1, 'invalid start byte'
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_file_content(process_id, filename, mock_request)
        
        assert exc_info.value.status_code == 400
        assert "not a text file" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_file_content_user_not_authenticated(self, mock_request):
        """Test get file content when user is not authenticated."""
        process_id = "test-process"
        filename = "test.yaml"

        with patch('app.routers.router_process.get_authenticated_user') as mock_auth:
            mock_auth.return_value.user_principal_id = None
            
            with pytest.raises(HTTPException) as exc_info:
                await get_file_content(process_id, filename, mock_request)
            
            assert exc_info.value.status_code == 401
            assert "User not authenticated" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_file_content_http_exception_passthrough(self, mock_request):
        """Test get file content HTTP exception passthrough."""
        process_id = "test-process"
        filename = "test.yaml"

        # Mock service to raise HTTPException
        http_exc = HTTPException(status_code=403, detail="Access denied")
        self.process_service.get_converted_file_content.side_effect = http_exc
        
        with pytest.raises(HTTPException) as exc_info:
            await get_file_content(process_id, filename, mock_request)
        
        assert exc_info.value.status_code == 403
        assert "Access denied" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_file_content_general_exception(self, mock_request):
        """Test get file content general exception handling."""
        process_id = "test-process"
        filename = "test.yaml"

        # Mock service to raise general exception
        self.process_service.get_converted_file_content.side_effect = Exception("Storage error")
        
        with pytest.raises(HTTPException) as exc_info:
            await get_file_content(process_id, filename, mock_request)
        
        assert exc_info.value.status_code == 500
        assert "Error retrieving file content" in str(exc_info.value.detail)


class TestIntegrationScenarios(TestRouterProcessBase):
    """Integration test scenarios combining multiple endpoints."""

    @pytest.mark.asyncio
    async def test_full_workflow_create_upload_start_process(self, mock_request, mock_response, sample_upload_file):
        """Test a full workflow: create -> upload -> start processing."""
        self.process_service.get_all_uploaded_files.return_value = [
            FileInfo(filename="test.yaml", content=b"content", content_type="text/yaml", size=7)
        ]

        with patch('app.routers.router_process.uuid4', return_value=UUID('12345678-1234-5678-9012-123456789012')):
            # Step 1: Create process
            create_result = await create(mock_request)
            assert isinstance(create_result, ProcessCreateResponse)
            assert create_result.process_id == '12345678-1234-5678-9012-123456789012'

            # Step 2: Upload files
            upload_result = await upload_files(create_result.process_id, [sample_upload_file], mock_request, mock_response)
            assert upload_result.message == "Files uploaded successfully"

            # Step 3: Start processing
            start_result = await start_processing(create_result.process_id, mock_request, mock_response)
            assert start_result["message"] == "Processing started successfully"

        # Verify all services were called
        self.process_repository.add_async.assert_called_once()
        self.process_service.save_files_to_blob.assert_called_once()
        self.process_service.process_enqueue.assert_called_once()


# Additional tests for router configuration
class TestRouterConfiguration:
    """Test router configuration and file info model."""
    
    def test_file_info_model_creation(self):
        """Test FileInfo model creation."""
        file_info = FileInfo(
            filename="test.yaml",
            content=b"test content", 
            content_type="text/yaml",
            size=12
        )
        
        assert file_info.filename == "test.yaml"
        assert file_info.content == b"test content"
        assert file_info.content_type == "text/yaml"
        assert file_info.size == 12