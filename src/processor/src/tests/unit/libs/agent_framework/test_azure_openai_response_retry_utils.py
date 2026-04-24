# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


from libs.agent_framework.azure_openai_response_retry import (
    ContextTrimConfig,
    RateLimitRetryConfig,
    _looks_like_context_length,
    _looks_like_rate_limit,
    _trim_messages,
    _truncate_text,
)


def test_rate_limit_retry_config_from_env_clamps_invalid_values(monkeypatch) -> None:
    monkeypatch.setenv("AOAI_429_MAX_RETRIES", "-3")
    monkeypatch.setenv("AOAI_429_BASE_DELAY_SECONDS", "-1")
    monkeypatch.setenv("AOAI_429_MAX_DELAY_SECONDS", "not-a-float")

    cfg = RateLimitRetryConfig.from_env()
    assert cfg.max_retries == 0
    assert cfg.base_delay_seconds == 0.0
    # Falls back to default (30.0) on parse failure, then clamped.
    assert cfg.max_delay_seconds == 30.0


def test_looks_like_rate_limit_detects_common_signals() -> None:
    assert _looks_like_rate_limit(Exception("Too Many Requests"))
    assert _looks_like_rate_limit(Exception("rate limit exceeded"))

    class E(Exception):
        pass

    e = E("no message")
    e.status_code = 429
    assert _looks_like_rate_limit(e)


def test_looks_like_context_length_detects_common_signals() -> None:
    assert _looks_like_context_length(Exception("maximum context length"))

    class E(Exception):
        pass

    e = E("something")
    e.status = 413
    assert _looks_like_context_length(e)


def test_truncate_text_includes_marker_and_respects_budget() -> None:
    text = "A" * 200 + "B" * 200
    truncated = _truncate_text(
        text, max_chars=120, keep_head_chars=40, keep_tail_chars=40
    )
    assert len(truncated) <= 120
    assert "TRUNCATED" in truncated


def test_trim_messages_keeps_system_and_tails_and_truncates_long_messages() -> None:
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "X" * 100},
        {"role": "assistant", "content": "Y" * 100},
        {"role": "user", "content": "Z" * 100},
    ]

    cfg = ContextTrimConfig(
        enabled=True,
        max_total_chars=200,
        max_message_chars=50,
        keep_last_messages=2,
        keep_head_chars=20,
        keep_tail_chars=10,
        keep_system_messages=True,
        retry_on_context_error=True,
    )

    trimmed = _trim_messages(messages, cfg=cfg)

    # system message is preserved; tail keeps last 2 non-system messages.
    assert trimmed[0]["role"] == "system"
    assert len(trimmed) == 3

    # Each long message should be truncated to <= max_message_chars.
    assert len(trimmed[1]["content"]) <= 50
    assert len(trimmed[2]["content"]) <= 50
