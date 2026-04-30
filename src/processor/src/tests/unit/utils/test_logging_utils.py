# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Tests for utils.logging_utils."""

from __future__ import annotations

import logging
import os
from unittest.mock import MagicMock, patch

import pytest
from azure.core.exceptions import HttpResponseError

from utils import logging_utils as lu


def test_configure_application_logging_production_mode(monkeypatch):
    monkeypatch.delenv("HTTPX_LOG_LEVEL", raising=False)
    monkeypatch.delenv("AZURE_CORE_ENABLE_HTTP_LOGGER", raising=False)
    with patch.object(lu.logging, "basicConfig") as bc:
        lu.configure_application_logging(debug_mode=False)
    bc.assert_called_with(level=logging.INFO, force=True)
    assert os.environ.get("HTTPX_LOG_LEVEL") == "WARNING"
    assert os.environ.get("AZURE_CORE_ENABLE_HTTP_LOGGER") == "false"
    assert logging.getLogger("azure.cosmos").level == logging.WARNING


def test_configure_application_logging_debug_mode():
    with patch.object(lu.logging, "basicConfig") as bc:
        lu.configure_application_logging(debug_mode=True)
    bc.assert_called_with(level=logging.DEBUG, force=True)
    # HTTP-ish loggers go to WARNING in debug mode
    assert logging.getLogger("httpx").level == logging.WARNING
    # Non-HTTP verbose loggers go to INFO in debug mode
    assert logging.getLogger("agent_framework").level == logging.INFO


def test_create_migration_logger_initializes_handlers_only_once():
    name = "test.migration.logger.unique.42"
    # Ensure a clean slate.
    logger = logging.getLogger(name)
    logger.handlers.clear()
    out1 = lu.create_migration_logger(name, level=logging.WARNING)
    assert out1 is logger
    assert len(out1.handlers) == 1
    assert out1.level == logging.WARNING
    # Calling again should not duplicate handlers.
    out2 = lu.create_migration_logger(name)
    assert len(out2.handlers) == 1


def test_safe_log_with_simple_kwargs():
    logger = MagicMock()
    lu.safe_log(logger, "INFO", "hello {name}", name="world")
    logger.info.assert_called_once_with("hello world")


def test_safe_log_stringifies_dict_list_and_exception():
    logger = MagicMock()
    err = ValueError("nope")
    lu.safe_log(
        logger,
        "warning",
        "d={d} l={l} e={e}",
        d={"a": 1},
        l=[1, 2],
        e=err,
    )
    msg = logger.warning.call_args.args[0]
    assert "{'a': 1}" in msg
    assert "[1, 2]" in msg
    assert "nope" in msg


def test_safe_log_raises_runtime_error_on_format_failure():
    logger = MagicMock()
    with pytest.raises(RuntimeError):
        # Missing kwarg triggers KeyError inside .format(); function logs
        # and re-raises as RuntimeError.
        lu.safe_log(logger, "info", "hello {missing}", other="x")
    logger.error.assert_called_once()


def test_get_error_details_basic_exception():
    try:
        raise ValueError("oops")
    except ValueError as e:
        details = lu.get_error_details(e)
    assert details["exception_type"] == "ValueError"
    assert details["exception_message"] == "oops"
    assert "Traceback" in details["full_traceback"] or details["full_traceback"]
    assert details["exception_args"] == ("oops",)


def test_get_error_details_includes_cause_and_context():
    try:
        try:
            raise KeyError("inner")
        except KeyError as inner:
            raise RuntimeError("outer") from inner
    except RuntimeError as e:
        details = lu.get_error_details(e)
    assert details["exception_cause"] is not None
    assert details["exception_context"] is not None


def test_get_error_details_for_http_response_error():
    err = HttpResponseError(message="bad")
    err.status_code = 500
    err.reason = "Server Error"
    details = lu.get_error_details(err)
    assert details["http_status_code"] == 500
    assert details["http_reason"] == "Server Error"
    assert "http_response" in details


def test_get_error_details_for_azure_chat_completion_like_error():
    class AzureChatCompletionError(Exception):
        pass

    e = AzureChatCompletionError("boom")
    e.model = "gpt-4"
    e.endpoint = "https://e"
    details = lu.get_error_details(e)
    assert details["azure_chat_completion_error"] is True
    assert details["model_deployment"] == "gpt-4"
    assert details["endpoint"] == "https://e"


def test_log_error_with_context_includes_kwargs_in_details():
    logger = MagicMock()
    err = ValueError("x")
    out = lu.log_error_with_context(logger, err, context="step", step_id="abc")
    logger.error.assert_called_once()
    assert out["additional_context"] == {"step_id": "abc"}


def test_format_specific_error_details_handles_http_and_service_codes():
    out = lu._format_specific_error_details(
        {
            "http_status_code": 503,
            "http_reason": "x",
            "service_error_code": "RateLimited",
        }
    )
    assert "HTTP Status Code: 503" in out
    assert "RateLimited" in out


def test_format_specific_error_details_azure_chat_branch():
    out = lu._format_specific_error_details(
        {
            "azure_chat_completion_error": True,
            "model_deployment": "m",
            "endpoint": "e",
        }
    )
    assert "Azure ChatCompletion Error Detected" in out
    assert "Model Deployment: m" in out
    assert "Endpoint: e" in out


def test_format_specific_error_details_returns_empty_when_nothing_relevant():
    assert lu._format_specific_error_details({}) == ""


def test_log_messages_constants_present():
    assert "{step}" in lu.LogMessages.ERROR_STEP_FAILED
    assert lu.LogMessages.SUCCESS_STEP.startswith("[SUCCESS]")
