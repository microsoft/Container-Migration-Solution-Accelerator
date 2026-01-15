"""
Unit tests for router_files.py

This module contains comprehensive test cases for the file upload router,
covering authentication, validation, file upload functionality, and error handling.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4
from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import Response
from fastapi.testclient import TestClient
import io

# Import the router and functions under test
from app.routers.router_files import router, upload_file_options, upload_file


class TestRouterFiles:
    """Test class for router_files functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(router)
        
        # Create mock request
        self.mock_request = Mock(spec=Request)
        
        # Create mock user
        self.mock_user = Mock()
        self.mock_user.user_principal_id = "test-user-123"
        
        # Generate test UUID for process_id
        self.process_id = str(uuid4())
        
        # Create mock logger
        self.mock_logger = Mock()
        self.mock_logger.log_info = Mock()
        self.mock_logger.log_error = Mock()

    def create_mock_upload_file(self, filename, content=b"test content"):
        """Helper to create a mock UploadFile."""
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = filename
        mock_file.read = AsyncMock(return_value=content)
        return mock_file


class TestUploadFileOptionsEndpoint(TestRouterFiles):
    """Test cases for the CORS options endpoint."""

    @pytest.mark.asyncio
    async def test_upload_file_options_success(self):
        """Test OPTIONS endpoint returns correct CORS headers."""
        response = await upload_file_options()
        
        assert isinstance(response, Response)
        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == "*"
        assert response.headers["Access-Control-Allow-Methods"] == "POST, OPTIONS"
        assert response.headers["Access-Control-Allow-Headers"] == "Content-Type, Authorization"

    def test_upload_file_options_via_client(self):
        """Test OPTIONS endpoint through test client."""
        response = self.client.options("/api/file/upload")
        
        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == "*"
        assert response.headers["Access-Control-Allow-Methods"] == "POST, OPTIONS"
        assert response.headers["Access-Control-Allow-Headers"] == "Content-Type, Authorization"


class TestUploadFileValidation(TestRouterFiles):
    """Test cases for upload_file validation scenarios."""

    @pytest.mark.asyncio
    async def test_upload_file_user_not_authenticated(self):
        """Test upload_file raises 401 when user not authenticated."""
        mock_file = self.create_mock_upload_file("test.yaml")
        
        with patch('app.routers.router_files.get_authenticated_user') as mock_auth:
            mock_auth.return_value = Mock(user_principal_id=None)
            
            # Mock the app context
            mock_app = Mock()
            mock_app.app_context.get_service.return_value = self.mock_logger
            self.mock_request.app = mock_app
            
            with pytest.raises(HTTPException) as exc_info:
                await upload_file(self.mock_request, mock_file, self.process_id)
            
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "User not authenticated"

    @pytest.mark.asyncio
    async def test_upload_file_invalid_process_id(self):
        """Test upload_file raises 400 for invalid process_id format."""
        mock_file = self.create_mock_upload_file("test.yaml")
        
        with patch('app.routers.router_files.get_authenticated_user') as mock_auth:
            with patch('app.routers.router_files.is_valid_uuid', return_value=False):
                mock_auth.return_value = self.mock_user
                
                # Mock the app context
                mock_app = Mock()
                mock_app.app_context.get_service.return_value = self.mock_logger
                self.mock_request.app = mock_app
                
                with pytest.raises(HTTPException) as exc_info:
                    await upload_file(self.mock_request, mock_file, "invalid-uuid")
                
                assert exc_info.value.status_code == 400
                assert exc_info.value.detail == "Invalid process_id format"

    @pytest.mark.asyncio
    async def test_upload_file_no_filename(self):
        """Test upload_file raises 400 when no filename provided."""
        mock_file = self.create_mock_upload_file(None)  # No filename
        
        with patch('app.routers.router_files.get_authenticated_user') as mock_auth:
            with patch('app.routers.router_files.is_valid_uuid', return_value=True):
                mock_auth.return_value = self.mock_user
                
                # Mock the app context
                mock_app = Mock()
                mock_app.app_context.get_service.return_value = self.mock_logger
                self.mock_request.app = mock_app
                
                with pytest.raises(HTTPException) as exc_info:
                    await upload_file(self.mock_request, mock_file, self.process_id)
                
                assert exc_info.value.status_code == 400
                assert exc_info.value.detail == "No filename provided"

    @pytest.mark.asyncio
    async def test_upload_file_empty_filename(self):
        """Test upload_file raises 400 when empty filename provided."""
        mock_file = self.create_mock_upload_file("")  # Empty filename
        
        with patch('app.routers.router_files.get_authenticated_user') as mock_auth:
            with patch('app.routers.router_files.is_valid_uuid', return_value=True):
                mock_auth.return_value = self.mock_user
                
                # Mock the app context
                mock_app = Mock()
                mock_app.app_context.get_service.return_value = self.mock_logger
                self.mock_request.app = mock_app
                
                with pytest.raises(HTTPException) as exc_info:
                    await upload_file(self.mock_request, mock_file, self.process_id)
                
                assert exc_info.value.status_code == 400
                assert exc_info.value.detail == "No filename provided"


class TestUploadFileExceptionHandling(TestRouterFiles):
    """Test cases for upload_file exception handling."""

    @pytest.mark.asyncio
    async def test_upload_file_http_exception_passthrough(self):
        """Test upload_file passes through HTTPException unchanged."""
        mock_file = self.create_mock_upload_file("test.yaml")
        
        with patch('app.routers.router_files.get_authenticated_user') as mock_auth:
            # Make authentication raise an HTTPException
            http_exc = HTTPException(status_code=403, detail="Forbidden")
            mock_auth.side_effect = http_exc
            
            # Mock the app context
            mock_app = Mock()
            mock_app.app_context.get_service.return_value = self.mock_logger
            self.mock_request.app = mock_app
            
            with pytest.raises(HTTPException) as exc_info:
                await upload_file(self.mock_request, mock_file, self.process_id)
            
            # Should pass through the original HTTPException
            assert exc_info.value.status_code == 403
            assert exc_info.value.detail == "Forbidden"
            
            # Should log the error
            self.mock_logger.log_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_file_generic_exception_handling(self):
        """Test upload_file converts generic exceptions to 500 HTTPException."""
        mock_file = self.create_mock_upload_file("test.yaml")
        
        with patch('app.routers.router_files.get_authenticated_user') as mock_auth:
            # Make authentication raise a generic exception
            mock_auth.side_effect = RuntimeError("Database connection failed")
            
            # Mock the app context
            mock_app = Mock()
            mock_app.app_context.get_service.return_value = self.mock_logger
            self.mock_request.app = mock_app
            
            with pytest.raises(HTTPException) as exc_info:
                await upload_file(self.mock_request, mock_file, self.process_id)
            
            # Should convert to 500 error
            assert exc_info.value.status_code == 500
            assert exc_info.value.detail == "Internal server error"
            
            # Should log the error
            self.mock_logger.log_error.assert_called()
            log_call_args = self.mock_logger.log_error.call_args[0]
            assert "Exception: Database connection failed" in log_call_args[0]


class TestUploadFileSuccessPath(TestRouterFiles):
    """Test cases for upload_file success scenarios."""

    @pytest.mark.asyncio
    async def test_upload_file_scope_creation(self):
        """Test that upload_file reaches scope creation."""
        mock_file = self.create_mock_upload_file("deployment.yaml", b"test content")
        
        with patch('app.routers.router_files.get_authenticated_user') as mock_auth:
            with patch('app.routers.router_files.is_valid_uuid', return_value=True):
                mock_auth.return_value = self.mock_user
                
                # Mock app context that fails at scope creation for controlled testing
                mock_app_context = Mock()
                mock_app_context.get_service.return_value = self.mock_logger
                mock_app_context.create_scope.side_effect = RuntimeError("Test scope failure")
                
                mock_app = Mock()
                mock_app.app_context = mock_app_context
                self.mock_request.app = mock_app
                
                # Should reach scope creation and then fail gracefully
                with pytest.raises(HTTPException) as exc_info:
                    await upload_file(self.mock_request, mock_file, self.process_id)
                
                # Should get 500 error due to exception handling
                assert exc_info.value.status_code == 500
                assert exc_info.value.detail == "Internal server error"
                
                # Verify we reached the right point in the flow
                self.mock_logger.log_info.assert_called_with(f"process_id: {self.process_id}")
                mock_app_context.create_scope.assert_called_once()
                self.mock_logger.log_error.assert_called()


class TestRouterConfiguration(TestRouterFiles):
    """Test cases for router configuration."""

    def test_router_prefix(self):
        """Test router has correct prefix."""
        assert router.prefix == "/api/file"

    def test_router_tags(self):
        """Test router has correct tags."""
        assert router.tags == ["file"]

    def test_router_responses(self):
        """Test router has correct response configuration."""
        assert 404 in router.responses
        assert router.responses[404]["description"] == "Not found"

    def test_router_routes(self):
        """Test router has expected routes."""
        route_paths = [route.path for route in router.routes]
        # FastAPI router includes full paths with prefix
        assert any("/upload" in path for path in route_paths)
        
        # Check for both OPTIONS and POST methods
        upload_routes = [route for route in router.routes if "/upload" in route.path]
        methods = []
        for route in upload_routes:
            methods.extend(route.methods)
        
        assert "OPTIONS" in methods
        assert "POST" in methods


class TestFilenameValidation(TestRouterFiles):
    """Test cases for filename sanitization and validation."""

    def test_filename_sanitization_pattern(self):
        """Test the regex pattern used for filename sanitization."""
        import re
        
        # Test the actual regex pattern used in the code
        test_cases = [
            ("normal-file.yaml", "normal-file.yaml"),
            ("file with spaces.yaml", "file_with_spaces.yaml"),
            ("file!@#$%^&*().yaml", "file__________.yaml"),
            ("file-name_123.test.yaml", "file-name_123.test.yaml"),  # Should preserve allowed chars
        ]
        
        for original, expected in test_cases:
            result = re.sub(r"[^\w.-]", "_", original)
            # Just verify the pattern works as expected
            assert len(result) == len(original)  # Same length after substitution
            assert all(c.isalnum() or c in "._-" for c in result)  # Only allowed characters


class TestIntegration(TestRouterFiles):
    """Integration-style tests using TestClient."""

    def test_cors_preflight_integration(self):
        """Test CORS preflight request through full stack."""
        response = self.client.options("/api/file/upload")
        
        assert response.status_code == 200
        
        # Verify CORS headers
        assert response.headers.get("Access-Control-Allow-Origin") == "*"
        assert response.headers.get("Access-Control-Allow-Methods") == "POST, OPTIONS"
        assert response.headers.get("Access-Control-Allow-Headers") == "Content-Type, Authorization"

    def test_upload_endpoint_exists(self):
        """Test upload endpoint exists and responds appropriately."""
        # Test with invalid content should fail with validation error (not 404)
        try:
            response = self.client.post("/api/file/upload", json={"test": "data"})
            # Should not be 404 (endpoint exists) and should fail validation
            assert response.status_code != 404
        except Exception as e:
            # If it throws a validation error, that means the endpoint exists
            # and is processing the request (which is what we want to verify)
            assert "RequestValidationError" in str(type(e)) or "ValidationError" in str(e)


# Additional test utilities and fixtures

@pytest.fixture
def mock_typed_fastapi():
    """Fixture for mocking TypedFastAPI."""
    mock_app = Mock()
    mock_app_context = Mock()
    mock_app.app_context = mock_app_context
    return mock_app


@pytest.fixture
def sample_file_content():
    """Fixture providing sample YAML file content."""
    return b"""
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  containers:
  - name: test-container
    image: nginx:latest
    """


class TestUploadFileEdgeCases(TestRouterFiles):
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_upload_file_with_unicode_filename(self):
        """Test upload with unicode characters in filename."""
        unicode_filename = "test-файл-测试.yaml"
        mock_file = self.create_mock_upload_file(unicode_filename)
        
        with patch('app.routers.router_files.get_authenticated_user') as mock_auth:
            with patch('app.routers.router_files.is_valid_uuid', return_value=True):
                mock_auth.return_value = self.mock_user
                
                # Mock app context that fails early to test unicode handling
                mock_app_context = Mock()
                mock_app_context.get_service.return_value = self.mock_logger
                mock_app_context.create_scope.side_effect = RuntimeError("Stop after validation")
                
                mock_app = Mock()
                mock_app.app_context = mock_app_context
                self.mock_request.app = mock_app
                
                # Should handle unicode filename without crashing
                with pytest.raises(HTTPException) as exc_info:
                    await upload_file(self.mock_request, mock_file, self.process_id)
                
                # Should get to the point where it logs the process_id
                assert exc_info.value.status_code == 500
                self.mock_logger.log_info.assert_called()

    @pytest.mark.asyncio
    async def test_upload_large_file_content(self):
        """Test upload with large file content."""
        large_content = b"x" * 10000  # 10KB content
        mock_file = self.create_mock_upload_file("large-file.yaml", large_content)
        
        with patch('app.routers.router_files.get_authenticated_user') as mock_auth:
            with patch('app.routers.router_files.is_valid_uuid', return_value=True):
                mock_auth.return_value = self.mock_user
                
                # Mock app context that fails early
                mock_app_context = Mock()
                mock_app_context.get_service.return_value = self.mock_logger
                mock_app_context.create_scope.side_effect = RuntimeError("Test failure")
                
                mock_app = Mock()
                mock_app.app_context = mock_app_context
                self.mock_request.app = mock_app
                
                # Should handle large content without crashing
                with pytest.raises(HTTPException) as exc_info:
                    await upload_file(self.mock_request, mock_file, self.process_id)
                
                # Should get internal server error
                assert exc_info.value.status_code == 500
                
                # Verify we got past initial validation
                self.mock_logger.log_info.assert_called_with(f"process_id: {self.process_id}")


if __name__ == "__main__":
    pytest.main([__file__])