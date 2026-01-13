from __future__ import annotations

import asyncio

import pytest

from services.queue_service import QueueMigrationService


class _FakeQueue:
    def __init__(self):
        self.deleted: list[tuple[str, str]] = []

    def delete_message(self, message_id: str, pop_receipt: str):
        self.deleted.append((message_id, pop_receipt))


class _FakeTelemetry:
    def __init__(self):
        self.deleted_process_ids: list[str] = []

    async def delete_process(self, process_id: str):
        self.deleted_process_ids.append(process_id)


class _FakeAppContext:
    def __init__(self, telemetry: _FakeTelemetry):
        self._telemetry = telemetry

    async def get_service_async(self, _service_type):
        return self._telemetry


@pytest.mark.parametrize("has_task_param", [True, False])
def test_stop_process_deletes_queue_and_telemetry_and_cancels_job(has_task_param: bool):
    async def _run():
        service = QueueMigrationService.__new__(QueueMigrationService)
        service.app_context = _FakeAppContext(_FakeTelemetry())
        service.main_queue = _FakeQueue()

        # minimal inflight tracking
        service._worker_inflight = {1: "p1"}
        service._worker_inflight_message = {1: ("m1", "r1")}
        service._worker_inflight_task_param = {1: object()} if has_task_param else {}

        # stub out blob cleanup to avoid threads/Azure
        async def _cleanup_process_blobs(_task_param):
            return None

        service._cleanup_process_blobs = _cleanup_process_blobs  # type: ignore[attr-defined]

        # in-flight job task should be cancelled by stop_process
        job_task = asyncio.create_task(asyncio.sleep(3600))
        service._worker_inflight_task = {1: job_task}

        ok = await service.stop_process("p1", timeout_seconds=0.1)
        assert ok is True

        # queue message deleted
        assert service.main_queue.deleted == [("m1", "r1")]

        # telemetry deleted
        telemetry = service.app_context._telemetry
        assert telemetry.deleted_process_ids == ["p1"]

        # job cancelled
        await asyncio.sleep(0)  # allow cancellation to propagate
        assert job_task.cancelled() is True

    asyncio.run(_run())
