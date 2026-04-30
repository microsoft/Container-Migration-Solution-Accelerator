# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for AgentFrameworkHelper and ClientType."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from libs.agent_framework.agent_framework_helper import (
    AgentFrameworkHelper,
    ClientType,
)


def test_initialize_raises_value_error_on_none_settings() -> None:
    helper = AgentFrameworkHelper()
    with pytest.raises(ValueError):
        helper.initialize(None)


def test_initialize_all_clients_raises_value_error_on_none_settings() -> None:
    helper = AgentFrameworkHelper()
    with pytest.raises(ValueError):
        helper._initialize_all_clients(settings=None)


def _make_settings(services: dict):
    s = MagicMock()
    s.get_available_services.return_value = list(services.keys())
    s.get_service_config.side_effect = lambda sid: services.get(sid)
    return s


def test_initialize_skips_service_when_no_config() -> None:
    helper = AgentFrameworkHelper()
    settings = _make_settings({"default": None})

    with patch(
        "libs.agent_framework.agent_framework_helper.get_bearer_token_provider",
        return_value="tp",
    ), patch.object(
        AgentFrameworkHelper, "create_client", return_value="client_x"
    ) as mock_create:
        helper.initialize(settings)

    assert "default" not in helper.ai_clients
    mock_create.assert_not_called()


def test_initialize_creates_clients_for_each_service() -> None:
    helper = AgentFrameworkHelper()
    cfg = SimpleNamespace(
        endpoint="https://e.example.com",
        chat_deployment_name="dep",
        api_version="2024-01-01",
    )
    settings = _make_settings({"default": cfg, "other": cfg})

    with patch(
        "libs.agent_framework.agent_framework_helper.get_bearer_token_provider",
        return_value="tp",
    ), patch.object(
        AgentFrameworkHelper, "create_client", return_value="client_x"
    ) as mock_create:
        helper.initialize(settings)

    assert helper.ai_clients == {"default": "client_x", "other": "client_x"}
    assert mock_create.call_count == 2


def test_get_client_async_returns_cached() -> None:
    helper = AgentFrameworkHelper()
    helper.ai_clients = {"default": "client-x"}

    assert asyncio.run(helper.get_client_async()) == "client-x"
    assert asyncio.run(helper.get_client_async("missing")) is None


def test_create_client_uses_default_token_provider_when_neither_credential_nor_provider() -> None:
    with patch(
        "libs.agent_framework.agent_framework_helper.get_bearer_token_provider",
        return_value="default-tp",
    ), patch(
        "libs.agent_framework.agent_framework_helper.AzureOpenAIResponseClientWithRetry",
        return_value="client",
    ) as mock_cls:
        result = AgentFrameworkHelper.create_client(
            ClientType.AzureOpenAIResponseWithRetry,
            endpoint="https://e",
            deployment_name="d",
            api_version="2024-01-01",
        )

    assert result == "client"
    kwargs = mock_cls.call_args.kwargs
    assert kwargs["ad_token_provider"] == "default-tp"
    assert kwargs["endpoint"] == "https://e"
    assert kwargs["deployment_name"] == "d"


def test_create_client_openai_chat_completion_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        AgentFrameworkHelper.create_client(
            ClientType.OpenAIChatCompletion, ad_token="x"
        )


def test_create_client_openai_assistant_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        AgentFrameworkHelper.create_client(ClientType.OpenAIAssistant, ad_token="x")


def test_create_client_openai_response_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        AgentFrameworkHelper.create_client(ClientType.OpenAIResponse, ad_token="x")


def test_create_client_azure_chat_completion_constructs_chat_client() -> None:
    fake_client = MagicMock(return_value="cc-instance")
    with patch.dict(
        "sys.modules",
        {"agent_framework.azure": MagicMock(AzureOpenAIChatClient=fake_client)},
    ):
        result = AgentFrameworkHelper.create_client(
            ClientType.AzureOpenAIChatCompletion,
            ad_token="x",
            endpoint="https://e",
            deployment_name="d",
        )
    assert result == "cc-instance"
    fake_client.assert_called_once()


def test_create_client_azure_assistant_constructs_assistant_client() -> None:
    fake_client = MagicMock(return_value="asst-instance")
    with patch.dict(
        "sys.modules",
        {"agent_framework.azure": MagicMock(AzureOpenAIAssistantsClient=fake_client)},
    ):
        result = AgentFrameworkHelper.create_client(
            ClientType.AzureOpenAIAssistant,
            ad_token="x",
            assistant_id="a-1",
            assistant_name="An",
            thread_id="t-1",
        )
    assert result == "asst-instance"
    kwargs = fake_client.call_args.kwargs
    assert kwargs["assistant_id"] == "a-1"


def test_create_client_azure_response_constructs_response_client() -> None:
    fake_client = MagicMock(return_value="resp-instance")
    with patch.dict(
        "sys.modules",
        {"agent_framework.azure": MagicMock(AzureOpenAIResponsesClient=fake_client)},
    ):
        result = AgentFrameworkHelper.create_client(
            ClientType.AzureOpenAIResponse,
            ad_token="x",
            endpoint="https://e",
        )
    assert result == "resp-instance"


def test_create_client_azure_response_with_retry_passes_retry_config() -> None:
    with patch(
        "libs.agent_framework.agent_framework_helper.AzureOpenAIResponseClientWithRetry",
        return_value="retry-instance",
    ) as mock_cls:
        result = AgentFrameworkHelper.create_client(
            ClientType.AzureOpenAIResponseWithRetry,
            credential="cred",
            retry_config="rc-x",
        )
    assert result == "retry-instance"
    assert mock_cls.call_args.kwargs["retry_config"] == "rc-x"


def test_create_client_azure_agent_constructs_agent_client() -> None:
    fake_client = MagicMock(return_value="agent-instance")
    with patch.dict(
        "sys.modules",
        {"agent_framework.azure": MagicMock(AzureAIAgentClient=fake_client)},
    ):
        result = AgentFrameworkHelper.create_client(
            ClientType.AzureOpenAIAgent,
            ad_token="x",
            agent_id="ag-1",
            agent_name="An",
            project_endpoint="https://p",
            model_deployment_name="m",
        )
    assert result == "agent-instance"
    kwargs = fake_client.call_args.kwargs
    assert kwargs["agent_id"] == "ag-1"


def test_create_client_unknown_type_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        AgentFrameworkHelper.create_client("not-a-client-type", ad_token="x")
