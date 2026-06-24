# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Unit tests for ``libs.logging.event_utils.track_event_if_configured``.

These tests exercise the gating behaviour that the rest of the
application depends on:

* When ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is unset / empty, the
  call is a no-op and the underlying SDK is *never* imported.
* When the env var is set, the call forwards through to
  ``azure.monitor.events.extension.track_event``.
* The "missing connection string" warning fires exactly once per
  process, with the wording the rest of the system asserts against.
* SDK exceptions are swallowed so telemetry can never break a request.

The tests deliberately avoid touching the real Azure Monitor SDK by
patching the symbol that the implementation imports lazily inside the
function. This keeps the suite hermetic and CI-friendly.
"""
from __future__ import annotations

import logging
import sys
import types
from typing import Any
from unittest.mock import MagicMock

import pytest

from libs.logging import event_utils
from libs.logging.event_utils import (
    APP_INSIGHTS_CONN_STRING_ENV,
    reset_unconfigured_warning_for_tests,
    track_event_if_configured,
)


@pytest.fixture(autouse=True)
def _reset_module_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts from a clean slate.

    Removes any process-wide env that would skew gating, resets the
    one-shot warning latch, and removes any cached
    ``azure.monitor.events.extension`` module so the lazy import path
    inside ``track_event_if_configured`` is exercised fresh on each
    test.
    """
    monkeypatch.delenv(APP_INSIGHTS_CONN_STRING_ENV, raising=False)
    reset_unconfigured_warning_for_tests()
    sys.modules.pop("azure.monitor.events.extension", None)


def _install_fake_track_event(call_log: list[tuple[str, dict[str, Any]]]) -> MagicMock:
    """Inject a fake ``azure.monitor.events.extension`` into ``sys.modules``.

    The implementation in ``event_utils`` does
    ``from azure.monitor.events.extension import track_event`` lazily;
    seeding ``sys.modules`` with a fake ensures we never hit the real
    SDK during tests and keeps the assertion surface narrow.
    """
    mock_track_event = MagicMock(
        side_effect=lambda name, properties: call_log.append((name, properties))
    )
    fake_module = types.ModuleType("azure.monitor.events.extension")
    fake_module.track_event = mock_track_event  # type: ignore[attr-defined]
    sys.modules["azure.monitor.events.extension"] = fake_module
    return mock_track_event


def test_no_op_when_connection_string_unset(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """With no env var, the helper must not call into the SDK at all."""
    call_log: list[tuple[str, dict[str, Any]]] = []
    mock_track_event = _install_fake_track_event(call_log)

    with caplog.at_level(logging.WARNING, logger=event_utils.logger.name):
        track_event_if_configured("CreateProcessSuccess", {"process_id": "abc"})

    mock_track_event.assert_not_called()
    assert call_log == []
    # Warning fires exactly once and references the event name.
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "APPLICATIONINSIGHTS_CONNECTION_STRING is not set" in warnings[0].getMessage()
    assert "CreateProcessSuccess" in warnings[0].getMessage()


def test_warning_fires_only_once_per_process(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Subsequent unconfigured calls must be silent (one-shot warning latch)."""
    _install_fake_track_event([])

    with caplog.at_level(logging.WARNING, logger=event_utils.logger.name):
        track_event_if_configured("First", {"k": 1})
        track_event_if_configured("Second", {"k": 2})
        track_event_if_configured("Third", {"k": 3})

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1, "Only the first unconfigured call should warn."


def test_unconfigured_warning_message_is_stable() -> None:
    """The exact warning template is part of the helper's contract."""
    assert event_utils._UNCONFIGURED_WARNING == (
        "APPLICATIONINSIGHTS_CONNECTION_STRING is not set; "
        "track_event_if_configured(name=%s) is a no-op."
    )


def test_forwards_to_track_event_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-empty connection string must route the call to the SDK."""
    monkeypatch.setenv(
        APP_INSIGHTS_CONN_STRING_ENV,
        "InstrumentationKey=00000000-0000-0000-0000-000000000000",
    )
    call_log: list[tuple[str, dict[str, Any]]] = []
    mock_track_event = _install_fake_track_event(call_log)

    track_event_if_configured(
        "UploadFilesSuccess",
        {"process_id": "p-1", "uploaded_count": 3},
    )

    mock_track_event.assert_called_once_with(
        "UploadFilesSuccess",
        {"process_id": "p-1", "uploaded_count": 3},
    )
    assert call_log == [
        ("UploadFilesSuccess", {"process_id": "p-1", "uploaded_count": 3})
    ]


def test_none_properties_normalised_to_empty_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Passing ``properties=None`` must surface as an empty dict to the SDK."""
    monkeypatch.setenv(
        APP_INSIGHTS_CONN_STRING_ENV,
        "InstrumentationKey=00000000-0000-0000-0000-000000000000",
    )
    call_log: list[tuple[str, dict[str, Any]]] = []
    _install_fake_track_event(call_log)

    track_event_if_configured("StartProcessingSuccess")

    assert call_log == [("StartProcessingSuccess", {})]


def test_whitespace_only_connection_string_is_treated_as_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A whitespace-only env var must not be considered configured."""
    monkeypatch.setenv(APP_INSIGHTS_CONN_STRING_ENV, "   ")
    call_log: list[tuple[str, dict[str, Any]]] = []
    mock_track_event = _install_fake_track_event(call_log)

    track_event_if_configured("Anything")

    mock_track_event.assert_not_called()
    assert call_log == []


def test_sdk_exception_is_swallowed(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An exception from ``track_event`` must be caught and logged, not raised."""
    monkeypatch.setenv(
        APP_INSIGHTS_CONN_STRING_ENV,
        "InstrumentationKey=00000000-0000-0000-0000-000000000000",
    )
    fake_module = types.ModuleType("azure.monitor.events.extension")
    fake_module.track_event = MagicMock(  # type: ignore[attr-defined]
        side_effect=RuntimeError("exporter dead")
    )
    sys.modules["azure.monitor.events.extension"] = fake_module

    with caplog.at_level(logging.ERROR, logger=event_utils.logger.name):
        # Must not raise even though the underlying SDK does.
        track_event_if_configured("DeleteProcessSuccess", {"process_id": "p-9"})

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert any(
        "Failed to publish App Insights custom event" in r.getMessage()
        for r in errors
    )
