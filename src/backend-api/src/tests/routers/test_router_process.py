"""Tests for routers/router_process.py."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from libs.base.typed_fastapi import TypedFastAPI
from libs.services.interfaces import ILoggerService
from libs.services.process_services import ProcessService
from libs.repositories.process_repository import ProcessRepository
from routers.router_process import router


AUTH_HEADERS = {"x-ms-client-principal-id": "user-1"}


def _make_async_cm(yielded):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=yielded)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _build(process_service=None, process_repo=None, configuration=None):
    app = TypedFastAPI()
    logger = MagicMock(spec=ILoggerService)

    process_service = process_service or MagicMock(spec=ProcessService)
    process_repo = process_repo or MagicMock()
    if not hasattr(process_repo, "add_async") or not isinstance(
        process_repo.add_async, AsyncMock
    ):
        process_repo.add_async = AsyncMock(return_value=None)
    # By default the authenticated caller (AUTH_HEADERS -> "user-1") owns the
    # process, so ownership checks pass. Individual tests override get_async to
    # exercise the not-found / not-owner (404) paths.
    if not isinstance(getattr(process_repo, "get_async", None), AsyncMock):
        process_repo.get_async = AsyncMock(
            return_value=SimpleNamespace(id="p-1", user_id="user-1")
        )

    scope = MagicMock()
    scope.get_service.side_effect = lambda t: (
        process_repo if t is ProcessRepository else MagicMock()
    )
    scope_cm = _make_async_cm(scope)

    ctx = MagicMock()
    ctx.configuration = configuration or SimpleNamespace(
        processor_control_url="http://proc:8080",
        processor_control_token="tok",
    )
    ctx.create_scope = MagicMock(return_value=scope_cm)

    def app_get(t):
        if t is ILoggerService:
            return logger
        if t is ProcessService:
            return process_service
        return MagicMock()

    ctx.get_service.side_effect = app_get
    app.app_context = ctx
    app.include_router(router)
    return app, process_service, process_repo


class TestCreateProcess:
    def test_returns_process_id(self):
        app, _svc, repo = _build()
        client = TestClient(app)
        res = client.post("/api/process/create", headers=AUTH_HEADERS)
        assert res.status_code == 200
        assert "process_id" in res.json()
        repo.add_async.assert_awaited()

    def test_returns_500_on_repo_error(self):
        repo = MagicMock()
        repo.add_async = AsyncMock(side_effect=RuntimeError("db down"))
        app, _, _ = _build(process_repo=repo)
        client = TestClient(app)
        res = client.post("/api/process/create", headers=AUTH_HEADERS)
        assert res.status_code == 500


class TestStatus:
    def test_returns_service_payload(self):
        svc = MagicMock(spec=ProcessService)
        svc.get_current_process = AsyncMock(return_value={"phase": "x"})
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.get("/api/process/status/abc/", headers=AUTH_HEADERS)
        assert res.status_code == 200
        assert res.json() == {"phase": "x"}

    def test_render_status(self):
        svc = MagicMock(spec=ProcessService)
        svc.render_current_process = AsyncMock(return_value=["a", "b"])
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.get("/api/process/status/abc/render/", headers=AUTH_HEADERS)
        assert res.status_code == 200
        assert res.json() == ["a", "b"]


class TestUploadFiles:
    def test_uploads_and_returns_files(self):
        svc = MagicMock(spec=ProcessService)
        svc.save_files_to_blob = AsyncMock(return_value=None)
        svc.get_all_uploaded_files = AsyncMock(return_value=[])
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.post(
            "/api/process/upload",
            data={"process_id": "p-1"},
            files={"files": ("a.txt", b"hi", "text/plain")},
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 200
        svc.save_files_to_blob.assert_awaited()

    def test_returns_500_on_service_error(self):
        svc = MagicMock(spec=ProcessService)
        svc.save_files_to_blob = AsyncMock(side_effect=RuntimeError("fail"))
        svc.get_all_uploaded_files = AsyncMock(return_value=[])
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.post(
            "/api/process/upload",
            data={"process_id": "p-1"},
            files={"files": ("a.txt", b"x", "text/plain")},
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 500


class TestDeleteFile:
    def test_returns_200(self):
        svc = MagicMock(spec=ProcessService)
        svc.delete_file_from_blob = AsyncMock(return_value=None)
        svc.get_all_uploaded_files = AsyncMock(return_value=[])
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.request(
            "DELETE",
            "/api/process/delete-file/foo.txt",
            data={"process_id": "p-1"},
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 200

    def test_returns_404_when_file_missing(self):
        svc = MagicMock(spec=ProcessService)
        svc.delete_file_from_blob = AsyncMock(side_effect=FileNotFoundError("x"))
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.request(
            "DELETE",
            "/api/process/delete-file/foo.txt",
            data={"process_id": "p-1"},
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 404


class TestDeleteProcess:
    def test_returns_200_with_deleted_count_message(self):
        svc = MagicMock(spec=ProcessService)
        svc.delete_all_files_from_blob = AsyncMock(return_value=3)
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.delete("/api/process/delete-process/p-1", headers=AUTH_HEADERS)
        assert res.status_code == 200
        assert "3 files removed" in res.json()["message"]

    def test_returns_500_on_error(self):
        svc = MagicMock(spec=ProcessService)
        svc.delete_all_files_from_blob = AsyncMock(side_effect=RuntimeError("boom"))
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.delete("/api/process/delete-process/p-1", headers=AUTH_HEADERS)
        assert res.status_code == 500


class TestStartProcessing:
    def test_returns_202(self):
        svc = MagicMock(spec=ProcessService)
        svc.process_enqueue = AsyncMock(return_value=None)
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.post(
            "/api/process/start-processing",
            data={"process_id": "p-1"},
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 202
        assert res.json()["status"] == "queued"

    def test_returns_500_on_service_error(self):
        svc = MagicMock(spec=ProcessService)
        svc.process_enqueue = AsyncMock(side_effect=RuntimeError("nope"))
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.post(
            "/api/process/start-processing",
            data={"process_id": "p-1"},
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 500


class TestDownload:
    def test_returns_zip(self):
        from routers.models.files import FileInfo

        files = [FileInfo(filename="a.txt", content=b"hello", content_type="text/plain", size=5)]
        svc = MagicMock(spec=ProcessService)
        svc.get_converted_files = AsyncMock(return_value=files)
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.get("/api/process/p-1/download", headers=AUTH_HEADERS)
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/zip"

    def test_returns_404_when_no_files(self):
        svc = MagicMock(spec=ProcessService)
        svc.get_converted_files = AsyncMock(return_value=[])
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.get("/api/process/p-1/download", headers=AUTH_HEADERS)
        assert res.status_code == 404


class TestProcessSummary:
    def test_returns_summary(self):
        from datetime import datetime, timezone

        entity = SimpleNamespace(id="p-1", created_at=datetime.now(timezone.utc))
        svc = MagicMock(spec=ProcessService)
        svc.get_process_summary = AsyncMock(return_value=(entity, ["a.txt", "b.txt"]))
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.get("/api/process/process-summary/p-1", headers=AUTH_HEADERS)
        assert res.status_code == 200
        body = res.json()
        assert body["Process"]["file_count"] == 2
        assert len(body["files"]) == 2

    def test_returns_500_on_error(self):
        svc = MagicMock(spec=ProcessService)
        svc.get_process_summary = AsyncMock(side_effect=RuntimeError("x"))
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.get("/api/process/process-summary/p-1", headers=AUTH_HEADERS)
        assert res.status_code == 500


class TestGetFileContent:
    def test_returns_content(self):
        svc = MagicMock(spec=ProcessService)
        svc.get_converted_file_content = AsyncMock(return_value="hello")
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.get("/api/process/p-1/file/a.txt", headers=AUTH_HEADERS)
        assert res.status_code == 200
        assert res.json() == {"content": "hello"}

    def test_returns_404_when_missing(self):
        svc = MagicMock(spec=ProcessService)
        svc.get_converted_file_content = AsyncMock(side_effect=FileNotFoundError())
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.get("/api/process/p-1/file/a.txt", headers=AUTH_HEADERS)
        assert res.status_code == 404

    def test_returns_400_on_unicode_error(self):
        svc = MagicMock(spec=ProcessService)
        svc.get_converted_file_content = AsyncMock(
            side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "x")
        )
        app, *_ = _build(process_service=svc)
        client = TestClient(app)
        res = client.get("/api/process/p-1/file/a.bin", headers=AUTH_HEADERS)
        assert res.status_code == 400


def _make_httpx_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data or {})
    resp.text = text
    return resp


def _patch_httpx_async_client(method, response):
    """Return a patcher that replaces httpx.AsyncClient with a context manager
    whose `.<method>` AsyncMock yields the given response."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    setattr(mock_client, method, AsyncMock(return_value=response))
    return patch("routers.router_process.httpx.AsyncClient", return_value=mock_client)


class TestCancelProcess:
    def test_returns_202_on_success(self):
        app, *_ = _build()
        client = TestClient(app)
        resp = _make_httpx_response(
            200,
            json_data={
                "kill_requested": True,
                "kill_state": "pending",
                "kill_requested_at": "2025-01-01",
            },
        )
        with _patch_httpx_async_client("post", resp):
            res = client.post("/api/process/cancel/p-1", headers=AUTH_HEADERS)
        assert res.status_code == 202
        assert res.json()["kill_state"] == "pending"

    def test_returns_502_on_processor_401(self):
        app, *_ = _build()
        client = TestClient(app)
        resp = _make_httpx_response(401, text="unauth")
        with _patch_httpx_async_client("post", resp):
            res = client.post("/api/process/cancel/p-1", headers=AUTH_HEADERS)
        assert res.status_code == 502

    def test_returns_502_on_processor_500(self):
        app, *_ = _build()
        client = TestClient(app)
        resp = _make_httpx_response(500, text="boom")
        with _patch_httpx_async_client("post", resp):
            res = client.post("/api/process/cancel/p-1", headers=AUTH_HEADERS)
        assert res.status_code == 502

    def test_returns_504_on_timeout(self):
        import httpx

        app, *_ = _build()
        client = TestClient(app)
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("t"))
        with patch(
            "routers.router_process.httpx.AsyncClient", return_value=mock_client
        ):
            res = client.post("/api/process/cancel/p-1", headers=AUTH_HEADERS)
        assert res.status_code == 504

    def test_returns_503_on_connect_error(self):
        import httpx

        app, *_ = _build()
        client = TestClient(app)
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("c"))
        with patch(
            "routers.router_process.httpx.AsyncClient", return_value=mock_client
        ):
            res = client.post("/api/process/cancel/p-1", headers=AUTH_HEADERS)
        assert res.status_code == 503


class TestCancelStatus:
    def test_returns_200_on_success(self):
        app, *_ = _build()
        client = TestClient(app)
        resp = _make_httpx_response(200, json_data={"kill_state": "pending"})
        with _patch_httpx_async_client("get", resp):
            res = client.get("/api/process/cancel/p-1/status", headers=AUTH_HEADERS)
        assert res.status_code == 200
        assert res.json() == {"kill_state": "pending"}

    def test_returns_502_on_processor_401(self):
        app, *_ = _build()
        client = TestClient(app)
        resp = _make_httpx_response(401, text="nope")
        with _patch_httpx_async_client("get", resp):
            res = client.get("/api/process/cancel/p-1/status", headers=AUTH_HEADERS)
        assert res.status_code == 502

    def test_returns_504_on_timeout(self):
        import httpx

        app, *_ = _build()
        client = TestClient(app)
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("t"))
        with patch(
            "routers.router_process.httpx.AsyncClient", return_value=mock_client
        ):
            res = client.get("/api/process/cancel/p-1/status", headers=AUTH_HEADERS)
        assert res.status_code == 504


# A process owned by a *different* user than the authenticated caller ("user-1").
OTHER_USER_PROCESS = SimpleNamespace(id="p-1", user_id="someone-else")


def _build_unowned(missing=False):
    """Build an app whose process repository returns a process the caller does
    not own (or no process at all when ``missing`` is True)."""
    repo = MagicMock()
    repo.get_async = AsyncMock(return_value=None if missing else OTHER_USER_PROCESS)
    app, svc, _ = _build(process_repo=repo)
    return app, svc


class TestProcessOwnershipEnforcement:
    """Every endpoint that accepts a process_id must reject callers who do not
    own the process with a 404 (not 403, to avoid confirming existence)."""

    def test_status_rejects_non_owner(self):
        app, _ = _build_unowned()
        res = TestClient(app).get("/api/process/status/p-1/", headers=AUTH_HEADERS)
        assert res.status_code == 404

    def test_render_status_rejects_non_owner(self):
        app, _ = _build_unowned()
        res = TestClient(app).get(
            "/api/process/status/p-1/render/", headers=AUTH_HEADERS
        )
        assert res.status_code == 404

    def test_upload_rejects_non_owner(self):
        app, svc = _build_unowned()
        svc.save_files_to_blob = AsyncMock(return_value=None)
        res = TestClient(app).post(
            "/api/process/upload",
            data={"process_id": "p-1"},
            files={"files": ("a.txt", b"hi", "text/plain")},
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 404
        svc.save_files_to_blob.assert_not_awaited()

    def test_delete_file_rejects_non_owner(self):
        app, svc = _build_unowned()
        svc.delete_file_from_blob = AsyncMock(return_value=None)
        res = TestClient(app).request(
            "DELETE",
            "/api/process/delete-file/foo.txt",
            data={"process_id": "p-1"},
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 404
        svc.delete_file_from_blob.assert_not_awaited()

    def test_delete_process_rejects_non_owner(self):
        app, svc = _build_unowned()
        svc.delete_all_files_from_blob = AsyncMock(return_value=1)
        res = TestClient(app).delete(
            "/api/process/delete-process/p-1", headers=AUTH_HEADERS
        )
        assert res.status_code == 404
        svc.delete_all_files_from_blob.assert_not_awaited()

    def test_start_processing_rejects_non_owner(self):
        app, svc = _build_unowned()
        svc.process_enqueue = AsyncMock(return_value=None)
        res = TestClient(app).post(
            "/api/process/start-processing",
            data={"process_id": "p-1"},
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 404
        svc.process_enqueue.assert_not_awaited()

    def test_download_rejects_non_owner(self):
        app, svc = _build_unowned()
        svc.get_converted_files = AsyncMock(return_value=[])
        res = TestClient(app).get("/api/process/p-1/download", headers=AUTH_HEADERS)
        assert res.status_code == 404
        svc.get_converted_files.assert_not_awaited()

    def test_process_summary_rejects_non_owner(self):
        app, svc = _build_unowned()
        svc.get_process_summary = AsyncMock(return_value=(None, []))
        res = TestClient(app).get(
            "/api/process/process-summary/p-1", headers=AUTH_HEADERS
        )
        assert res.status_code == 404
        svc.get_process_summary.assert_not_awaited()

    def test_file_content_rejects_non_owner(self):
        app, svc = _build_unowned()
        svc.get_converted_file_content = AsyncMock(return_value="x")
        res = TestClient(app).get(
            "/api/process/p-1/file/a.txt", headers=AUTH_HEADERS
        )
        assert res.status_code == 404
        svc.get_converted_file_content.assert_not_awaited()

    def test_cancel_rejects_non_owner_without_calling_processor(self):
        app, _ = _build_unowned()
        resp = _make_httpx_response(200, json_data={})
        with _patch_httpx_async_client("post", resp) as patched:
            res = TestClient(app).post("/api/process/cancel/p-1", headers=AUTH_HEADERS)
        assert res.status_code == 404
        patched.assert_not_called()

    def test_cancel_status_rejects_non_owner_without_calling_processor(self):
        app, _ = _build_unowned()
        resp = _make_httpx_response(200, json_data={})
        with _patch_httpx_async_client("get", resp) as patched:
            res = TestClient(app).get(
                "/api/process/cancel/p-1/status", headers=AUTH_HEADERS
            )
        assert res.status_code == 404
        patched.assert_not_called()

    def test_missing_process_returns_404(self):
        app, _ = _build_unowned(missing=True)
        res = TestClient(app).get("/api/process/p-1/download", headers=AUTH_HEADERS)
        assert res.status_code == 404
