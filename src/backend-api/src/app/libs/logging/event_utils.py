# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Lightweight helpers for emitting Application Insights *custom events*.

The backend-api routers want to emit structured events such as
``"UploadFilesSuccess"`` / ``"UploadFilesError"`` for business-level
observability — independent of whatever distributed-tracing spans the
OpenTelemetry instrumentation produces. ``azure-monitor-events-extension``
provides ``track_event`` for exactly this purpose, but two practical
problems show up in production:

1. ``track_event`` raises (or warns repeatedly) when called before
   ``configure_azure_monitor`` has been invoked — for example in unit
   tests or in local dev runs where ``APPLICATIONINSIGHTS_CONNECTION_STRING``
   is intentionally unset.
2. Importing ``azure.monitor.events.extension`` eagerly at module
   import time slows cold-start and pulls in the OTEL log SDK even for
   code paths that never emit a custom event.

``track_event_if_configured`` solves both problems. It:

* short-circuits when the connection string env var is empty/unset and
  emits a single warning the first time it is called (subsequent
  unconfigured calls are silent — see ``_warned_unconfigured`` below);
* lazily imports ``azure.monitor.events.extension`` only on the first
  configured call;
* swallows and logs export failures so that telemetry problems can
  never break a request.

The function is deliberately small and side-effect-free outside the
optional Application Insights call. Tests can therefore verify both
the gating behaviour and the export behaviour without standing up a
real OpenTelemetry pipeline.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Mapping

logger = logging.getLogger(__name__)

# Environment variable that ``configure_azure_monitor`` keys off and that
# we use as the single source of truth for "is App Insights configured".
APP_INSIGHTS_CONN_STRING_ENV = "APPLICATIONINSIGHTS_CONNECTION_STRING"

# Public message constant so tests can assert on the wording without
# duplicating the string. We deliberately do not include the env-var
# value in any log message — see hard-constraint #8 (never echo secrets).
_UNCONFIGURED_WARNING = (
    "APPLICATIONINSIGHTS_CONNECTION_STRING is not set; "
    "track_event_if_configured(name=%s) is a no-op."
)

# Module-level latch so we warn at most once per process when the
# connection string is missing. Reset by tests via
# ``reset_unconfigured_warning_for_tests``.
_warned_unconfigured: bool = False


def _is_app_insights_configured() -> bool:
    """Return True iff the App Insights connection string is non-empty.

    Reading the environment on every call (rather than caching at import
    time) is intentional: ``Application_Base.__init__`` may load the
    ``.env`` file or pull values from Azure App Configuration *after*
    this module has been imported.
    """
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

    Parameters
    ----------
    name:
        Event name as it should appear in the App Insights ``customEvents``
        table. Use ``PascalCase`` for consistency with the rest of the
        product (e.g. ``"UploadFilesSuccess"``, ``"StartProcessingError"``).
    properties:
        Optional mapping of string keys to JSON-serialisable values that
        will land in ``customDimensions``. ``None`` is normalised to an
        empty dict before being forwarded.

    Behaviour
    ---------
    * If ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is unset or empty,
      this is a no-op. A single warning is logged the first time this
      occurs in the process; subsequent calls are silent.
    * If the env var is set, ``azure.monitor.events.extension.track_event``
      is invoked. Any exception raised during export is caught and logged
      at ``WARNING`` level — telemetry must never break a request.
    """
    global _warned_unconfigured

    # Fast-path: missing connection string -> no-op (with a one-shot warning).
    if not _is_app_insights_configured():
        if not _warned_unconfigured:
            logger.warning(_UNCONFIGURED_WARNING, name)
            _warned_unconfigured = True
        return

    safe_properties: dict[str, Any] = dict(properties) if properties else {}

    try:
        # Lazy import: keeps cold-start cheap and lets unit tests patch
        # the symbol via ``monkeypatch.setattr`` on this module.
        from azure.monitor.events.extension import track_event  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - dependency declared in pyproject
        logger.warning(
            "azure-monitor-events-extension is not installed; "
            "skipping track_event(name=%s).",
            name,
        )
        return

    try:
        track_event(name, safe_properties)
    except Exception:  # noqa: BLE001 — telemetry must never break a request
        logger.exception(
            "Failed to publish App Insights custom event name=%s.", name
        )
