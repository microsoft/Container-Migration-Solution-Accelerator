# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from steps.migration_processor import (
    MigrationProcessor,
    WorkflowExecutorFailedException,
    WorkflowOutputMissingException,
)


def _run(coro):
    return asyncio.run(coro)


class TestWorkflowOutputMissingException:
    def test_message_includes_source(self):
        exc = WorkflowOutputMissingException("analysis")
        assert "analysis" in str(exc)
        assert exc.source_executor_id == "analysis"

    def test_message_handles_none_source(self):
        exc = WorkflowOutputMissingException(None)
        assert "<unknown>" in str(exc)


class TestWorkflowExecutorFailedException:
    def test_details_to_dict_with_none(self):
        assert WorkflowExecutorFailedException._details_to_dict(None) == {"details": None}

    def test_details_to_dict_with_dict(self):
        d = {"executor_id": "x"}
        assert WorkflowExecutorFailedException._details_to_dict(d) == d

    def test_details_to_dict_with_pydantic_v2_object(self):
        class V2Like:
            def model_dump(self):
                return {"executor_id": "v2"}

        result = WorkflowExecutorFailedException._details_to_dict(V2Like())
        assert result == {"executor_id": "v2"}

    def test_details_to_dict_with_pydantic_v1_object(self):
        class V1Like:
            def dict(self):
                return {"executor_id": "v1"}

        result = WorkflowExecutorFailedException._details_to_dict(V1Like())
        assert result == {"executor_id": "v1"}

    def test_details_to_dict_with_pydantic_v2_failure_falls_back(self):
        class Bad:
            def model_dump(self):
                raise RuntimeError("nope")

            def dict(self):
                return {"from": "dict"}

        result = WorkflowExecutorFailedException._details_to_dict(Bad())
        assert result == {"from": "dict"}

    def test_details_to_dict_falls_back_to_vars(self):
        class Plain:
            def __init__(self):
                self.executor_id = "plain"
                self.message = "ok"

        result = WorkflowExecutorFailedException._details_to_dict(Plain())
        assert result["executor_id"] == "plain"

    def test_details_to_dict_falls_back_to_repr_on_error(self):
        class NoVars:
            __slots__ = ()

        result = WorkflowExecutorFailedException._details_to_dict(NoVars())
        assert "details" in result

    def test_format_message_with_traceback(self):
        msg = WorkflowExecutorFailedException._format_message({
            "executor_id": "x",
            "error_type": "ValueError",
            "message": "bad",
            "traceback": "Traceback...",
        })
        assert "Traceback" in msg
        assert "x" in msg

    def test_format_message_without_traceback(self):
        msg = WorkflowExecutorFailedException._format_message({
            "executor_id": "x",
            "error_type": "ValueError",
            "message": "bad",
        })
        assert "WorkflowErrorDetails" in msg

    def test_format_message_with_unknown_fields(self):
        msg = WorkflowExecutorFailedException._format_message({})
        assert "<unknown>" in msg

    def test_constructor_stores_details(self):
        exc = WorkflowExecutorFailedException({"executor_id": "x", "message": "m"})
        assert exc.details == {"executor_id": "x", "message": "m"}


class TestCreateMemoryStore:
    def _make_processor(self):
        p = MigrationProcessor.__new__(MigrationProcessor)
        p.app_context = MagicMock()
        return p

    def test_disabled_when_env_off(self, monkeypatch):
        monkeypatch.setenv("SHARED_MEMORY_ENABLED", "0")
        p = self._make_processor()
        result = _run(p._create_memory_store("proc-1"))
        assert result is None

    def test_returns_none_when_no_service_config(self, monkeypatch):
        monkeypatch.setenv("SHARED_MEMORY_ENABLED", "true")
        p = self._make_processor()
        helper = MagicMock()
        helper.settings.get_service_config.return_value = None
        p.app_context.get_service.return_value = helper
        result = _run(p._create_memory_store("proc-1"))
        assert result is None

    def test_returns_none_when_no_embedding_deployment(self, monkeypatch):
        monkeypatch.setenv("SHARED_MEMORY_ENABLED", "true")
        p = self._make_processor()
        helper = MagicMock()
        cfg = MagicMock(embedding_deployment_name="")
        helper.settings.get_service_config.return_value = cfg
        p.app_context.get_service.return_value = helper
        result = _run(p._create_memory_store("proc-1"))
        assert result is None

    def test_returns_none_on_exception(self, monkeypatch):
        monkeypatch.setenv("SHARED_MEMORY_ENABLED", "true")
        p = self._make_processor()
        p.app_context.get_service.side_effect = RuntimeError("fail")
        result = _run(p._create_memory_store("proc-1"))
        assert result is None
