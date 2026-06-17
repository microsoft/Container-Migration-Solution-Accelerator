# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime

from libs.agent_framework.groupchat_orchestrator import GroupChatOrchestrator


@dataclass
class _Msg:
    author_name: str = ""
    text: str = ""
    contents: object = None
    role: object = None


def _make_orchestrator() -> GroupChatOrchestrator:
    return GroupChatOrchestrator(
        name="t",
        process_id="p1",
        participants={"Coordinator": object()},
        memory_client=None,  # not used by _complete_agent_response
        coordinator_name="Coordinator",
        result_output_format=None,
    )


def test_coordinator_complete_terminates_when_selected_participant_none_even_without_finish_true():
    async def _run():
        orch = _make_orchestrator()

        # Everyone who participated signed off PASS.
        orch._conversation = [
            _Msg(author_name="AKS Expert", text="SIGN-OFF: PASS"),
            _Msg(author_name="Chief Architect", text="SIGN-OFF: PASS"),
        ]

        orch._current_agent_start_time = datetime.now()
        orch._current_agent_response = [
            json.dumps(
                {
                    "selected_participant": None,
                    "instruction": "complete",
                    "finish": False,
                    "final_message": "done",
                }
            )
        ]

        await orch._complete_agent_response("Coordinator", callback=None)

        assert orch._termination_requested is True
        assert orch._termination_instruction == "complete"
        assert orch._termination_final_message == "done"

    asyncio.run(_run())


def test_coordinator_complete_rejected_when_signoffs_missing():
    async def _run():
        orch = _make_orchestrator()

        # Agent participated but never produced a SIGN-OFF.
        orch._conversation = [
            _Msg(author_name="AKS Expert", text="Reviewed; looks good."),
        ]

        orch._current_agent_start_time = datetime.now()
        orch._current_agent_response = [
            json.dumps(
                {
                    "selected_participant": None,
                    "instruction": "complete",
                    "finish": False,
                    "final_message": "done",
                }
            )
        ]

        await orch._complete_agent_response("Coordinator", callback=None)

        assert orch._termination_requested is False

    asyncio.run(_run())


def test_loop_detection_resets_when_other_agent_makes_progress_between_repeated_selections():
    async def _run():
        orch = _make_orchestrator()
        orch._conversation = []

        def _coordinator_select(participant: str, instruction: str = "do"):
            orch._current_agent_start_time = datetime.now()
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

        def _agent_reply(text: str = "ok"):
            orch._current_agent_start_time = datetime.now()
            orch._current_agent_response = [text]

        # 1) Coordinator selects the same participant.
        _coordinator_select("Chief Architect")
        await orch._complete_agent_response("Coordinator", callback=None)

        # 2) A DIFFERENT participant responds (real progress, not the looped-on one).
        _agent_reply("progress")
        await orch._complete_agent_response("AKS Expert", callback=None)

        # 3) Coordinator repeats the same selection twice.
        _coordinator_select("Chief Architect")
        await orch._complete_agent_response("Coordinator", callback=None)
        _coordinator_select("Chief Architect")
        await orch._complete_agent_response("Coordinator", callback=None)

        # With the progress-reset behavior, this should NOT have tripped the 3x loop breaker.
        assert orch._forced_termination_requested is False

    asyncio.run(_run())


@dataclass
class _AgentResponseUpdateStub:
    """Mimics the agent-framework 1.3.0 AgentResponseUpdate shape.

    Only the fields actually read by ``_handle_agent_update`` /
    ``_normalize_executor_id`` matter. In 1.3.0 ``agent_id`` is no longer
    populated by ``map_chat_to_agent_update`` - only ``author_name`` is set.
    This stub reproduces that shape.
    """

    author_name: str | None = None
    agent_id: str | None = None
    contents: list = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.contents is None:
            self.contents = []


def test_handle_agent_update_resolves_coordinator_via_author_name_when_agent_id_is_none():
    """Regression guard for agent-framework 1.3.0.

    In 1.3.0 ``AgentResponseUpdate.agent_id`` is ``None`` because
    ``map_chat_to_agent_update`` only sets ``author_name``. Reading
    ``event.agent_id`` alone silently produced an empty string, so
    ``agent_name == self.coordinator_name`` never matched and loop
    detection / coordinator termination signal extraction silently
    no-opped. The orchestrator must treat ``author_name`` as the
    authoritative source.
    """

    async def _run():
        orch = _make_orchestrator()

        event = _AgentResponseUpdateStub(
            author_name="Coordinator",
            agent_id=None,
        )

        # No-op tool/text processing: we only care about agent identity.
        await orch._handle_agent_update(event, stream_callback=None, callback=None)  # type: ignore[arg-type]

        assert orch._last_executor_id == "Coordinator", (
            "author_name must be used to identify the agent; otherwise "
            "_last_executor_id stays empty and downstream coordinator "
            "checks silently fail."
        )

    asyncio.run(_run())


def test_loop_detection_fires_on_3_consecutive_coordinator_selections_via_handle_agent_update():
    """End-to-end check: feeding 3 identical Coordinator selections through
    ``_handle_agent_update`` (the path used in production) must trigger the
    loop-detection forced termination. This is the path that was silently
    broken in the 1.3.0 regression.
    """

    async def _run():
        orch = _make_orchestrator()
        orch._conversation = []

        coordinator_json = json.dumps(
            {
                "selected_participant": "Chief Architect",
                "instruction": "re-list",
                "finish": False,
                "final_message": "",
            }
        )

        # Simulate three consecutive Coordinator turns, each emitting the
        # same selection. Between each Coordinator turn we drive an update
        # from a non-Coordinator agent so the orchestrator's "agent switch"
        # logic completes the previous Coordinator response (which is what
        # actually runs loop-detection at line 1080).
        for _ in range(3):
            # Coordinator emits its selection as a streaming chunk.
            await orch._handle_agent_update(
                _AgentResponseUpdateStub(author_name="Coordinator"),
                stream_callback=None,
                callback=None,
            )  # type: ignore[arg-type]
            orch._current_agent_response = [coordinator_json]

            # Then Chief Architect emits a chunk: the agent switch closes
            # out the Coordinator response and runs loop detection.
            await orch._handle_agent_update(
                _AgentResponseUpdateStub(author_name="Chief Architect"),
                stream_callback=None,
                callback=None,
            )  # type: ignore[arg-type]
            orch._current_agent_response = ["ack"]

        # Closing the final Chief Architect response keeps state consistent.
        await orch._complete_agent_response("Chief Architect", callback=None)

        assert orch._forced_termination_requested is True, (
            "Loop detection failed to fire after 3 identical Coordinator "
            "selections via _handle_agent_update; agent identity resolution "
            "is broken."
        )

    asyncio.run(_run())


def test_handle_agent_update_prefers_executor_id_over_author_name():
    """In agent-framework 1.3.0, the workflow runner always wraps payloads in
    a ``WorkflowEvent`` whose ``executor_id`` is the ``AgentExecutor.id``
    (= the agent's name). This is the most reliable identity source - more
    reliable than ``author_name`` which may differ if the agent runtime
    rewrites the chat author. The handler must prefer ``executor_id`` when
    provided.
    """

    async def _run():
        orch = _make_orchestrator()

        # author_name disagrees with the framework executor_id on purpose.
        event = _AgentResponseUpdateStub(
            author_name="SomethingElse",
            agent_id=None,
        )

        await orch._handle_agent_update(
            event,
            executor_id="Coordinator",
            stream_callback=None,
            callback=None,
        )  # type: ignore[arg-type]

        assert orch._last_executor_id == "Coordinator", (
            "executor_id from the WorkflowEvent wrapper must take precedence "
            "over event.author_name; otherwise downstream coordinator checks "
            "may resolve to the wrong agent."
        )

    asyncio.run(_run())


def test_handle_agent_update_strips_executor_id_prefix():
    """``GroupChatBuilder`` may wrap executor ids with a
    ``groupchat_agent:Coordinator`` prefix. ``_normalize_executor_id`` must
    strip it so the agent name compares cleanly against ``coordinator_name``.
    """

    async def _run():
        orch = _make_orchestrator()

        event = _AgentResponseUpdateStub(author_name=None, agent_id=None)

        await orch._handle_agent_update(
            event,
            executor_id="groupchat_agent:Coordinator",
            stream_callback=None,
            callback=None,
        )  # type: ignore[arg-type]

        assert orch._last_executor_id == "Coordinator", (
            "_normalize_executor_id must strip the framework prefix so "
            "agent identity matches the configured coordinator_name."
        )

    asyncio.run(_run())
