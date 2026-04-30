# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Unit tests covering the small helper methods on FailureContext."""

from datetime import datetime

import pytest

from libs.reporting.models.failure_context import (
    FailureContext,
    FailureSeverity,
    FailureType,
)


def _make_context(**overrides) -> FailureContext:
    base = dict(
        failure_id="failure-1",
        failure_type=FailureType.UNKNOWN_ERROR,
        severity=FailureSeverity.LOW,
        error_message="boom",
    )
    base.update(overrides)
    return FailureContext(**base)


def test_timestamp_iso_returns_iso_format_of_timestamp():
    fixed_ts = 1_700_000_000.0
    ctx = _make_context(timestamp=fixed_ts)

    iso = ctx.timestamp_iso

    assert iso == datetime.fromtimestamp(fixed_ts).isoformat()


def test_add_retry_attempt_increments_count_and_appends_message():
    ctx = _make_context()

    ctx.add_retry_attempt("retried network call")
    ctx.add_retry_attempt("retried again")

    assert ctx.retry_count == 2
    assert ctx.previous_attempts == [
        "Attempt 1: retried network call",
        "Attempt 2: retried again",
    ]


def test_correlate_with_sets_correlation_id_when_unset():
    ctx = _make_context()

    ctx.correlate_with("other-failure-id")

    assert ctx.correlation_id == "other-failure-id"


def test_correlate_with_does_not_overwrite_existing_correlation_id():
    ctx = _make_context(correlation_id="original")

    ctx.correlate_with("ignored-failure-id")

    assert ctx.correlation_id == "original"


@pytest.mark.parametrize(
    "failure_type",
    [
        FailureType.TIMEOUT,
        FailureType.LLM_API_FAILURE,
        FailureType.YAML_PARSING_ERROR,
    ],
)
def test_failure_context_accepts_various_failure_types(failure_type):
    ctx = _make_context(failure_type=failure_type)

    assert ctx.failure_type is failure_type
