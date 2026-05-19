# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from libs.agent_framework.azure_openai_response_retry import (
    ContextTrimConfig,
    RateLimitRetryConfig,
    _estimate_message_text,
    _format_exc_brief,
    _get_message_role,
    _looks_like_context_length,
    _looks_like_rate_limit,
    _looks_like_save_blob_call,
    _looks_like_tool_result,
    _safe_str,
    _set_message_text,
    _summarize_save_blob,
    _trim_messages,
    _truncate_text,
    _try_get_retry_after_seconds,
)


class TestFormatExcBrief:
    def test_with_message(self):
        assert _format_exc_brief(ValueError("boom")) == "ValueError: boom"

    def test_no_message(self):
        assert _format_exc_brief(ValueError("")) == "ValueError"


class TestRateLimitRetryConfig:
    def test_from_env_defaults(self, monkeypatch):
        for k in ("AOAI_429_MAX_RETRIES", "AOAI_429_BASE_DELAY_SECONDS", "AOAI_429_MAX_DELAY_SECONDS"):
            monkeypatch.delenv(k, raising=False)
        cfg = RateLimitRetryConfig.from_env()
        assert cfg.max_retries == 8
        assert cfg.base_delay_seconds == 5.0

    def test_from_env_with_values(self, monkeypatch):
        monkeypatch.setenv("AOAI_429_MAX_RETRIES", "3")
        monkeypatch.setenv("AOAI_429_BASE_DELAY_SECONDS", "2.5")
        monkeypatch.setenv("AOAI_429_MAX_DELAY_SECONDS", "60.0")
        cfg = RateLimitRetryConfig.from_env()
        assert cfg.max_retries == 3
        assert cfg.base_delay_seconds == 2.5
        assert cfg.max_delay_seconds == 60.0

    def test_from_env_with_invalid_int(self, monkeypatch):
        monkeypatch.setenv("AOAI_429_MAX_RETRIES", "abc")
        cfg = RateLimitRetryConfig.from_env()
        assert cfg.max_retries == 8

    def test_from_env_negative_clamped(self, monkeypatch):
        monkeypatch.setenv("AOAI_429_MAX_RETRIES", "-3")
        monkeypatch.setenv("AOAI_429_BASE_DELAY_SECONDS", "-1")
        cfg = RateLimitRetryConfig.from_env()
        assert cfg.max_retries == 0
        assert cfg.base_delay_seconds == 0.0


class TestLooksLikeRateLimit:
    def test_text_indicator(self):
        assert _looks_like_rate_limit(Exception("Too Many Requests")) is True
        assert _looks_like_rate_limit(Exception("rate limit exceeded")) is True

    def test_status_429(self):
        e = Exception("anything")
        e.status_code = 429
        assert _looks_like_rate_limit(e) is True

    def test_status_500(self):
        e = Exception("server")
        e.status_code = 503
        assert _looks_like_rate_limit(e) is True

    def test_empty_message_treated_transient(self):
        assert _looks_like_rate_limit(Exception("")) is True

    def test_chained_cause(self):
        inner = Exception("rate limit")
        outer = Exception("wrapper")
        outer.__cause__ = inner
        assert _looks_like_rate_limit(outer) is True

    def test_returns_false_for_unrelated(self):
        e = Exception("validation failed: bad input")
        e.status_code = 400
        assert _looks_like_rate_limit(e) is False


class TestLooksLikeContextLength:
    def test_text_indicator(self):
        assert _looks_like_context_length(Exception("maximum context length exceeded"))

    def test_400_with_context_keyword(self):
        e = Exception("token limit exceeded")
        e.status_code = 400
        assert _looks_like_context_length(e) is True

    def test_400_without_context_keyword(self):
        e = Exception("invalid argument")
        e.status_code = 400
        assert _looks_like_context_length(e) is False

    def test_chained_cause(self):
        inner = Exception("maximum context length exceeded")
        outer = Exception("oops")
        outer.__cause__ = inner
        assert _looks_like_context_length(outer) is True


class TestSafeStr:
    def test_none(self):
        assert _safe_str(None) == ""

    def test_str_passthrough(self):
        assert _safe_str("hi") == "hi"

    def test_int_converted(self):
        assert _safe_str(123) == "123"


class TestToolResultDetection:
    def test_short_text_returns_false(self):
        assert _looks_like_tool_result("short") is False

    def test_blob_indicator_returns_true(self):
        text = '{"blob_name": "x.txt", ' + "x" * 100 + '}'
        assert _looks_like_tool_result(text) is True

    def test_no_indicators(self):
        assert _looks_like_tool_result("a" * 100) is False


class TestSaveBlobCallDetection:
    def test_empty_returns_false(self):
        assert _looks_like_save_blob_call("") is False

    def test_short_returns_false(self):
        assert _looks_like_save_blob_call("save_content_to_blob(short)") is False

    def test_long_call_returns_true(self):
        text = "save_content_to_blob(" + "x" * 1500 + ")"
        assert _looks_like_save_blob_call(text) is True


class TestSummarizeSaveBlob:
    def test_extracts_blob_name(self):
        text = '{"blob_name": "report.pdf", "data": "x"}'
        result = _summarize_save_blob(text, max_chars=200)
        assert "report.pdf" in result

    def test_unknown_when_no_blob_name(self):
        text = '{"other": "data"}'
        result = _summarize_save_blob(text, max_chars=200)
        assert "unknown" in result


class TestTruncateText:
    def test_zero_max(self):
        assert _truncate_text("x" * 100, max_chars=0, keep_head_chars=0, keep_tail_chars=0) == ""

    def test_empty(self):
        assert _truncate_text("", max_chars=10, keep_head_chars=5, keep_tail_chars=5) == ""

    def test_short_passthrough(self):
        assert _truncate_text("hi", max_chars=100, keep_head_chars=5, keep_tail_chars=5) == "hi"

    def test_truncates_with_marker(self):
        text = "A" * 500 + "B" * 500
        result = _truncate_text(text, max_chars=200, keep_head_chars=50, keep_tail_chars=50)
        assert "TRUNCATED" in result

    def test_no_tail_when_remaining_zero(self):
        text = "X" * 100
        result = _truncate_text(text, max_chars=20, keep_head_chars=20, keep_tail_chars=10)
        assert len(result) <= 20


class TestEstimateMessageText:
    def test_none(self):
        assert _estimate_message_text(None) == ""

    def test_dict_with_content(self):
        assert _estimate_message_text({"content": "hello"}) == "hello"

    def test_dict_with_text(self):
        assert _estimate_message_text({"text": "hi"}) == "hi"

    def test_object_with_content(self):
        class M:
            content = "msg"

        assert _estimate_message_text(M()) == "msg"

    def test_dict_fallback(self):
        result = _estimate_message_text({"role": "user"})
        assert "user" in result


class TestMessageRole:
    def test_dict(self):
        assert _get_message_role({"role": "user"}) == "user"

    def test_dict_no_role(self):
        assert _get_message_role({}) is None

    def test_object(self):
        class M:
            role = "system"

        assert _get_message_role(M()) == "system"

    def test_none(self):
        assert _get_message_role(None) is None


class TestSetMessageText:
    def test_dict_with_content(self):
        result = _set_message_text({"content": "old"}, "new")
        assert result["content"] == "new"

    def test_dict_with_text(self):
        result = _set_message_text({"text": "old"}, "new")
        assert result["text"] == "new"

    def test_dict_with_no_known_keys(self):
        result = _set_message_text({"role": "user"}, "new")
        assert result["content"] == "new"

    def test_object_with_content(self):
        class M:
            content = "old"

        m = M()
        result = _set_message_text(m, "new")
        assert result.content == "new"


class TestContextTrimConfigFromEnv:
    def test_defaults_when_unset(self, monkeypatch):
        for k in [
            "AOAI_CTX_TRIM_ENABLED",
            "AOAI_CTX_MAX_TOTAL_CHARS",
            "AOAI_CTX_MAX_MESSAGE_CHARS",
            "AOAI_CTX_KEEP_LAST_MESSAGES",
            "AOAI_CTX_KEEP_HEAD_CHARS",
            "AOAI_CTX_KEEP_TAIL_CHARS",
            "AOAI_CTX_KEEP_SYSTEM_MESSAGES",
            "AOAI_CTX_RETRY_ON_CONTEXT_ERROR",
        ]:
            monkeypatch.delenv(k, raising=False)
        cfg = ContextTrimConfig.from_env()
        assert cfg.enabled is True

    def test_disabled_via_env(self, monkeypatch):
        monkeypatch.setenv("AOAI_CTX_TRIM_ENABLED", "0")
        cfg = ContextTrimConfig.from_env()
        assert cfg.enabled is False

    def test_invalid_int_falls_back(self, monkeypatch):
        monkeypatch.setenv("AOAI_CTX_MAX_TOTAL_CHARS", "abc")
        cfg = ContextTrimConfig.from_env()
        assert cfg.max_total_chars == 240_000


class TestTrimMessages:
    def test_disabled_returns_copy(self):
        cfg = ContextTrimConfig(enabled=False)
        msgs = [{"role": "user", "content": "hi"}]
        out = _trim_messages(list(msgs), cfg=cfg)
        assert out == msgs

    def test_keeps_last_n(self):
        cfg = ContextTrimConfig(
            enabled=True,
            max_total_chars=10_000,
            max_message_chars=0,
            keep_last_messages=2,
            keep_system_messages=False,
        )
        msgs = [
            {"role": "user", "content": f"msg {i}"} for i in range(10)
        ]
        out = _trim_messages(list(msgs), cfg=cfg)
        assert len(out) == 2
        assert "msg 9" in out[-1]["content"]

    def test_summarizes_save_blob_call(self):
        cfg = ContextTrimConfig(enabled=True, max_total_chars=100_000, keep_last_messages=10)
        big = (
            'save_content_to_blob {"blob_name": "report.json", "content": "'
            + "x" * 2000
            + '"}'
        )
        msgs = [{"role": "user", "content": big}]
        out = _trim_messages(list(msgs), cfg=cfg)
        assert "report.json" in out[-1]["content"]

    def test_drops_old_when_over_budget(self):
        cfg = ContextTrimConfig(
            enabled=True,
            max_total_chars=200,
            max_message_chars=0,
            keep_last_messages=20,
            keep_system_messages=False,
        )
        msgs = [{"role": "user", "content": "y" * 100} for _ in range(10)]
        out = _trim_messages(list(msgs), cfg=cfg)
        assert sum(len(m["content"]) for m in out) <= 200


class TestTryGetRetryAfter:
    def test_int_attribute(self):
        e = Exception("x")
        e.retry_after = 7
        assert _try_get_retry_after_seconds(e) == 7.0

    def test_string_attribute(self):
        e = Exception("x")
        e.retry_after = "12.5"
        assert _try_get_retry_after_seconds(e) == 12.5

    def test_invalid_string_returns_none(self):
        e = Exception("x")
        e.retry_after = "not-a-number"
        assert _try_get_retry_after_seconds(e) is None

    def test_headers_dict(self):
        e = Exception("x")
        e.retry_after = None
        e.headers = {"retry-after": "42"}
        assert _try_get_retry_after_seconds(e) == 42.0

    def test_no_attributes_returns_none(self):
        assert _try_get_retry_after_seconds(Exception("x")) is None

    def test_inner_exception(self):
        inner = Exception("inner")
        inner.retry_after = 5
        outer = Exception("outer")
        outer.inner_exception = inner
        assert _try_get_retry_after_seconds(outer) == 5.0
