# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from libs.agent_framework.agent_builder import AgentBuilder


def _builder():
    return AgentBuilder(chat_client=MagicMock())


class TestFluentSetters:
    def test_default_state(self):
        b = _builder()
        assert b._instructions is None
        assert b._tools is None
        assert b._tool_choice == "auto"
        assert b._kwargs == {}

    def test_with_instructions(self):
        b = _builder().with_instructions("hello")
        assert b._instructions == "hello"

    def test_with_id(self):
        b = _builder().with_id("agent-1")
        assert b._id == "agent-1"

    def test_with_name(self):
        b = _builder().with_name("MyAgent")
        assert b._name == "MyAgent"

    def test_with_description(self):
        b = _builder().with_description("desc")
        assert b._description == "desc"

    def test_with_temperature(self):
        b = _builder().with_temperature(0.7)
        assert b._temperature == 0.7

    def test_with_max_tokens(self):
        b = _builder().with_max_tokens(123)
        assert b._max_tokens == 123

    def test_with_tools(self):
        tools = [lambda: None]
        b = _builder().with_tools(tools)
        assert b._tools is tools

    def test_with_tool_choice(self):
        b = _builder().with_tool_choice("required")
        assert b._tool_choice == "required"

    def test_with_middleware(self):
        m = [MagicMock()]
        b = _builder().with_middleware(m)
        assert b._middleware == m

    def test_with_middleware_single(self):
        m = MagicMock()
        b = _builder().with_middleware(m)
        assert b._middleware == [m]

    def test_with_context_providers(self):
        cp = MagicMock()
        b = _builder().with_context_providers(cp)
        assert b._context_providers == [cp]

    def test_with_context_providers_list(self):
        cp1, cp2 = MagicMock(), MagicMock()
        b = _builder().with_context_providers([cp1, cp2])
        assert b._context_providers == [cp1, cp2]

    def test_with_conversation_id(self):
        b = _builder().with_conversation_id("conv-1")
        assert b._conversation_id == "conv-1"

    def test_with_model_id(self):
        b = _builder().with_model_id("gpt-4")
        assert b._model_id == "gpt-4"

    def test_with_top_p(self):
        b = _builder().with_top_p(0.9)
        assert b._top_p == 0.9

    def test_with_frequency_penalty(self):
        b = _builder().with_frequency_penalty(-0.2)
        assert b._frequency_penalty == -0.2

    def test_with_presence_penalty(self):
        b = _builder().with_presence_penalty(0.5)
        assert b._presence_penalty == 0.5

    def test_with_seed(self):
        b = _builder().with_seed(42)
        assert b._seed == 42

    def test_with_stop(self):
        b = _builder().with_stop(["X", "Y"])
        assert b._stop == ["X", "Y"]

    def test_with_response_format(self):
        class Resp:
            pass

        b = _builder().with_response_format(Resp)
        assert b._response_format is Resp

    def test_with_metadata(self):
        b = _builder().with_metadata({"k": "v"})
        assert b._metadata == {"k": "v"}

    def test_with_user(self):
        b = _builder().with_user("alice")
        assert b._user == "alice"

    def test_with_additional_chat_options(self):
        b = _builder().with_additional_chat_options({"x": 1})
        assert b._additional_chat_options == {"x": 1}

    def test_with_store(self):
        b = _builder().with_store(True)
        assert b._store is True

    def test_with_message_store_factory(self):
        def f():
            return MagicMock()
        b = _builder().with_message_store_factory(f)
        assert b._chat_message_store_factory is f

    def test_with_logit_bias(self):
        b = _builder().with_logit_bias({"1": 0.5})
        assert b._logit_bias == {"1": 0.5}

    def test_with_kwargs_merges(self):
        b = _builder().with_kwargs(a=1).with_kwargs(b=2)
        assert b._kwargs == {"a": 1, "b": 2}

    def test_chaining_returns_self_each_step(self):
        b = _builder()
        out = (
            b.with_name("n")
            .with_id("i")
            .with_temperature(0.1)
            .with_max_tokens(10)
            .with_top_p(0.5)
        )
        assert out is b


class TestBuild:
    def test_build_passes_all_state_to_chat_agent(self):
        chat_client = MagicMock()
        with patch("libs.agent_framework.agent_builder.Agent") as mock_chat:
            agent = (
                AgentBuilder(chat_client)
                .with_instructions("inst")
                .with_id("id1")
                .with_name("name1")
                .with_description("desc1")
                .with_temperature(0.3)
                .with_max_tokens(100)
                .with_kwargs(extra=42)
                .build()
            )
        assert agent is mock_chat.return_value
        kwargs = mock_chat.call_args.kwargs
        assert kwargs["client"] is chat_client
        assert kwargs["instructions"] == "inst"
        assert kwargs["id"] == "id1"
        assert kwargs["name"] == "name1"
        assert kwargs["description"] == "desc1"
        default_options = kwargs["default_options"]
        assert default_options["temperature"] == 0.3
        assert default_options["max_tokens"] == 100
        assert default_options["tool_choice"] == "auto"
        assert kwargs["extra"] == 42


class TestStaticFactories:
    def test_create_agent_invokes_chat_agent(self):
        chat_client = MagicMock()
        with patch("libs.agent_framework.agent_builder.Agent") as mock_chat:
            agent = AgentBuilder.create_agent(
                chat_client=chat_client,
                instructions="i",
                name="n",
                temperature=0.4,
            )
        assert agent is mock_chat.return_value
        kwargs = mock_chat.call_args.kwargs
        assert kwargs["client"] is chat_client
        assert kwargs["instructions"] == "i"
        assert kwargs["name"] == "n"
        assert kwargs["default_options"]["temperature"] == 0.4

    def test_create_agent_by_agentinfo_uses_helper_and_creates_client(self):
        # Build a fake AgentInfo with the minimum surface used by the method
        helper = MagicMock()
        helper.settings.get_service_config.return_value = SimpleNamespace(
            endpoint="https://x",
            chat_deployment_name="gpt",
            api_version="2024-02-01",
        )
        helper.create_client.return_value = "client-instance"
        agent_info = SimpleNamespace(
            agent_framework_helper=helper,
            agent_type="azure_openai",
            agent_instruction="instr",
            agent_system_prompt=None,
            agent_name="A",
            agent_description="D",
        )
        with patch(
            "libs.agent_framework.agent_builder.get_bearer_token_provider",
            return_value="token-provider",
        ), patch("libs.agent_framework.agent_builder.Agent") as mock_chat:
            agent = AgentBuilder.create_agent_by_agentinfo(
                service_id="default",
                agent_info=agent_info,
                temperature=0.2,
            )
        assert agent is mock_chat.return_value
        helper.settings.get_service_config.assert_called_once_with("default")
        helper.create_client.assert_called_once()
        ck = mock_chat.call_args.kwargs
        assert ck["client"] == "client-instance"
        assert ck["instructions"] == "instr"
        assert ck["name"] == "A"
        assert ck["description"] == "D"
        assert ck["default_options"]["temperature"] == 0.2

    def test_create_agent_by_agentinfo_falls_back_to_system_prompt(self):
        helper = MagicMock()
        helper.settings.get_service_config.return_value = SimpleNamespace(
            endpoint="https://x",
            chat_deployment_name="gpt",
            api_version="2024-02-01",
        )
        helper.create_client.return_value = "client"
        agent_info = SimpleNamespace(
            agent_framework_helper=helper,
            agent_type="azure_openai",
            agent_instruction=None,
            agent_system_prompt="fallback",
            agent_name="A",
            agent_description="D",
        )
        with patch(
            "libs.agent_framework.agent_builder.get_bearer_token_provider",
            return_value="tp",
        ), patch("libs.agent_framework.agent_builder.Agent") as mock_chat:
            AgentBuilder.create_agent_by_agentinfo(
                service_id="default", agent_info=agent_info
            )
        assert mock_chat.call_args.kwargs["instructions"] == "fallback"

    def test_create_agent_by_agentinfo_raises_when_service_config_missing(self):
        helper = MagicMock()
        helper.settings.get_service_config.return_value = None
        agent_info = SimpleNamespace(
            agent_framework_helper=helper,
            agent_type="azure_openai",
            agent_instruction="x",
            agent_system_prompt=None,
            agent_name="A",
            agent_description="D",
        )
        import pytest

        with pytest.raises(ValueError, match="Service config"):
            AgentBuilder.create_agent_by_agentinfo(
                service_id="missing", agent_info=agent_info
            )
