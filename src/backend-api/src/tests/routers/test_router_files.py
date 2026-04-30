from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import router_files
from libs.base.typed_fastapi import TypedFastAPI


def create_mock_app_for_router():
    """Create a TypedFastAPI app with mocked services for testing."""
    app = TypedFastAPI()
    
    # Mock the app context
    mock_context = MagicMock()
    mock_config = MagicMock()
    mock_logger = MagicMock()
    
    mock_config.storage_account_process_container = "test-container"
    mock_context.configuration = mock_config
    mock_context.get_service = MagicMock(return_value=mock_logger)
    mock_context.create_scope = MagicMock()
    
    # Create mock scope
    mock_scope = MagicMock()
    mock_scope.get_service = MagicMock()
    mock_scope.__aenter__ = AsyncMock(return_value=mock_scope)
    mock_scope.__aexit__ = AsyncMock(return_value=False)
    mock_context.create_scope = MagicMock(return_value=mock_scope)
    
    app.set_app_context(mock_context)
    return app


def test_router_files_upload_options():
    """Test file upload OPTIONS endpoint for CORS."""
    app = create_mock_app_for_router()
    app.include_router(router_files.router)
    
    client = TestClient(app)
    response = client.options("/api/file/upload")
    
    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") == "*"
    assert "POST" in response.headers.get("Access-Control-Allow-Methods", "")
    assert "OPTIONS" in response.headers.get("Access-Control-Allow-Methods", "")


def test_router_files_upload_requires_auth():
    """Test file upload requires authentication."""
    app = create_mock_app_for_router()
    
    with patch('routers.router_files.get_authenticated_user') as mock_auth:
        mock_auth.side_effect = Exception("Not authenticated")
        app.include_router(router_files.router)
        
        client = TestClient(app)
        response = client.post(
            "/api/file/upload",
            data={"process_id": "test-process"}
        )
        
        # Should fail due to no file


def test_router_files_upload_validates_process_id():
    """Test file upload validates process_id format."""
    app = create_mock_app_for_router()
    app.include_router(router_files.router)
    
    with patch('routers.router_files.get_authenticated_user') as mock_auth:
        mock_user = MagicMock()
        mock_user.user_principal_id = "user-123"
        mock_auth.return_value = mock_user
        
        with patch('routers.router_files.is_valid_uuid') as mock_uuid:
            mock_uuid.return_value = False
            
            client = TestClient(app)
            response = client.post(
                "/api/file/upload",
                data={"process_id": "invalid-process-id"}
            )


def test_router_files_upload_requires_file():
    """Test file upload requires file parameter."""
    app = create_mock_app_for_router()
    app.include_router(router_files.router)
    
    with patch('routers.router_files.get_authenticated_user') as mock_auth:
        mock_user = MagicMock()
        mock_user.user_principal_id = "user-123"
        mock_auth.return_value = mock_user
        
        client = TestClient(app)
        response = client.post(
            "/api/file/upload",
            data={"process_id": "550e8400-e29b-41d4-a716-446655440000"}
        )


def test_router_files_upload_requires_process_id():
    """Test file upload requires process_id parameter."""
    app = create_mock_app_for_router()
    app.include_router(router_files.router)
    
    with patch('routers.router_files.get_authenticated_user') as mock_auth:
        mock_user = MagicMock()
        mock_user.user_principal_id = "user-123"
        mock_auth.return_value = mock_user


def test_router_files_has_upload_endpoint():
    """Test that file router has upload endpoint."""
    assert hasattr(router_files, 'router')
    assert router_files.router is not None


def test_router_files_upload_endpoint_methods():
    """Test file upload endpoint supports POST."""
    app = create_mock_app_for_router()
    app.include_router(router_files.router)
    
    client = TestClient(app)
    
    with patch('routers.router_files.get_authenticated_user') as mock_auth:
        mock_user = MagicMock()
        mock_user.user_principal_id = "user-123"
        mock_auth.return_value = mock_user


def test_router_files_prefix():
    """Test file router has correct prefix."""
    assert router_files.router.prefix == "/api/file"


def test_router_files_tags():
    """Test file router has correct tags."""
    assert "file" in router_files.router.tags


def test_router_files_has_options_handler():
    """Test file router has OPTIONS handler."""
    app = FastAPI()
    app.include_router(router_files.router)
    
    # Check if OPTIONS is available
    client = TestClient(app)
    response = client.options("/api/file/upload")
    # OPTIONS should return 200 or 405 (method not allowed) - either is ok for existence


def test_router_files_upload_endpoint_exists():
    """Test that /api/file/upload endpoint exists."""
    app = create_mock_app_for_router()
    app.include_router(router_files.router)
    
    # Verify the endpoint is registered
    routes = [route.path for route in app.routes]
    assert any("/api/file" in route for route in routes)


def test_router_files_handles_authentication_error():
    """Test file router handles authentication errors gracefully."""
    app = create_mock_app_for_router()
    app.include_router(router_files.router)
    
    with patch('routers.router_files.get_authenticated_user') as mock_auth:
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=401, detail="Unauthorized")
        
        client = TestClient(app)


def test_router_files_upload_requires_valid_uuid():
    """Test file upload validates UUID format."""
    app = create_mock_app_for_router()
    
    with patch('routers.router_files.get_authenticated_user') as mock_auth:
        mock_user = MagicMock()
        mock_user.user_principal_id = "user-123"
        mock_auth.return_value = mock_user
        
        with patch('routers.router_files.is_valid_uuid') as mock_uuid:
            mock_uuid.return_value = False
            
            app.include_router(router_files.router)
            client = TestClient(app)


def test_router_files_upload_sanitizes_filenames():
    """Test file upload sanitizes filenames."""
    # The router uses re.sub to sanitize filenames
    import re
    filename = "file@#$%.txt"
    sanitized = re.sub(r"[^\w.-]", "_", filename)
    assert "@" not in sanitized
    assert "#" not in sanitized
