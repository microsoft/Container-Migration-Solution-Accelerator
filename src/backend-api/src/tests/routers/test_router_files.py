"""Tests for routers/router_files.py."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from libs.base.typed_fastapi import TypedFastAPI
from libs.services.interfaces import ILoggerService
from routers.router_files import router


def _make_async_cm(yielded):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=yielded)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_app(*, process_record=None, file_count=1, blob_helper=None):
    app = TypedFastAPI()

    logger = MagicMock(spec=ILoggerService)
    process_repo = MagicMock()
    process_repo.get_async = AsyncMock(
        return_value=process_record
        or SimpleNamespace(
            id="p-1",
            user_id="user-1",
            source_file_count=0,
            status="initialized",
        )
    )
    process_repo.update_async = AsyncMock(return_value=None)

    file_repo = MagicMock()
    file_repo.add_async = AsyncMock(return_value=None)
    file_repo.count_async = AsyncMock(return_value=file_count)

    if blob_helper is None:
        blob_helper = MagicMock()
        blob_helper.upload_blob = AsyncMock(return_value=None)

    blob_cm = _make_async_cm(blob_helper)

    def scope_get_service(t):
        from libs.repositories.file_repository import FileRepository
        from libs.repositories.process_repository import ProcessRepository
        from libs.sas.storage import AsyncStorageBlobHelper

        if t is ProcessRepository:
            return process_repo
        if t is FileRepository:
            return file_repo
        if t is AsyncStorageBlobHelper:
            return blob_cm
        return MagicMock()

    scope = MagicMock()
    scope.get_service.side_effect = scope_get_service
    scope_cm = _make_async_cm(scope)

    ctx = MagicMock()
    ctx.configuration = SimpleNamespace(storage_account_process_container="container")
    ctx.create_scope = MagicMock(return_value=scope_cm)

    def app_get_service(t):
        if t is ILoggerService:
            return logger
        return MagicMock()

    ctx.get_service.side_effect = app_get_service
    app.app_context = ctx
    app.include_router(router)
    return app, {
        "logger": logger,
        "process_repo": process_repo,
        "file_repo": file_repo,
        "blob_helper": blob_helper,
    }


VALID_PROCESS_ID = "123e4567-e89b-42d3-a456-426614174000"
AUTH_HEADERS = {"x-ms-client-principal-id": "user-1"}


class TestUploadOptions:
    def test_returns_200(self):
        app, _ = _make_app()
        client = TestClient(app)
        res = client.options("/api/file/upload")
        assert res.status_code == 200

    def test_returns_cors_headers(self):
        app, _ = _make_app()
        client = TestClient(app)
        res = client.options("/api/file/upload")
        assert res.headers["Access-Control-Allow-Origin"] == "*"
        assert "POST" in res.headers["Access-Control-Allow-Methods"]


class TestUploadFile:
    def test_uploads_file_successfully(self):
        app, mocks = _make_app()
        client = TestClient(app)
        res = client.post(
            "/api/file/upload",
            files={"file": ("hello.txt", b"hi", "text/plain")},
            data={"process_id": VALID_PROCESS_ID},
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["file"]["original_name"] == "hello.txt"
        assert body["batch"]["batch_id"] == "p-1"
        mocks["blob_helper"].upload_blob.assert_awaited()
        mocks["process_repo"].update_async.assert_awaited()

    def test_returns_400_on_invalid_process_id(self):
        app, _ = _make_app()
        client = TestClient(app)
        res = client.post(
            "/api/file/upload",
            files={"file": ("x.txt", b"x", "text/plain")},
            data={"process_id": "not-a-uuid"},
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 400

    def test_sanitizes_filename_to_blob_path(self):
        app, mocks = _make_app()
        client = TestClient(app)
        client.post(
            "/api/file/upload",
            files={"file": ("a b!c.txt", b"x", "text/plain")},
            data={"process_id": VALID_PROCESS_ID},
            headers=AUTH_HEADERS,
        )
        kwargs = mocks["blob_helper"].upload_blob.await_args.kwargs
        assert kwargs["blob_name"].endswith("/source/a_b_c.txt")

    def test_marks_status_ready_to_process_when_files_exist(self):
        app, mocks = _make_app(file_count=3)
        client = TestClient(app)
        client.post(
            "/api/file/upload",
            files={"file": ("a.txt", b"x", "text/plain")},
            data={"process_id": VALID_PROCESS_ID},
            headers=AUTH_HEADERS,
        )
        updated = mocks["process_repo"].update_async.await_args.args[0]
        assert updated.source_file_count == 3
        assert updated.status == "ready_to_process"

    def test_returns_500_when_blob_upload_fails(self):
        bad_blob = MagicMock()
        bad_blob.upload_blob = AsyncMock(side_effect=RuntimeError("boom"))
        app, _ = _make_app(blob_helper=bad_blob)
        client = TestClient(app)
        res = client.post(
            "/api/file/upload",
            files={"file": ("a.txt", b"x", "text/plain")},
            data={"process_id": VALID_PROCESS_ID},
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 500

    def test_returns_404_when_caller_does_not_own_process(self):
        # Process exists but is owned by a different user than the caller.
        app, mocks = _make_app(
            process_record=SimpleNamespace(
                id="p-1",
                user_id="someone-else",
                source_file_count=0,
                status="initialized",
            )
        )
        client = TestClient(app)
        res = client.post(
            "/api/file/upload",
            files={"file": ("a.txt", b"x", "text/plain")},
            data={"process_id": VALID_PROCESS_ID},
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 404
        mocks["blob_helper"].upload_blob.assert_not_awaited()
        mocks["process_repo"].update_async.assert_not_awaited()

    def test_returns_404_when_process_missing(self):
        app, mocks = _make_app(process_record=False)
        # Force get_async to return None (no such process).
        mocks["process_repo"].get_async = AsyncMock(return_value=None)
        client = TestClient(app)
        res = client.post(
            "/api/file/upload",
            files={"file": ("a.txt", b"x", "text/plain")},
            data={"process_id": VALID_PROCESS_ID},
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 404
        mocks["blob_helper"].upload_blob.assert_not_awaited()
