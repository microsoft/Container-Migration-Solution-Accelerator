# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Lightweight helpers for emitting Application Insights custom events from the processor service.

Mirrors the backend-api ``track_event_if_configured`` pattern so the processor
can emit structured custom events (e.g. token usage) to the same Application
Insights workspace.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Mapping

logger = logging.getLogger(__name__)

APP_INSIGHTS_CONN_STRING_ENV = "APPLICATIONINSIGHTS_CONNECTION_STRING"

_UNCONFIGURED_WARNING = (
    "APPLICATIONINSIGHTS_CONNECTION_STRING is not set; "
    "track_event_if_configured(name=%s) is a no-op."
)

_warned_unconfigured: bool = False


def _is_app_insights_configured() -> bool:
    value = os.environ.get(APP_INSIGHTS_CONN_STRING_ENV)
    return bool(value and value.strip())


def reset_unconfigured_warning_for_tests() -> None:
    """Test-only helper: reset the once-per-process warning latch."""
    global _warned_unconfigured
    _warned_unconfigured = False


def track_event_if_configured(
    name: str, properties: Mapping[str, Any] | None = None
) -> None:
    """Emit an Application Insights custom event, gated on configuration.

    No-op when ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is unset.
    Swallows export failures so telemetry never breaks processing.
    """
    global _warned_unconfigured

    if not _is_app_insights_configured():
        if not _warned_unconfigured:
            logger.warning(_UNCONFIGURED_WARNING, name)
            _warned_unconfigured = True
        return

    safe_properties: dict[str, Any] = dict(properties) if properties else {}

    try:
        from azure.monitor.events.extension import track_event  # type: ignore[import-not-found]
    except ImportError:
        logger.warning(
            "azure-monitor-events-extension is not installed; "
            "skipping track_event(name=%s).",
            name,
        )
        return

    try:
        track_event(name, safe_properties)
    except Exception:
        logger.exception(
            "Failed to publish App Insights custom event name=%s.", name
        )
