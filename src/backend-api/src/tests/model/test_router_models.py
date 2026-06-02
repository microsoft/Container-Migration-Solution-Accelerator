import base64
import json

import pytest
from pydantic import ValidationError

from routers.models.files import Batch, File, FileInfo, FileUploadResult
from routers.models.processes import (
    FileContentResponse,
    FileInfo as ProcessFileInfo,
    ProcessCreateResponse,
    ProcessInfo,
    ProcessSummaryFileInfo,
    ProcessSummaryResponse,
    enlist_process_queue_response,
)


class TestFileEntity:
    def test_attributes_assigned(self):
        f = File(file_id="fid", original_name="orig.txt")
        assert f.file_id == "fid"
        assert f.original_name == "orig.txt"


class TestBatch:
    def test_batch_id_assigned(self):
        b = Batch(batch_id="bid")
        assert b.batch_id == "bid"


class TestFileUploadResult:
    def test_composes_batch_and_file(self):
        result = FileUploadResult(batch_id="b1", file_id="f1", file_name="x.yaml")
        assert isinstance(result.batch, Batch)
        assert isinstance(result.file, File)
        assert result.batch.batch_id == "b1"
        assert result.file.file_id == "f1"
        assert result.file.original_name == "x.yaml"


class TestFileInfo:
    def test_excludes_content_from_serialization(self):
        info = FileInfo(
            filename="a.txt",
            content=b"secret",
            content_type="text/plain",
            size=6,
        )
        dumped = info.model_dump()
        assert "content" not in dumped
        assert dumped["filename"] == "a.txt"

    def test_validation_requires_filename(self):
        with pytest.raises(ValidationError):
            FileInfo(content_type="text/plain", size=0)


class TestProcessSchemas:
    def test_process_create_response(self):
        assert ProcessCreateResponse(process_id="x").process_id == "x"

    def test_process_info_requires_fields(self):
        with pytest.raises(ValidationError):
            ProcessInfo(process_id="x")  # missing created_at/file_count

    def test_process_summary_response_round_trip(self):
        from datetime import datetime, timezone

        info = ProcessInfo(
            process_id="p",
            created_at=datetime.now(timezone.utc),
            file_count=2,
        )
        summary = ProcessSummaryResponse(
            Process=info,
            files=[ProcessSummaryFileInfo(filename="a")],
        )
        assert summary.Process.process_id == "p"
        assert summary.files[0].filename == "a"

    def test_file_content_response(self):
        assert FileContentResponse(content="hello").content == "hello"

    def test_process_file_info_validation(self):
        info = ProcessFileInfo(filename="f", content_type="text/plain", size=1)
        assert info.filename == "f"


class TestEnlistProcessQueueResponse:
    def test_to_base64_round_trip(self):
        resp = enlist_process_queue_response(
            user_id="u",
            process_id="p",
            message="m",
            files=[ProcessFileInfo(filename="a", content_type="text/plain", size=1)],
        )
        decoded = json.loads(base64.b64decode(resp.to_base64()).decode())
        assert decoded["user_id"] == "u"
        assert decoded["process_id"] == "p"
        assert decoded["files"][0]["filename"] == "a"

    def test_optional_fields_default_to_none(self):
        resp = enlist_process_queue_response(user_id="u", process_id="p")
        assert resp.message is None
        assert resp.files is None
