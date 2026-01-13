from __future__ import annotations

import asyncio

import pytest

from services.queue_service import QueueMigrationService
from steps.analysis.models.step_param import Analysis_TaskParam


class _FakeQueue:
    def __init__(self):
        self.deleted: list[tuple[str, str]] = []

    def delete_message(self, message_id: str, pop_receipt: str):
        self.deleted.append((message_id, pop_receipt))


class _FakeQueueMessage:
    def __init__(self, message_id: str = "m1", pop_receipt: str = "r1"):
        self.id = message_id
        self.pop_receipt = pop_receipt


@pytest.mark.parametrize("pass_task_param", [True, False])
def test_failed_no_retry_clears_output_folder_when_task_param_available(
    pass_task_param: bool,
):
    async def _run():
        service = QueueMigrationService.__new__(QueueMigrationService)
        service.app_context = None
        service.main_queue = _FakeQueue()

        called: list[str] = []

        async def _cleanup_output_blobs(task_param: Analysis_TaskParam):
            called.append(task_param.output_file_folder)

        service._cleanup_output_blobs = _cleanup_output_blobs  # type: ignore[attr-defined]

        task_param = (
            Analysis_TaskParam(
                process_id="p1",
                container_name="c1",
                source_file_folder="p1/source",
                workspace_file_folder="p1/workspace",
                output_file_folder="p1/output",
            )
            if pass_task_param
            else None
        )

        await service._handle_failed_no_retry(
            queue_message=_FakeQueueMessage(),
            process_id="p1",
            failure_reason="boom",
            execution_time=1.23,
            task_param=task_param,
        )

        assert service.main_queue.deleted == [("m1", "r1")]
        if pass_task_param:
            assert called == ["p1/output"]
        else:
            assert called == []

    asyncio.run(_run())
