# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Coverage for QueueMigrationService internals: worker loop, processing,
control watcher, blob cleanup, and start/stop lifecycle."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.queue_service import QueueMigrationService, QueueServiceConfig
from steps.analysis.models.step_param import Analysis_TaskParam


def _run(coro):
    return asyncio.run(coro)


def _service(account: str = "myacct", queue: str = "q") -> QueueMigrationService:
    """Bypass __init__ to avoid real Azure clients."""
    s = QueueMigrationService.__new__(QueueMigrationService)
    s.config = QueueServiceConfig(
        storage_account_name=account,
        queue_name=queue,
        poll_interval_seconds=0,  # don't slow tests
        control_poll_interval_seconds=0,
        visibility_timeout_minutes=1,
        concurrent_workers=1,
    )
    s.is_running = False
    s.app_context = None
    s.main_queue = MagicMock()
    s.queue_service = MagicMock()
    s.active_workers = set()
    s._worker_tasks = {}
    s._worker_inflight = {}
    s._worker_inflight_message = {}
    s._worker_inflight_task_param = {}
    s._worker_inflight_task = {}
    s._control_watcher_task = None
    s.instance_id = 123
    s.debug_mode = False
    return s


def _task_param(pid: str = "p1") -> Analysis_TaskParam:
    return Analysis_TaskParam(
        process_id=pid,
        container_name="c",
        source_file_folder=f"{pid}/source",
        workspace_file_folder=f"{pid}/workspace",
        output_file_folder=f"{pid}/converted",
    )


# -----------------------------------------------------------------------------
# stop_service
# -----------------------------------------------------------------------------


class TestStopService:
    def test_stop_service_clears_state_and_closes_clients(self):
        s = _service()
        s.is_running = True
        QueueMigrationService._active_instances.add(s.instance_id)
        s._worker_inflight = {1: "p"}
        s._worker_inflight_message = {1: ("m", "r")}
        s._worker_inflight_task_param = {1: _task_param()}
        s._worker_inflight_task = {1: MagicMock()}
        _run(s.stop_service())
        assert s.is_running is False
        assert s._worker_inflight == {}
        assert s._worker_inflight_message == {}
        assert s._worker_inflight_task_param == {}
        assert s._worker_inflight_task == {}
        assert s.instance_id not in QueueMigrationService._active_instances
        s.main_queue.close.assert_called_once()
        s.queue_service.close.assert_called_once()

    def test_stop_service_cancels_workers(self):
        s = _service()
        s.is_running = True

        async def _long():
            await asyncio.sleep(60)

        async def _go():
            t1 = asyncio.create_task(_long())
            s._worker_tasks = {1: t1}
            await s.stop_service()
            assert t1.cancelled() or t1.done()

        _run(_go())

    def test_stop_service_cancels_control_watcher(self):
        s = _service()
        s.is_running = True

        async def _long():
            await asyncio.sleep(60)

        async def _go():
            wt = asyncio.create_task(_long())
            s._control_watcher_task = wt
            await s.stop_service()
            assert wt.cancelled() or wt.done()
            assert s._control_watcher_task is None

        _run(_go())

    def test_stop_service_swallows_close_errors(self):
        s = _service()
        s.is_running = True
        s.main_queue.close.side_effect = RuntimeError("boom")
        s.queue_service.close.side_effect = RuntimeError("boom")
        _run(s.stop_service())  # no raise


# -----------------------------------------------------------------------------
# stop_worker
# -----------------------------------------------------------------------------


class TestStopWorker:
    def test_stop_worker_missing_returns_false(self):
        s = _service()
        ok = _run(s.stop_worker(99))
        assert ok is False

    def test_stop_worker_cancels_completed_task(self):
        """stop_worker called against an already-completed task still returns True
        and cleans up bookkeeping."""
        s = _service()

        async def _quick():
            return "done"

        async def _go():
            t = asyncio.create_task(_quick())
            await asyncio.sleep(0)  # let it finish
            s._worker_tasks = {2: t}
            s._worker_inflight = {2: "pid"}
            ok = await s.stop_worker(2, timeout_seconds=1.0)
            assert ok is True
            assert 2 not in s._worker_tasks
            assert 2 not in s._worker_inflight

        _run(_go())

    def test_stop_worker_no_inflight_branch(self):
        """Cover the 'no inflight' log branch."""
        s = _service()

        async def _quick():
            return None

        async def _go():
            t = asyncio.create_task(_quick())
            await asyncio.sleep(0)
            s._worker_tasks = {3: t}
            ok = await s.stop_worker(3, timeout_seconds=1.0)
            assert ok is True

        _run(_go())


# -----------------------------------------------------------------------------
# control watcher
# -----------------------------------------------------------------------------


class TestControlWatcher:
    def test_idle_when_no_inflight(self):
        s = _service()
        s.is_running = True
        ctx = MagicMock()
        ctrl = MagicMock()
        ctx.get_service_async = AsyncMock(return_value=ctrl)
        s.app_context = ctx

        async def _go():
            task = asyncio.create_task(s._control_watcher_loop())
            await asyncio.sleep(0.01)
            s.is_running = False
            await asyncio.sleep(0.01)
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        _run(_go())

    def test_processes_kill_request(self):
        s = _service()
        s.is_running = True
        s._worker_inflight = {1: "p1"}

        record = SimpleNamespace(kill_requested=True, kill_state="pending")
        # Track invocations: after first ack/mark_executed, flip is_running so loop exits.
        ctrl = MagicMock()
        ctrl.get = AsyncMock(return_value=record)

        async def _ack(*_a, **_kw):
            s.is_running = False  # let the loop exit cleanly after this ack

        ctrl.ack_executing = AsyncMock(side_effect=_ack)
        ctrl.mark_executed = AsyncMock()
        ctx = MagicMock()
        ctx.get_service_async = AsyncMock(return_value=ctrl)
        s.app_context = ctx
        s.stop_process = AsyncMock(return_value=True)

        _run(s._control_watcher_loop())
        ctrl.ack_executing.assert_awaited()
        ctrl.mark_executed.assert_awaited()

    def test_skips_records_already_executed(self):
        s = _service()
        s.is_running = True
        s._worker_inflight = {1: "p1"}

        record = SimpleNamespace(kill_requested=True, kill_state="executed")
        ctrl = MagicMock()
        get_calls = {"n": 0}

        async def _get(_pid):
            get_calls["n"] += 1
            if get_calls["n"] >= 1:
                s.is_running = False  # exit after first iteration
            return record

        ctrl.get = AsyncMock(side_effect=_get)
        ctrl.ack_executing = AsyncMock()
        ctx = MagicMock()
        ctx.get_service_async = AsyncMock(return_value=ctrl)
        s.app_context = ctx

        _run(s._control_watcher_loop())
        ctrl.ack_executing.assert_not_awaited()

    def test_falls_back_to_direct_construction(self):
        s = _service()
        s.is_running = False  # don't loop
        ctx = MagicMock()
        ctx.get_service_async = AsyncMock(side_effect=RuntimeError("no svc"))
        s.app_context = ctx
        with patch("services.queue_service.ProcessControlManager") as MockMgr:
            MockMgr.return_value = MagicMock()
            _run(s._control_watcher_loop())
            MockMgr.assert_called_once_with(ctx)

    def test_swallows_loop_iteration_errors(self):
        s = _service()
        s.is_running = True
        s._worker_inflight = {1: "p1"}
        ctrl = MagicMock()
        get_calls = {"n": 0}

        async def _get(_pid):
            get_calls["n"] += 1
            if get_calls["n"] >= 1:
                s.is_running = False  # exit after first iteration
            raise RuntimeError("bad")

        ctrl.get = AsyncMock(side_effect=_get)
        ctx = MagicMock()
        ctx.get_service_async = AsyncMock(return_value=ctrl)
        s.app_context = ctx

        _run(s._control_watcher_loop())  # exception swallowed by loop


# -----------------------------------------------------------------------------
# _worker_loop
# -----------------------------------------------------------------------------


class TestWorkerLoop:
    def test_worker_loop_no_main_queue_sleeps(self):
        s = _service()
        s.main_queue = None
        s.is_running = True
        # After one iteration of the no-queue branch, exit cleanly.
        original_sleep = asyncio.sleep
        sleep_calls = {"n": 0}

        async def _patched_sleep(delay, *a, **kw):
            sleep_calls["n"] += 1
            if sleep_calls["n"] >= 1:
                s.is_running = False
            await original_sleep(0)

        with patch("services.queue_service.asyncio.sleep", new=_patched_sleep):
            _run(s._worker_loop(1))
        assert sleep_calls["n"] >= 1

    def test_worker_loop_swallows_receive_errors(self):
        s = _service()
        s.is_running = True

        original_sleep = asyncio.sleep
        sleep_calls = {"n": 0}

        def _receive(*_a, **_kw):
            raise RuntimeError("transient")

        async def _patched_sleep(delay, *a, **kw):
            sleep_calls["n"] += 1
            if sleep_calls["n"] >= 1:
                s.is_running = False
            await original_sleep(0)

        s.main_queue.receive_messages.side_effect = _receive
        with patch("services.queue_service.asyncio.sleep", new=_patched_sleep):
            _run(s._worker_loop(1))

    def test_worker_loop_iterates_message(self):
        s = _service()
        s.is_running = True

        msg = SimpleNamespace(id="m1", pop_receipt="r1", content="x")

        # Configure to yield one message then no more — flip is_running
        call_state = {"calls": 0}

        def _receive(*_a, **_kw):
            call_state["calls"] += 1
            if call_state["calls"] == 1:
                return iter([msg])
            s.is_running = False
            return iter([])

        s.main_queue.receive_messages.side_effect = _receive

        async def _process(worker_id, queue_message):  # noqa: D401
            return None

        s._process_queue_message = _process  # type: ignore[assignment]

        _run(s._worker_loop(7))
        assert call_state["calls"] >= 1

    def test_worker_loop_handles_job_crash(self):
        """Job exception triggers _handle_failed_no_retry path."""
        s = _service()
        s.is_running = True
        msg = SimpleNamespace(id="m1", pop_receipt="r1", content="x")
        call_state = {"calls": 0}

        def _receive(*_a, **_kw):
            call_state["calls"] += 1
            if call_state["calls"] == 1:
                return iter([msg])
            s.is_running = False
            return iter([])

        s.main_queue.receive_messages.side_effect = _receive

        async def _crash(worker_id, queue_message):  # noqa: D401
            raise RuntimeError("boom")

        s._process_queue_message = _crash  # type: ignore[assignment]
        s._handle_failed_no_retry = AsyncMock()

        _run(s._worker_loop(1))
        s._handle_failed_no_retry.assert_awaited()


# -----------------------------------------------------------------------------
# _process_queue_message
# -----------------------------------------------------------------------------


class TestProcessQueueMessage:
    def test_invalid_payload_triggers_failure_no_retry(self):
        s = _service()
        s._handle_failed_no_retry = AsyncMock()
        msg = SimpleNamespace(id="m1", pop_receipt="r1", content="not-json")
        _run(s._process_queue_message(1, msg))
        s._handle_failed_no_retry.assert_awaited()
        # process_id is "<unknown>" since parsing failed
        kwargs = s._handle_failed_no_retry.await_args.kwargs
        assert kwargs.get("process_id") == "<unknown>" or s._handle_failed_no_retry.await_args.args[1] == "<unknown>"

    def test_success_path_calls_successful_handler(self):
        s = _service()
        ctx = MagicMock()
        proc = MagicMock()
        proc.run = AsyncMock(return_value=SimpleNamespace(is_hard_terminated=False))
        ctx.get_service.return_value = proc
        s.app_context = ctx
        s._handle_successful_processing = AsyncMock()
        s._handle_failed_no_retry = AsyncMock()

        import json
        payload = {
            "process_id": "p1",
            "user_id": "u",
            "migration_request": {
                "process_id": "p1",
                "user_id": "u",
                "container_name": "c",
                "source_file_folder": "p1/source",
                "workspace_file_folder": "p1/workspace",
                "output_file_folder": "p1/converted",
            },
        }
        msg = SimpleNamespace(id="m1", pop_receipt="r1", content=json.dumps(payload))
        _run(s._process_queue_message(2, msg))
        s._handle_successful_processing.assert_awaited_once()
        s._handle_failed_no_retry.assert_not_awaited()

    def test_hard_terminated_result_routes_to_no_retry_with_process_scope(self):
        s = _service()
        ctx = MagicMock()
        result = SimpleNamespace(
            is_hard_terminated=True,
            blocking_issues=["a", "b"],
            reason="denied",
        )
        proc = MagicMock()
        proc.run = AsyncMock(return_value=result)
        ctx.get_service.return_value = proc
        s.app_context = ctx
        s._handle_failed_no_retry = AsyncMock()
        s._handle_successful_processing = AsyncMock()

        import json
        payload = {
            "process_id": "p1",
            "user_id": "u",
            "migration_request": {
                "process_id": "p1",
                "user_id": "u",
                "container_name": "c",
                "source_file_folder": "p1/source",
                "workspace_file_folder": "p1/workspace",
                "output_file_folder": "p1/converted",
            },
        }
        msg = SimpleNamespace(id="m1", pop_receipt="r1", content=json.dumps(payload))
        _run(s._process_queue_message(3, msg))
        s._handle_failed_no_retry.assert_awaited_once()
        kwargs = s._handle_failed_no_retry.await_args.kwargs
        assert kwargs.get("cleanup_scope") == "process"

    def test_workflow_returns_none_treated_as_failure(self):
        s = _service()
        ctx = MagicMock()
        proc = MagicMock()
        proc.run = AsyncMock(return_value=None)
        ctx.get_service.return_value = proc
        s.app_context = ctx
        s._handle_failed_no_retry = AsyncMock()
        s._handle_successful_processing = AsyncMock()

        import json
        payload = {
            "process_id": "p1",
            "user_id": "u",
            "migration_request": {
                "process_id": "p1",
                "user_id": "u",
                "container_name": "c",
                "source_file_folder": "p1/source",
                "workspace_file_folder": "p1/workspace",
                "output_file_folder": "p1/converted",
            },
        }
        msg = SimpleNamespace(id="m1", pop_receipt="r1", content=json.dumps(payload))
        _run(s._process_queue_message(4, msg))
        s._handle_failed_no_retry.assert_awaited_once()

    def test_workflow_executor_failed_routes_to_no_retry(self):
        s = _service()
        ctx = MagicMock()
        from steps.migration_processor import WorkflowExecutorFailedException

        proc = MagicMock()
        proc.run = AsyncMock(side_effect=WorkflowExecutorFailedException("nope"))
        ctx.get_service.return_value = proc
        s.app_context = ctx
        s._handle_failed_no_retry = AsyncMock()

        import json
        payload = {
            "process_id": "p1",
            "user_id": "u",
            "migration_request": {
                "process_id": "p1",
                "user_id": "u",
                "container_name": "c",
                "source_file_folder": "p1/source",
                "workspace_file_folder": "p1/workspace",
                "output_file_folder": "p1/converted",
            },
        }
        msg = SimpleNamespace(id="m1", pop_receipt="r1", content=json.dumps(payload))
        _run(s._process_queue_message(5, msg))
        s._handle_failed_no_retry.assert_awaited_once()

    def test_unhandled_exception_routes_to_no_retry(self):
        s = _service()
        ctx = MagicMock()
        proc = MagicMock()
        proc.run = AsyncMock(side_effect=RuntimeError("kaboom"))
        ctx.get_service.return_value = proc
        s.app_context = ctx
        s._handle_failed_no_retry = AsyncMock()

        import json
        payload = {
            "process_id": "p1",
            "user_id": "u",
            "migration_request": {
                "process_id": "p1",
                "user_id": "u",
                "container_name": "c",
                "source_file_folder": "p1/source",
                "workspace_file_folder": "p1/workspace",
                "output_file_folder": "p1/converted",
            },
        }
        msg = SimpleNamespace(id="m1", pop_receipt="r1", content=json.dumps(payload))
        _run(s._process_queue_message(6, msg))
        s._handle_failed_no_retry.assert_awaited_once()


# -----------------------------------------------------------------------------
# _handle_successful_processing
# -----------------------------------------------------------------------------


class TestHandleSuccessfulProcessing:
    def test_deletes_message_on_success(self):
        s = _service()
        s.debug_mode = True
        msg = SimpleNamespace(id="m1", pop_receipt="r1")
        _run(s._handle_successful_processing(msg, "p1", 1.5))
        s.main_queue.delete_message.assert_called_once_with("m1", "r1")

    def test_swallows_resource_not_found(self):
        from azure.core.exceptions import ResourceNotFoundError
        s = _service()
        s.main_queue.delete_message.side_effect = ResourceNotFoundError("gone")
        msg = SimpleNamespace(id="m1", pop_receipt="r1")
        _run(s._handle_successful_processing(msg, "p1", 1.5))

    def test_swallows_azure_error(self):
        from azure.core.exceptions import AzureError
        s = _service()
        s.main_queue.delete_message.side_effect = AzureError("boom")
        msg = SimpleNamespace(id="m1", pop_receipt="r1")
        _run(s._handle_successful_processing(msg, "p1", 1.5))


# -----------------------------------------------------------------------------
# _handle_failed_no_retry
# -----------------------------------------------------------------------------


class TestHandleFailedNoRetry:
    def test_writes_failure_telemetry_when_app_context_present(self):
        s = _service()
        ctx = MagicMock()
        telemetry = MagicMock()
        telemetry.get_current_process = AsyncMock(
            return_value=SimpleNamespace(step="design")
        )
        telemetry.record_failure_outcome = AsyncMock()
        ctx.get_service_async = AsyncMock(return_value=telemetry)
        s.app_context = ctx
        msg = SimpleNamespace(id="m1", pop_receipt="r1")
        _run(
            s._handle_failed_no_retry(
                msg, "p1", "boom", 0.5, task_param=None, cleanup_scope="output"
            )
        )
        telemetry.record_failure_outcome.assert_awaited_once()

    def test_swallows_telemetry_failure(self):
        s = _service()
        ctx = MagicMock()
        telemetry = MagicMock()
        telemetry.get_current_process = AsyncMock(side_effect=RuntimeError("x"))
        telemetry.record_failure_outcome = AsyncMock(side_effect=RuntimeError("y"))
        ctx.get_service_async = AsyncMock(return_value=telemetry)
        s.app_context = ctx
        msg = SimpleNamespace(id="m1", pop_receipt="r1")
        # Should not raise even if telemetry blows up
        _run(s._handle_failed_no_retry(msg, "p1", "boom", 0.5))

    def test_skips_telemetry_for_unknown_process(self):
        s = _service()
        ctx = MagicMock()
        ctx.get_service_async = AsyncMock()
        s.app_context = ctx
        msg = SimpleNamespace(id="m1", pop_receipt="r1")
        _run(s._handle_failed_no_retry(msg, "<unknown>", "boom", 0.5))
        ctx.get_service_async.assert_not_called()

    def test_cleanup_scope_process(self):
        s = _service()
        s.app_context = None
        s._cleanup_process_blobs = AsyncMock()
        s._cleanup_output_blobs = AsyncMock()
        msg = SimpleNamespace(id="m1", pop_receipt="r1")
        tp = _task_param()
        _run(
            s._handle_failed_no_retry(
                msg, "p1", "boom", 0.5, task_param=tp, cleanup_scope="process"
            )
        )
        s._cleanup_process_blobs.assert_awaited_once_with(tp)
        s._cleanup_output_blobs.assert_not_called()

    def test_cleanup_swallows_blob_errors(self):
        s = _service()
        s.app_context = None
        s._cleanup_output_blobs = AsyncMock(side_effect=RuntimeError("io"))
        msg = SimpleNamespace(id="m1", pop_receipt="r1")
        # Should not raise
        _run(s._handle_failed_no_retry(msg, "p1", "boom", 0.5, task_param=_task_param()))

    def test_swallows_delete_error(self):
        from azure.core.exceptions import AzureError
        s = _service()
        s.app_context = None
        s.main_queue.delete_message.side_effect = AzureError("nope")
        msg = SimpleNamespace(id="m1", pop_receipt="r1")
        _run(s._handle_failed_no_retry(msg, "p1", "boom", 0.5))


# -----------------------------------------------------------------------------
# _cleanup_process_blobs_sync / _cleanup_output_blobs_sync
# -----------------------------------------------------------------------------


class TestCleanupBlobsSync:
    def test_no_account_skips(self):
        s = _service(account="")
        s._cleanup_process_blobs_sync(_task_param())  # no exception

    def test_no_blobs_returns_early(self):
        s = _service()
        with patch("services.queue_service.StorageBlobHelper") as MockHelper, \
             patch("services.queue_service.get_azure_credential", return_value=MagicMock()):
            helper = MockHelper.return_value
            helper.list_blobs.return_value = []
            s._cleanup_process_blobs_sync(_task_param())

    def test_deletes_blobs_and_dir(self):
        s = _service()
        with patch("services.queue_service.StorageBlobHelper") as MockHelper, \
             patch("services.queue_service.get_azure_credential", return_value=MagicMock()), \
             patch("importlib.import_module") as mock_import:
            helper = MockHelper.return_value
            helper.list_blobs.return_value = [
                {"name": "p1/file.txt"},
                {"name": "p1/", "is_directory": True},  # directory entry skipped
                {"name": "p1/converted"},  # placeholder skipped
                {"name": ""},
            ]
            helper.delete_multiple_blobs.return_value = {"p1/file.txt": True}

            dl_mod = MagicMock()
            DataLakeServiceClient = MagicMock()
            dl_mod.DataLakeServiceClient = DataLakeServiceClient
            mock_import.return_value = dl_mod

            s._cleanup_process_blobs_sync(_task_param())
            helper.delete_multiple_blobs.assert_called_once()
            DataLakeServiceClient.assert_called_once()

    def test_dir_delete_typeerror_recursive(self):
        s = _service()
        with patch("services.queue_service.StorageBlobHelper") as MockHelper, \
             patch("services.queue_service.get_azure_credential", return_value=MagicMock()), \
             patch("importlib.import_module") as mock_import:
            helper = MockHelper.return_value
            helper.list_blobs.return_value = [{"name": "p1/file.txt"}]
            helper.delete_multiple_blobs.return_value = {"p1/file.txt": True}

            dir_client = MagicMock()
            dir_client.delete_directory.side_effect = [
                TypeError("got multiple values for keyword argument 'recursive'"),
                None,
            ]
            fs = MagicMock()
            fs.get_directory_client.return_value = dir_client
            dl_client = MagicMock()
            dl_client.get_file_system_client.return_value = fs
            DataLakeServiceClient = MagicMock(return_value=dl_client)
            dl_mod = MagicMock(DataLakeServiceClient=DataLakeServiceClient)
            mock_import.return_value = dl_mod

            s._cleanup_process_blobs_sync(_task_param())
            assert dir_client.delete_directory.call_count == 2

    def test_top_level_exception_swallowed(self):
        s = _service()
        with patch("services.queue_service.StorageBlobHelper", side_effect=RuntimeError("bad")), \
             patch("services.queue_service.get_azure_credential", return_value=MagicMock()):
            s._cleanup_process_blobs_sync(_task_param())  # no raise

    def test_output_cleanup_no_account(self):
        s = _service(account="")
        s._cleanup_output_blobs_sync(_task_param())

    def test_output_cleanup_refuses_broad_prefix(self):
        s = _service()
        tp = _task_param()
        # Force output_file_folder to broad path matching "<pid>"
        tp = Analysis_TaskParam(
            process_id="p1",
            container_name="c",
            source_file_folder="p1/source",
            workspace_file_folder="p1/workspace",
            output_file_folder="p1",  # broad
        )
        with patch("services.queue_service.StorageBlobHelper") as MockHelper, \
             patch("services.queue_service.get_azure_credential", return_value=MagicMock()):
            s._cleanup_output_blobs_sync(tp)
            MockHelper.assert_not_called()

    def test_output_cleanup_no_blobs(self):
        s = _service()
        with patch("services.queue_service.StorageBlobHelper") as MockHelper, \
             patch("services.queue_service.get_azure_credential", return_value=MagicMock()):
            helper = MockHelper.return_value
            helper.list_blobs.return_value = [
                {"name": ""},
                {"name": "p1/converted", "is_directory": True},
                {"name": "p1/converted"},  # equals dir name → skipped
            ]
            s._cleanup_output_blobs_sync(_task_param())
            helper.delete_multiple_blobs.assert_not_called()

    def test_output_cleanup_deletes(self):
        s = _service()
        with patch("services.queue_service.StorageBlobHelper") as MockHelper, \
             patch("services.queue_service.get_azure_credential", return_value=MagicMock()), \
             patch("importlib.import_module") as mock_import:
            helper = MockHelper.return_value
            helper.list_blobs.return_value = [{"name": "p1/converted/a.yaml"}]
            helper.delete_multiple_blobs.return_value = {"p1/converted/a.yaml": True}

            DataLakeServiceClient = MagicMock()
            dl_mod = MagicMock(DataLakeServiceClient=DataLakeServiceClient)
            mock_import.return_value = dl_mod

            s._cleanup_output_blobs_sync(_task_param())
            helper.delete_multiple_blobs.assert_called_once()

    def test_async_wrappers_invoke_sync(self):
        s = _service()
        s._cleanup_process_blobs_sync = MagicMock()
        s._cleanup_output_blobs_sync = MagicMock()
        _run(s._cleanup_process_blobs(_task_param()))
        _run(s._cleanup_output_blobs(_task_param()))
        s._cleanup_process_blobs_sync.assert_called_once()
        s._cleanup_output_blobs_sync.assert_called_once()


# -----------------------------------------------------------------------------
# start_service (high-level smoke)
# -----------------------------------------------------------------------------


class TestStartService:
    def test_start_service_already_running_returns(self):
        s = _service()
        s.is_running = True
        _run(s.start_service())  # returns early; no exception

    def test_start_service_runs_and_completes(self):
        s = _service()
        s.is_running = False
        s._ensure_queues_exist = AsyncMock()
        s._control_watcher_loop = AsyncMock()

        async def _no_op_worker(self_, worker_id):
            return None

        # Patch worker loop to immediate return
        s._worker_loop = lambda wid: asyncio.sleep(0)  # type: ignore[assignment]
        _run(s.start_service())
        assert s.is_running is False  # finally clause


# -----------------------------------------------------------------------------
# process_message wrapper
# -----------------------------------------------------------------------------


class TestProcessMessageEntrypoint:
    def test_calls_worker_loop_with_id_1(self):
        s = _service()
        s._worker_loop = AsyncMock()
        _run(s.process_message())
        s._worker_loop.assert_awaited_once_with(worker_id=1)
