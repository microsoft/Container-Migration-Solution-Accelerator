# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Azure OpenAI Responses client wrapper with rate-limit-aware retry logic."""

from __future__ import annotations

import asyncio
import copy
import logging
import os
import random
import re
from dataclasses import dataclass
from typing import Any, MutableSequence

from agent_framework.openai import OpenAIChatClient, OpenAIChatCompletionClient
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
)
from tenacity.wait import wait_base

logger = logging.getLogger(__name__)


def _extract_tokens_from_dict_or_obj(ud: Any) -> tuple[int, int, int]:
    """Extract (input, output, total) token counts from a dict or object."""
    inp = out = tot = 0
    if isinstance(ud, dict):
        inp = ud.get("input_token_count", 0) or ud.get("input_tokens", 0) or 0
        out = ud.get("output_token_count", 0) or ud.get("output_tokens", 0) or 0
        tot = ud.get("total_token_count", 0) or ud.get("total_tokens", 0) or 0
    else:
        inp = getattr(ud, "input_token_count", 0) or getattr(ud, "input_tokens", 0) or 0
        out = getattr(ud, "output_token_count", 0) or getattr(ud, "output_tokens", 0) or 0
        tot = getattr(ud, "total_token_count", 0) or getattr(ud, "total_tokens", 0) or 0
    if not tot:
        tot = int(inp) + int(out)
    return int(inp), int(out), int(tot)


def _try_emit_token_event(inp: int, out: int, tot: int, source: str) -> None:
    """Log token usage found in stream/response for diagnostics.

    The actual LLM_Token_Usage event is emitted by TokenUsageTracker.record()
    in the orchestrator, which has full context (agent, step, model, user).
    This function only logs for debugging to avoid duplicate events.
    """
    if tot > 0 or inp > 0 or out > 0:
        logger.info(
            "[TOKEN_STREAM] usage found: input=%s output=%s total=%s source=%s",
            inp, out, tot, source,
        )


def _emit_usage_from_stream_item(item: Any) -> None:
    """Check a streamed ChatResponseUpdate for usage Content and emit an App Insights event.

    Checks multiple locations where usage data may appear:
    1. item.contents[] with type="usage" and usage_details
    2. item.usage (direct attribute - some SDK versions)
    3. item.metadata with usage keys
    """
    try:
        item_type = type(item).__name__

        # --- Path 1: contents list with Content(type="usage") ---
        contents = getattr(item, "contents", None)
        if contents:
            for content in contents:
                ctype = getattr(content, "type", None)
                if ctype == "usage":
                    # SDK UsageContent uses "details"; fall back to "usage_details"
                    ud = getattr(content, "details", None) or getattr(content, "usage_details", None)
                    if ud:
                        inp, out, tot = _extract_tokens_from_dict_or_obj(ud)
                        _try_emit_token_event(inp, out, tot, "stream_contents")
                        return

        # --- Path 2: direct .usage attribute ---
        usage = getattr(item, "usage", None)
        if usage is not None:
            inp, out, tot = _extract_tokens_from_dict_or_obj(usage)
            _try_emit_token_event(inp, out, tot, "stream_usage_attr")
            return

        # --- Path 3: .metadata dict with usage keys ---
        metadata = getattr(item, "metadata", None)
        if isinstance(metadata, dict):
            if any(k in metadata for k in ("input_tokens", "input_token_count", "usage")):
                usage_data = metadata.get("usage", metadata)
                inp, out, tot = _extract_tokens_from_dict_or_obj(usage_data)
                _try_emit_token_event(inp, out, tot, "stream_metadata")
                return

        # --- Diagnostic: log item shape for debugging (only for non-text items) ---
        if contents:
            content_types = [getattr(c, "type", "?") for c in contents]
            if any(t not in ("text",) for t in content_types):
                logger.debug(
                    "[TOKEN_DIAG] item_type=%s content_types=%s attrs=%s",
                    item_type,
                    content_types,
                    [a for a in dir(item) if not a.startswith("_")],
                )
    except Exception as e:
        logger.debug("[TOKEN_STREAM] error in emit: %s", e)


def _emit_usage_from_response(response: Any) -> None:
    """Extract and emit token usage from a non-streaming ChatResponse.

    Checks usage_details (SDK attribute) and contents for UsageContent items.
    """
    try:
        # Path 1: response.usage_details (ChatResponse from SDK)
        ud = getattr(response, "usage_details", None) or getattr(response, "details", None)
        if ud is not None:
            inp, out, tot = _extract_tokens_from_dict_or_obj(ud)
            _try_emit_token_event(inp, out, tot, "response_usage_details")
            return

        # Path 2: response.usage direct attribute
        usage = getattr(response, "usage", None)
        if usage is not None:
            inp, out, tot = _extract_tokens_from_dict_or_obj(usage)
            _try_emit_token_event(inp, out, tot, "response_usage_attr")
            return

        # Path 3: contents list with UsageContent
        contents = getattr(response, "contents", None)
        if contents:
            for content in contents:
                ctype = getattr(content, "type", None)
                if ctype == "usage":
                    ud = getattr(content, "details", None) or getattr(content, "usage_details", None)
                    if ud:
                        inp, out, tot = _extract_tokens_from_dict_or_obj(ud)
                        _try_emit_token_event(inp, out, tot, "response_contents")
                        return

        # Path 4: messages list with usage content
        messages = getattr(response, "messages", None)
        if messages:
            for msg in messages:
                msg_contents = getattr(msg, "contents", None)
                if not msg_contents:
                    continue
                for item in msg_contents:
                    if getattr(item, "type", None) == "usage":
                        ud = getattr(item, "details", None) or getattr(item, "usage_details", None)
                        if ud:
                            inp, out, tot = _extract_tokens_from_dict_or_obj(ud)
                            _try_emit_token_event(inp, out, tot, "response_msg_contents")
                            return
    except Exception as e:
        logger.debug("[TOKEN_RESPONSE] error in emit: %s", e)


def _format_exc_brief(exc: BaseException) -> str:
    name = type(exc).__name__
    msg = str(exc)
    return f"{name}: {msg}" if msg else name


@dataclass(frozen=True)
class RateLimitRetryConfig:
    max_retries: int = 8
    base_delay_seconds: float = 5.0
    max_delay_seconds: float = 120.0

    @staticmethod
    def from_env(
        max_retries_env: str = "AOAI_429_MAX_RETRIES",
        base_delay_env: str = "AOAI_429_BASE_DELAY_SECONDS",
        max_delay_env: str = "AOAI_429_MAX_DELAY_SECONDS",
    ) -> "RateLimitRetryConfig":
        def _int(name: str, default: int) -> int:
            try:
                return int(os.getenv(name, str(default)))
            except Exception:
                return default

        def _float(name: str, default: float) -> float:
            try:
                return float(os.getenv(name, str(default)))
            except Exception:
                return default

        return RateLimitRetryConfig(
            max_retries=max(0, _int(max_retries_env, 8)),
            base_delay_seconds=max(0.0, _float(base_delay_env, 5.0)),
            max_delay_seconds=max(0.0, _float(max_delay_env, 120.0)),
        )


def _looks_like_rate_limit(error: BaseException) -> bool:
    msg = str(error).lower()
    if any(s in msg for s in ["too many requests", "rate limit", "429", "throttle"]):
        return True

    status = getattr(error, "status_code", None) or getattr(error, "status", None)
    if status == 429:
        return True

    # Treat empty error messages as transient (likely connection reset or
    # incomplete response from Azure front-end) — worth retrying.
    if not msg or msg == str(type(error).__name__).lower():
        return True

    # Server errors (5xx) are transient and should be retried.
    if isinstance(status, int) and 500 <= status < 600:
        return True

    # "The model produced invalid content" is a transient error from Azure OpenAI
    # when the model output fails content/schema validation — worth retrying.
    # "No tool call found" is a 400 error when the conversation has orphaned
    # function call outputs with no matching tool call request.
    if any(
        s in msg
        for s in [
            "model produced invalid content",
            "invalid content",
            "no tool call found",
        ]
    ):
        return True

    cause = getattr(error, "__cause__", None)
    if cause and cause is not error:
        return _looks_like_rate_limit(cause)

    return False


def _looks_like_context_length(error: BaseException) -> bool:
    msg = str(error).lower()
    if any(
        s in msg
        for s in [
            "exceeds the context window",
            "maximum context length",
            "context length",
            "too many tokens",
            "prompt is too long",
            "input is too long",
            "please reduce the length",
        ]
    ):
        return True

    status = getattr(error, "status_code", None) or getattr(error, "status", None)
    if status in (400, 413):
        # Only treat 400/413 as context-length if the message actually mentions it.
        # Generic 400s (e.g. "No tool output found") must NOT trigger trim retries.
        context_keywords = [
            "context window",
            "context length",
            "too many tokens",
            "prompt is too long",
            "input is too long",
            "reduce the length",
            "maximum.*length",
            "token limit",
        ]
        if any(kw in msg for kw in context_keywords):
            return True

    cause = getattr(error, "__cause__", None)
    if cause and cause is not error:
        return _looks_like_context_length(cause)

    return False


def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    return str(val)


def _looks_like_tool_result(text: str) -> bool:
    """Heuristic: detect tool/function result messages by content patterns."""
    if not text or len(text) < 50:
        return False
    # Common patterns in tool results from blob operations
    indicators = [
        '"blob_name"',
        '"container_name"',
        '"folder_path"',
        '"content":',
        '"size":',
        '"last_modified":',
        "BlobProperties",
        "Successfully saved",
        "# ",
        "## ",  # Markdown headers from read_blob_content
    ]
    return any(ind in text[:500] for ind in indicators)


def _looks_like_save_blob_call(text: str) -> bool:
    """Detect save_content_to_blob tool calls with large content arguments."""
    if not text:
        return False
    return "save_content_to_blob" in text[:200] and len(text) > 1000


def _summarize_save_blob(text: str, max_chars: int) -> str:
    """Extract blob name and size from save_content_to_blob call."""
    import re

    blob_match = re.search(r'"blob_name"\s*:\s*"([^"]+)"', text)
    blob_name = blob_match.group(1) if blob_match else "unknown"
    return f"[saved {blob_name} to blob storage ({len(text)} chars)]"


def _truncate_text(
    text: str, *, max_chars: int, keep_head_chars: int, keep_tail_chars: int
) -> str:
    if max_chars <= 0:
        return ""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text

    head = text[: max(0, min(keep_head_chars, max_chars))]
    remaining = max_chars - len(head)
    if remaining <= 0:
        return head

    tail_len = max(0, min(keep_tail_chars, remaining))
    if tail_len <= 0:
        return head

    tail = text[-tail_len:]
    omitted = len(text) - (len(head) + len(tail))
    marker = f"\n... [TRUNCATED {omitted} CHARS] ...\n"

    budget = max_chars - (len(head) + len(tail))
    if budget <= 0:
        return head + tail
    if len(marker) > budget:
        marker = marker[:budget]

    return head + marker + tail


def _estimate_message_text(message: Any) -> str:
    if message is None:
        return ""

    if isinstance(message, dict):
        # Common shapes: {role, content}, {role, text}, {role, contents}
        for key in ("content", "text", "contents"):
            if key in message:
                return _safe_str(message.get(key))
        return _safe_str(message)

    # Attribute-based objects.
    for attr in ("content", "text", "contents"):
        if hasattr(message, attr):
            return _safe_str(getattr(message, attr))
    return _safe_str(message)


def _get_message_role(message: Any) -> str | None:
    if message is None:
        return None
    if isinstance(message, dict):
        role = message.get("role")
        return role if isinstance(role, str) else None
    role = getattr(message, "role", None)
    return role if isinstance(role, str) else None


def _set_message_text(message: Any, new_text: str) -> Any:
    """Best-effort setter for message text.

    - For dict messages: returns a shallow-copied dict with content/text updated.
    - For objects: tries to set .content or .text; if that fails, returns original.
    """
    if isinstance(message, dict):
        out = dict(message)
        if "content" in out:
            out["content"] = new_text
        elif "text" in out:
            out["text"] = new_text
        elif "contents" in out:
            out["contents"] = new_text
        else:
            out["content"] = new_text
        return out

    for attr in ("content", "text"):
        if hasattr(message, attr):
            try:
                setattr(message, attr, new_text)
                return message
            except Exception:
                pass
    return message


# OpenAI Chat Completions requires message `name` to match this pattern:
#   ^[^\s<|\\/>]+$
# Agent display names like "Chief Architect" contain spaces and are rejected.
# We replace any run of disallowed characters with a single underscore so the
# wire-format passes validation while preserving readability.
_OPENAI_NAME_INVALID_CHARS = re.compile(r"[\s<|\\/>]+")


def _sanitize_author_name(name: Any) -> Any:
    """Sanitize a single author_name for OpenAI Chat Completions.

    Returns the original value when it is not a string, is empty, or is already
    valid. Otherwise returns a string with disallowed characters collapsed to
    underscores and surrounding underscores stripped. If the result would be
    empty (e.g. name was all whitespace), returns ``None`` so the field can be
    dropped entirely.
    """
    if not isinstance(name, str):
        return name
    if not name:
        return None
    if not _OPENAI_NAME_INVALID_CHARS.search(name):
        return name
    sanitized = _OPENAI_NAME_INVALID_CHARS.sub("_", name).strip("_")
    return sanitized or None


def _sanitize_author_names(
    messages: MutableSequence[Any],
) -> MutableSequence[Any] | list[Any]:
    """Return ``messages`` with each entry's author_name sanitized.

    - For dict-shaped messages, the ``name`` key is rewritten on a shallow copy
      (and removed if the sanitized value would be empty).
    - For ``agent_framework.Message``-like objects, ``author_name`` is rewritten
      on a shallow copy so the originals (which may live in long-lived agent
      state) are not mutated.
    - Messages that don't need sanitization are returned unchanged. If nothing
      needed sanitization the original sequence is returned as-is.
    """
    out: list[Any] = []
    any_changed = False
    for m in messages:
        # Dict form: {"role": ..., "name": ..., "content": ...}
        if isinstance(m, dict):
            name = m.get("name")
            if isinstance(name, str):
                sanitized = _sanitize_author_name(name)
                if sanitized != name:
                    new_m = dict(m)
                    if sanitized:
                        new_m["name"] = sanitized
                    else:
                        new_m.pop("name", None)
                    out.append(new_m)
                    any_changed = True
                    continue
            out.append(m)
            continue

        # Object form (agent_framework Message): has .author_name attribute.
        name = getattr(m, "author_name", None)
        if isinstance(name, str):
            sanitized = _sanitize_author_name(name)
            if sanitized != name:
                try:
                    new_m = copy.copy(m)
                    new_m.author_name = sanitized
                    out.append(new_m)
                    any_changed = True
                    continue
                except Exception:
                    # Last-resort in-place fallback if copy/setattr is blocked.
                    try:
                        m.author_name = sanitized
                    except Exception:
                        pass
        out.append(m)
    return out if any_changed else messages


@dataclass(frozen=True)
class ContextTrimConfig:
    """Character-budget based context trimming.

    This is a defensive control to prevent hard failures like
    "input exceeds the context window" when upstream accidentally injects
    huge blobs (telemetry JSON, repeated instructions, etc.).
    """

    enabled: bool = True
    # GPT-5.1 supports 272K input tokens (~800K chars). With workspace context
    # injected into system instructions (never trimmed) and Qdrant shared memory
    # providing cross-step context, we can keep fewer conversation messages.
    max_total_chars: int = 400_000
    max_message_chars: int = 0  # Disabled — with keep_last_messages=15, per-message truncation is unnecessary
    keep_last_messages: int = 15
    keep_head_chars: int = 12_000
    keep_tail_chars: int = 4_000
    keep_system_messages: bool = True
    retry_on_context_error: bool = True

    @staticmethod
    def from_env(
        enabled_env: str = "AOAI_CTX_TRIM_ENABLED",
        max_total_chars_env: str = "AOAI_CTX_MAX_TOTAL_CHARS",
        max_message_chars_env: str = "AOAI_CTX_MAX_MESSAGE_CHARS",
        keep_last_messages_env: str = "AOAI_CTX_KEEP_LAST_MESSAGES",
        keep_head_chars_env: str = "AOAI_CTX_KEEP_HEAD_CHARS",
        keep_tail_chars_env: str = "AOAI_CTX_KEEP_TAIL_CHARS",
        keep_system_messages_env: str = "AOAI_CTX_KEEP_SYSTEM_MESSAGES",
        retry_on_context_error_env: str = "AOAI_CTX_RETRY_ON_CONTEXT_ERROR",
    ) -> "ContextTrimConfig":
        def _int(name: str, default: int) -> int:
            try:
                return int(os.getenv(name, str(default)))
            except Exception:
                return default

        def _bool(name: str, default: bool) -> bool:
            raw = os.getenv(name)
            if raw is None:
                return default
            return str(raw).strip().lower() in ("1", "true", "yes", "y", "on")

        return ContextTrimConfig(
            enabled=_bool(enabled_env, True),
            max_total_chars=max(0, _int(max_total_chars_env, 240_000)),
            max_message_chars=max(0, _int(max_message_chars_env, 20_000)),
            keep_last_messages=max(1, _int(keep_last_messages_env, 15)),
            keep_head_chars=max(0, _int(keep_head_chars_env, 10_000)),
            keep_tail_chars=max(0, _int(keep_tail_chars_env, 3_000)),
            keep_system_messages=_bool(keep_system_messages_env, True),
            retry_on_context_error=_bool(retry_on_context_error_env, True),
        )


def _trim_messages(
    messages: MutableSequence[Any], *, cfg: ContextTrimConfig
) -> list[Any]:
    if not cfg.enabled:
        return list(messages)

    # ──────────────────────────────────────────────────────────────────────
    # Phase 0: Summarize large save_content_to_blob calls.
    # Write payloads are redundant once persisted — replace with a short
    # summary. Read tool results are never truncated so the model always
    # has the full file content to reason about.
    # ──────────────────────────────────────────────────────────────────────
    SAVE_ARG_MAX_CHARS = 200  # Truncate save_content_to_blob arguments

    for i, m in enumerate(messages):
        text = _estimate_message_text(m)
        if _looks_like_save_blob_call(text) and len(text) > SAVE_ARG_MAX_CHARS:
            summary = _summarize_save_blob(text, SAVE_ARG_MAX_CHARS)
            messages[i] = _set_message_text(m, summary)

    # Keep last N messages; optionally keep system messages from the head.
    system_messages: list[Any] = []
    tail: list[Any] = list(messages)

    if cfg.keep_system_messages:
        for m in messages:
            if _get_message_role(m) == "system":
                system_messages.append(m)
            else:
                break

    if cfg.keep_last_messages > 0:
        tail = tail[-cfg.keep_last_messages :]

    # De-dupe large repeated blobs using author-less fingerprint on head/tail text.
    seen_fingerprints: set[tuple[str, str]] = set()
    cleaned: list[Any] = []

    for idx, m in enumerate(tail):
        text = _estimate_message_text(m)
        fp = (text[:200], text[-200:])
        if fp in seen_fingerprints:
            continue
        seen_fingerprints.add(fp)

        # Never truncate the last message — the agent needs it in full
        # to reason about the most recent tool result or instruction.
        is_last = idx == len(tail) - 1
        if (
            not is_last
            and cfg.max_message_chars > 0
            and len(text) > cfg.max_message_chars
        ):
            text = _truncate_text(
                text,
                max_chars=cfg.max_message_chars,
                keep_head_chars=cfg.keep_head_chars,
                keep_tail_chars=cfg.keep_tail_chars,
            )
            m = _set_message_text(m, text)
        cleaned.append(m)

    # Enforce overall budget by trimming oldest messages from the non-system tail.
    combined: list[Any] = system_messages + cleaned
    if cfg.max_total_chars <= 0:
        return combined

    def _total_chars(msgs: list[Any]) -> int:
        return sum(len(_estimate_message_text(x)) for x in msgs)

    while len(combined) > 1 and _total_chars(combined) > cfg.max_total_chars:
        # Prefer dropping earliest non-system message.
        # Never drop the last message — the model needs at least one.
        drop_index = 0
        if cfg.keep_system_messages and system_messages:
            drop_index = len(system_messages)
        if drop_index >= len(combined) - 1:
            # Only system messages (+ maybe 1 non-system) remain — truncate the last one.
            last = combined[-1]
            text = _estimate_message_text(last)
            text = _truncate_text(
                text,
                max_chars=cfg.max_total_chars,
                keep_head_chars=min(cfg.keep_head_chars, cfg.max_total_chars),
                keep_tail_chars=min(cfg.keep_tail_chars, cfg.max_total_chars),
            )
            combined[-1] = _set_message_text(last, text)
            break
        combined.pop(drop_index)

    return combined


def _try_get_retry_after_seconds(error: BaseException) -> float | None:
    inner = getattr(error, "inner_exception", None)
    if isinstance(inner, BaseException) and inner is not error:
        inner_retry = _try_get_retry_after_seconds(inner)
        if inner_retry is not None:
            return inner_retry

    candidates: list[Any] = []
    candidates.append(getattr(error, "retry_after", None))

    response = getattr(error, "response", None)
    if response is not None:
        candidates.append(getattr(response, "headers", None))

    headers = getattr(error, "headers", None)
    if headers is not None:
        candidates.append(headers)

    for item in candidates:
        if item is None:
            continue
        if isinstance(item, (int, float)):
            return float(item)
        if isinstance(item, str):
            try:
                return float(item)
            except Exception:
                continue
        if isinstance(item, dict):
            for key in ("retry-after", "Retry-After"):
                if key in item:
                    try:
                        return float(item[key])
                    except Exception:
                        pass
    return None


async def _retry_call(coro_factory, *, config: RateLimitRetryConfig):
    def _log_before_sleep(retry_state) -> None:
        exc = None
        if retry_state.outcome is not None and retry_state.outcome.failed:
            exc = retry_state.outcome.exception()

        # Tenacity sets next_action when it's about to sleep.
        sleep_s = None
        next_action = getattr(retry_state, "next_action", None)
        if next_action is not None:
            sleep_s = getattr(next_action, "sleep", None)

        retry_after = _try_get_retry_after_seconds(exc) if exc is not None else None
        status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        attempt = getattr(retry_state, "attempt_number", None)
        max_attempts = config.max_retries + 1

        logger.warning(
            "[AOAI_RETRY] attempt %s/%s; sleeping=%ss; retry_after=%s; status=%s; error=%s",
            attempt,
            max_attempts,
            None if sleep_s is None else round(float(sleep_s), 3),
            None if retry_after is None else round(float(retry_after), 3),
            status,
            None if exc is None else _format_exc_brief(exc),
        )

    class _WaitRetryAfterOrExpJitter(wait_base):
        def __init__(self, retry_config: RateLimitRetryConfig):
            self._cfg = retry_config

        def __call__(self, retry_state) -> float:
            exc = None
            if retry_state.outcome is not None and retry_state.outcome.failed:
                exc = retry_state.outcome.exception()

            if exc is not None:
                retry_after = _try_get_retry_after_seconds(exc)
                if retry_after is not None and retry_after >= 0:
                    return float(retry_after)

            attempt_index = max(0, retry_state.attempt_number - 1)
            delay = self._cfg.base_delay_seconds * (2**attempt_index)
            delay = min(delay, self._cfg.max_delay_seconds)
            delay = delay + random.uniform(0.0, 0.25 * max(delay, 0.1))
            return float(delay)

    retrying = AsyncRetrying(
        retry=retry_if_exception(_looks_like_rate_limit),
        stop=stop_after_attempt(config.max_retries + 1),
        wait=_WaitRetryAfterOrExpJitter(config),
        before_sleep=_log_before_sleep,
        reraise=True,
    )

    async for attempt in retrying:
        with attempt:
            return await coro_factory()

    raise RuntimeError("Retry loop exhausted unexpectedly")


class AzureOpenAIResponseClientWithRetry(OpenAIChatClient):
    """Azure OpenAI Responses client with 429 retry at the request boundary.

    Retry is centralized in the client layer (not in orchestrators) by retrying the
    underlying Responses calls made by `OpenAIChatClient`.
    """

    def __init__(
        self,
        *args: Any,
        retry_config: RateLimitRetryConfig | None = None,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._retry_config = retry_config or RateLimitRetryConfig.from_env()
        self._context_trim_config = ContextTrimConfig.from_env()

    def _inner_get_response(
        self, *, messages: MutableSequence[Any], options: Any = None, stream: bool = False, **kwargs: Any
    ) -> Any:
        """Override that adds retry + context-trimming around the parent call.

        Must remain a regular ``def`` (not ``async def``) because the parent
        returns different types depending on *stream*:
        - stream=False → Awaitable[ChatResponse]
        - stream=True  → ResponseStream  (AsyncIterable)
        """
        effective_messages = self._maybe_trim_messages(messages)

        if not effective_messages:
            # Empty inputs occur legitimately in group-chat orchestration when the
            # same speaker is selected twice in a row (the orchestrator's broadcast
            # excludes the source). The parent client's `_prepare_options` still
            # prepends the agent's system instructions, so the API call has content.
            logger.debug(
                "[AOAI_RETRY] empty messages list received; relying on options.instructions"
            )
            effective_messages = messages

        if stream:
            # For streaming, delegate to the parent which returns a proper
            # ResponseStream. The framework checks isinstance(result, ResponseStream)
            # and async generators fail that check.
            parent_inner = super(
                AzureOpenAIResponseClientWithRetry, self
            )._inner_get_response
            return parent_inner(
                messages=effective_messages, options=options, stream=True, **kwargs
            )
        else:
            return self._non_streaming_with_retry(
                effective_messages=effective_messages,
                original_messages=messages,
                options=options,
                **kwargs,
            )

    def _maybe_trim_messages(
        self, messages: MutableSequence[Any]
    ) -> MutableSequence[Any] | list[Any]:
        """Apply pre-call context trimming if enabled and over budget."""
        if not self._context_trim_config.enabled:
            return messages
        approx_chars = sum(len(_estimate_message_text(m)) for m in messages)
        if (
            self._context_trim_config.max_total_chars > 0
            and approx_chars > self._context_trim_config.max_total_chars
        ):
            trimmed = _trim_messages(messages, cfg=self._context_trim_config)
            if not trimmed:
                logger.warning(
                    "[AOAI_CTX_TRIM] trimming would remove all messages; keeping originals"
                )
                return messages
            logger.warning(
                "[AOAI_CTX_TRIM] pre-trimmed request messages: approx_chars=%s -> %s; count=%s -> %s",
                approx_chars,
                sum(len(_estimate_message_text(m)) for m in trimmed),
                len(messages),
                len(trimmed),
            )
            return trimmed
        return messages

    async def _non_streaming_with_retry(
        self,
        *,
        effective_messages: MutableSequence[Any] | list[Any],
        original_messages: MutableSequence[Any],
        options: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Non-streaming path: full retry + context-trim fallback."""
        parent_inner = super(
            AzureOpenAIResponseClientWithRetry, self
        )._inner_get_response

        try:
            response = await _retry_call(
                lambda: parent_inner_get_response(
                    messages=effective_messages, chat_options=chat_options, **kwargs
                ),
                config=self._retry_config,
            )
            # Extract and emit token usage from non-streaming response
            _emit_usage_from_response(response)
            return response
        except Exception as e:
            if not (
                self._context_trim_config.enabled
                and self._context_trim_config.retry_on_context_error
                and _looks_like_context_length(e)
            ):
                raise

            trimmed = _trim_messages(
                original_messages,
                cfg=ContextTrimConfig(
                    enabled=True,
                    max_total_chars=max(
                        50_000, self._context_trim_config.max_total_chars - 80_000
                    ),
                    max_message_chars=max(
                        3_000, self._context_trim_config.max_message_chars - 6_000
                    ),
                    keep_last_messages=max(
                        6, self._context_trim_config.keep_last_messages - 12
                    ),
                    keep_head_chars=max(
                        1_000, self._context_trim_config.keep_head_chars - 4_000
                    ),
                    keep_tail_chars=self._context_trim_config.keep_tail_chars,
                    keep_system_messages=True,
                    retry_on_context_error=True,
                ),
            )
            if not trimmed:
                logger.warning(
                    "[AOAI_CTX_TRIM] aggressive trim would remove all messages; re-raising original error"
                )
                raise
            logger.warning(
                "[AOAI_CTX_TRIM] retrying after context-length error; count=%s -> %s",
                len(original_messages),
                len(trimmed),
            )
            trim_delay = min(
                self._retry_config.base_delay_seconds,
                self._retry_config.max_delay_seconds,
            )
            logger.info(
                "[AOAI_CTX_TRIM] sleeping %ss before retry", round(trim_delay, 1)
            )
            await asyncio.sleep(trim_delay)
            return await _retry_call(
                lambda: parent_inner(
                    messages=trimmed, options=options, stream=False, **kwargs
                ),
                config=self._retry_config,
            )


class AzureOpenAIChatClientWithRetry(OpenAIChatCompletionClient):
    """Azure OpenAI Chat (Chat Completions) client with 429 retry at the request boundary.

    Wraps the ``/chat/completions`` endpoint used by Agent Framework by overriding
    the internal ``_inner_get_response`` method. This client works with all Azure
    OpenAI API versions including ``2025-03-01-preview``.

    Use this in preference to ``AzureOpenAIResponseClientWithRetry`` when the
    ``/responses`` endpoint (and the ``v1`` API version it requires) is not
    available in the target Azure OpenAI resource.
    """

    def __init__(
        self,
        *args: Any,
        retry_config: RateLimitRetryConfig | None = None,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._retry_config = retry_config or RateLimitRetryConfig.from_env()
        self._context_trim_config = ContextTrimConfig.from_env()

    def _inner_get_response(
        self, *, messages: MutableSequence[Any], options: Any = None, stream: bool = False, **kwargs: Any
    ) -> Any:
        """Override that adds retry + context-trimming around the parent call.

        Must remain a regular ``def`` (not ``async def``) because the parent
        returns different types depending on *stream*:
        - stream=False → Awaitable[ChatResponse]
        - stream=True  → ResponseStream  (AsyncIterable)
        """
        effective_messages = self._maybe_trim_messages(messages)

        if not effective_messages:
            # Empty inputs occur legitimately in group-chat orchestration when the
            # same speaker is selected twice in a row (the orchestrator's broadcast
            # excludes the source). The parent client's `_prepare_options` still
            # prepends the agent's system instructions, so the API call has content.
            logger.debug(
                "[AOAI_RETRY] empty messages list received; relying on options.instructions"
            )
            effective_messages = messages

        # OpenAI Chat Completions validates message `name` against ^[^\s<|\\/>]+$.
        # Sanitize before sending so agent display names like "Chief Architect"
        # don't trip a 400 BadRequest. Originals are shallow-copied, not mutated.
        # NOTE: this is a defense-in-depth pass on ``Message.author_name``.
        # The authoritative sanitization happens in ``_prepare_messages_for_openai``
        # below, which sanitizes the FINAL dict ``name`` field right before the
        # request is sent — catching any name that slips in via framework-internal
        # message construction (e.g. compaction, memory context providers,
        # orchestrator-injected messages) that bypasses this early pass.
        effective_messages = _sanitize_author_names(effective_messages)

        if stream:
            # For streaming, delegate to the parent which returns a proper
            # ResponseStream. The framework checks isinstance(result, ResponseStream)
            # and async generators fail that check.
            parent_inner = super(
                AzureOpenAIChatClientWithRetry, self
            )._inner_get_response
            return parent_inner(
                messages=effective_messages, options=options, stream=True, **kwargs
            )
        else:
            return self._non_streaming_with_retry(
                effective_messages=effective_messages,
                original_messages=messages,
                options=options,
                **kwargs,
            )

    def _prepare_messages_for_openai(self, chat_messages, *args: Any, **kwargs: Any):  # type: ignore[override]
        """Sanitize message ``name`` fields after framework conversion to wire format.

        The parent ``_prepare_messages_for_openai`` walks ``Message`` objects and
        builds the OpenAI dict payload (``{"role": ..., "name": ..., "content": ...}``).
        The ``name`` field is copied from ``Message.author_name`` and is validated
        by the OpenAI Chat Completions API against ``^[^\\s<|\\\\/>]+$``.

        We override here as a final, authoritative sanitization point. Even though
        ``_inner_get_response`` already sanitizes ``Message.author_name``, names
        can still reach this layer unsanitized from:

        * ``OpenAIChatCompletionClient._prepare_options`` calling
          ``prepend_instructions_to_messages`` (which does not author_name, but
          downstream callers may add named messages).
        * ``ChatAgent`` / memory context providers materializing messages with
          ``author_name`` set inside the agent run loop, after the client receives
          the original sequence.
        * Any framework-internal compaction or message-rewriting path that
          constructs new ``Message`` objects.

        Sanitizing the dict output is the single chokepoint guaranteed to be
        on every Chat Completions request, regardless of how the messages were
        assembled upstream.
        """
        result = super()._prepare_messages_for_openai(chat_messages, *args, **kwargs)
        for msg in result:
            if not isinstance(msg, dict):
                continue
            name = msg.get("name")
            if not isinstance(name, str):
                continue
            sanitized = _sanitize_author_name(name)
            if sanitized == name:
                continue
            if sanitized:
                msg["name"] = sanitized
            else:
                msg.pop("name", None)
        return result

    def _maybe_trim_messages(
        self, messages: MutableSequence[Any]
    ) -> MutableSequence[Any] | list[Any]:
        """Apply pre-call context trimming if enabled and over budget."""
        if not self._context_trim_config.enabled:
            return messages
        approx_chars = sum(len(_estimate_message_text(m)) for m in messages)
        if (
            self._context_trim_config.max_total_chars > 0
            and approx_chars > self._context_trim_config.max_total_chars
        ):
            trimmed = _trim_messages(messages, cfg=self._context_trim_config)
            if not trimmed:
                logger.warning(
                    "[AOAI_CTX_TRIM] trimming would remove all messages; keeping originals"
                )
                return messages
            logger.warning(
                "[AOAI_CTX_TRIM] pre-trimmed chat request messages: approx_chars=%s -> %s; count=%s -> %s",
                approx_chars,
                sum(len(_estimate_message_text(m)) for m in trimmed),
                len(messages),
                len(trimmed),
            )
            return trimmed
        return messages

            iterator = stream.__aiter__()
            try:
                first = await iterator.__anext__()

                async def _tail():
                    yield first
                    async for item in iterator:
                        yield item

                _item_count = 0
                _last_item = None
                async for item in _tail():
                    _item_count += 1
                    _last_item = item
                    _emit_usage_from_stream_item(item)
                    yield item

                # After stream completes, log diagnostic about the last item
                if _last_item is not None:
                    try:
                        _attrs = [a for a in dir(_last_item) if not a.startswith("_")]
                        _contents = getattr(_last_item, "contents", None)
                        _content_info = []
                        if _contents:
                            for _c in _contents:
                                _ct = getattr(_c, "type", "?")
                                _ca = [a for a in dir(_c) if not a.startswith("_")]
                                _content_info.append({"type": _ct, "attrs": _ca})
                        _usage_attr = getattr(_last_item, "usage", None)
                        logger.info(
                            "[TOKEN_DIAG_FINAL] stream_items=%d last_item_type=%s attrs=%s contents=%s usage_attr=%s",
                            _item_count,
                            type(_last_item).__name__,
                            _attrs,
                            _content_info,
                            repr(_usage_attr) if _usage_attr is not None else "None",
                        )
                    except Exception:
                        pass
                return
            except StopAsyncIteration:
                return
            except Exception as e:
                close = getattr(stream, "aclose", None)
                if callable(close):
                    try:
                        await close()
                    except Exception:
                        logger.debug("Best-effort close of response stream failed", exc_info=True)

                # Progressive retry for context-length failures.
                if (
                    self._context_trim_config.enabled
                    and self._context_trim_config.retry_on_context_error
                    and _looks_like_context_length(e)
                ):
                    # Make trimming progressively more aggressive on each retry
                    # GPT-5.1: 272K input tokens ≈ 800K chars. Scale down from 600K default.
                    scale = attempt_index + 1
                    aggressive_cfg = ContextTrimConfig(
                        enabled=True,
                        max_total_chars=max(
                            30_000,
                            self._context_trim_config.max_total_chars - scale * 100_000,
                        ),
                        max_message_chars=max(
                            2_000,
                            self._context_trim_config.max_message_chars - scale * 8_000,
                        ),
                        keep_last_messages=max(
                            4,
                            self._context_trim_config.keep_last_messages - scale * 8,
                        ),
                        keep_head_chars=max(
                            500,
                            self._context_trim_config.keep_head_chars - scale * 3_000,
                        ),
                        keep_tail_chars=max(
                            500,
                            self._context_trim_config.keep_tail_chars - scale * 1_000,
                        ),
                        keep_system_messages=True,
                        retry_on_context_error=True,
                    )
                    trimmed = _trim_messages(effective_messages, cfg=aggressive_cfg)
                    logger.warning(
                        "[AOAI_CTX_TRIM_STREAM] retrying after context-length error (attempt %s); count=%s -> %s, budget=%s",
                        attempt_index + 1,
                        len(effective_messages),
                        len(trimmed),
                        aggressive_cfg.max_total_chars,
                    )
                    effective_messages = trimmed
                    if attempt_index >= attempts - 1:
                        # No more retries available.
                        raise

                    # Cool down before retrying — immediate retries after trimming
                    # tend to trigger 429s because the API hasn't recovered yet.
                    trim_delay = self._retry_config.base_delay_seconds * (
                        2**attempt_index
                    )
                    trim_delay = min(trim_delay, self._retry_config.max_delay_seconds)
                    logger.info(
                        "[AOAI_CTX_TRIM_STREAM] sleeping %ss before retry",
                        round(trim_delay, 1),
                    )
                    await asyncio.sleep(trim_delay)
                    continue

        try:
            return await _retry_call(
                lambda: parent_inner(
                    messages=effective_messages, options=options, stream=False, **kwargs
                ),
                config=self._retry_config,
            )
        except Exception as e:
            if not (
                self._context_trim_config.enabled
                and self._context_trim_config.retry_on_context_error
                and _looks_like_context_length(e)
            ):
                raise

            trimmed = _trim_messages(
                original_messages,
                cfg=ContextTrimConfig(
                    enabled=True,
                    max_total_chars=max(
                        50_000, self._context_trim_config.max_total_chars - 80_000
                    ),
                    max_message_chars=max(
                        3_000, self._context_trim_config.max_message_chars - 6_000
                    ),
                    keep_last_messages=max(
                        6, self._context_trim_config.keep_last_messages - 12
                    ),
                    keep_head_chars=max(
                        1_000, self._context_trim_config.keep_head_chars - 4_000
                    ),
                    keep_tail_chars=self._context_trim_config.keep_tail_chars,
                    keep_system_messages=True,
                    retry_on_context_error=True,
                ),
            )
            if not trimmed:
                logger.warning(
                    "[AOAI_CTX_TRIM] aggressive trim would remove all messages; re-raising original error"
                )
                raise
            logger.warning(
                "[AOAI_CTX_TRIM] retrying chat after context-length error; count=%s -> %s",
                len(original_messages),
                len(trimmed),
            )
            # Re-sanitize names on the freshly-trimmed messages before retry.
            trimmed = _sanitize_author_names(trimmed)
            trim_delay = min(
                self._retry_config.base_delay_seconds,
                self._retry_config.max_delay_seconds,
            )
            logger.info(
                "[AOAI_CTX_TRIM] sleeping %ss before retry", round(trim_delay, 1)
            )
            await asyncio.sleep(trim_delay)
            return await _retry_call(
                lambda: parent_inner(
                    messages=trimmed, options=options, stream=False, **kwargs
                ),
                config=self._retry_config,
            )
