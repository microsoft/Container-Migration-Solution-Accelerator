# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Application-level logging and telemetry helpers.

This subpackage hosts the small Application Insights / OpenTelemetry
integration helpers used by the backend-api application:

- ``event_utils`` — a tiny wrapper around
  ``azure.monitor.events.extension.track_event`` that no-ops when the
  ``APPLICATIONINSIGHTS_CONNECTION_STRING`` environment variable is not
  configured. Callers can therefore emit structured events from
  any router/service without conditionally guarding each call site.
- ``span_filters`` — custom OpenTelemetry ``SpanProcessor`` implementations
  that drop noisy spans before they are exported to Application Insights
  (per-chunk ASGI ``http.response.body`` spans and Cosmos DB dependency
  spans). These keep the App Insights ingestion cost and the
  end-to-end transaction view clean for the Container Migration workflow.

Nothing in this subpackage imports Azure SDKs at module-import time, so
it is safe to import from contexts where the App Insights SDK may not be
fully wired up yet (e.g. application bootstrap before
``configure_azure_monitor`` has run).
"""
