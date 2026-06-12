# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


from libs.agent_framework.azure_openai_response_retry import (
    ContextTrimConfig,
    RateLimitRetryConfig,
    _looks_like_context_length,
    _looks_like_rate_limit,
    _sanitize_author_name,
    _sanitize_author_names,
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
    # Falls back to default (120.0) on parse failure, then clamped (max(0, 120.0)).
    assert cfg.max_delay_seconds == 120.0


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

    e = E("prompt is too long")
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

    # Non-last long messages are truncated to <= max_message_chars.
    # The last message is intentionally never truncated (agent needs full context).
    assert len(trimmed[1]["content"]) <= 50
    assert len(trimmed[2]["content"]) == 100


# ---------------------------------------------------------------------------
# author_name sanitization (Chat Completions name pattern: ^[^\s<|\\/>]+$)
# ---------------------------------------------------------------------------


def test_sanitize_author_name_passthrough_for_valid_names() -> None:
    assert _sanitize_author_name("Coordinator") == "Coordinator"
    assert _sanitize_author_name("ResultGenerator") == "ResultGenerator"
    assert _sanitize_author_name("agent-1_2.x") == "agent-1_2.x"


def test_sanitize_author_name_replaces_whitespace_and_specials() -> None:
    assert _sanitize_author_name("Chief Architect") == "Chief_Architect"
    assert _sanitize_author_name("AKS Expert") == "AKS_Expert"
    # Tabs/newlines collapse to a single underscore.
    assert _sanitize_author_name("a\tb\nc") == "a_b_c"
    # Each disallowed char in the pattern is replaced.
    assert _sanitize_author_name("foo/bar\\baz|qux<x>y") == "foo_bar_baz_qux_x_y"


def test_sanitize_author_name_handles_edge_cases() -> None:
    assert _sanitize_author_name(None) is None
    assert _sanitize_author_name("") == ""
    assert _sanitize_author_name(123) == 123
    # All-invalid input collapses to empty -> None (so callers drop the field).
    assert _sanitize_author_name("   ") is None
    # Leading/trailing underscores from sanitization are stripped.
    assert _sanitize_author_name("  Chief  Architect  ") == "Chief_Architect"


def test_sanitize_author_names_dict_messages_shallow_copy() -> None:
    original = [
        {"role": "system", "content": "sys"},
        {"role": "assistant", "name": "Chief Architect", "content": "hi"},
        {"role": "user", "name": "Coordinator", "content": "ok"},
    ]
    out = _sanitize_author_names(original)

    # New list when changes happened.
    assert out is not original
    # Originals untouched.
    assert original[1]["name"] == "Chief Architect"
    # Unchanged messages share identity with originals (shallow copy only when needed).
    assert out[0] is original[0]
    assert out[2] is original[2]
    # Changed message is a new dict with sanitized name.
    assert out[1] is not original[1]
    assert out[1]["name"] == "Chief_Architect"
    assert out[1]["content"] == "hi"


def test_sanitize_author_names_dict_messages_drops_empty_name() -> None:
    original = [
        {"role": "assistant", "name": "   ", "content": "hello"},
    ]
    out = _sanitize_author_names(original)
    assert "name" not in out[0]
    assert out[0]["content"] == "hello"


def test_sanitize_author_names_returns_input_when_nothing_changes() -> None:
    original = [
        {"role": "system", "content": "sys"},
        {"role": "assistant", "name": "Coordinator", "content": "hi"},
    ]
    out = _sanitize_author_names(original)
    # Same sequence object returned to avoid pointless copies.
    assert out is original


def test_sanitize_author_names_object_messages_shallow_copy() -> None:
    class _Msg:
        def __init__(self, role: str, author_name: str | None, content: str) -> None:
            self.role = role
            self.author_name = author_name
            self.content = content

    m1 = _Msg("assistant", "Chief Architect", "hi")
    m2 = _Msg("assistant", "Coordinator", "ok")
    original = [m1, m2]

    out = _sanitize_author_names(original)

    # Original object untouched.
    assert m1.author_name == "Chief Architect"
    # Changed message replaced with a shallow copy carrying sanitized name.
    assert out[0] is not m1
    assert out[0].author_name == "Chief_Architect"
    assert out[0].content == "hi"
    # Unchanged message is the same instance.
    assert out[1] is m2
