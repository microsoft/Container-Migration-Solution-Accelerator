"""Tests for libs/services/process_services.py."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from libs.base.typed_fastapi import TypedFastAPI
from libs.services.interfaces import ILoggerService
from libs.services.process_services import ProcessService
from libs.repositories.process_repository import ProcessRepository
from libs.repositories.process_status_repository import ProcessStatusRepository
from libs.sas.storage.blob.async_helper import AsyncStorageBlobHelper
from libs.sas.storage.queue.async_helper import AsyncStorageQueueHelper
from routers.models.files import FileInfo
from routers.models.processes import enlist_process_queue_response


def _make_async_cm(yielded):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=yielded)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_service(*, blob_helper=None, queue_helper=None, scope_services=None):
    app = TypedFastAPI()
    logger = MagicMock(spec=ILoggerService)

    blob_helper = blob_helper or MagicMock()
    queue_helper = queue_helper or MagicMock()
    blob_cm = _make_async_cm(blob_helper)
    queue_cm = _make_async_cm(queue_helper)

    scope = MagicMock()
    scope.get_service.side_effect = lambda t: (
        (scope_services or {}).get(t, MagicMock())
    )
    scope_cm = _make_async_cm(scope)

    ctx = MagicMock()
    ctx.configuration = SimpleNamespace(
        storage_account_process_container="container",
        storage_account_process_queue="queue",
    )
    ctx.create_scope = MagicMock(return_value=scope_cm)

    def app_get(t):
        if t is ILoggerService:
            return logger
        if t is AsyncStorageBlobHelper:
            return blob_cm
        if t is AsyncStorageQueueHelper:
            return queue_cm
        return MagicMock()

    ctx.get_service.side_effect = app_get
    app.app_context = ctx
    return ProcessService(app), {
        "blob": blob_helper,
        "queue": queue_helper,
        "logger": logger,
        "scope": scope,
    }


@pytest.mark.asyncio
class TestSaveFilesToBlob:
    async def test_creates_container_when_missing(self):
        blob = MagicMock()
        blob.container_exists = AsyncMock(return_value=False)
        blob.create_container = AsyncMock(return_value=None)
        blob.upload_blob = AsyncMock(return_value=None)
        svc, _ = _make_service(blob_helper=blob)
        await svc.save_files_to_blob(
            "p1", [FileInfo(filename="a.txt", content=b"x", content_type="t", size=1)]
        )
        blob.create_container.assert_awaited_once()
        blob.upload_blob.assert_awaited_once()

    async def test_skips_create_when_container_exists(self):
        blob = MagicMock()
        blob.container_exists = AsyncMock(return_value=True)
        blob.create_container = AsyncMock(return_value=None)
        blob.upload_blob = AsyncMock(return_value=None)
        svc, _ = _make_service(blob_helper=blob)
        await svc.save_files_to_blob(
            "p1", [FileInfo(filename="a.txt", content=b"x", content_type="t", size=1)]
        )
        blob.create_container.assert_not_awaited()


@pytest.mark.asyncio
class TestGetAllUploadedFiles:
    async def test_returns_files(self):
        blob = MagicMock()
        blob.list_blobs = AsyncMock(
            return_value=[{"name": "p1/source/a.txt"}, {"name": "p1/source/"}]
        )
        blob.get_blob_properties = AsyncMock(
            return_value={"content_type": "text/plain", "size": 7}
        )
        svc, _ = _make_service(blob_helper=blob)
        files = await svc.get_all_uploaded_files("p1")
        assert len(files) == 1
        assert files[0].filename == "a.txt"
        assert files[0].size == 7

    async def test_propagates_error(self):
        blob = MagicMock()
        blob.list_blobs = AsyncMock(side_effect=RuntimeError("x"))
        svc, _ = _make_service(blob_helper=blob)
        with pytest.raises(RuntimeError):
            await svc.get_all_uploaded_files("p1")


@pytest.mark.asyncio
class TestDeleteFileFromBlob:
    async def test_deletes_existing(self):
        blob = MagicMock()
        blob.blob_exists = AsyncMock(return_value=True)
        blob.delete_blob = AsyncMock(return_value=None)
        svc, _ = _make_service(blob_helper=blob)
        await svc.delete_file_from_blob("p1", "a.txt")
        blob.delete_blob.assert_awaited_once()

    async def test_raises_filenotfound_when_missing(self):
        blob = MagicMock()
        blob.blob_exists = AsyncMock(return_value=False)
        svc, _ = _make_service(blob_helper=blob)
        with pytest.raises(FileNotFoundError):
            await svc.delete_file_from_blob("p1", "missing.txt")

    async def test_propagates_other_errors(self):
        blob = MagicMock()
        blob.blob_exists = AsyncMock(return_value=True)
        blob.delete_blob = AsyncMock(side_effect=RuntimeError("x"))
        svc, _ = _make_service(blob_helper=blob)
        with pytest.raises(RuntimeError):
            await svc.delete_file_from_blob("p1", "a.txt")


@pytest.mark.asyncio
class TestDeleteAllFilesFromBlob:
    async def test_deletes_each_and_returns_count(self):
        blob = MagicMock()
        blob.list_blobs = AsyncMock(
            return_value=[
                {"name": "p1/source/a.txt"},
                {"name": "p1/source/b.txt"},
                {"name": "p1/source/"},
            ]
        )
        blob.delete_blob = AsyncMock(return_value=None)
        svc, _ = _make_service(blob_helper=blob)
        count = await svc.delete_all_files_from_blob("p1")
        assert count == 2

    async def test_continues_when_one_fails(self):
        blob = MagicMock()
        blob.list_blobs = AsyncMock(
            return_value=[{"name": "p1/source/a.txt"}, {"name": "p1/source/b.txt"}]
        )
        blob.delete_blob = AsyncMock(side_effect=[RuntimeError("x"), None])
        svc, _ = _make_service(blob_helper=blob)
        count = await svc.delete_all_files_from_blob("p1")
        assert count == 1


@pytest.mark.asyncio
class TestProcessEnqueue:
    async def test_creates_queue_and_sends_message(self):
        queue = MagicMock()
        queue.queue_exists = AsyncMock(return_value=False)
        queue.create_queue = AsyncMock(return_value=None)
        queue.send_message = AsyncMock(return_value=None)
        svc, _ = _make_service(queue_helper=queue)
        msg = enlist_process_queue_response(user_id="u", process_id="p", message="hi")
        await svc.process_enqueue(msg)
        queue.create_queue.assert_awaited_once()
        queue.send_message.assert_awaited_once()

    async def test_skips_create_when_queue_exists(self):
        queue = MagicMock()
        queue.queue_exists = AsyncMock(return_value=True)
        queue.create_queue = AsyncMock(return_value=None)
        queue.send_message = AsyncMock(return_value=None)
        svc, _ = _make_service(queue_helper=queue)
        msg = enlist_process_queue_response(user_id="u", process_id="p")
        await svc.process_enqueue(msg)
        queue.create_queue.assert_not_awaited()
        queue.send_message.assert_awaited_once()


@pytest.mark.asyncio
class TestGetCurrentProcess:
    async def test_returns_repo_value(self):
        repo = MagicMock()
        repo.get_process_status_by_process_id = AsyncMock(return_value="snapshot")
        svc, _ = _make_service(scope_services={ProcessStatusRepository: repo})
        assert await svc.get_current_process("p1") == "snapshot"


@pytest.mark.asyncio
class TestRenderCurrentProcess:
    async def test_returns_repo_value(self):
        repo = MagicMock()
        repo.render_agent_status = AsyncMock(return_value=["a", "b"])
        svc, _ = _make_service(scope_services={ProcessStatusRepository: repo})
        assert await svc.render_current_process("p1") == ["a", "b"]


@pytest.mark.asyncio
class TestGetConvertedFiles:
    async def test_downloads_and_returns_files(self):
        blob = MagicMock()
        blob.list_blobs = AsyncMock(return_value=[{"name": "p1/converted/a.txt"}])
        blob.download_blob = AsyncMock(return_value=b"hello")
        svc, _ = _make_service(blob_helper=blob)
        files = await svc.get_converted_files("p1")
        assert files[0].filename == "a.txt"
        assert files[0].content == b"hello"
        assert files[0].size == 5

    async def test_propagates_error(self):
        blob = MagicMock()
        blob.list_blobs = AsyncMock(side_effect=RuntimeError("x"))
        svc, _ = _make_service(blob_helper=blob)
        with pytest.raises(RuntimeError):
            await svc.get_converted_files("p1")


@pytest.mark.asyncio
class TestGetProcessSummary:
    async def test_returns_entity_and_filenames(self):
        repo = MagicMock()
        entity = SimpleNamespace(id="p1")
        repo.get_async = AsyncMock(return_value=entity)
        blob = MagicMock()
        blob.list_blobs = AsyncMock(
            return_value=[
                {"name": "p1/converted/a.txt"},
                {"name": "p1/converted/"},
            ]
        )
        svc, _ = _make_service(
            blob_helper=blob, scope_services={ProcessRepository: repo}
        )
        result_entity, names = await svc.get_process_summary("p1")
        assert result_entity is entity
        assert names == ["a.txt"]

    async def test_raises_when_process_missing(self):
        repo = MagicMock()
        repo.get_async = AsyncMock(return_value=None)
        svc, _ = _make_service(scope_services={ProcessRepository: repo})
        with pytest.raises(ValueError):
            await svc.get_process_summary("p1")


@pytest.mark.asyncio
class TestGetConvertedFileContent:
    async def test_returns_decoded_content(self):
        blob = MagicMock()
        blob.download_blob = AsyncMock(return_value="hello".encode())
        svc, _ = _make_service(blob_helper=blob)
        assert await svc.get_converted_file_content("p1", "a.txt") == "hello"

    async def test_returns_empty_string_when_blob_empty(self):
        blob = MagicMock()
        blob.download_blob = AsyncMock(return_value=None)
        svc, _ = _make_service(blob_helper=blob)
        assert await svc.get_converted_file_content("p1", "a.txt") == ""

    async def test_propagates_error(self):
        blob = MagicMock()
        blob.download_blob = AsyncMock(side_effect=RuntimeError("x"))
        svc, _ = _make_service(blob_helper=blob)
        with pytest.raises(RuntimeError):
            await svc.get_converted_file_content("p1", "a.txt")
