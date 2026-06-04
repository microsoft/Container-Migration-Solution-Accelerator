# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Coverage for GroupChatOrchestrator helpers, dataclass model_dump/to_json,
loop detection, tool-call processing, conversation truncation and final-result
building. Avoids running the full async workflow (which requires the real
agent_framework GroupChat runtime)."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import libs.agent_framework.groupchat_orchestrator as groupchat_module

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"


class Message:
    def __init__(self, *, role, text=None, contents=None, author_name=None):
        self.role = role
        self.text = text
        self.contents = contents
        self.author_name = author_name


groupchat_module.Message = Message
from libs.agent_framework.groupchat_orchestrator import (  # noqa: E402
    AgentResponse,
    GroupChatOrchestrator,
    OrchestrationResult,
)


def _run(coro):
    return asyncio.run(coro)


@dataclass
class _Msg:
    """Lightweight stand-in for a Message."""

    source: str = ""
    content: str = ""
    text: str = ""
    role: object = None
    author_name: str | None = None
    contents: object = None


def _make_orch(participants=None, result_format=None):
    return GroupChatOrchestrator(
        name="t",
        process_id="p1",
        participants=participants or {"Coordinator": object()},
        memory_client=None,
        coordinator_name="Coordinator",
        result_output_format=result_format,
    )


# -----------------------------------------------------------------------------
# AgentResponse / OrchestrationResult dataclasses
# -----------------------------------------------------------------------------


class TestAgentResponseDump:
    def test_model_dump_with_datetime(self):
        ts = datetime(2024, 1, 1, 12, 0, 0)
        r = AgentResponse(agent_id="a", agent_name="A", message="m", timestamp=ts)
        d = r.model_dump()
        assert d["timestamp"] == ts.isoformat()
        assert d["agent_id"] == "a"

    def test_model_dump_with_string_timestamp(self):
        r = AgentResponse(
            agent_id="a", agent_name="A", message="m", timestamp="not a datetime"
        )
        d = r.model_dump()
        assert d["timestamp"] == "not a datetime"


class TestOrchestrationResultJsonable:
    def test_to_jsonable_primitives(self):
        assert OrchestrationResult._to_jsonable(None) is None
        assert OrchestrationResult._to_jsonable("hi") == "hi"
        assert OrchestrationResult._to_jsonable(1) == 1
        assert OrchestrationResult._to_jsonable(1.5) == 1.5
        assert OrchestrationResult._to_jsonable(True) is True

    def test_to_jsonable_datetime(self):
        ts = datetime(2024, 1, 1)
        assert OrchestrationResult._to_jsonable(ts) == ts.isoformat()

    def test_to_jsonable_dict_and_list(self):
        out = OrchestrationResult._to_jsonable({"a": [1, 2], "b": (3, 4)})
        assert out == {"a": [1, 2], "b": [3, 4]}

    def test_to_jsonable_pydantic_v2(self):
        m = MagicMock()
        m.model_dump = MagicMock(return_value={"x": 1})
        m.dict = MagicMock(return_value={"y": 2})
        out = OrchestrationResult._to_jsonable(m)
        assert out == {"x": 1}

    def test_to_jsonable_pydantic_v1_fallback(self):
        class Obj:
            def dict(self):
                return {"y": 2}

        out = OrchestrationResult._to_jsonable(Obj())
        assert out == {"y": 2}

    def test_to_jsonable_dataclass(self):
        @dataclass
        class D:
            x: int = 5

        out = OrchestrationResult._to_jsonable(D())
        assert out == {"x": 5}

    def test_to_jsonable_vars_fallback(self):
        class Anon:
            def __init__(self):
                self.k = "v"

        out = OrchestrationResult._to_jsonable(Anon())
        assert out == {"k": "v"}

    def test_to_jsonable_str_fallback(self):
        # Object with no __dict__ falls back to str()
        out = OrchestrationResult._to_jsonable(object.__new__(object))
        # Either a dict or str; must be a string for slot-only objects
        assert isinstance(out, (dict, str))

    def test_model_dump_and_to_json(self):
        r = OrchestrationResult(
            success=True,
            conversation=[],
            agent_responses=[
                AgentResponse(agent_id="a", agent_name="A", message="m", timestamp=datetime(2024, 1, 1))
            ],
            tool_usage={},
            result=None,
            error=None,
            execution_time_seconds=1.5,
        )
        d = r.model_dump()
        assert d["success"] is True
        assert d["execution_time_seconds"] == 1.5
        s = r.to_json(indent=0)
        assert isinstance(s, str)
        assert '"success"' in s


# -----------------------------------------------------------------------------
# Forced termination + try_build_forced_result
# -----------------------------------------------------------------------------


class TestForcedTermination:
    def test_request_forced_termination_sets_state(self):
        orch = _make_orch()
        orch._request_forced_termination(reason="r", termination_type="hard_timeout")
        assert orch._forced_termination_requested is True
        assert orch._forced_termination_reason == "r"

    def test_request_forced_termination_noop_when_already_set(self):
        orch = _make_orch()
        orch._termination_requested = True
        orch._request_forced_termination(reason="r", termination_type="t")
        assert orch._forced_termination_requested is False

    def test_try_build_forced_result_no_format_returns_none(self):
        orch = _make_orch(result_format=None)
        assert orch._try_build_forced_result(reason="r", termination_type="t") is None

    def test_try_build_forced_result_populates_known_fields(self):
        from pydantic import BaseModel

        class Model(BaseModel):
            result: bool = False
            reason: str = ""
            is_hard_terminated: bool = False
            termination_type: str = ""
            blocking_issues: list[str] = []
            process_id: str = ""

        orch = _make_orch(result_format=Model)
        m = orch._try_build_forced_result(reason="boom", termination_type="hard_timeout")
        assert m.is_hard_terminated is True
        assert m.reason == "boom"
        assert m.termination_type == "hard_timeout"
        assert m.blocking_issues == ["boom"]
        assert m.process_id == "p1"

    def test_try_build_forced_result_handles_optional_fields(self):
        from pydantic import BaseModel

        class Model(BaseModel):
            output: str | None = None
            termination_output: str | None = None
            reason: str = ""

        orch = _make_orch(result_format=Model)
        m = orch._try_build_forced_result(reason="r", termination_type="hard_blocked")
        assert m.output is None
        assert m.termination_output is None


# -----------------------------------------------------------------------------
# get_result_generator_name
# -----------------------------------------------------------------------------


class TestGetResultGeneratorName:
    def test_default(self):
        assert _make_orch().get_result_generator_name() == "ResultGenerator"


# -----------------------------------------------------------------------------
# _validate_sign_offs
# -----------------------------------------------------------------------------


class TestValidateSignOffs:
    def test_all_pass(self):
        orch = _make_orch()
        msgs = [
            _Msg(source="A", content="SIGN-OFF: PASS"),
            _Msg(source="B", content="SIGN-OFF:PASS"),
        ]
        ok, reason = orch._validate_sign_offs(msgs)
        assert ok is True

    def test_pending_blocks(self):
        orch = _make_orch()
        msgs = [_Msg(source="A", content="SIGN-OFF: PENDING")]
        ok, reason = orch._validate_sign_offs(msgs)
        assert ok is False
        assert "PENDING" in reason

    def test_fail_blocks(self):
        orch = _make_orch()
        msgs = [_Msg(source="A", content="SIGN-OFF: FAIL")]
        ok, reason = orch._validate_sign_offs(msgs)
        assert ok is False
        assert "FAIL" in reason

    def test_missing_blocks(self):
        orch = _make_orch()
        msgs = [_Msg(source="A", content="some text without signoff")]
        ok, reason = orch._validate_sign_offs(msgs)
        assert ok is False
        assert "missing" in reason

    def test_excludes_coordinator_and_resultgenerator(self):
        orch = _make_orch()
        msgs = [
            _Msg(source="Coordinator", content="ignored"),
            _Msg(source="ResultGenerator", content="ignored"),
        ]
        ok, _ = orch._validate_sign_offs(msgs)
        assert ok is True


# -----------------------------------------------------------------------------
# _extract_first_json_payload
# -----------------------------------------------------------------------------


class TestExtractFirstJsonPayload:
    def test_pure_json_object(self):
        out = GroupChatOrchestrator._extract_first_json_payload('{"a":1}')
        assert out == '{"a":1}'

    def test_json_with_trailing_text(self):
        out = GroupChatOrchestrator._extract_first_json_payload('{"a":1} SIGN-OFF: PASS')
        assert out == '{"a":1}'

    def test_json_with_leading_text(self):
        out = GroupChatOrchestrator._extract_first_json_payload('prefix {"a":1}')
        assert '{"a":1}' in out

    def test_empty_returns_empty(self):
        assert GroupChatOrchestrator._extract_first_json_payload("") == ""
        assert GroupChatOrchestrator._extract_first_json_payload("   ") == ""

    def test_no_json_returns_input(self):
        out = GroupChatOrchestrator._extract_first_json_payload("plain text")
        assert out == "plain text"

    def test_unparsable_after_position_returns_input(self):
        out = GroupChatOrchestrator._extract_first_json_payload("text {not json")
        assert "text {not json" in out

    def test_non_string_raises(self):
        with pytest.raises(TypeError):
            GroupChatOrchestrator._extract_first_json_payload(123)  # type: ignore[arg-type]


# -----------------------------------------------------------------------------
# initialize
# -----------------------------------------------------------------------------


class TestInitialize:
    def test_initialize_sets_initialized(self):
        orch = _make_orch()
        _run(orch.initialize())
        assert orch._initialized is True

    def test_initialize_skipped_if_already_done(self):
        orch = _make_orch()
        orch._initialized = True
        _run(orch.initialize())  # no error


# -----------------------------------------------------------------------------
# _normalize_executor_id
# -----------------------------------------------------------------------------


class TestNormalizeExecutorId:
    def test_strips_prefix(self):
        orch = _make_orch()
        assert orch._normalize_executor_id("groupchat_agent:Coordinator") == "Coordinator"

    def test_no_prefix(self):
        orch = _make_orch()
        assert orch._normalize_executor_id("Bare") == "Bare"


# -----------------------------------------------------------------------------
# _append_text_chunk
# -----------------------------------------------------------------------------


class TestAppendTextChunk:
    def test_no_text_attr(self):
        orch = _make_orch()
        ev = SimpleNamespace(data=SimpleNamespace())  # no `text` attr
        orch._current_agent_response = []
        orch._append_text_chunk(ev)  # noop
        assert orch._current_agent_response == []

    def test_falsy_text(self):
        orch = _make_orch()
        ev = SimpleNamespace(data=SimpleNamespace(text=""))
        orch._current_agent_response = []
        orch._append_text_chunk(ev)
        assert orch._current_agent_response == []

    def test_text_object_with_text_attr(self):
        orch = _make_orch()
        text_obj = SimpleNamespace(text="hello")
        ev = SimpleNamespace(data=SimpleNamespace(text=text_obj))
        orch._current_agent_response = []
        orch._append_text_chunk(ev)
        assert orch._current_agent_response == ["hello"]

    def test_text_string(self):
        orch = _make_orch()
        ev = SimpleNamespace(data=SimpleNamespace(text="raw"))
        orch._current_agent_response = []
        orch._append_text_chunk(ev)
        assert orch._current_agent_response == ["raw"]


# -----------------------------------------------------------------------------
# _start_agent_if_needed
# -----------------------------------------------------------------------------


class TestStartAgentIfNeeded:
    def test_same_executor_noop(self):
        orch = _make_orch()
        orch._last_executor_id = "A"
        orch._current_agent_response = ["x"]
        _run(orch._start_agent_if_needed("A", None, None))
        # no change
        assert orch._current_agent_response == ["x"]

    def test_switch_completes_previous(self):
        orch = _make_orch()
        orch._last_executor_id = "A"
        orch._current_agent_response = ["msg"]
        completed = []

        async def _cb(resp):
            completed.append(resp)

        _run(orch._start_agent_if_needed("B", None, _cb))
        assert orch._last_executor_id == "B"
        assert orch._current_agent_response == []
        assert len(completed) == 1

    def test_stream_callback_invoked_on_switch(self):
        orch = _make_orch()
        orch._last_executor_id = None
        captured = []

        async def _stream_cb(s):
            captured.append(s)

        _run(orch._start_agent_if_needed("X", _stream_cb, None))
        assert len(captured) == 1
        assert captured[0].response_type == "message"

    def test_stream_callback_failure_is_swallowed(self):
        orch = _make_orch()
        orch._last_executor_id = None

        async def _bad_stream(_):
            raise RuntimeError("boom")

        _run(orch._start_agent_if_needed("X", _bad_stream, None))


# -----------------------------------------------------------------------------
# _process_tool_calls + helpers
# -----------------------------------------------------------------------------


class TestProcessToolCalls:
    def test_no_tool_calls_returns_immediately(self):
        orch = _make_orch()
        ev = SimpleNamespace(data=SimpleNamespace(contents=None))
        _run(orch._process_tool_calls(ev, "A", None))

    def test_records_complete_dict_args(self):
        orch = _make_orch()
        item = SimpleNamespace(name="search", call_id="c1", arguments={"q": "x"})
        ev = SimpleNamespace(data=SimpleNamespace(contents=[item]))
        _run(orch._process_tool_calls(ev, "A", None))
        assert "search" in {tc["tool_name"] for tc in orch.agent_tool_usage["A"]}

    def test_skips_when_already_recorded(self):
        orch = _make_orch()
        item = SimpleNamespace(name="search", call_id="c1", arguments={"q": "x"})
        ev = SimpleNamespace(data=SimpleNamespace(contents=[item]))
        _run(orch._process_tool_calls(ev, "A", None))
        # second pass should be skipped
        _run(orch._process_tool_calls(ev, "A", None))
        assert len(orch.agent_tool_usage["A"]) == 1

    def test_skips_invalid_calls(self):
        orch = _make_orch()
        item = SimpleNamespace(name=None, call_id=None, arguments=None)
        ev = SimpleNamespace(data=SimpleNamespace(contents=[item]))
        _run(orch._process_tool_calls(ev, "A", None))
        assert orch.agent_tool_usage == {}

    def test_streamed_string_args_buffer_until_complete(self):
        orch = _make_orch()

        # Send incomplete JSON args, then complete
        item1 = SimpleNamespace(name="t", call_id="c", arguments='{"q":"hel')
        ev1 = SimpleNamespace(data=SimpleNamespace(contents=[item1]))
        _run(orch._process_tool_calls(ev1, "A", None))
        # not yet recorded
        assert "A" not in orch.agent_tool_usage or not orch.agent_tool_usage["A"]

        item2 = SimpleNamespace(name="t", call_id="c", arguments='{"q":"hello"}')
        ev2 = SimpleNamespace(data=SimpleNamespace(contents=[item2]))
        _run(orch._process_tool_calls(ev2, "A", None))
        assert orch.agent_tool_usage["A"][0]["arguments"] == {"q": "hello"}


class TestParseOrBufferToolArgs:
    def test_dict_passthrough(self):
        orch = _make_orch()
        parsed, raw = orch._parse_or_buffer_tool_args(("A", "c"), {"k": 1})
        assert parsed == {"k": 1}
        assert raw == {"k": 1}

    def test_string_buffered(self):
        orch = _make_orch()
        parsed, raw = orch._parse_or_buffer_tool_args(("A", "c"), '{"k":1}')
        assert parsed == {"k": 1}

    def test_string_invalid_returns_none(self):
        orch = _make_orch()
        parsed, raw = orch._parse_or_buffer_tool_args(("A", "c"), '{"k":')
        assert parsed is None

    def test_other_returns_none(self):
        orch = _make_orch()
        parsed, raw = orch._parse_or_buffer_tool_args(("A", "c"), 123)
        assert parsed is None and raw == 123


class TestMergeStreamedArgs:
    def test_existing_none(self):
        orch = _make_orch()
        assert orch._merge_streamed_args(None, "abc") == "abc"

    def test_incoming_starts_with_existing(self):
        orch = _make_orch()
        assert orch._merge_streamed_args("ab", "abcde") == "abcde"

    def test_existing_starts_with_incoming(self):
        orch = _make_orch()
        assert orch._merge_streamed_args("abcde", "ab") == "abcde"

    def test_concatenates(self):
        orch = _make_orch()
        assert orch._merge_streamed_args("abc", "xyz") == "abcxyz"


class TestArgsComplete:
    def test_dict_args(self):
        assert _make_orch()._args_complete({}, None) is True

    def test_string_with_parsed(self):
        assert _make_orch()._args_complete("x", {"k": 1}) is True

    def test_string_no_parsed(self):
        assert _make_orch()._args_complete("x", None) is False

    def test_none(self):
        assert _make_orch()._args_complete(None, None) is True


class TestRecordToolCall:
    def test_appends_when_new(self):
        orch = _make_orch()
        info = {"tool_name": "t", "call_id": "c", "arguments": {}, "timestamp": "x"}
        orch._record_tool_call("A", ("A", "c"), info)
        assert orch.agent_tool_usage["A"] == [info]
        assert ("A", "c") in orch._tool_call_recorded

    def test_updates_existing_index(self):
        orch = _make_orch()
        info1 = {"tool_name": "t", "call_id": "c", "arguments": {}, "timestamp": "1"}
        info2 = {"tool_name": "t", "call_id": "c", "arguments": {"x": 1}, "timestamp": "2"}
        orch._record_tool_call("A", ("A", "c"), info1)
        orch._record_tool_call("A", ("A", "c"), info2)
        assert orch.agent_tool_usage["A"][0]["timestamp"] == "2"


class TestEmitToolCallOnce:
    def test_no_callback_noop(self):
        orch = _make_orch()
        _run(
            orch._emit_tool_call_once(
                agent_name="A", call_key=("A", "c"), tool_name="t",
                parsed_args={"x": 1}, stream_callback=None,
            )
        )
        assert ("A", "c") not in orch._tool_call_emitted

    def test_only_emits_once(self):
        orch = _make_orch()
        captured = []

        async def _cb(s):
            captured.append(s)

        _run(orch._emit_tool_call_once("A", ("A", "c"), "t", {"x": 1}, _cb))
        _run(orch._emit_tool_call_once("A", ("A", "c"), "t", {"x": 1}, _cb))
        assert len(captured) == 1

    def test_swallows_callback_exception(self):
        orch = _make_orch()

        async def _bad(_):
            raise RuntimeError("nope")

        _run(orch._emit_tool_call_once("A", ("A", "c"), "t", {"x": 1}, _bad))


# -----------------------------------------------------------------------------
# _extract_function_calls
# -----------------------------------------------------------------------------


class TestExtractFunctionCalls:
    def test_empty_returns_empty(self):
        orch = _make_orch()
        assert orch._extract_function_calls(None) == []
        assert orch._extract_function_calls([]) == []

    def test_object_path(self):
        orch = _make_orch()
        items = [SimpleNamespace(name="t", call_id="c", arguments={"x": 1})]
        out = orch._extract_function_calls(items)
        assert out == [{"name": "t", "call_id": "c", "arguments": {"x": 1}}]

    def test_dict_path(self):
        orch = _make_orch()
        items = [{"type": "function_call", "name": "t", "call_id": "c", "arguments": {}}]
        out = orch._extract_function_calls(items)
        assert out == [{"name": "t", "call_id": "c", "arguments": {}}]

    def test_skips_unrelated(self):
        orch = _make_orch()
        items = [{"type": "text", "name": "t", "call_id": "c"}]
        # name+call_id present on dict but matched as object first; falls through to dict path with non-tool-call type → skipped
        out = orch._extract_function_calls(items)
        # dict path only matches when type ∈ {function_call, tool_call}; here type='text' so skipped
        assert out == []


# -----------------------------------------------------------------------------
# _backfill_tool_usage_from_conversation
# -----------------------------------------------------------------------------


class TestBackfillToolUsage:
    def test_skips_non_assistant(self):
        orch = _make_orch()
        msg = SimpleNamespace(role=ROLE_USER, contents=[])
        orch._backfill_tool_usage_from_conversation([msg])
        assert orch.agent_tool_usage == {}

    def test_records_calls_from_assistant(self):
        orch = _make_orch()
        item = SimpleNamespace(name="t", call_id="c", arguments={"x": 1})
        msg = SimpleNamespace(
            role=ROLE_ASSISTANT, author_name="A", contents=[item]
        )
        orch._backfill_tool_usage_from_conversation([msg])
        assert orch.agent_tool_usage["A"][0]["tool_name"] == "t"

    def test_dedup_already_recorded(self):
        orch = _make_orch()
        # Pre-mark this call as already recorded
        orch._tool_call_recorded.add(("A", "c"))
        item = SimpleNamespace(name="t", call_id="c", arguments={})
        msg = SimpleNamespace(
            role=ROLE_ASSISTANT, author_name="A", contents=[item]
        )
        orch._backfill_tool_usage_from_conversation([msg])
        assert "A" in orch.agent_tool_usage
        assert orch.agent_tool_usage["A"] == []

    def test_swallows_exceptions(self):
        orch = _make_orch()
        # Invalid msg causes attribute access to raise — swallowed by `except Exception`
        broken = MagicMock()
        broken.role = MagicMock(side_effect=RuntimeError("x"))
        orch._backfill_tool_usage_from_conversation([broken])  # no raise


# -----------------------------------------------------------------------------
# _complete_agent_response (additional paths)
# -----------------------------------------------------------------------------


class TestCompleteAgentResponse:
    def test_no_pending_response_returns_early(self):
        orch = _make_orch()
        orch._current_agent_response = []
        _run(orch._complete_agent_response("A", None))

    def test_callback_swallows_exception(self):
        orch = _make_orch()
        orch._current_agent_response = ["msg"]
        orch._current_agent_start_time = datetime.now()

        async def _bad(_):
            raise RuntimeError("cb err")

        _run(orch._complete_agent_response("A", _bad))
        # response was still recorded
        assert orch.agent_responses[-1].agent_name == "A"

    def test_records_invocation_for_non_termination_selection(self):
        orch = _make_orch()
        orch._current_agent_response = [
            json.dumps(
                {
                    "selected_participant": "Architect",
                    "instruction": "do",
                    "finish": False,
                    "final_message": "",
                }
            )
        ]
        orch._current_agent_start_time = datetime.now()
        orch._conversation = []
        _run(orch._complete_agent_response("Coordinator", None))
        assert "Architect" in orch._agent_invoked_at

    def test_loop_breaker_triggered_after_3_repeats_without_progress(self):
        orch = _make_orch()
        orch._conversation = []

        def _select(participant: str, instruction: str = "do"):
            orch._current_agent_response = [
                json.dumps(
                    {
                        "selected_participant": participant,
                        "instruction": instruction,
                        "finish": False,
                        "final_message": "",
                    }
                )
            ]
            orch._current_agent_start_time = datetime.now()

        _select("A")
        _run(orch._complete_agent_response("Coordinator", None))
        _select("A")
        _run(orch._complete_agent_response("Coordinator", None))
        _select("A")
        _run(orch._complete_agent_response("Coordinator", None))

        assert orch._forced_termination_requested is True


# -----------------------------------------------------------------------------
# _build_groupchat
# -----------------------------------------------------------------------------


class TestBuildGroupchat:
    def test_build_groupchat_invokes_builder(self):
        orch = _make_orch(participants={
            "Coordinator": "coord",
            "Architect": "arch",
            "ResultGenerator": "rg",
        })
        with patch("libs.agent_framework.groupchat_orchestrator.GroupChatBuilder") as MockBuilder:
            built = MagicMock()
            built.set_manager.return_value = built
            built.participants.return_value = built
            built.build.return_value = "wf"
            MockBuilder.return_value = built
            wf = _run(orch._build_groupchat())
        assert wf == "wf"
        # ResultGenerator excluded from participants
        kwargs = built.participants.call_args.args[0]
        assert "arch" in kwargs
        assert "rg" not in kwargs


# -----------------------------------------------------------------------------
# _truncate_text + _build_result_generator_conversation
# -----------------------------------------------------------------------------


class TestTruncateText:
    def test_zero_max_returns_empty(self):
        out = GroupChatOrchestrator._truncate_text(
            "x" * 100, max_chars=0, keep_head_chars=10, keep_tail_chars=10
        )
        assert out == ""

    def test_empty(self):
        assert GroupChatOrchestrator._truncate_text("", max_chars=10, keep_head_chars=5, keep_tail_chars=5) == ""

    def test_short_passthrough(self):
        out = GroupChatOrchestrator._truncate_text(
            "hi", max_chars=10, keep_head_chars=5, keep_tail_chars=5
        )
        assert out == "hi"

    def test_long_truncated_with_marker(self):
        text = "A" * 200 + "B" * 200
        out = GroupChatOrchestrator._truncate_text(
            text, max_chars=100, keep_head_chars=20, keep_tail_chars=20
        )
        assert "TRUNCATED" in out

    def test_remaining_zero_returns_head(self):
        text = "X" * 100
        out = GroupChatOrchestrator._truncate_text(
            text, max_chars=20, keep_head_chars=20, keep_tail_chars=10
        )
        assert len(out) <= 20

    def test_tail_zero_returns_head(self):
        text = "Y" * 100
        out = GroupChatOrchestrator._truncate_text(
            text, max_chars=15, keep_head_chars=15, keep_tail_chars=0
        )
        assert out == "Y" * 15


class TestBuildResultGeneratorConversation:
    def test_excludes_named_authors(self):

        orch = _make_orch()
        msgs = [
            Message(role=ROLE_ASSISTANT, text="from coord", author_name="Coordinator"),
            Message(role=ROLE_ASSISTANT, text="from architect", author_name="Architect"),
        ]
        out = orch._build_result_generator_conversation(
            msgs,
            exclude_authors={"Coordinator"},
            max_messages=10,
            max_total_chars=10_000,
            max_chars_per_message=10_000,
            keep_head_chars=100,
            keep_tail_chars=50,
        )
        assert any("Architect" == m.author_name for m in out)
        assert all("Coordinator" != m.author_name for m in out)

    def test_dedupes_identical_payloads(self):

        orch = _make_orch()
        big = "X" * 1000
        msgs = [
            Message(role=ROLE_ASSISTANT, text=big, author_name="A"),
            Message(role=ROLE_ASSISTANT, text=big, author_name="A"),
        ]
        out = orch._build_result_generator_conversation(
            msgs,
            exclude_authors=None,
            max_messages=10,
            max_total_chars=100_000,
            max_chars_per_message=10_000,
            keep_head_chars=100,
            keep_tail_chars=50,
        )
        assert len(out) == 1

    def test_truncates_messages_to_per_message_budget(self):

        orch = _make_orch()
        msgs = [
            Message(role=ROLE_ASSISTANT, text="A" * 500, author_name="X"),
        ]
        out = orch._build_result_generator_conversation(
            msgs,
            exclude_authors=None,
            max_messages=10,
            max_total_chars=10_000,
            max_chars_per_message=100,
            keep_head_chars=20,
            keep_tail_chars=20,
        )
        assert len(out[-1].text) <= 100

    def test_total_budget_enforced(self):

        orch = _make_orch()
        msgs = [
            Message(role=ROLE_ASSISTANT, text="A" * 100, author_name=str(i))
            for i in range(20)
        ]
        out = orch._build_result_generator_conversation(
            msgs,
            exclude_authors=None,
            max_messages=20,
            max_total_chars=200,
            max_chars_per_message=0,  # disabled per-message budget
            keep_head_chars=50,
            keep_tail_chars=10,
        )
        total = sum(len(m.text) for m in out)
        assert total <= 200

    def test_max_messages_caps_count(self):

        orch = _make_orch()
        msgs = [
            Message(role=ROLE_ASSISTANT, text=f"m{i}", author_name=str(i))
            for i in range(20)
        ]
        out = orch._build_result_generator_conversation(
            msgs,
            exclude_authors=None,
            max_messages=3,
            max_total_chars=10_000,
            max_chars_per_message=0,
            keep_head_chars=10,
            keep_tail_chars=10,
        )
        assert len(out) == 3


# -----------------------------------------------------------------------------
# get_tool_usage_summary
# -----------------------------------------------------------------------------


class TestToolUsageSummary:
    def test_empty(self):
        orch = _make_orch()
        out = orch.get_tool_usage_summary()
        assert out["total_tool_calls"] == 0

    def test_aggregates(self):
        orch = _make_orch()
        orch.agent_tool_usage = {
            "A": [{"tool_name": "search"}, {"tool_name": "search"}],
            "B": [{"tool_name": "open"}],
        }
        out = orch.get_tool_usage_summary()
        assert out["total_tool_calls"] == 3
        assert out["calls_by_agent"] == {"A": 2, "B": 1}
        assert out["calls_by_tool"] == {"search": 2, "open": 1}

    def test_unknown_tool_name(self):
        orch = _make_orch()
        orch.agent_tool_usage = {"A": [{}]}
        out = orch.get_tool_usage_summary()
        assert out["calls_by_tool"] == {"unknown": 1}


# -----------------------------------------------------------------------------
# _generate_final_result
# -----------------------------------------------------------------------------


class TestGenerateFinalResult:
    def test_parses_valid_json(self):
        from pydantic import BaseModel

        class Model(BaseModel):
            x: int

        rg = MagicMock()
        run_result = SimpleNamespace(messages=[SimpleNamespace(text='{"x":5}')])
        rg.run = AsyncMock(return_value=run_result)
        orch = _make_orch(participants={"Coordinator": object(), "ResultGenerator": rg}, result_format=Model)
        out = _run(
            orch._generate_final_result(
                conversation=[Message(role=ROLE_ASSISTANT, text="x", author_name="A")],
                result_format=Model,
                result_generator_name="ResultGenerator",
            )
        )
        assert out.x == 5

    def test_retry_on_validation_error(self):
        from pydantic import BaseModel

        class Model(BaseModel):
            x: int

        rg = MagicMock()
        # First run returns invalid JSON; second returns valid.
        first = SimpleNamespace(messages=[SimpleNamespace(text='{"x":"not_int"}')])
        second = SimpleNamespace(messages=[SimpleNamespace(text='{"x":7}')])
        rg.run = AsyncMock(side_effect=[first, second])
        orch = _make_orch(participants={"Coordinator": object(), "ResultGenerator": rg}, result_format=Model)
        out = _run(
            orch._generate_final_result(
                conversation=[Message(role=ROLE_ASSISTANT, text="x", author_name="A")],
                result_format=Model,
                result_generator_name="ResultGenerator",
            )
        )
        assert out.x == 7
        assert rg.run.await_count == 2


# -----------------------------------------------------------------------------
# _handle_agent_update high-level pipeline
# -----------------------------------------------------------------------------


class TestHandleAgentUpdate:
    def test_invokes_subroutines(self):
        orch = _make_orch()
        ev = SimpleNamespace(
            executor_id="groupchat_agent:A",
            data=SimpleNamespace(text="chunk", contents=None),
        )
        _run(orch._handle_agent_update(ev, None, None))
        assert orch._last_executor_id == "A"
        assert orch._current_agent_response == ["chunk"]
