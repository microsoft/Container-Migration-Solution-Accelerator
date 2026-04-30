# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for AgentBuilder fluent API and factory methods."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from libs.agent_framework.agent_builder import AgentBuilder


def _captured_chat_agent():
    """Patch ChatAgent in agent_builder; returns the patcher and the mock."""
    return patch("libs.agent_framework.agent_builder.ChatAgent")


def test_init_stores_chat_client_and_defaults() -> None:
    client = SimpleNamespace()
    b = AgentBuilder(client)
    assert b._chat_client is client
    assert b._instructions is None
    assert b._tool_choice == "auto"
    assert b._tools is None


def test_with_methods_are_chainable_and_set_attributes() -> None:
    client = SimpleNamespace()
    b = AgentBuilder(client)
    result = (
        b.with_instructions("inst")
        .with_id("id-1")
        .with_name("n")
        .with_description("desc")
        .with_temperature(0.5)
        .with_max_tokens(100)
        .with_tools(["t1"])
        .with_tool_choice("required")
        .with_middleware(["m"])
        .with_context_providers(["cp"])
        .with_conversation_id("conv-1")
        .with_model_id("model-x")
        .with_top_p(0.9)
        .with_frequency_penalty(0.1)
        .with_presence_penalty(0.2)
        .with_seed(42)
        .with_stop(["STOP"])
        .with_metadata({"k": "v"})
        .with_user("alice")
        .with_additional_chat_options({"reasoning": "high"})
        .with_store(True)
        .with_logit_bias({"a": 1.0})
        .with_kwargs(extra="e1")
        .with_kwargs(extra2="e2")
    )

    assert result is b
    assert b._instructions == "inst"
    assert b._id == "id-1"
    assert b._name == "n"
    assert b._description == "desc"
    assert b._temperature == 0.5
    assert b._max_tokens == 100
    assert b._tools == ["t1"]
    assert b._tool_choice == "required"
    assert b._middleware == ["m"]
    assert b._context_providers == ["cp"]
    assert b._conversation_id == "conv-1"
    assert b._model_id == "model-x"
    assert b._top_p == 0.9
    assert b._frequency_penalty == 0.1
    assert b._presence_penalty == 0.2
    assert b._seed == 42
    assert b._stop == ["STOP"]
    assert b._metadata == {"k": "v"}
    assert b._user == "alice"
    assert b._additional_chat_options == {"reasoning": "high"}
    assert b._store is True
    assert b._logit_bias == {"a": 1.0}
    assert b._kwargs == {"extra": "e1", "extra2": "e2"}


def test_with_response_format_and_message_store_factory() -> None:
    b = AgentBuilder(SimpleNamespace())

    class M:
        pass

    factory = lambda: object()
    assert b.with_response_format(M)._response_format is M
    assert b.with_message_store_factory(factory)._chat_message_store_factory is factory


def test_build_creates_chat_agent_with_all_params() -> None:
    client = SimpleNamespace()
    with _captured_chat_agent() as mock_chat_agent:
        mock_chat_agent.return_value = "agent-instance"
        b = (
            AgentBuilder(client)
            .with_name("WeatherBot")
            .with_instructions("be helpful")
            .with_temperature(0.7)
            .with_max_tokens(500)
        )
        agent = b.build()

    assert agent == "agent-instance"
    kwargs = mock_chat_agent.call_args.kwargs
    assert kwargs["chat_client"] is client
    assert kwargs["name"] == "WeatherBot"
    assert kwargs["instructions"] == "be helpful"
    assert kwargs["temperature"] == 0.7
    assert kwargs["max_tokens"] == 500
    assert kwargs["tool_choice"] == "auto"


def test_build_passes_kwargs_through() -> None:
    with _captured_chat_agent() as mock_chat_agent:
        mock_chat_agent.return_value = "x"
        AgentBuilder(SimpleNamespace()).with_kwargs(custom="value").build()

    assert mock_chat_agent.call_args.kwargs["custom"] == "value"


def test_create_agent_static_factory_creates_chat_agent() -> None:
    with _captured_chat_agent() as mock_chat_agent:
        mock_chat_agent.return_value = "static-agent"
        result = AgentBuilder.create_agent(
            chat_client="cc",
            instructions="inst",
            name="N",
            temperature=0.3,
        )

    assert result == "static-agent"
    kwargs = mock_chat_agent.call_args.kwargs
    assert kwargs["instructions"] == "inst"
    assert kwargs["name"] == "N"
    assert kwargs["temperature"] == 0.3
    assert kwargs["chat_client"] == "cc"


def _make_agent_info(agent_type="t", instruction="instr", system_prompt="sys"):
    framework_helper = MagicMock()
    framework_helper.settings.get_service_config.return_value = SimpleNamespace(
        endpoint="https://e",
        chat_deployment_name="d",
        api_version="2024-01-01",
    )
    framework_helper.create_client.return_value = "client-from-helper"
    return SimpleNamespace(
        agent_framework_helper=framework_helper,
        agent_type=agent_type,
        agent_name="MyAgent",
        agent_description="MyDesc",
        agent_instruction=instruction,
        agent_system_prompt=system_prompt,
    )


def test_create_agent_by_agentinfo_uses_agent_instruction() -> None:
    info = _make_agent_info(instruction="primary-instruction", system_prompt="sys")
    with patch(
        "libs.agent_framework.agent_builder.get_bearer_token_provider",
        return_value="tp",
    ), _captured_chat_agent() as mock_chat_agent:
        mock_chat_agent.return_value = "agent-built"
        result = AgentBuilder.create_agent_by_agentinfo(
            service_id="default",
            agent_info=info,
            temperature=0.4,
        )

    assert result == "agent-built"
    kwargs = mock_chat_agent.call_args.kwargs
    assert kwargs["instructions"] == "primary-instruction"
    assert kwargs["name"] == "MyAgent"
    assert kwargs["description"] == "MyDesc"
    assert kwargs["temperature"] == 0.4


def test_create_agent_by_agentinfo_falls_back_to_system_prompt() -> None:
    info = _make_agent_info(instruction=None, system_prompt="fallback-prompt")
    with patch(
        "libs.agent_framework.agent_builder.get_bearer_token_provider",
        return_value="tp",
    ), _captured_chat_agent() as mock_chat_agent:
        mock_chat_agent.return_value = "ok"
        AgentBuilder.create_agent_by_agentinfo(service_id="default", agent_info=info)

    kwargs = mock_chat_agent.call_args.kwargs
    assert kwargs["instructions"] == "fallback-prompt"


def test_create_agent_by_agentinfo_raises_when_service_config_missing() -> None:
    info = _make_agent_info()
    info.agent_framework_helper.settings.get_service_config.return_value = None

    with pytest.raises(ValueError, match="Service config"):
        AgentBuilder.create_agent_by_agentinfo(service_id="bad", agent_info=info)
