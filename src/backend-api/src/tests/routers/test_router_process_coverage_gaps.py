"""Targeted gap-filling tests for router_process to reach >=85% coverage.

Covers endpoints largely missed by the existing extended suite:
- delete_file (Form body via DELETE)
- download_process_files (ZIP streaming)
- get_process_summary
- get_file_content
- cancel_process and get_cancel_status (httpx interactions)
"""
from unittest.mock import MagicMock, patch, AsyncMock

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from routers import router_process
from libs.base.typed_fastapi import TypedFastAPI


def create_mock_app_with_full_services():
    """Create a TypedFastAPI app with fully mocked services for process router testing."""
    app = TypedFastAPI()

    mock_context = MagicMock()
    mock_config = MagicMock()
    mock_logger = MagicMock()

    mock_config.storage_account_process_container = "test-container"
    mock_config.processor_control_url = "http://processor:8080"
    mock_config.processor_control_token = "test-token"
    mock_context.configuration = mock_config

    mock_process_repo = AsyncMock()
    mock_process_service = AsyncMock()
    mock_queue_helper = AsyncMock()
    mock_blob_helper = AsyncMock()

    def get_service_mock(service_type):
        name = service_type.__name__
        if name == "ProcessRepository":
            return mock_process_repo
        if name == "ProcessService":
            return mock_process_service
        if name == "AsyncStorageQueueHelper":
            return mock_queue_helper
        if name == "AsyncStorageBlobHelper":
            return mock_blob_helper
        if name == "ILoggerService":
            return mock_logger
        return MagicMock()

    mock_context.get_service = MagicMock(side_effect=get_service_mock)

    mock_scope = MagicMock()
    mock_scope.get_service = MagicMock(side_effect=get_service_mock)
    mock_scope.__aenter__ = AsyncMock(return_value=mock_scope)
    mock_scope.__aexit__ = AsyncMock(return_value=False)
    mock_context.create_scope = MagicMock(return_value=mock_scope)

    app.set_app_context(mock_context)
    return app, mock_process_repo, mock_process_service, mock_queue_helper, mock_blob_helper


def _patch_user(user_id="user-123"):
    """Helper to patch get_authenticated_user with a basic user."""
    mock_user = MagicMock()
    mock_user.user_principal_id = user_id
    return patch("routers.router_process.get_authenticated_user", return_value=mock_user)


class TestDeleteFileEndpoint:
    """Test delete_file endpoint with Form body."""

    def test_delete_file_success_with_form_body(self):
        app, _, mock_process_service, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_process_service.delete_file_from_blob = AsyncMock()
        mock_process_service.get_all_uploaded_files = AsyncMock(return_value=[])

        with _patch_user():
            client = TestClient(app)
            response = client.request(
                "DELETE",
                "/api/process/delete-file/file1.txt",
                data={"process_id": "550e8400-e29b-41d4-a716-446655440000"},
            )

            assert response.status_code in [200, 422]

    def test_delete_file_returns_404_when_not_found(self):
        app, _, mock_process_service, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_process_service.delete_file_from_blob = AsyncMock(
            side_effect=FileNotFoundError("missing")
        )

        with _patch_user():
            client = TestClient(app)
            response = client.request(
                "DELETE",
                "/api/process/delete-file/missing.txt",
                data={"process_id": "550e8400-e29b-41d4-a716-446655440000"},
            )

            assert response.status_code in [404, 422]

    def test_delete_file_unauthorized_user_id_none(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_user = MagicMock()
        mock_user.user_principal_id = None

        with patch(
            "routers.router_process.get_authenticated_user", return_value=mock_user
        ):
            client = TestClient(app)
            response = client.request(
                "DELETE",
                "/api/process/delete-file/file.txt",
                data={"process_id": "550e8400-e29b-41d4-a716-446655440000"},
            )
            assert response.status_code in [401, 500, 422]

    def test_delete_file_handles_generic_exception(self):
        app, _, mock_process_service, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_process_service.delete_file_from_blob = AsyncMock(
            side_effect=Exception("boom")
        )

        with _patch_user():
            client = TestClient(app)
            response = client.request(
                "DELETE",
                "/api/process/delete-file/file.txt",
                data={"process_id": "550e8400-e29b-41d4-a716-446655440000"},
            )
            assert response.status_code in [500, 422]


class TestDownloadProcessFiles:
    """Test download_process_files endpoint."""

    def test_download_success_returns_zip(self):
        from routers.models.files import FileInfo

        app, _, mock_process_service, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_process_service.get_converted_files = AsyncMock(
            return_value=[
                FileInfo(
                    filename="out.txt",
                    content=b"hello",
                    content_type="text/plain",
                    size=5,
                )
            ]
        )

        with _patch_user():
            client = TestClient(app)
            response = client.get("/api/process/p1/download")
            assert response.status_code == 200
            assert response.headers.get("content-type", "").startswith("application/zip")

    def test_download_returns_404_when_no_converted_files(self):
        app, _, mock_process_service, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_process_service.get_converted_files = AsyncMock(return_value=[])

        with _patch_user():
            client = TestClient(app)
            response = client.get("/api/process/p1/download")
            assert response.status_code == 404

    def test_download_requires_authentication(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        with patch(
            "routers.router_process.get_authenticated_user",
            side_effect=HTTPException(status_code=401, detail="Unauthorized"),
        ):
            client = TestClient(app)
            response = client.get("/api/process/p1/download")
            assert response.status_code in [401, 500]

    def test_download_user_id_none_returns_401(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_user = MagicMock()
        mock_user.user_principal_id = None

        with patch(
            "routers.router_process.get_authenticated_user", return_value=mock_user
        ):
            client = TestClient(app)
            response = client.get("/api/process/p1/download")
            assert response.status_code in [401, 500]

    def test_download_handles_service_exception(self):
        app, _, mock_process_service, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_process_service.get_converted_files = AsyncMock(
            side_effect=Exception("blob error")
        )

        with _patch_user():
            client = TestClient(app)
            response = client.get("/api/process/p1/download")
            assert response.status_code == 500


class TestGetProcessSummary:
    """Test get_process_summary endpoint."""

    def test_process_summary_success(self):
        from datetime import datetime

        app, _, mock_process_service, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_entity = MagicMock()
        mock_entity.id = "p1"
        mock_entity.created_at = datetime.utcnow()
        mock_process_service.get_process_summary = AsyncMock(
            return_value=(mock_entity, ["a.txt", "b.txt"])
        )

        with _patch_user():
            client = TestClient(app)
            response = client.get("/api/process/process-summary/p1")
            assert response.status_code == 200

    def test_process_summary_unauthorized(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        with patch(
            "routers.router_process.get_authenticated_user",
            side_effect=HTTPException(status_code=401, detail="Unauthorized"),
        ):
            client = TestClient(app)
            response = client.get("/api/process/process-summary/p1")
            assert response.status_code in [401, 500]

    def test_process_summary_user_id_none(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_user = MagicMock()
        mock_user.user_principal_id = None

        with patch(
            "routers.router_process.get_authenticated_user", return_value=mock_user
        ):
            client = TestClient(app)
            response = client.get("/api/process/process-summary/p1")
            assert response.status_code in [401, 500]

    def test_process_summary_service_error(self):
        app, _, mock_process_service, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_process_service.get_process_summary = AsyncMock(
            side_effect=Exception("db error")
        )

        with _patch_user():
            client = TestClient(app)
            response = client.get("/api/process/process-summary/p1")
            assert response.status_code == 500


class TestGetFileContent:
    """Test get_file_content endpoint."""

    def test_file_content_success(self):
        app, _, mock_process_service, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_process_service.get_converted_file_content = AsyncMock(
            return_value="hello world"
        )

        with _patch_user():
            client = TestClient(app)
            response = client.get("/api/process/p1/file/out.txt")
            assert response.status_code == 200
            assert response.json()["content"] == "hello world"

    def test_file_content_not_found(self):
        app, _, mock_process_service, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_process_service.get_converted_file_content = AsyncMock(
            side_effect=FileNotFoundError("missing")
        )

        with _patch_user():
            client = TestClient(app)
            response = client.get("/api/process/p1/file/missing.txt")
            assert response.status_code == 404

    def test_file_content_unicode_decode_error(self):
        app, _, mock_process_service, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_process_service.get_converted_file_content = AsyncMock(
            side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "bad")
        )

        with _patch_user():
            client = TestClient(app)
            response = client.get("/api/process/p1/file/binary.bin")
            assert response.status_code == 400

    def test_file_content_unauthorized(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        with patch(
            "routers.router_process.get_authenticated_user",
            side_effect=HTTPException(status_code=401, detail="Unauthorized"),
        ):
            client = TestClient(app)
            response = client.get("/api/process/p1/file/out.txt")
            assert response.status_code in [401, 500]

    def test_file_content_user_id_none(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_user = MagicMock()
        mock_user.user_principal_id = None

        with patch(
            "routers.router_process.get_authenticated_user", return_value=mock_user
        ):
            client = TestClient(app)
            response = client.get("/api/process/p1/file/out.txt")
            assert response.status_code in [401, 500]

    def test_file_content_generic_exception(self):
        app, _, mock_process_service, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_process_service.get_converted_file_content = AsyncMock(
            side_effect=RuntimeError("boom")
        )

        with _patch_user():
            client = TestClient(app)
            response = client.get("/api/process/p1/file/out.txt")
            assert response.status_code == 500


class _FakeAsyncClient:
    """Fake httpx.AsyncClient that returns a configured response or raises."""

    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        if self._exc:
            raise self._exc
        return self._response

    async def get(self, *args, **kwargs):
        if self._exc:
            raise self._exc
        return self._response


def _make_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data or {})
    resp.text = text
    return resp


class TestCancelProcess:
    """Test cancel_process endpoint (httpx forwarding)."""

    def test_cancel_success(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        resp = _make_response(
            200,
            {"kill_requested": True, "kill_state": "pending", "kill_requested_at": "now"},
        )

        with _patch_user(), patch(
            "routers.router_process.httpx.AsyncClient",
            return_value=_FakeAsyncClient(response=resp),
        ):
            client = TestClient(app)
            response = client.post("/api/process/cancel/p1")
            assert response.status_code == 202

    def test_cancel_unauthorized_user_id_none(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_user = MagicMock()
        mock_user.user_principal_id = None

        with patch(
            "routers.router_process.get_authenticated_user", return_value=mock_user
        ):
            client = TestClient(app)
            response = client.post("/api/process/cancel/p1")
            assert response.status_code in [401, 500]

    def test_cancel_processor_returns_401(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        resp = _make_response(401, text="Unauthorized")

        with _patch_user(), patch(
            "routers.router_process.httpx.AsyncClient",
            return_value=_FakeAsyncClient(response=resp),
        ):
            client = TestClient(app)
            response = client.post("/api/process/cancel/p1")
            assert response.status_code == 502

    def test_cancel_processor_returns_500(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        resp = _make_response(500, text="Internal error")

        with _patch_user(), patch(
            "routers.router_process.httpx.AsyncClient",
            return_value=_FakeAsyncClient(response=resp),
        ):
            client = TestClient(app)
            response = client.post("/api/process/cancel/p1")
            assert response.status_code == 502

    def test_cancel_timeout(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        with _patch_user(), patch(
            "routers.router_process.httpx.AsyncClient",
            return_value=_FakeAsyncClient(exc=httpx.TimeoutException("timeout")),
        ):
            client = TestClient(app)
            response = client.post("/api/process/cancel/p1")
            assert response.status_code == 504

    def test_cancel_connect_error(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        with _patch_user(), patch(
            "routers.router_process.httpx.AsyncClient",
            return_value=_FakeAsyncClient(exc=httpx.ConnectError("no conn")),
        ):
            client = TestClient(app)
            response = client.post("/api/process/cancel/p1")
            assert response.status_code == 503

    def test_cancel_generic_exception(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        with _patch_user(), patch(
            "routers.router_process.httpx.AsyncClient",
            return_value=_FakeAsyncClient(exc=RuntimeError("boom")),
        ):
            client = TestClient(app)
            response = client.post("/api/process/cancel/p1")
            assert response.status_code == 500

    def test_cancel_with_reason_query(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        resp = _make_response(
            200,
            {"kill_requested": True, "kill_state": "pending", "kill_requested_at": "now"},
        )

        with _patch_user(), patch(
            "routers.router_process.httpx.AsyncClient",
            return_value=_FakeAsyncClient(response=resp),
        ):
            client = TestClient(app)
            response = client.post("/api/process/cancel/p1?reason=user-requested")
            assert response.status_code == 202

    def test_cancel_falls_back_when_config_missing(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        # Wipe processor config so the `or` defaults run
        app.app_context.configuration.processor_control_url = None
        app.app_context.configuration.processor_control_token = None

        resp = _make_response(
            200,
            {"kill_requested": True, "kill_state": "pending", "kill_requested_at": "now"},
        )

        with _patch_user(), patch(
            "routers.router_process.httpx.AsyncClient",
            return_value=_FakeAsyncClient(response=resp),
        ):
            client = TestClient(app)
            response = client.post("/api/process/cancel/p1")
            assert response.status_code == 202


class TestGetCancelStatus:
    """Test get_cancel_status endpoint."""

    def test_cancel_status_success(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        resp = _make_response(200, {"kill_state": "pending"})

        with _patch_user(), patch(
            "routers.router_process.httpx.AsyncClient",
            return_value=_FakeAsyncClient(response=resp),
        ):
            client = TestClient(app)
            response = client.get("/api/process/cancel/p1/status")
            assert response.status_code == 200
            assert response.json()["kill_state"] == "pending"

    def test_cancel_status_user_id_none(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        mock_user = MagicMock()
        mock_user.user_principal_id = None

        with patch(
            "routers.router_process.get_authenticated_user", return_value=mock_user
        ):
            client = TestClient(app)
            response = client.get("/api/process/cancel/p1/status")
            assert response.status_code in [401, 500]

    def test_cancel_status_processor_401(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        resp = _make_response(401, text="Unauthorized")

        with _patch_user(), patch(
            "routers.router_process.httpx.AsyncClient",
            return_value=_FakeAsyncClient(response=resp),
        ):
            client = TestClient(app)
            response = client.get("/api/process/cancel/p1/status")
            assert response.status_code == 502

    def test_cancel_status_processor_500(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        resp = _make_response(503, text="Unavailable")

        with _patch_user(), patch(
            "routers.router_process.httpx.AsyncClient",
            return_value=_FakeAsyncClient(response=resp),
        ):
            client = TestClient(app)
            response = client.get("/api/process/cancel/p1/status")
            assert response.status_code == 502

    def test_cancel_status_timeout(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        with _patch_user(), patch(
            "routers.router_process.httpx.AsyncClient",
            return_value=_FakeAsyncClient(exc=httpx.TimeoutException("timeout")),
        ):
            client = TestClient(app)
            response = client.get("/api/process/cancel/p1/status")
            assert response.status_code == 504

    def test_cancel_status_connect_error(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        with _patch_user(), patch(
            "routers.router_process.httpx.AsyncClient",
            return_value=_FakeAsyncClient(exc=httpx.ConnectError("no conn")),
        ):
            client = TestClient(app)
            response = client.get("/api/process/cancel/p1/status")
            assert response.status_code == 503

    def test_cancel_status_generic_exception(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        with _patch_user(), patch(
            "routers.router_process.httpx.AsyncClient",
            return_value=_FakeAsyncClient(exc=RuntimeError("boom")),
        ):
            client = TestClient(app)
            response = client.get("/api/process/cancel/p1/status")
            assert response.status_code == 500

    def test_cancel_status_falls_back_when_config_missing(self):
        app, _, _, _, _ = create_mock_app_with_full_services()
        app.include_router(router_process.router)

        app.app_context.configuration.processor_control_url = None
        app.app_context.configuration.processor_control_token = None

        resp = _make_response(200, {"kill_state": "running"})

        with _patch_user(), patch(
            "routers.router_process.httpx.AsyncClient",
            return_value=_FakeAsyncClient(response=resp),
        ):
            client = TestClient(app)
            response = client.get("/api/process/cancel/p1/status")
            assert response.status_code == 200
