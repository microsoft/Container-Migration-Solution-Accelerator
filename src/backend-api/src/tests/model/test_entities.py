from datetime import datetime

from libs.models.entities import AgentStatus, File, Process, ProcessStatus
from libs.models.messages import ProcessStartQueueMessage


class TestProcess:
    def test_default_field_values(self):
        process = Process(id="p1", user_id="u1")
        assert process.id == "p1"
        assert process.user_id == "u1"
        assert process.source_file_count == 0
        assert process.result_file_count == 0
        assert process.status == "initialized"
        assert isinstance(process.created_at, datetime)
        assert isinstance(process.updated_at, datetime)

    def test_overrides(self):
        process = Process(
            id="p1",
            user_id="u1",
            source_file_count=2,
            result_file_count=3,
            status="ready_to_process",
        )
        assert process.source_file_count == 2
        assert process.result_file_count == 3
        assert process.status == "ready_to_process"


class TestFile:
    def test_default_counts_zero(self):
        file_ = File(id="f1", process_id="p1", name="n", blob_path="b")
        assert file_.error_count == 0
        assert file_.syntax_count == 0
        assert isinstance(file_.created_at, datetime)


class TestAgentStatus:
    def test_time_stamp_default_is_iso_string(self):
        status = AgentStatus(name="agent", role="role", status="ok")
        # datetime.fromisoformat will raise if not ISO
        assert isinstance(status.time_stamp, str)
        datetime.fromisoformat(status.time_stamp)


class TestProcessStatus:
    def test_status_list_assignment(self):
        agents = [AgentStatus(name="a", role="r", status="s")]
        ps = ProcessStatus(id="ps", process_id="p", phase="ph", status=agents)
        assert ps.process_id == "p"
        assert ps.phase == "ph"
        assert len(ps.status) == 1


class TestProcessStartQueueMessage:
    def test_to_base64_roundtrip(self):
        import base64
        import json

        msg = ProcessStartQueueMessage(process_id="p", user_id="u")
        encoded = msg.to_base64()
        decoded = json.loads(base64.b64decode(encoded).decode())
        assert decoded == {"process_id": "p", "user_id": "u"}
