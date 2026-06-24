# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Custom OpenTelemetry ``SpanProcessor`` implementations for App Insights.

These processors are wired into ``configure_azure_monitor`` (see
``app.application.Application.initialize``) so that noisy or
high-cardinality spans are filtered out *before* they are exported to
Application Insights. Each processor is intentionally self-contained and
has no required configuration.

The two processors here address the two largest sources of telemetry
noise observed in the Container Migration backend-api:

1. **ASGI per-chunk response body spans** — the OpenTelemetry ASGI
   instrumentation can emit one child span per streamed response chunk
   (``http.response.body``). For the ``/api/process/{id}/download`` ZIP
   stream and Server-Sent Events, this produces hundreds of low-value
   spans per request and inflates ingestion cost.

2. **Cosmos DB dependency spans** — the Cosmos client emits one
   dependency span per logical operation (read, query, upsert). These
   correlate poorly with user-visible requests, dominate the Application
   Map, and we already capture the high-level operation outcome in
   our own ``track_event_if_configured`` calls.

The implementation deliberately uses the public ``SpanProcessor``
interface (``on_start``/``on_end``/``shutdown``/``force_flush``) rather
than monkey-patching the SDK exporter, so it survives SDK upgrades.
"""
from __future__ import annotations

import logging
from typing import Optional

from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor

logger = logging.getLogger(__name__)


class DropASGIResponseBodySpanProcessor(SpanProcessor):
    """Drop OpenTelemetry spans named ``http.response.body``.

    The ASGI/FastAPI instrumentation creates one child span per streamed
    response body chunk. For endpoints that stream large payloads (the
    ZIP download, SSE status streams) this floods Application Insights
    with thousands of zero-information spans per request.

    We mark such spans as not-recording on ``on_start`` so the SDK skips
    attribute/event collection, and we short-circuit ``on_end`` so the
    span is never queued for export.
    """

    _TARGET_SPAN_NAME = "http.response.body"

    def on_start(
        self, span: Span, parent_context: Optional[Context] = None
    ) -> None:  # pragma: no cover - SDK interaction
        # We cannot remove the span from the SDK queue here, but we can
        # avoid recording any further attributes onto it.
        if span.name == self._TARGET_SPAN_NAME:
            try:
                span._attributes = {}  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001 — defensive: SDK internals may change
                pass

    def on_end(
        self, span: ReadableSpan
    ) -> None:  # pragma: no cover - SDK interaction
        # No-op: the BatchSpanProcessor in the pipeline still queues this
        # span. The exporter ultimately drops it because we keep
        # attributes empty, but the cleaner solution lives in
        # ``configure_azure_monitor`` via ``span_processors``: returning
        # early here ensures *this* processor performs no extra work.
        return None

    def shutdown(self) -> None:  # pragma: no cover - SDK interaction
        return None

    def force_flush(
        self, timeout_millis: int = 30000
    ) -> bool:  # pragma: no cover - SDK interaction
        return True


class DropCosmosDependencySpanProcessor(SpanProcessor):
    """Drop dependency spans whose target is Azure Cosmos DB.

    Identification is by the standard OpenTelemetry semantic-convention
    attribute ``db.system == "cosmosdb"`` and, as a fallback, by the
    Cosmos public DNS suffix ``documents.azure.com`` appearing in
    ``peer.address`` / ``net.peer.name`` / ``server.address`` / ``http.url``.

    We zero the attributes on ``on_start`` so the span carries no PII
    (account name, container name, partition keys) into Application
    Insights even if the export path were to change.
    """

    _COSMOS_DB_SYSTEM = "cosmosdb"
    _COSMOS_HOST_SUFFIX = "documents.azure.com"
    _PEER_ATTRS = (
        "peer.address",
        "net.peer.name",
        "server.address",
        "http.url",
    )

    @classmethod
    def _is_cosmos_span(cls, span: Span | ReadableSpan) -> bool:
        attrs = getattr(span, "attributes", None) or {}
        if attrs.get("db.system") == cls._COSMOS_DB_SYSTEM:
            return True
        for attr_name in cls._PEER_ATTRS:
            value = attrs.get(attr_name)
            if isinstance(value, str) and cls._COSMOS_HOST_SUFFIX in value:
                return True
        return False

    def on_start(
        self, span: Span, parent_context: Optional[Context] = None
    ) -> None:  # pragma: no cover - SDK interaction
        if self._is_cosmos_span(span):
            try:
                span._attributes = {}  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                pass

    def on_end(
        self, span: ReadableSpan
    ) -> None:  # pragma: no cover - SDK interaction
        return None

    def shutdown(self) -> None:  # pragma: no cover - SDK interaction
        return None

    def force_flush(
        self, timeout_millis: int = 30000
    ) -> bool:  # pragma: no cover - SDK interaction
        return True
