# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import base64
import json

import pytest

from services.queue_service import (
    MigrationQueueMessage,
    create_default_migration_request,
    is_base64_encoded,
)


class _FakeQueueMessage:
    def __init__(self, content: str | bytes):
        self.content = content


def test_is_base64_encoded_detects_encoded_payload():
    raw = b"hello world"
    encoded = base64.b64encode(raw).decode("utf-8")
    assert is_base64_encoded(encoded) is True
    assert is_base64_encoded("not base64") is False


def test_create_default_migration_request_formats_expected_folders():
    req = create_default_migration_request(process_id="p1", user_id="u1")
    assert req["process_id"] == "p1"
    assert req["user_id"] == "u1"
    assert req["container_name"] == "processes"
    assert req["source_file_folder"] == "p1/source"
    assert req["workspace_file_folder"] == "p1/workspace"
    assert req["output_file_folder"] == "p1/output"


def test_migration_queue_message_requires_mandatory_fields_in_request():
    with pytest.raises(ValueError, match=r"missing mandatory fields"):
        MigrationQueueMessage(process_id="p1", migration_request={"process_id": "p1"})


def test_from_queue_message_parses_plain_json():
    payload = {
        "process_id": "p1",
        "user_id": "u1",
        "migration_request": {
            "process_id": "p1",
            "user_id": "u1",
            "container_name": "c1",
            "source_file_folder": "p1/source",
            "workspace_file_folder": "p1/workspace",
            "output_file_folder": "p1/output",
        },
    }
    msg = _FakeQueueMessage(json.dumps(payload))
    parsed = MigrationQueueMessage.from_queue_message(msg)  # type: ignore[arg-type]
    assert parsed.process_id == "p1"
    assert parsed.user_id == "u1"
    assert parsed.migration_request["container_name"] == "c1"


def test_from_queue_message_decodes_base64_json():
    payload = {
        "process_id": "p1",
        "user_id": "u1",
        "migration_request": {
            "process_id": "p1",
            "user_id": "u1",
            "container_name": "c1",
            "source_file_folder": "p1/source",
            "workspace_file_folder": "p1/workspace",
            "output_file_folder": "p1/output",
        },
    }
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    msg = _FakeQueueMessage(encoded)
    parsed = MigrationQueueMessage.from_queue_message(msg)  # type: ignore[arg-type]
    assert parsed.process_id == "p1"
    assert parsed.user_id == "u1"


def test_from_queue_message_autocompletes_when_only_process_id_is_provided():
    payload = {"process_id": "p1", "user_id": "u1", "unexpected": "ignored"}
    msg = _FakeQueueMessage(json.dumps(payload))
    parsed = MigrationQueueMessage.from_queue_message(msg)  # type: ignore[arg-type]

    assert parsed.process_id == "p1"
    assert parsed.user_id == "u1"
    # Auto-filled request fields
    req = parsed.migration_request
    assert req["container_name"] == "processes"
    assert req["source_file_folder"] == "p1/source"
    assert req["workspace_file_folder"] == "p1/workspace"
    assert req["output_file_folder"] == "p1/output"
    # Fields required by __post_init__ must be present
    assert req["process_id"] == "p1"
    assert req["user_id"] == "u1"


def test_from_queue_message_rejects_non_json_payload():
    msg = _FakeQueueMessage("this is not json")
    with pytest.raises(ValueError, match=r"Invalid queue message format"):
        MigrationQueueMessage.from_queue_message(msg)  # type: ignore[arg-type]
