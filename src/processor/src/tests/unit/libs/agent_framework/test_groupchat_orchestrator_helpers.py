# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Comprehensive tests for GroupChatOrchestrator helpers and flows."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from libs.agent_framework import groupchat_orchestrator as gco
from libs.agent_framework.groupchat_orchestrator import (
    AgentResponse,
    GroupChatOrchestrator,
    OrchestrationResult,
)


def _make_orch(**overrides) -> GroupChatOrchestrator:
    kwargs = {
        "name": "t",
        "process_id": "p1",
        "participants": {"Coordinator": object()},
        "memory_client": None,
        "coordinator_name": "Coordinator",
        "result_output_format": None,
    }
    kwargs.update(overrides)
    return GroupChatOrchestrator(**kwargs)


# ── OrchestrationResult ────────────────────────────────────────────────────

def test_to_jsonable_handles_primitives_and_none() -> None:
    assert OrchestrationResult._to_jsonable(None) is None
    assert OrchestrationResult._to_jsonable(1) == 1
    assert OrchestrationResult._to_jsonable("s") == "s"
    assert OrchestrationResult._to_jsonable(True) is True


def test_to_jsonable_handles_datetime_dict_list() -> None:
    dt = datetime(2024, 1, 2, 3, 4, 5)
    assert OrchestrationResult._to_jsonable(dt) == dt.isoformat()
    assert OrchestrationResult._to_jsonable({1: dt}) == {"1": dt.isoformat()}
    assert OrchestrationResult._to_jsonable([dt, 1]) == [dt.isoformat(), 1]
    assert OrchestrationResult._to_jsonable({1, 2}) == [1, 2] or set(
        OrchestrationResult._to_jsonable({1, 2})
    ) == {1, 2}


def test_to_jsonable_uses_model_dump_when_available() -> None:
    class M:
        def model_dump(self):
            return {"x": 1}

    assert OrchestrationResult._to_jsonable(M()) == {"x": 1}


def test_to_jsonable_uses_dict_method_for_pydantic_v1_objects() -> None:
    class P:
        def dict(self):
            return {"y": 2}

    assert OrchestrationResult._to_jsonable(P()) == {"y": 2}


def test_to_jsonable_uses_dataclass_asdict() -> None:
    @dataclass
    class D:
        a: int = 1

    assert OrchestrationResult._to_jsonable(D()) == {"a": 1}


def test_to_jsonable_falls_back_to_vars_or_str() -> None:
    class O:
        def __init__(self):
            self.k = "v"

    assert OrchestrationResult._to_jsonable(O()) == {"k": "v"}


def test_to_jsonable_falls_back_to_str_when_vars_fails() -> None:
    # tuple has no __dict__, but goes through list path.
    assert OrchestrationResult._to_jsonable((1, 2)) == [1, 2]


def test_orchestration_result_model_dump_and_to_json() -> None:
    r = OrchestrationResult(
        success=True,
        conversation=[],
        agent_responses=[
            AgentResponse(
                agent_id="a",
                agent_name="a",
                message="m",
                timestamp=datetime(2024, 1, 1),
            )
        ],
        tool_usage={"a": []},
    )
    dumped = r.model_dump()
    assert dumped["success"] is True
    assert dumped["agent_responses"][0]["agent_name"] == "a"
    parsed = json.loads(r.to_json())
    assert parsed["success"] is True


def test_agent_response_model_dump_string_timestamp() -> None:
    r = AgentResponse(agent_id="a", agent_name="a", message="m", timestamp="not-a-dt")
    assert r.model_dump()["timestamp"] == "not-a-dt"


# ── Forced termination + result builder ────────────────────────────────────

def test_request_forced_termination_sets_flags() -> None:
    o = _make_orch()
    o._request_forced_termination(reason="r", termination_type="hard_timeout")
    assert o._forced_termination_requested is True
    assert o._forced_termination_reason == "r"
    assert o._forced_termination_type == "hard_timeout"


def test_request_forced_termination_no_op_when_already_terminated() -> None:
    o = _make_orch()
    o._termination_requested = True
    o._request_forced_termination(reason="r", termination_type="hard_timeout")
    assert o._forced_termination_requested is False


def test_try_build_forced_result_returns_none_without_format() -> None:
    o = _make_orch()
    assert o._try_build_forced_result(reason="r", termination_type="t") is None


def test_try_build_forced_result_populates_known_fields() -> None:
    class Out(BaseModel):
        result: bool = False
        reason: str | None = None
        is_hard_terminated: bool = False
        termination_type: str | None = None
        blocking_issues: list[str] = []
        process_id: str | None = None
        output: Any = None
        termination_output: Any = None

    o = _make_orch(result_output_format=Out)
    out = o._try_build_forced_result(reason="timeout", termination_type="hard_timeout")
    assert isinstance(out, Out)
    assert out.is_hard_terminated is True
    assert out.termination_type == "hard_timeout"
    assert out.blocking_issues == ["timeout"]
    assert out.process_id == "p1"


# ── Pure helpers ───────────────────────────────────────────────────────────

def test_get_result_generator_name_default() -> None:
    assert _make_orch().get_result_generator_name() == "ResultGenerator"


def test_validate_sign_offs_all_pass() -> None:
    o = _make_orch()
    msgs = [
        SimpleNamespace(source="A", content="SIGN-OFF: PASS"),
        SimpleNamespace(source="B", content="SIGN-OFF: PASS"),
    ]
    valid, reason = o._validate_sign_offs(msgs)
    assert valid is True
    assert reason == ""


def test_validate_sign_offs_includes_missing_pending_fail() -> None:
    o = _make_orch()
    msgs = [
        SimpleNamespace(source="A", content="SIGN-OFF: FAIL"),
        SimpleNamespace(source="B", content="SIGN-OFF: PENDING"),
        SimpleNamespace(source="C", content="reviewed"),
    ]
    valid, reason = o._validate_sign_offs(msgs)
    assert valid is False
    assert "FAIL" in reason
    assert "PENDING" in reason
    assert "missing" in reason


def test_extract_first_json_payload_clean_object() -> None:
    out = GroupChatOrchestrator._extract_first_json_payload('{"a": 1}')
    assert json.loads(out) == {"a": 1}


def test_extract_first_json_payload_with_trailing_text() -> None:
    out = GroupChatOrchestrator._extract_first_json_payload('{"a": 1} SIGN-OFF: PASS')
    assert json.loads(out) == {"a": 1}


def test_extract_first_json_payload_with_leading_prose() -> None:
    out = GroupChatOrchestrator._extract_first_json_payload('Here is JSON: {"a": 2}')
    assert json.loads(out) == {"a": 2}


def test_extract_first_json_payload_empty_returns_empty() -> None:
    assert GroupChatOrchestrator._extract_first_json_payload("") == ""


def test_extract_first_json_payload_no_json_returns_input() -> None:
    assert GroupChatOrchestrator._extract_first_json_payload("plain text") == "plain text"


def test_extract_first_json_payload_invalid_json_returns_input() -> None:
    text = "prefix {not-json}"
    assert GroupChatOrchestrator._extract_first_json_payload(text) == text.strip()


def test_extract_first_json_payload_non_string_raises() -> None:
    with pytest.raises(TypeError):
        GroupChatOrchestrator._extract_first_json_payload(123)


def test_normalize_executor_id_strips_prefix() -> None:
    o = _make_orch()
    assert o._normalize_executor_id("groupchat_agent:Coordinator") == "Coordinator"
    assert o._normalize_executor_id("Plain") == "Plain"


def test_merge_streamed_args_returns_incoming_when_no_existing() -> None:
    o = _make_orch()
    assert o._merge_streamed_args(None, "abc") == "abc"


def test_merge_streamed_args_returns_full_when_incoming_extends() -> None:
    o = _make_orch()
    assert o._merge_streamed_args("ab", "abcd") == "abcd"
    assert o._merge_streamed_args("abcd", "ab") == "abcd"
    assert o._merge_streamed_args("ab", "cd") == "abcd"


def test_args_complete_branches() -> None:
    o = _make_orch()
    assert o._args_complete({"k": 1}, {"k": 1}) is True
    assert o._args_complete("{}", {"k": 1}) is True
    assert o._args_complete(None, None) is True
    assert o._args_complete("partial", None) is False


def test_record_tool_call_adds_then_updates() -> None:
    o = _make_orch()
    key = ("agent", "id1")
    info = {"tool_name": "t", "arguments": {}, "call_id": "id1", "timestamp": "2024-01-01T00:00:00"}
    o._record_tool_call("agent", key, info)
    assert o.agent_tool_usage["agent"] == [info]

    info2 = dict(info, arguments={"updated": True})
    o._record_tool_call("agent", key, info2)
    assert o.agent_tool_usage["agent"] == [info2]


def test_extract_function_calls_object_path() -> None:
    o = _make_orch()
    item = SimpleNamespace(name="t", call_id="c1", arguments={"x": 1})
    calls = o._extract_function_calls([item])
    assert calls == [{"name": "t", "call_id": "c1", "arguments": {"x": 1}}]


def test_extract_function_calls_dict_path_function_call() -> None:
    o = _make_orch()
    items = [{"type": "function_call", "name": "t", "call_id": "c1", "arguments": "{}"}]
    calls = o._extract_function_calls(items)
    assert calls[0]["call_id"] == "c1"


def test_extract_function_calls_skips_unknown_dict() -> None:
    o = _make_orch()
    assert o._extract_function_calls([{"type": "other"}]) == []


def test_extract_function_calls_none_returns_empty() -> None:
    assert _make_orch()._extract_function_calls(None) == []


# ── _backfill_tool_usage_from_conversation ─────────────────────────────────

def test_backfill_tool_usage_from_conversation_adds_calls() -> None:
    from agent_framework import Role

    o = _make_orch()
    item = SimpleNamespace(name="t", call_id="cid", arguments={"x": 1})
    msg = SimpleNamespace(role=Role.ASSISTANT, author_name="agent1", contents=[item])
    o._backfill_tool_usage_from_conversation([msg])
    assert "agent1" in o.agent_tool_usage
    assert o.agent_tool_usage["agent1"][0]["call_id"] == "cid"


def test_backfill_tool_usage_skips_non_assistant() -> None:
    from agent_framework import Role

    o = _make_orch()
    msg = SimpleNamespace(role=Role.USER, author_name="u", contents=[])
    o._backfill_tool_usage_from_conversation([msg])
    assert o.agent_tool_usage == {}


def test_backfill_tool_usage_swallows_exceptions() -> None:
    o = _make_orch()
    bad = SimpleNamespace()  # accessing role on bare ns is fine; trick: make role property raise
    # Force exception by using object() (no role attr -> getattr returns None -> skip; need exception path)
    class Boom:
        @property
        def role(self):
            raise RuntimeError("boom")

    o._backfill_tool_usage_from_conversation([Boom()])
    assert o.agent_tool_usage == {}


# ── _truncate_text static ───────────────────────────────────────────────────

def test_static_truncate_text_under_budget() -> None:
    assert (
        GroupChatOrchestrator._truncate_text(
            "abc", max_chars=10, keep_head_chars=4, keep_tail_chars=4
        )
        == "abc"
    )


def test_static_truncate_text_zero_budget_or_empty() -> None:
    assert (
        GroupChatOrchestrator._truncate_text(
            "abc", max_chars=0, keep_head_chars=0, keep_tail_chars=0
        )
        == ""
    )
    assert (
        GroupChatOrchestrator._truncate_text(
            "", max_chars=10, keep_head_chars=0, keep_tail_chars=0
        )
        == ""
    )


def test_static_truncate_text_includes_marker() -> None:
    text = "A" * 100 + "B" * 100
    out = GroupChatOrchestrator._truncate_text(
        text, max_chars=80, keep_head_chars=20, keep_tail_chars=20
    )
    assert "TRUNCATED" in out
    assert len(out) <= 80


def test_static_truncate_text_only_head_when_no_tail_room() -> None:
    text = "A" * 100
    out = GroupChatOrchestrator._truncate_text(
        text, max_chars=10, keep_head_chars=10, keep_tail_chars=0
    )
    assert out == "A" * 10


# ── get_tool_usage_summary ──────────────────────────────────────────────────

def test_get_tool_usage_summary_empty() -> None:
    o = _make_orch()
    s = o.get_tool_usage_summary()
    assert s == {"total_tool_calls": 0, "calls_by_agent": {}, "calls_by_tool": {}}


def test_get_tool_usage_summary_with_data() -> None:
    o = _make_orch()
    o.agent_tool_usage = {
        "a": [{"tool_name": "t1"}, {"tool_name": "t1"}],
        "b": [{"tool_name": "t2"}],
    }
    s = o.get_tool_usage_summary()
    assert s["total_tool_calls"] == 3
    assert s["calls_by_agent"] == {"a": 2, "b": 1}
    assert s["calls_by_tool"] == {"t1": 2, "t2": 1}


# ── _build_result_generator_conversation ────────────────────────────────────

def test_build_result_generator_conversation_excludes_authors_and_dedupes() -> None:
    o = _make_orch()

    msgs = [
        SimpleNamespace(author_name="Coordinator", text="ignore me", role="assistant"),
        SimpleNamespace(author_name="A", text="hello world" + "x" * 100, role="assistant"),
        # duplicate fingerprint of the previous message
        SimpleNamespace(author_name="A", text="hello world" + "x" * 100, role="assistant"),
        SimpleNamespace(author_name="B", text="bye world" + "x" * 100, role="assistant"),
    ]

    with patch("libs.agent_framework.groupchat_orchestrator.ChatMessage") as MockMsg:
        MockMsg.side_effect = lambda **kw: SimpleNamespace(**kw)
        out = o._build_result_generator_conversation(
            msgs,
            exclude_authors={"Coordinator"},
            max_messages=5,
            max_total_chars=1000,
            max_chars_per_message=50,
            keep_head_chars=10,
            keep_tail_chars=10,
        )

    authors = [m.author_name for m in out]
    assert "Coordinator" not in authors
    assert authors.count("A") == 1


def test_build_result_generator_conversation_respects_max_messages() -> None:
    o = _make_orch()
    msgs = [
        SimpleNamespace(author_name=f"A{i}", text=f"msg-{i}", role="assistant")
        for i in range(5)
    ]
    with patch("libs.agent_framework.groupchat_orchestrator.ChatMessage") as MockMsg:
        MockMsg.side_effect = lambda **kw: SimpleNamespace(**kw)
        out = o._build_result_generator_conversation(
            msgs,
            exclude_authors=None,
            max_messages=2,
            max_total_chars=10_000,
            max_chars_per_message=100,
            keep_head_chars=50,
            keep_tail_chars=50,
        )
    assert len(out) == 2


# ── _build_groupchat ────────────────────────────────────────────────────────

def test_build_groupchat_sets_manager_and_participants() -> None:
    other_agent = object()
    o = _make_orch(participants={"Coordinator": "coord", "A": other_agent})
    builder = MagicMock()
    builder.set_manager.return_value = builder
    builder.participants.return_value = builder
    builder.build.return_value = "workflow"

    with patch(
        "libs.agent_framework.groupchat_orchestrator.GroupChatBuilder",
        return_value=builder,
    ):
        wf = asyncio.run(o._build_groupchat())

    assert wf == "workflow"
    builder.set_manager.assert_called_once_with("coord")
    builder.participants.assert_called_once_with([other_agent])


def test_build_groupchat_excludes_result_generator_from_participants() -> None:
    o = _make_orch(
        participants={
            "Coordinator": "coord",
            "ResultGenerator": "rg",
            "A": "a",
        }
    )
    builder = MagicMock()
    builder.set_manager.return_value = builder
    builder.participants.return_value = builder
    builder.build.return_value = "wf"

    with patch(
        "libs.agent_framework.groupchat_orchestrator.GroupChatBuilder",
        return_value=builder,
    ):
        asyncio.run(o._build_groupchat())

    builder.participants.assert_called_once_with(["a"])


# ── initialize ──────────────────────────────────────────────────────────────

def test_initialize_runs_once() -> None:
    o = _make_orch()
    asyncio.run(o.initialize())
    assert o._initialized is True
    asyncio.run(o.initialize())  # second call is a no-op
    assert o._initialized is True


# ── _generate_final_result ─────────────────────────────────────────────────

def test_generate_final_result_validates_response_text() -> None:
    class Out(BaseModel):
        v: int = 0

    rg = MagicMock()
    rg.run = AsyncMock(
        return_value=SimpleNamespace(messages=[SimpleNamespace(text='{"v": 7}')])
    )
    o = _make_orch(participants={"Coordinator": object(), "ResultGenerator": rg})
    o.result_format = Out

    with patch.object(
        o, "_build_result_generator_conversation", return_value=[]
    ):
        result = asyncio.run(o._generate_final_result([], Out, "ResultGenerator"))

    assert isinstance(result, Out)
    assert result.v == 7


def test_generate_final_result_retries_on_validation_error() -> None:
    class Out(BaseModel):
        v: int

    rg = MagicMock()
    rg.run = AsyncMock(
        side_effect=[
            SimpleNamespace(messages=[SimpleNamespace(text="{not-json")]),
            SimpleNamespace(messages=[SimpleNamespace(text='{"v": 5}')]),
        ]
    )
    o = _make_orch(participants={"Coordinator": object(), "ResultGenerator": rg})
    o.result_format = Out

    with patch.object(
        o, "_build_result_generator_conversation", return_value=[]
    ):
        result = asyncio.run(o._generate_final_result([], Out, "ResultGenerator"))

    assert result.v == 5
    assert rg.run.call_count == 2


# ── _handle_agent_update / streaming sub-helpers ───────────────────────────

def test_handle_agent_update_buffers_text_and_emits_stream() -> None:
    o = _make_orch()
    text_obj = SimpleNamespace(text="hello ")
    event = SimpleNamespace(
        executor_id="groupchat_agent:Coordinator",
        data=SimpleNamespace(text=text_obj, contents=None),
    )

    stream_cb = AsyncMock()
    asyncio.run(o._handle_agent_update(event, stream_callback=stream_cb))
    assert o._last_executor_id == "Coordinator"
    assert o._current_agent_response == ["hello "]
    stream_cb.assert_called_once()


def test_handle_agent_update_records_tool_call() -> None:
    o = _make_orch()
    item = SimpleNamespace(name="my_tool", call_id="cid", arguments={"x": 1})
    event = SimpleNamespace(
        executor_id="groupchat_agent:A",
        data=SimpleNamespace(text=None, contents=[item]),
    )
    stream_cb = AsyncMock()
    asyncio.run(o._handle_agent_update(event, stream_callback=stream_cb))
    assert o.agent_tool_usage["A"][0]["tool_name"] == "my_tool"


def test_handle_agent_update_swallows_stream_callback_failure() -> None:
    o = _make_orch()
    text_obj = SimpleNamespace(text="x")
    event = SimpleNamespace(
        executor_id="groupchat_agent:Z",
        data=SimpleNamespace(text=text_obj, contents=None),
    )

    stream_cb = AsyncMock(side_effect=RuntimeError("nope"))
    # Should NOT raise
    asyncio.run(o._handle_agent_update(event, stream_callback=stream_cb))


def test_complete_agent_response_with_callback_swallows_callback_errors() -> None:
    o = _make_orch()
    o._current_agent_response = ["chunk"]
    o._current_agent_start_time = datetime.now()
    cb = AsyncMock(side_effect=RuntimeError("nope"))
    asyncio.run(o._complete_agent_response("agent1", cb))
    # callback called but exception swallowed
    cb.assert_called_once()
    assert len(o.agent_responses) == 1


def test_complete_agent_response_returns_early_when_no_response() -> None:
    o = _make_orch()
    asyncio.run(o._complete_agent_response("agent", None))
    assert o.agent_responses == []


# ── run_stream end-to-end (mocked workflow) ────────────────────────────────

def test_run_stream_returns_success_result_with_minimum_setup() -> None:
    from agent_framework import WorkflowOutputEvent

    o = _make_orch()

    async def fake_stream(_):
        yield WorkflowOutputEvent(data=[], source_executor_id="x")

    workflow = SimpleNamespace(run_stream=fake_stream)

    async def _build():
        return workflow

    with patch.object(o, "_build_groupchat", side_effect=_build):
        result = asyncio.run(o.run_stream("task"))

    assert isinstance(result, OrchestrationResult)
    assert result.success is True
    assert result.error is None


def test_run_stream_calls_on_workflow_complete_callback() -> None:
    from agent_framework import WorkflowOutputEvent

    o = _make_orch()
    cb = AsyncMock()

    async def fake_stream(_):
        yield WorkflowOutputEvent(data=[], source_executor_id="x")

    workflow = SimpleNamespace(run_stream=fake_stream)

    async def _build():
        return workflow

    with patch.object(o, "_build_groupchat", side_effect=_build):
        asyncio.run(o.run_stream("task", on_workflow_complete=cb))

    cb.assert_called_once()


def test_run_stream_returns_error_result_when_build_raises() -> None:
    o = _make_orch()

    async def boom():
        raise RuntimeError("explode")

    with patch.object(o, "_build_groupchat", side_effect=boom):
        result = asyncio.run(o.run_stream("task"))

    assert result.success is False
    assert result.error == "explode"
