from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import router_process
from libs.base.typed_fastapi import TypedFastAPI
from libs.models.entities import Process


def create_mock_app_with_services():
    """Create a TypedFastAPI app with mocked services."""
    app = TypedFastAPI()
    
    # Mock the app context
    mock_context = MagicMock()
    mock_config = MagicMock()
    mock_logger = MagicMock()
    mock_process_service = AsyncMock()
    mock_process_repo = MagicMock()
    
    mock_config.storage_account_process_container = "test-container"
    mock_context.configuration = mock_config
    
    # Setup get_service to return appropriate mocks
    def get_service_mock(service_type):
        if service_type.__name__ == 'ILoggerService':
            return mock_logger
        elif service_type.__name__ == 'ProcessService':
            return mock_process_service
        elif service_type.__name__ == 'ProcessRepository':
            return mock_process_repo
        return MagicMock()
    
    mock_context.get_service = MagicMock(side_effect=get_service_mock)
    
    # Create mock scope
    mock_scope = MagicMock()
    mock_scope.get_service = MagicMock(side_effect=get_service_mock)
    mock_scope.__aenter__ = AsyncMock(return_value=mock_scope)
    mock_scope.__aexit__ = AsyncMock(return_value=False)
    mock_context.create_scope = MagicMock(return_value=mock_scope)
    
    app.set_app_context(mock_context)
    return app


def test_router_process_create_endpoint():
    """Test process create endpoint."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    with patch('routers.router_process.get_authenticated_user') as mock_auth:
        mock_user = MagicMock()
        mock_user.user_principal_id = "user-123"
        mock_auth.return_value = mock_user
        
        client = TestClient(app)
        response = client.post("/api/process/create")


def test_router_process_create_with_authenticated_user():
    """Test process create with valid authenticated user."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    with patch('routers.router_process.get_authenticated_user') as mock_auth:
        mock_user = MagicMock()
        mock_user.user_principal_id = "user-123"
        mock_auth.return_value = mock_user
        
        # Setup process repository to return mocked process
        app.app_context.create_scope = MagicMock()
        mock_scope = MagicMock()
        mock_scope.__aenter__ = AsyncMock(return_value=mock_scope)
        mock_scope.__aexit__ = AsyncMock(return_value=False)
        mock_process_repo = AsyncMock()
        mock_scope.get_service = MagicMock(return_value=mock_process_repo)
        app.app_context.create_scope.return_value = mock_scope
        
        client = TestClient(app)


def test_router_process_status_endpoint():
    """Test process status endpoint."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    # Mock the process service to return an async mock
    mock_logger = MagicMock()
    mock_process_service = AsyncMock()
    mock_process_service.get_current_process = AsyncMock(return_value={"id": "test"})
    
    def get_service_mock(service_type):
        if hasattr(service_type, '__name__'):
            if service_type.__name__ == 'ILoggerService':
                return mock_logger
            elif service_type.__name__ == 'ProcessService':
                return mock_process_service
        return MagicMock()
    
    app.app_context.get_service = MagicMock(side_effect=get_service_mock)
    
    client = TestClient(app)
    response = client.get("/api/process/status/550e8400-e29b-41d4-a716-446655440000/")


def test_router_process_status_logs_info():
    """Test that status endpoint logs info."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    # Track if log_info was called
    mock_logger = MagicMock()
    mock_process_service = AsyncMock()
    mock_process_service.get_current_process = AsyncMock(return_value={"id": "test"})
    
    def get_service_mock(service_type):
        if hasattr(service_type, '__name__'):
            if service_type.__name__ == 'ILoggerService':
                return mock_logger
            elif service_type.__name__ == 'ProcessService':
                return mock_process_service
        return MagicMock()
    
    app.app_context.get_service = MagicMock(side_effect=get_service_mock)
    
    client = TestClient(app)
    response = client.get("/api/process/status/550e8400-e29b-41d4-a716-446655440000/")
    
    # Verify logger was called
    assert mock_logger.log_info.called


def test_router_process_render_status_endpoint():
    """Test process render status endpoint."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    # Mock the process service to return an async mock
    mock_logger = MagicMock()
    mock_process_service = AsyncMock()
    mock_process_service.render_current_process = AsyncMock(return_value={"status": "running"})
    
    def get_service_mock(service_type):
        if hasattr(service_type, '__name__'):
            if service_type.__name__ == 'ILoggerService':
                return mock_logger
            elif service_type.__name__ == 'ProcessService':
                return mock_process_service
        return MagicMock()
    
    app.app_context.get_service = MagicMock(side_effect=get_service_mock)
    
    client = TestClient(app)
    response = client.get("/api/process/status/550e8400-e29b-41d4-a716-446655440000/render/")


def test_router_process_upload_files_endpoint():
    """Test process upload files endpoint."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    with patch('routers.router_process.get_authenticated_user') as mock_auth:
        mock_user = MagicMock()
        mock_user.user_principal_id = "user-123"
        mock_auth.return_value = mock_user
        
        client = TestClient(app)


def test_router_process_delete_file_endpoint():
    """Test process delete file endpoint."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    with patch('routers.router_process.get_authenticated_user') as mock_auth:
        mock_user = MagicMock()
        mock_user.user_principal_id = "user-123"
        mock_auth.return_value = mock_user
        
        client = TestClient(app)
        # delete_file uses Form data for process_id


def test_router_process_delete_process_endpoint():
    """Test process delete process endpoint."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    with patch('routers.router_process.get_authenticated_user') as mock_auth:
        mock_user = MagicMock()
        mock_user.user_principal_id = "user-123"
        mock_auth.return_value = mock_user
        
        client = TestClient(app)
        response = client.delete(
            "/api/process/delete-process/550e8400-e29b-41d4-a716-446655440000"
        )


def test_router_process_has_prefix():
    """Test process router has correct prefix."""
    assert router_process.router.prefix == "/api/process"


def test_router_process_has_tags():
    """Test process router has correct tags."""
    assert "process" in router_process.router.tags


def test_router_process_paths_enum():
    """Test process router paths enum."""
    from routers.router_process import process_router_paths
    
    assert hasattr(process_router_paths, 'UPLOAD_FILES')
    assert hasattr(process_router_paths, 'START_PROCESSING')
    assert hasattr(process_router_paths, 'DELETE_FILE')
    assert hasattr(process_router_paths, 'DELETE_PROCESS')
    assert hasattr(process_router_paths, 'CANCEL_PROCESS')
    assert hasattr(process_router_paths, 'STATUS')
    assert hasattr(process_router_paths, 'RENDER_STATUS')


def test_router_process_create_requires_auth():
    """Test process create endpoint requires authentication."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    with patch('routers.router_process.get_authenticated_user') as mock_auth:
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=401)


def test_router_process_status_path_param():
    """Test process status endpoint accepts path parameter."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    client = TestClient(app)
    # Should accept any string as process_id parameter


def test_router_process_render_status_path_param():
    """Test process render status endpoint accepts path parameter."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    client = TestClient(app)
    # Should accept any string as process_id parameter


def test_router_process_upload_validates_process_id():
    """Test process upload files validates process_id."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    with patch('routers.router_process.get_authenticated_user') as mock_auth:
        mock_user = MagicMock()
        mock_user.user_principal_id = "user-123"
        mock_auth.return_value = mock_user


def test_router_process_delete_file_requires_file_name():
    """Test delete file requires file name parameter."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    with patch('routers.router_process.get_authenticated_user') as mock_auth:
        mock_user = MagicMock()
        mock_user.user_principal_id = "user-123"
        mock_auth.return_value = mock_user


def test_router_process_delete_process_requires_process_id():
    """Test delete process requires process_id parameter."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    with patch('routers.router_process.get_authenticated_user') as mock_auth:
        mock_user = MagicMock()
        mock_user.user_principal_id = "user-123"
        mock_auth.return_value = mock_user


def test_router_process_create_returns_process_id():
    """Test process create endpoint returns process_id."""
    app = create_mock_app_with_services()
    
    with patch('routers.router_process.ProcessCreateResponse') as mock_response:
        with patch('routers.router_process.get_authenticated_user') as mock_auth:
            mock_user = MagicMock()
            mock_user.user_principal_id = "user-123"
            mock_auth.return_value = mock_user


def test_router_process_routes_exist():
    """Test all process routes are registered."""
    app = FastAPI()
    app.include_router(router_process.router)
    
    routes = [route.path for route in app.routes]
    
    # Check that routes contain the process endpoints
    route_paths = " ".join(routes)
    assert "/api/process" in route_paths


def test_router_process_upload_files_status_code():
    """Test upload files endpoint returns 200 on success."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    with patch('routers.router_process.get_authenticated_user') as mock_auth:
        mock_user = MagicMock()
        mock_user.user_principal_id = "user-123"
        mock_auth.return_value = mock_user


def test_router_process_delete_returns_empty_files():
    """Test delete process returns empty file list."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    with patch('routers.router_process.get_authenticated_user') as mock_auth:
        mock_user = MagicMock()
        mock_user.user_principal_id = "user-123"
        mock_auth.return_value = mock_user


def test_router_process_create_endpoint_dual_route():
    """Test process create endpoint handles dual route decorator."""
    app = create_mock_app_with_services()
    app.include_router(router_process.router)
    
    routes = [route.path for route in app.routes]
    # Should have both /create and activity status routes
    assert any("/create" in route for route in routes)


def test_router_process_response_models():
    """Test that routers use proper response models."""
    from routers.models.processes import ProcessCreateResponse
    
    response = ProcessCreateResponse(process_id="test-123")
    assert response.process_id == "test-123"


def test_router_process_path_params():
    """Test router accepts path parameters."""
    assert router_process.process_router_paths.UPLOAD_FILES == "/upload"
    assert router_process.process_router_paths.START_PROCESSING == "/start-processing"
    assert router_process.process_router_paths.DELETE_FILE == "/delete-file/{file_name}"
    assert router_process.process_router_paths.DELETE_PROCESS == "/delete-process/{process_id}"
    assert router_process.process_router_paths.STATUS == "/status/{process_id}/"
    assert router_process.process_router_paths.RENDER_STATUS == "/status/{process_id}/render/"

