import logging
from enum import Enum
from typing import Optional

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from pydantic import Field, PrivateAttr, ValidationError
from semantic_kernel.agents import (
    AzureAIAgent,
    AzureAIAgentSettings,
    AzureAssistantAgent,
    ChatCompletionAgent,
)
from semantic_kernel.connectors.ai.open_ai import (
    AzureChatCompletion,
    AzureTextCompletion,
)
from semantic_kernel.connectors.ai.prompt_execution_settings import (
    PromptExecutionSettings,
)
from semantic_kernel.exceptions.service_exceptions import ServiceInitializationError
from semantic_kernel.functions import KernelArguments, KernelFunction, KernelPlugin
from semantic_kernel.kernel import Kernel
from semantic_kernel.prompt_template import PromptTemplateConfig

from libs.application.application_configuration import Configuration
from libs.base.SKBase import SKBaseModel


class service_type(Enum):
    Chat_Completion = "ChatCompletion"
    Text_Completion = "TextCompletion"


class semantic_kernel_agent(SKBaseModel):
    kernel: Kernel = Field(default_factory=Kernel)
    plugins_directory: str | None = None
    _settings: Optional[Configuration] = PrivateAttr(default=None)

    def __init__(self, env_file_path: str | None = None, **data):
        super().__init__(**data)
        self.kernel = Kernel()
        self._initialize_settings(env_file_path=env_file_path)

    def _initialize_settings(self, env_file_path: str | None = None):
        try:
            # self._settings = semantic_kernel_settings.create(
            #     env_file_path=env_file_path
            # )

            self._settings = Configuration(env_file_path=env_file_path)

        except ValidationError as ex:
            raise ServiceInitializationError(
                "Error initializing Semantic kernel settings", ex
            ) from ex

        if not self._settings.global_llm_service:
            self._settings.global_llm_service = "AzureOpenAI"

    def get_plugin(self, plugin_name: str):
        # Check if the plugin is already added
        if plugin_name in self.kernel.plugins:
            return self.kernel.get_plugin(plugin_name)
        return None

    def get_function(self, plugin_name: str, function_name: str):
        # Check if the function is already added
        if self.get_plugin(plugin_name) is None:
            return None

        if function_name in self.kernel.plugins[plugin_name].functions:
            return self.kernel.plugins[plugin_name].functions[function_name]
        return None

    def add_plugin(self, plugin: KernelPlugin, plugin_name: str):
        # Check if the plugin is already added
        registered_plugin = self.get_plugin(plugin_name)
        if registered_plugin:
            return registered_plugin

        self.kernel.add_plugin(plugin=plugin, plugin_name=plugin_name)
        return self.kernel.get_plugin(plugin_name)

    def add_plugin_from_directory(self, parent_directory: str, plugin_name: str):
        # Check if the plugin is already added
        plugin = self.get_plugin(plugin_name)
        if plugin:
            return plugin

        self.kernel.add_plugin(
            parent_directory=parent_directory, plugin_name=plugin_name
        )
        return self.kernel.get_plugin(plugin_name)

    def add_function(
        self,
        plugin_name: str | None,
        function: KernelFunction | None = None,
        function_name: str | None = None,
        prompt_template_config: PromptTemplateConfig | None = None,
    ):
        # Check if the plugin is already added
        queried_plugin = self.get_plugin(plugin_name)
        if not queried_plugin:
            # Register the plugin
            self.add_plugin(
                plugin=KernelPlugin(name=plugin_name), plugin_name=plugin_name
            )

        # Check if the function is already added
        queried_function = self.get_function(
            # if function_name is not provided, use the function name from the function object
            function_name=function_name if function_name else function.name,
            plugin_name=plugin_name,
        )

        if queried_function:
            return queried_function

        self.kernel.add_function(
            plugin_name=plugin_name,
            function=function,
            function_name=function_name,
            prompt_template_config=prompt_template_config,
        )

        return self.kernel.get_function(
            plugin_name=plugin_name,
            function_name=function_name if function_name else function.name,
        )

    def get_azure_chat_completion_agent(
        self,
        agent_name: str,
        agent_instructions: str,
        execution_settings: PromptExecutionSettings | None = None,
        plugins: list[KernelPlugin] | None = None,
    ):
        # Check if the agent is already added
        new_agent = ChatCompletionAgent(
            service=AzureChatCompletion(),
            name=agent_name,
            instructions=agent_instructions,
            arguments=KernelArguments(
                settings=execution_settings,
            ),
            plugins=plugins,
        )
        return new_agent

    async def get_azure_ai_agent(
        self,
        agent_name: str,
        instructions: str,
        plugins: list[KernelPlugin] | None = None,
        agent_id: str | None = None,
    ):
        if not self._settings.global_llm_service == "AzureOpenAI":
            raise ServiceInitializationError("Supports AzureOpenAI only")

        client = AzureAIAgent.create_client(credential=DefaultAzureCredential())
        agent_definition: AzureAIAgent | None = None

        if agent_id:
            # Check if the agent is already added
            try:
                agent_definition = await client.agents.get_agent(agent_id)
            except Exception:
                # Create a new agent
                agent_definition = await client.agents.create_agent(
                    model=AzureAIAgentSettings().model_deployment_name,
                    name=agent_name,
                    instructions=instructions,
                )
                logging.info(
                    f"Agent is not found. \nCreating new agent with name: {agent_name}, agent_id: {agent_definition.id}"
                )
        else:
            logging.info(
                f"Creating new agent with name: {agent_name}, agent_id: {agent_id}"
            )
            # Create a new agent
            agent_definition = await client.agents.create_agent(
                model=AzureAIAgentSettings().model_deployment_name,
                name=agent_name,
                instructions=instructions,
            )

        agent = AzureAIAgent(
            client=client, definition=agent_definition, plugins=plugins
        )

        return agent

    async def get_azure_assistant_agent(self, agent_name: str, agent_instructions: str):
        client, model = AzureAssistantAgent.setup_resources(
            ad_token_provider=get_bearer_token_provider(
                DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
            ),
            env_file_path=self._settings.env_file_path,
        )
        definition = await client.beta.assistants.create(
            model=model, instructions=agent_instructions, name=agent_name
        )
        return AzureAssistantAgent(
            client=client,
            definition=definition,
        )

    def get_kernel(
        self,
        service_id: str | None = "default",
        service_type: service_type = service_type.Chat_Completion,
    ) -> Kernel:
        if not self._settings.global_llm_service == "AzureOpenAI":
            raise ServiceInitializationError("Supports AzureOpenAI only")

        # Check if the service is already added
        if service_id in self.kernel.services:
            return self.kernel

        if service_type == service_type.Chat_Completion:
            self.kernel.add_service(AzureChatCompletion(service_id=service_id))
        else:
            self.kernel.add_service(AzureTextCompletion(service_id=service_id))
        return self.kernel

    def get_prompt_execution_settings_from_service_id(self, service_id: str):
        return self.kernel.get_prompt_execution_settings_from_service_id(service_id)
