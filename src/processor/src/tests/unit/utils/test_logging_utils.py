# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
from unittest.mock import MagicMock

import pytest

from utils.logging_utils import (
    LogMessages,
    _format_specific_error_details,
    configure_application_logging,
    create_migration_logger,
    get_error_details,
    log_error_with_context,
    safe_log,
)


class TestConfigureApplicationLogging:
    def test_production_mode_sets_warning_levels(self):
        configure_application_logging(debug_mode=False)
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("azure.cosmos").level == logging.WARNING

    def test_debug_mode_keeps_http_warning_but_info_for_others(self):
        configure_application_logging(debug_mode=True)
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("asyncio").level == logging.INFO


class TestCreateMigrationLogger:
    def test_creates_logger_with_handler(self):
        logger = create_migration_logger("test.migration.unique1")
        assert logger.handlers
        assert logger.level == logging.INFO

    def test_does_not_duplicate_handlers_on_repeat_calls(self):
        name = "test.migration.unique2"
        logger1 = create_migration_logger(name)
        handler_count = len(logger1.handlers)
        logger2 = create_migration_logger(name)
        assert len(logger2.handlers) == handler_count

    def test_respects_level_argument(self):
        logger = create_migration_logger("test.migration.debug", level=logging.DEBUG)
        assert logger.level == logging.DEBUG


class TestSafeLog:
    def test_substitutes_variables_in_template(self):
        logger = MagicMock(spec=logging.Logger)
        safe_log(logger, "info", "value={value}", value=42)
        logger.info.assert_called_once_with("value=42")

    def test_complex_objects_converted_to_strings(self):
        logger = MagicMock(spec=logging.Logger)
        safe_log(logger, "warning", "data={d}", d={"a": 1})
        called = logger.warning.call_args[0][0]
        assert "{'a': 1}" in called

    def test_exception_value_safely_stringified(self):
        logger = MagicMock(spec=logging.Logger)
        safe_log(logger, "error", "err={e}", e=ValueError("boom"))
        called = logger.error.call_args[0][0]
        assert "boom" in called

    def test_format_failure_raises_runtime_error(self):
        logger = MagicMock(spec=logging.Logger)
        with pytest.raises(RuntimeError):
            safe_log(logger, "info", "missing {missing_key}", other=1)
        assert logger.error.called


class TestGetErrorDetails:
    def test_basic_exception_details(self):
        try:
            raise ValueError("boom")
        except ValueError as e:
            details = get_error_details(e)
        assert details["exception_type"] == "ValueError"
        assert details["exception_message"] == "boom"

    def test_chained_exception_details(self):
        try:
            try:
                raise ValueError("orig")
            except ValueError as inner:
                raise RuntimeError("wrap") from inner
        except RuntimeError as e:
            details = get_error_details(e)
        assert details["exception_cause"] is not None
        assert "orig" in details["exception_cause"]

    def test_http_response_error_includes_http_fields(self):
        from azure.core.exceptions import HttpResponseError

        err = HttpResponseError(message="bad")
        err.status_code = 503
        err.reason = "Service Unavailable"
        details = get_error_details(err)
        assert details["http_status_code"] == 503
        assert details["http_reason"] == "Service Unavailable"


class TestFormatSpecificErrorDetails:
    def test_http_details_formatted(self):
        out = _format_specific_error_details(
            {"http_status_code": 500, "http_reason": "Server Error"}
        )
        assert "HTTP Status Code: 500" in out
        assert "HTTP Reason: Server Error" in out

    def test_service_error_code_formatted(self):
        out = _format_specific_error_details({"service_error_code": "SVC42"})
        assert "Service Error Code: SVC42" in out

    def test_azure_chat_completion_error_with_model_and_endpoint(self):
        out = _format_specific_error_details(
            {
                "azure_chat_completion_error": True,
                "model_deployment": "gpt-4o",
                "endpoint": "https://example.openai.azure.com",
            }
        )
        assert "Azure ChatCompletion Error Detected" in out
        assert "gpt-4o" in out
        assert "openai.azure.com" in out

    def test_empty_dict_returns_empty_string(self):
        assert _format_specific_error_details({}) == ""


class TestLogErrorWithContext:
    def test_logs_error_and_returns_details(self):
        logger = MagicMock(spec=logging.Logger)
        try:
            raise ValueError("ctx-err")
        except ValueError as e:
            details = log_error_with_context(logger, e, context="MyOp", k="v")

        assert details["exception_type"] == "ValueError"
        assert details["additional_context"] == {"k": "v"}
        assert logger.error.called


class TestLogMessages:
    def test_format_templates_have_placeholders(self):
        formatted = LogMessages.ERROR_STEP_FAILED.format(step="analysis", error="x")
        assert "analysis" in formatted and "x" in formatted

        formatted = LogMessages.SUCCESS_COMPLETED.format(operation="op", details="d")
        assert "op" in formatted and "d" in formatted

        formatted = LogMessages.INFO_PROCESSING.format(item="thing")
        assert "thing" in formatted
