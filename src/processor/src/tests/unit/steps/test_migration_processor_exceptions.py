# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from steps.migration_processor import (
    WorkflowExecutorFailedException,
    WorkflowOutputMissingException,
)


class _DetailsWithDict:
    def __init__(self, payload: dict):
        self._payload = payload

    def dict(self):  # pydantic v1 shape
        return dict(self._payload)


class _DetailsWithModelDump:
    def __init__(self, payload: dict):
        self._payload = payload

    def model_dump(self):  # pydantic v2 shape
        return dict(self._payload)


class _DetailsWithAttrs:
    def __init__(self):
        self.executor_id = "analysis"
        self.error_type = "ValueError"
        self.message = "boom"


def test_workflow_output_missing_exception_message():
    assert "source_executor_id=<unknown>" in str(WorkflowOutputMissingException(None))
    assert "source_executor_id=analysis" in str(
        WorkflowOutputMissingException("analysis")
    )


def test_workflow_executor_failed_exception_formats_message_without_traceback():
    details = {
        "executor_id": "analysis",
        "error_type": "ValueError",
        "message": "bad input",
    }
    exc = WorkflowExecutorFailedException(details)
    text = str(exc)
    assert "Executor analysis failed (ValueError): bad input" in text
    assert "WorkflowErrorDetails" in text


def test_workflow_executor_failed_exception_includes_traceback_when_present():
    details = {
        "executor_id": "yaml",
        "error_type": "RuntimeError",
        "message": "oops",
        "traceback": "trace here",
    }
    exc = WorkflowExecutorFailedException(details)
    text = str(exc)
    assert "Executor yaml failed (RuntimeError): oops" in text
    assert "Traceback:" in text
    assert "trace here" in text


def test_details_to_dict_handles_model_dump_dict_and_attrs():
    payload = {"executor_id": "design", "error_type": "X", "message": "m"}

    got = WorkflowExecutorFailedException._details_to_dict(
        _DetailsWithModelDump(payload)
    )
    assert got["executor_id"] == "design"

    got = WorkflowExecutorFailedException._details_to_dict(_DetailsWithDict(payload))
    assert got["executor_id"] == "design"

    got = WorkflowExecutorFailedException._details_to_dict(_DetailsWithAttrs())
    assert got["executor_id"] == "analysis"
