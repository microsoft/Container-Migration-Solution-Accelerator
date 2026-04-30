"""Targeted gap-filling tests for process_services to reach >=85% coverage.

Covers blob/queue error paths, missing-config paths, and the
get_converted_file_content / get_process_summary / render_current_process
methods which were not exercised by the existing extended suite.
"""
import asyncio
from unittest.mock import MagicMock, AsyncMock

from libs.services.process_services import ProcessService
from routers.models.files import FileInfo
from routers.models.processes import enlist_process_queue_response


def _run(coro):
    return asyncio.run(coro)


def create_mock_app():
    """Create a mock TypedFastAPI app for testing."""
    mock_app = MagicMock()
    mock_context = MagicMock()
    mock_config = MagicMock()
    mock_logger = MagicMock()

    mock_config.storage_account_process_container = "test-container"
    mock_config.storage_account_process_queue = "test-queue"
    mock_context.configuration = mock_config
    mock_context.get_service = MagicMock(return_value=mock_logger)
    mock_app.app_context = mock_context

    return mock_app, mock_context, mock_logger, mock_config


def _make_blob_helper(**method_returns):
    """Build a blob helper async-context-manager mock."""
    helper = MagicMock()
    helper.__aenter__ = AsyncMock(return_value=method_returns.pop("aenter_value", helper))
    helper.__aexit__ = AsyncMock(return_value=False)
    for name, value in method_returns.items():
        if isinstance(value, Exception):
            setattr(helper, name, AsyncMock(side_effect=value))
        else:
            setattr(helper, name, AsyncMock(return_value=value))
    return helper


class TestSaveFilesToBlobErrors:
    def test_raises_when_blob_helper_unavailable(self):
        mock_app, mock_context, _, _ = create_mock_app()
        helper = _make_blob_helper(aenter_value=None)
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)
        files = [FileInfo(filename="a.txt", content=b"x", content_type="text/plain", size=1)]

        async def go():
            try:
                await service.save_files_to_blob("p1", files)
                return False
            except ValueError as e:
                return "Blob helper service is not available" in str(e)

        assert _run(go())


class TestGetAllUploadedFilesErrors:
    def test_raises_when_blob_helper_unavailable(self):
        mock_app, mock_context, _, _ = create_mock_app()
        helper = _make_blob_helper(aenter_value=None)
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.get_all_uploaded_files("p1")
                return False
            except ValueError as e:
                return "Blob helper service is not available" in str(e)

        assert _run(go())

    def test_raises_when_container_not_configured(self):
        mock_app, mock_context, _, mock_config = create_mock_app()
        mock_config.storage_account_process_container = None
        helper = _make_blob_helper()
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.get_all_uploaded_files("p1")
                return False
            except ValueError as e:
                return "container name is not configured" in str(e)

        assert _run(go())

    def test_propagates_blob_listing_exception(self):
        mock_app, mock_context, _, _ = create_mock_app()
        helper = _make_blob_helper(list_blobs=RuntimeError("listing failed"))
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.get_all_uploaded_files("p1")
                return False
            except RuntimeError:
                return True

        assert _run(go())


class TestDeleteFileFromBlobErrors:
    def test_raises_when_blob_helper_unavailable(self):
        mock_app, mock_context, _, _ = create_mock_app()
        helper = _make_blob_helper(aenter_value=None)
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.delete_file_from_blob("p1", "f.txt")
                return False
            except ValueError as e:
                return "Blob helper service is not available" in str(e)

        assert _run(go())

    def test_raises_when_container_not_configured(self):
        mock_app, mock_context, _, mock_config = create_mock_app()
        mock_config.storage_account_process_container = None
        helper = _make_blob_helper()
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.delete_file_from_blob("p1", "f.txt")
                return False
            except ValueError as e:
                return "container name is not configured" in str(e)

        assert _run(go())

    def test_propagates_generic_exception(self):
        mock_app, mock_context, _, _ = create_mock_app()
        helper = _make_blob_helper(blob_exists=RuntimeError("boom"))
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.delete_file_from_blob("p1", "f.txt")
                return False
            except RuntimeError:
                return True

        assert _run(go())


class TestDeleteAllFilesFromBlobErrors:
    def test_raises_when_blob_helper_unavailable(self):
        mock_app, mock_context, _, _ = create_mock_app()
        helper = _make_blob_helper(aenter_value=None)
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.delete_all_files_from_blob("p1")
                return False
            except ValueError as e:
                return "Blob helper service is not available" in str(e)

        assert _run(go())

    def test_raises_when_container_not_configured(self):
        mock_app, mock_context, _, mock_config = create_mock_app()
        mock_config.storage_account_process_container = None
        helper = _make_blob_helper()
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.delete_all_files_from_blob("p1")
                return False
            except ValueError as e:
                return "container name is not configured" in str(e)

        assert _run(go())

    def test_propagates_listing_exception(self):
        mock_app, mock_context, _, _ = create_mock_app()
        helper = _make_blob_helper(list_blobs=RuntimeError("list failed"))
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.delete_all_files_from_blob("p1")
                return False
            except RuntimeError:
                return True

        assert _run(go())


class TestRenderCurrentProcess:
    def test_render_current_process_calls_repo(self):
        mock_app, mock_context, _, _ = create_mock_app()

        repo = AsyncMock()
        repo.render_agent_status = AsyncMock(return_value={"phase": "x"})

        scope = MagicMock()
        scope.get_service = MagicMock(return_value=repo)
        scope.__aenter__ = AsyncMock(return_value=scope)
        scope.__aexit__ = AsyncMock(return_value=False)
        mock_context.create_scope = MagicMock(return_value=scope)

        service = ProcessService(mock_app)

        async def go():
            return await service.render_current_process("p1")

        result = _run(go())
        assert result == {"phase": "x"}
        repo.render_agent_status.assert_called_once_with("p1")


class TestGetConvertedFilesErrors:
    def test_raises_when_container_not_configured(self):
        mock_app, mock_context, _, mock_config = create_mock_app()
        mock_config.storage_account_process_container = None
        helper = _make_blob_helper()
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.get_converted_files("p1")
                return False
            except ValueError as e:
                return "container name is not configured" in str(e)

        assert _run(go())

    def test_propagates_listing_exception(self):
        mock_app, mock_context, _, _ = create_mock_app()
        helper = _make_blob_helper(list_blobs=RuntimeError("oops"))
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.get_converted_files("p1")
                return False
            except RuntimeError:
                return True

        assert _run(go())


class TestGetProcessSummary:
    def test_returns_entity_and_filenames(self):
        mock_app, mock_context, _, _ = create_mock_app()

        process_repo = AsyncMock()
        process_entity = MagicMock(id="p1")
        process_repo.get_async = AsyncMock(return_value=process_entity)

        scope = MagicMock()
        scope.get_service = MagicMock(return_value=process_repo)
        scope.__aenter__ = AsyncMock(return_value=scope)
        scope.__aexit__ = AsyncMock(return_value=False)
        mock_context.create_scope = MagicMock(return_value=scope)

        helper = _make_blob_helper(
            list_blobs=[
                {"name": "p1/converted/"},  # folder entry filtered out
                {"name": "p1/converted/a.txt"},
                {"name": "p1/converted/b.txt"},
            ]
        )
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            return await service.get_process_summary("p1")

        entity, names = _run(go())
        assert entity is process_entity
        assert sorted(names) == ["a.txt", "b.txt"]

    def test_raises_when_process_not_found(self):
        mock_app, mock_context, _, _ = create_mock_app()

        process_repo = AsyncMock()
        process_repo.get_async = AsyncMock(return_value=None)

        scope = MagicMock()
        scope.get_service = MagicMock(return_value=process_repo)
        scope.__aenter__ = AsyncMock(return_value=scope)
        scope.__aexit__ = AsyncMock(return_value=False)
        mock_context.create_scope = MagicMock(return_value=scope)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.get_process_summary("missing")
                return False
            except ValueError as e:
                return "not found" in str(e)

        assert _run(go())

    def test_raises_when_blob_helper_unavailable(self):
        mock_app, mock_context, _, _ = create_mock_app()

        process_repo = AsyncMock()
        process_repo.get_async = AsyncMock(return_value=MagicMock(id="p1"))

        scope = MagicMock()
        scope.get_service = MagicMock(return_value=process_repo)
        scope.__aenter__ = AsyncMock(return_value=scope)
        scope.__aexit__ = AsyncMock(return_value=False)
        mock_context.create_scope = MagicMock(return_value=scope)

        helper = _make_blob_helper(aenter_value=None)

        def get_service(svc):
            # blob helper resolved via top-level get_service call
            return helper

        mock_context.get_service = MagicMock(side_effect=get_service)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.get_process_summary("p1")
                return False
            except (ValueError, Exception) as e:
                return "Blob helper service is not available" in str(e)

        assert _run(go())

    def test_raises_when_container_not_configured(self):
        mock_app, mock_context, _, mock_config = create_mock_app()
        mock_config.storage_account_process_container = None

        process_repo = AsyncMock()
        process_repo.get_async = AsyncMock(return_value=MagicMock(id="p1"))

        scope = MagicMock()
        scope.get_service = MagicMock(return_value=process_repo)
        scope.__aenter__ = AsyncMock(return_value=scope)
        scope.__aexit__ = AsyncMock(return_value=False)
        mock_context.create_scope = MagicMock(return_value=scope)

        helper = _make_blob_helper()
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.get_process_summary("p1")
                return False
            except (ValueError, Exception) as e:
                return "container name is not configured" in str(e)

        assert _run(go())


class TestGetConvertedFileContent:
    def test_returns_decoded_content(self):
        mock_app, mock_context, _, _ = create_mock_app()
        helper = _make_blob_helper(download_blob=b"hello world")
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            return await service.get_converted_file_content("p1", "out.txt")

        assert _run(go()) == "hello world"

    def test_returns_empty_string_when_blob_empty(self):
        mock_app, mock_context, _, _ = create_mock_app()
        helper = _make_blob_helper(download_blob=b"")
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            return await service.get_converted_file_content("p1", "out.txt")

        assert _run(go()) == ""

    def test_raises_when_blob_helper_unavailable(self):
        mock_app, mock_context, _, _ = create_mock_app()
        helper = _make_blob_helper(aenter_value=None)
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.get_converted_file_content("p1", "out.txt")
                return False
            except ValueError as e:
                return "Blob helper service is not available" in str(e)

        assert _run(go())

    def test_raises_when_container_not_configured(self):
        mock_app, mock_context, _, mock_config = create_mock_app()
        mock_config.storage_account_process_container = None
        helper = _make_blob_helper()
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.get_converted_file_content("p1", "out.txt")
                return False
            except ValueError as e:
                return "container name is not configured" in str(e)

        assert _run(go())

    def test_propagates_download_exception(self):
        mock_app, mock_context, _, _ = create_mock_app()
        helper = _make_blob_helper(download_blob=RuntimeError("download error"))
        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)

        async def go():
            try:
                await service.get_converted_file_content("p1", "out.txt")
                return False
            except RuntimeError:
                return True

        assert _run(go())


class TestProcessEnqueueIntegration:
    def test_enqueue_with_files_in_message(self):
        """Exercise the success path with an actual queue message having files."""
        mock_app, mock_context, _, _ = create_mock_app()

        helper = MagicMock()
        helper.__aenter__ = AsyncMock(return_value=helper)
        helper.__aexit__ = AsyncMock(return_value=False)
        helper.queue_exists = AsyncMock(return_value=True)
        helper.send_message = AsyncMock()

        mock_context.get_service = MagicMock(return_value=helper)

        service = ProcessService(mock_app)
        msg = enlist_process_queue_response(
            message="ok",
            user_id="u1",
            process_id="p1",
            files=[],
        )

        async def go():
            await service.process_enqueue(msg)

        _run(go())
        helper.send_message.assert_called_once()
