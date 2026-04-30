# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Extended unit tests for azure_openai_response_retry helpers and client wrappers."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from libs.agent_framework import azure_openai_response_retry as mod
from libs.agent_framework.azure_openai_response_retry import (
    AzureOpenAIResponseClientWithRetry,
    ContextTrimConfig,
    RateLimitRetryConfig,
    _estimate_message_text,
    _format_exc_brief,
    _get_message_role,
    _looks_like_context_length,
    _looks_like_rate_limit,
    _looks_like_save_blob_call,
    _looks_like_tool_result,
    _retry_call,
    _safe_str,
    _set_message_text,
    _summarize_save_blob,
    _trim_messages,
    _truncate_text,
    _try_get_retry_after_seconds,
)


# ── Pure helper coverage ───────────────────────────────────────────────────

def test_format_exc_brief_with_and_without_message() -> None:
    assert _format_exc_brief(ValueError("oops")) == "ValueError: oops"
    assert _format_exc_brief(ValueError()) == "ValueError"


def test_safe_str_handles_none_and_objects() -> None:
    assert _safe_str(None) == ""
    assert _safe_str("abc") == "abc"
    assert _safe_str(123) == "123"


def test_looks_like_tool_result_short_text_returns_false() -> None:
    assert not _looks_like_tool_result("")
    assert not _looks_like_tool_result("short")


def test_looks_like_tool_result_recognizes_indicators() -> None:
    assert _looks_like_tool_result('"blob_name": "file.txt"' + "x" * 60)
    assert _looks_like_tool_result("Successfully saved" + "x" * 60)


def test_looks_like_save_blob_call_requires_marker_and_size() -> None:
    assert not _looks_like_save_blob_call("")
    assert not _looks_like_save_blob_call("save_content_to_blob short")
    big = "save_content_to_blob" + "x" * 1500
    assert _looks_like_save_blob_call(big)


def test_summarize_save_blob_extracts_blob_name() -> None:
    text = '{"blob_name": "report.json"}' + "x" * 2000
    summary = _summarize_save_blob(text, 200)
    assert "report.json" in summary
    assert "blob storage" in summary


def test_summarize_save_blob_unknown_when_no_blob_name() -> None:
    text = "save_content_to_blob no name " + "x" * 2000
    summary = _summarize_save_blob(text, 200)
    assert "unknown" in summary


def test_estimate_message_text_dict_contents() -> None:
    assert _estimate_message_text({"content": "abc"}) == "abc"
    assert _estimate_message_text({"text": "tx"}) == "tx"
    assert _estimate_message_text({"contents": "ct"}) == "ct"


def test_estimate_message_text_object_attributes() -> None:
    obj = SimpleNamespace(content="objc")
    assert _estimate_message_text(obj) == "objc"
    obj2 = SimpleNamespace(text="objt")
    assert _estimate_message_text(obj2) == "objt"


def test_estimate_message_text_none_returns_empty() -> None:
    assert _estimate_message_text(None) == ""


def test_get_message_role_dict_object_and_invalid() -> None:
    assert _get_message_role({"role": "system"}) == "system"
    assert _get_message_role(SimpleNamespace(role="user")) == "user"
    assert _get_message_role({"role": 5}) is None
    assert _get_message_role(None) is None


def test_set_message_text_dict_with_existing_keys() -> None:
    out = _set_message_text({"content": "old"}, "new")
    assert out["content"] == "new"
    out = _set_message_text({"text": "old"}, "new")
    assert out["text"] == "new"
    out = _set_message_text({"contents": "old"}, "new")
    assert out["contents"] == "new"


def test_set_message_text_dict_no_known_key_adds_content() -> None:
    out = _set_message_text({"role": "u"}, "new")
    assert out["content"] == "new"


def test_set_message_text_object_with_attribute() -> None:
    obj = SimpleNamespace(content="old")
    out = _set_message_text(obj, "new")
    assert out.content == "new"


def test_set_message_text_object_without_known_attribute_returns_unchanged() -> None:
    obj = object()
    assert _set_message_text(obj, "new") is obj


def test_truncate_text_zero_max_or_empty_returns_empty() -> None:
    assert _truncate_text("abc", max_chars=0, keep_head_chars=10, keep_tail_chars=10) == ""
    assert _truncate_text("", max_chars=10, keep_head_chars=10, keep_tail_chars=10) == ""


def test_truncate_text_under_budget_returns_unchanged() -> None:
    assert _truncate_text("abc", max_chars=10, keep_head_chars=2, keep_tail_chars=2) == "abc"


def test_truncate_text_only_head_when_no_tail_room() -> None:
    text = "A" * 50
    out = _truncate_text(text, max_chars=10, keep_head_chars=10, keep_tail_chars=0)
    assert out == "A" * 10


def test_context_trim_config_from_env_parses_and_clamps(monkeypatch) -> None:
    monkeypatch.setenv("AOAI_CTX_TRIM_ENABLED", "yes")
    monkeypatch.setenv("AOAI_CTX_MAX_TOTAL_CHARS", "abc")  # invalid -> default
    monkeypatch.setenv("AOAI_CTX_KEEP_LAST_MESSAGES", "0")  # clamped to 1
    monkeypatch.setenv("AOAI_CTX_KEEP_SYSTEM_MESSAGES", "false")
    cfg = ContextTrimConfig.from_env()
    assert cfg.enabled is True
    assert cfg.max_total_chars == 240_000  # default fallback
    assert cfg.keep_last_messages == 1
    assert cfg.keep_system_messages is False


def test_context_trim_config_from_env_defaults_when_unset() -> None:
    cfg = ContextTrimConfig.from_env()
    assert cfg.max_total_chars >= 0


def test_try_get_retry_after_seconds_from_attribute() -> None:
    err = SimpleNamespace(retry_after=3.0)
    assert _try_get_retry_after_seconds(err) == 3.0


def test_try_get_retry_after_seconds_from_string_attribute() -> None:
    err = SimpleNamespace(retry_after="2.5")
    assert _try_get_retry_after_seconds(err) == 2.5


def test_try_get_retry_after_seconds_from_headers_dict() -> None:
    err = SimpleNamespace(retry_after=None, headers={"Retry-After": "4"})
    assert _try_get_retry_after_seconds(err) == 4.0


def test_try_get_retry_after_seconds_returns_none_when_no_signal() -> None:
    assert _try_get_retry_after_seconds(SimpleNamespace(retry_after=None)) is None


def test_looks_like_rate_limit_5xx_status() -> None:
    err = SimpleNamespace(status_code=503)
    assert _looks_like_rate_limit(err)


def test_looks_like_context_length_propagates_through_cause() -> None:
    inner = Exception("maximum context length exceeded")
    outer = Exception("wrapper")
    outer.__cause__ = inner
    assert _looks_like_context_length(outer)


def test_trim_messages_disabled_returns_copy() -> None:
    msgs = [{"role": "user", "content": "hi"}]
    out = _trim_messages(msgs, cfg=ContextTrimConfig(enabled=False))
    assert out == msgs
    assert out is not msgs


def test_trim_messages_summarizes_save_blob_calls() -> None:
    big_blob = '{"blob_name":"f.txt"}save_content_to_blob' + "y" * 1500
    msgs = [
        {"role": "user", "content": big_blob},
        {"role": "assistant", "content": "ok"},
    ]
    out = _trim_messages(
        msgs,
        cfg=ContextTrimConfig(
            enabled=True,
            max_total_chars=10_000,
            max_message_chars=0,
            keep_last_messages=10,
            keep_head_chars=100,
            keep_tail_chars=100,
            keep_system_messages=False,
            retry_on_context_error=True,
        ),
    )
    # First message should have been replaced with a summary.
    assert "blob storage" in out[0]["content"]


def test_trim_messages_drops_oldest_to_meet_budget() -> None:
    msgs = [
        {"role": "user", "content": "A" * 500},
        {"role": "assistant", "content": "B" * 500},
        {"role": "user", "content": "C" * 500},
    ]
    out = _trim_messages(
        msgs,
        cfg=ContextTrimConfig(
            enabled=True,
            max_total_chars=600,
            max_message_chars=0,
            keep_last_messages=10,
            keep_head_chars=100,
            keep_tail_chars=100,
            keep_system_messages=False,
            retry_on_context_error=True,
        ),
    )
    total = sum(len(m["content"]) for m in out)
    assert total <= 600


def test_trim_messages_truncates_only_remaining_system_when_all_dropped() -> None:
    msgs = [
        {"role": "system", "content": "S" * 1000},
    ]
    out = _trim_messages(
        msgs,
        cfg=ContextTrimConfig(
            enabled=True,
            max_total_chars=200,
            max_message_chars=0,
            keep_last_messages=10,
            keep_head_chars=50,
            keep_tail_chars=50,
            keep_system_messages=True,
            retry_on_context_error=True,
        ),
    )
    assert len(out) == 1
    assert len(out[0]["content"]) <= 200


def test_trim_messages_dedupes_repeated_blobs() -> None:
    msgs = [
        {"role": "user", "content": "duplicate" + "x" * 250},
        {"role": "user", "content": "duplicate" + "x" * 250},
    ]
    out = _trim_messages(
        msgs,
        cfg=ContextTrimConfig(
            enabled=True,
            max_total_chars=10_000,
            max_message_chars=0,
            keep_last_messages=10,
            keep_head_chars=50,
            keep_tail_chars=50,
            keep_system_messages=False,
            retry_on_context_error=True,
        ),
    )
    assert len(out) == 1


# ── _retry_call coverage ───────────────────────────────────────────────────

def test_retry_call_returns_value_on_first_success() -> None:
    async def factory():
        return "ok"

    cfg = RateLimitRetryConfig(max_retries=1, base_delay_seconds=0, max_delay_seconds=0)
    result = asyncio.run(_retry_call(factory, config=cfg))
    assert result == "ok"


def test_retry_call_retries_on_rate_limit_then_succeeds() -> None:
    calls = {"n": 0}

    async def factory():
        calls["n"] += 1
        if calls["n"] < 2:
            err = Exception("Too Many Requests")
            raise err
        return "good"

    cfg = RateLimitRetryConfig(max_retries=3, base_delay_seconds=0, max_delay_seconds=0)
    with patch("libs.agent_framework.azure_openai_response_retry.asyncio.sleep", new=AsyncMock()):
        result = asyncio.run(_retry_call(factory, config=cfg))
    assert result == "good"
    assert calls["n"] == 2


def test_retry_call_reraises_non_retryable_error() -> None:
    async def factory():
        raise ValueError("boom")

    cfg = RateLimitRetryConfig(max_retries=2, base_delay_seconds=0, max_delay_seconds=0)
    with pytest.raises(ValueError):
        asyncio.run(_retry_call(factory, config=cfg))


# ── Client wrapper coverage ─────────────────────────────────────────────────

def _make_client(retry_cfg=None, trim_cfg=None) -> AzureOpenAIResponseClientWithRetry:
    """Construct a wrapper instance bypassing parent SDK initialisation."""
    obj = AzureOpenAIResponseClientWithRetry.__new__(AzureOpenAIResponseClientWithRetry)
    obj._retry_config = retry_cfg or RateLimitRetryConfig(
        max_retries=1, base_delay_seconds=0, max_delay_seconds=0
    )
    obj._context_trim_config = trim_cfg or ContextTrimConfig(
        enabled=True,
        max_total_chars=400_000,
        max_message_chars=0,
        keep_last_messages=15,
        keep_head_chars=12_000,
        keep_tail_chars=4_000,
        keep_system_messages=True,
        retry_on_context_error=True,
    )
    return obj


def test_inner_get_response_returns_value_when_under_budget() -> None:
    client = _make_client()
    parent_mock = AsyncMock(return_value="response")

    async def parent_unbound(self, **kwargs):
        return await parent_mock(**kwargs)

    with patch.object(
        mod.AzureOpenAIResponsesClient,
        "_inner_get_response",
        parent_unbound,
        create=True,
    ):
        result = asyncio.run(
            client._inner_get_response(
                messages=[{"role": "user", "content": "hi"}],
                chat_options=None,
            )
        )

    assert result == "response"
    parent_mock.assert_called_once()


def test_inner_get_response_pre_trims_when_over_budget() -> None:
    client = _make_client(
        trim_cfg=ContextTrimConfig(
            enabled=True,
            max_total_chars=100,
            max_message_chars=0,
            keep_last_messages=2,
            keep_head_chars=20,
            keep_tail_chars=10,
            keep_system_messages=True,
            retry_on_context_error=True,
        )
    )
    parent_mock = AsyncMock(return_value="r")

    async def parent_unbound(self, **kwargs):
        return await parent_mock(**kwargs)

    msgs = [
        {"role": "user", "content": "X" * 200},
        {"role": "user", "content": "Y" * 200},
    ]

    with patch.object(
        mod.AzureOpenAIResponsesClient,
        "_inner_get_response",
        parent_unbound,
        create=True,
    ):
        asyncio.run(
            client._inner_get_response(messages=msgs, chat_options=None)
        )

    # Confirm parent called with trimmed messages (smaller payload).
    sent_msgs = parent_mock.call_args.kwargs["messages"]
    total = sum(len(m["content"]) for m in sent_msgs)
    assert total <= 200  # well under the original 400 chars


def test_inner_get_response_retries_on_context_length_error() -> None:
    client = _make_client()
    calls = {"n": 0}

    async def parent(self, *, messages, chat_options, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise Exception("maximum context length exceeded")
        return "recovered"

    with patch.object(
        mod.AzureOpenAIResponsesClient,
        "_inner_get_response",
        parent,
        create=True,
    ), patch(
        "libs.agent_framework.azure_openai_response_retry.asyncio.sleep",
        new=AsyncMock(),
    ):
        result = asyncio.run(
            client._inner_get_response(
                messages=[{"role": "user", "content": "hi"}],
                chat_options=None,
            )
        )

    assert result == "recovered"
    assert calls["n"] == 2


def test_inner_get_response_reraises_non_context_non_rate_error() -> None:
    client = _make_client()

    async def parent(self, **kwargs):
        raise ValueError("not retryable")

    with patch.object(
        mod.AzureOpenAIResponsesClient,
        "_inner_get_response",
        parent,
        create=True,
    ):
        with pytest.raises(ValueError):
            asyncio.run(
                client._inner_get_response(
                    messages=[{"role": "user", "content": "hi"}],
                    chat_options=None,
                )
            )


def test_inner_get_streaming_response_yields_items() -> None:
    client = _make_client()

    async def stream_gen(self, **kwargs):
        for x in ["a", "b", "c"]:
            yield x

    with patch.object(
        mod.AzureOpenAIResponsesClient,
        "_inner_get_streaming_response",
        stream_gen,
        create=True,
    ):
        async def collect():
            return [
                item
                async for item in client._inner_get_streaming_response(
                    messages=[{"role": "user", "content": "hi"}],
                    chat_options=None,
                )
            ]

        items = asyncio.run(collect())
    assert items == ["a", "b", "c"]


def test_inner_get_streaming_response_retries_on_context_length() -> None:
    client = _make_client()
    attempts = {"n": 0}

    async def stream_gen(self, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise Exception("maximum context length exceeded")
            yield  # unreachable; needed to make this an async generator
        for x in ["x", "y"]:
            yield x

    with patch.object(
        mod.AzureOpenAIResponsesClient,
        "_inner_get_streaming_response",
        stream_gen,
        create=True,
    ), patch(
        "libs.agent_framework.azure_openai_response_retry.asyncio.sleep",
        new=AsyncMock(),
    ):
        async def collect():
            return [
                item
                async for item in client._inner_get_streaming_response(
                    messages=[{"role": "user", "content": "hi"}],
                    chat_options=None,
                )
            ]

        items = asyncio.run(collect())

    assert items == ["x", "y"]
    assert attempts["n"] == 2


def test_inner_get_streaming_response_reraises_unrelated_error() -> None:
    client = _make_client()

    async def stream_gen(self, **kwargs):
        raise ValueError("boom")
        yield

    with patch.object(
        mod.AzureOpenAIResponsesClient,
        "_inner_get_streaming_response",
        stream_gen,
        create=True,
    ):
        async def collect():
            async for _ in client._inner_get_streaming_response(
                messages=[{"role": "user", "content": "hi"}],
                chat_options=None,
            ):
                pass

        with pytest.raises(ValueError):
            asyncio.run(collect())
