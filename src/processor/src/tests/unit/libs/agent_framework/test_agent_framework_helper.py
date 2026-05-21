# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from libs.agent_framework.agent_framework_helper import (
    AgentFrameworkHelper,
    ClientType,
)


def _run(coro):
    return asyncio.run(coro)


class TestInitialization:
    def test_init_creates_empty_registry(self):
        h = AgentFrameworkHelper()
        assert h.ai_clients == {}

    def test_initialize_requires_settings(self):
        h = AgentFrameworkHelper()
        with pytest.raises(ValueError):
            h.initialize(None)

    def test_initialize_all_clients_skips_invalid(self):
        h = AgentFrameworkHelper()
        settings = MagicMock()
        settings.get_available_services.return_value = ["default", "broken"]
        cfg_default = MagicMock(
            endpoint="https://x", chat_deployment_name="gpt-4", api_version="v1"
        )
        # broken returns None to exercise the warning path
        settings.get_service_config.side_effect = lambda sid: cfg_default if sid == "default" else None

        with patch(
            "libs.agent_framework.agent_framework_helper.get_bearer_token_provider",
            return_value="token",
        ), patch.object(
            AgentFrameworkHelper, "create_client", return_value="client_obj"
        ) as mock_create:
            h.initialize(settings)
        assert h.ai_clients == {"default": "client_obj"}
        assert mock_create.call_count == 1

    def test_get_client_async_returns_cached(self):
        h = AgentFrameworkHelper()
        h.ai_clients["default"] = "cached_client"
        result = _run(h.get_client_async("default"))
        assert result == "cached_client"

    def test_get_client_async_returns_none_for_missing(self):
        h = AgentFrameworkHelper()
        result = _run(h.get_client_async("nope"))
        assert result is None


class TestCreateClient:
    def test_not_implemented_openai_chat(self):
        with pytest.raises(NotImplementedError):
            AgentFrameworkHelper.create_client(ClientType.OpenAIChatCompletion)

    def test_not_implemented_openai_assistant(self):
        with pytest.raises(NotImplementedError):
            AgentFrameworkHelper.create_client(ClientType.OpenAIAssistant)

    def test_not_implemented_openai_response(self):
        with pytest.raises(NotImplementedError):
            AgentFrameworkHelper.create_client(ClientType.OpenAIResponse)

    def test_unsupported_client_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            AgentFrameworkHelper.create_client("garbage")  # type: ignore[arg-type]

    def test_azure_openai_response_with_retry(self):
        with patch(
            "libs.agent_framework.agent_framework_helper.AzureOpenAIResponseClientWithRetry"
        ) as mock_cls:
            client = AgentFrameworkHelper.create_client(
                ClientType.AzureOpenAIResponseWithRetry,
                endpoint="https://x",
                deployment_name="gpt-4",
                ad_token_provider="token",
            )
        assert client is mock_cls.return_value
        kwargs = mock_cls.call_args.kwargs
        assert kwargs["endpoint"] == "https://x"
        assert kwargs["deployment_name"] == "gpt-4"
        assert kwargs["ad_token_provider"] == "token"

    def test_default_token_provider_when_no_credential(self):
        with patch(
            "libs.agent_framework.agent_framework_helper.AzureOpenAIResponseClientWithRetry"
        ) as mock_cls, patch(
            "libs.agent_framework.agent_framework_helper.get_bearer_token_provider",
            return_value="default-token",
        ):
            AgentFrameworkHelper.create_client(
                ClientType.AzureOpenAIResponseWithRetry,
                endpoint="https://x",
                deployment_name="gpt-4",
            )
        assert mock_cls.call_args.kwargs["ad_token_provider"] == "default-token"

    def test_azure_openai_chat_completion(self):
        fake_module = types.ModuleType("agent_framework.azure")
        with patch.dict(sys.modules, {"agent_framework.azure": fake_module}):
            with pytest.raises(NotImplementedError, match="AzureOpenAIChatClient was removed"):
                AgentFrameworkHelper.create_client(
                    ClientType.AzureOpenAIChatCompletion,
                    endpoint="https://x",
                    deployment_name="gpt-4",
                    ad_token_provider="t",
                )

    def test_azure_openai_assistant(self):
        fake_module = types.ModuleType("agent_framework.azure")
        with patch.dict(sys.modules, {"agent_framework.azure": fake_module}):
            with pytest.raises(NotImplementedError, match="AzureOpenAIAssistantsClient was removed"):
                AgentFrameworkHelper.create_client(
                    ClientType.AzureOpenAIAssistant,
                    endpoint="https://x",
                    deployment_name="gpt-4",
                    ad_token_provider="t",
                )

    def test_azure_openai_response(self):
        fake_module = types.ModuleType("agent_framework.azure")
        with patch.dict(sys.modules, {"agent_framework.azure": fake_module}):
            with pytest.raises(NotImplementedError, match="AzureOpenAIResponsesClient was removed"):
                AgentFrameworkHelper.create_client(
                    ClientType.AzureOpenAIResponse,
                    endpoint="https://x",
                    deployment_name="gpt-4",
                    ad_token_provider="t",
                )

    def test_azure_openai_agent(self):
        fake_module = types.ModuleType("agent_framework.azure")
        fake_module.DurableAIAgentClient = MagicMock(return_value="agent_client")
        with patch.dict(sys.modules, {"agent_framework.azure": fake_module}):
            client = AgentFrameworkHelper.create_client(
                ClientType.AzureOpenAIAgent,
                project_endpoint="https://proj",
                model_deployment_name="gpt-4",
                ad_token_provider="t",
            )
        assert client == "agent_client"
