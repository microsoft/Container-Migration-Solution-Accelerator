from enum import Enum
from typing import Any, cast

from jinja2 import Template
from pydantic import BaseModel, Field
from semantic_kernel.agents import (
    Agent,
    AssistantAgentThread,
    AzureAIAgent,
    AzureAIAgentThread,
    AzureAssistantAgent,
    ChatCompletionAgent,
    ChatHistoryAgentThread,
)
from semantic_kernel.agents.azure_ai.azure_ai_agent import AgentsApiResponseFormatOption
from semantic_kernel.connectors.ai.function_choice_behavior import (
    FunctionChoiceBehavior,
)
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)
from semantic_kernel.connectors.ai.prompt_execution_settings import (
    PromptExecutionSettings,
)

# Note: MCP import disabled due to dependency compatibility
# from semantic_kernel.connectors.mcp import MCPPluginBase
from semantic_kernel.contents import ChatMessageContent
from semantic_kernel.functions import KernelPlugin

from libs.base.KernelAgent import semantic_kernel_agent
from libs.base.SKLogicBase import SKLogicBase


class AgentType(str, Enum):
    AzureAssistantAgent = "AzureAssistantAgent"
    AzureAIAgent = "AzureAIAgent"
    ChatCompletionAgent = "ChatCompletionAgent"


class agent_info(BaseModel):
    agent_name: str
    agent_type: AgentType
    agent_system_prompt: str | None = Field(default=None)
    agent_description: str | None = Field(default=None)
    agent_instruction: str | None = Field(default=None)

    @staticmethod
    def update_prompt(template: str, **kwargs):
        return Template(template).render(**kwargs)

    def render(self, **kwargs) -> "agent_info":
        """Simple template rendering method"""
        # Render agent_system_prompt if it contains Jinja templates
        if self.agent_system_prompt and (
            "{{" in self.agent_system_prompt or "{%" in self.agent_system_prompt
        ):
            self.agent_system_prompt = Template(self.agent_system_prompt).render(
                **kwargs
            )
        # Render agent_instruction if it exists and contains templates
        if self.agent_instruction and (
            "{{" in self.agent_instruction or "{%" in self.agent_instruction
        ):
            self.agent_instruction = Template(self.agent_instruction).render(**kwargs)
        return self


class pluginInfo(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    plugin: (
        KernelPlugin | object
    )  # object for kernel function classes (MCP support disabled)
    plugin_name: str
    is_mcp_plugin: bool = False


class AgentBuilder(SKLogicBase):
    settings: AzureChatPromptExecutionSettings | PromptExecutionSettings | None = Field(
        default=None
    )
    meta_data: agent_info | None = Field(default=None)

    def __init__(
        self,
        kernel_agent: semantic_kernel_agent,
        agent: Agent
        | AzureAssistantAgent
        | AzureAIAgent
        | ChatCompletionAgent
        | None = None,
        **data: Any,
    ):
        super().__init__(kernel_agent, **data)
        # self.meta_data = agent

    async def __aenter__(self):
        """Async context manager entry for cleanup support."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - can be extended for cleanup if needed."""
        pass

    def _init_agent(self, service_id: str | None = "default"):
        """Initialize agent settings - called automatically by SKLogicBase constructor"""
        if service_id is None:
            service_id = "default"

        self.settings = self.kernel_agent.get_prompt_execution_settings_from_service_id(
            service_id
        )

        # CRITICAL: Apply strict token limits to prevent 428K token errors
        # Use max_completion_tokens instead of max_tokens for newer OpenAI API
        if hasattr(self.settings, "max_completion_tokens"):
            self.settings.max_completion_tokens = 4000  # Strict output limit
        elif hasattr(self.settings, "max_tokens"):
            self.settings.max_tokens = 4000  # Fallback for older API
        if hasattr(self.settings, "temperature"):
            self.settings.temperature = 1.0  # O3 model only supports temperature=1.0

        self.settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

    async def _init_agent_async(self, service_id):
        """Async initialization if needed"""
        pass

    async def execute(self, func_params: dict[str, Any] | None = None):
        """Execute method required by SKLogicBase"""
        pass

    async def _set_up_agent(
        self,
        agent_info: agent_info,
        service_id: str = "default",
        plugins: list[KernelPlugin | object | dict[str, Any]] | None = None,
        response_format: AgentsApiResponseFormatOption | None = None,
    ):
        """Set up agent based on agent_info.agent_type"""
        if plugins is None:
            plugins = []

        self.meta_data = agent_info

        match agent_info.agent_type:
            case AgentType.AzureAssistantAgent:
                await self._setup_azure_assistant_agent(agent_info, plugins)
            case AgentType.AzureAIAgent:
                await self._setup_azure_ai_agent(agent_info, plugins)
            case AgentType.ChatCompletionAgent:
                await self._setup_chat_completion_agent(
                    agent_info=agent_info, service_id=service_id, plugins=plugins
                )
            case _:
                raise ValueError(f"Unsupported agent type: {agent_info.agent_type}")

    async def execute_thread(
        self,
        user_input: str | list[str | ChatMessageContent],
        thread: ChatHistoryAgentThread
        | AssistantAgentThread
        | AzureAIAgentThread
        | None = None,
        response_format: AgentsApiResponseFormatOption | None = None,
    ) -> tuple[
        str | ChatHistoryAgentThread | AssistantAgentThread | AzureAIAgentThread
    ]:
        if self.agent is None:
            raise ValueError("Agent not initialized. Call _set_up_agent() first.")

        contents = []

        async for content in self.agent.invoke_stream(
            messages=user_input,
            thread=thread,
            # response_format=response_format
        ):
            contents.append(content)

        message_content = "".join([content.content.content for content in contents])
        # Parse response based on format using dynamic Pydantic deserialization
        # if response_format:
        #     parsed_content = response_format(**json.loads(message_content))
        #     message_content = str(parsed_content)

        # Ensure thread is not None for return type compatibility
        if thread is None:
            # Create a default thread if none provided - this depends on your agent type
            # You may need to adjust this based on your specific requirements
            # Check type of agent.
            if isinstance(self.agent, AzureAssistantAgent):
                thread = AssistantAgentThread(client=self.agent.client)
            elif isinstance(self.agent, AzureAIAgent):
                thread = AzureAIAgentThread(client=self.agent.client)
            elif isinstance(self.agent, ChatCompletionAgent):
                thread = ChatHistoryAgentThread()

        return (message_content, thread)

    async def _setup_azure_assistant_agent(
        self,
        agent_info: agent_info,
        plugins: list[KernelPlugin | object | dict[str, Any]],
    ):
        """Setup Azure Assistant Agent"""
        self.agent = await self.kernel_agent.get_azure_assistant_agent(
            agent_name=agent_info.agent_name,
            agent_instructions=agent_info.agent_system_prompt,
            # execution_settings=self.settings,
            # plugins=plugins,
        )

    async def _setup_azure_ai_agent(
        self,
        agent_info: agent_info,
        plugins: list[KernelPlugin | object | dict[str, Any]],
    ):
        """Setup Azure AI Agent"""
        self.agent = await self.kernel_agent.get_azure_ai_agent(
            agent_name=agent_info.agent_name,
            instructions=agent_info.agent_instruction,
            plugins=plugins,
        )

    async def _setup_chat_completion_agent(
        self,
        agent_info: agent_info,
        service_id: str = "default",
        plugins: list[KernelPlugin | object | dict[str, Any]] = None,
    ):
        """Setup Chat Completion Agent"""
        self.agent = await self.kernel_agent.get_azure_chat_completion_agent(
            agent_name=agent_info.agent_name,
            agent_description=agent_info.agent_description,
            agent_instructions=agent_info.agent_instruction,
            service_id=service_id,
            execution_settings=cast(AzureChatPromptExecutionSettings, self.settings),
            plugins=plugins,
        )

    @classmethod
    async def create_agent(
        cls,
        kernel_agent: semantic_kernel_agent,
        agent_info: agent_info,
        service_id: str = "default",
        plugins: list[KernelPlugin | object | dict[str, Any]] = Field(default=list),
        response_format: AgentsApiResponseFormatOption | None = None,
    ):
        """Create and return a configured agent based on agent_info"""
        if plugins is None:
            plugins = []

        agent_instance = cls(
            kernel_agent=kernel_agent,
            agent=kernel_agent.kernel.get_service(service_id=service_id),
            response_format=response_format,
        )

        # Initialize ExecutionSettings
        agent_instance._init_agent(service_id=service_id)

        # Set up the specific agent type and configuration
        await agent_instance._set_up_agent(
            agent_info=agent_info,
            plugins=plugins,
            service_id=service_id,
            response_format=response_format,
        )
        return agent_instance


# Note: MCP plugin creation function disabled due to compatibility
# def create_mcp_plugin_info(plugin: MCPPluginBase, name: str) -> pluginInfo:
#     """Create a plugin_info for an MCP plugin."""
#     return pluginInfo(plugin=plugin, plugin_name=name, is_mcp_plugin=True)


def create_kernel_plugin_info(plugin: KernelPlugin | object, name: str) -> pluginInfo:
    """Create a plugin_info for a Kernel plugin (KernelPlugin instance or class with @kernel_function)."""
    return pluginInfo(plugin=plugin, plugin_name=name, is_mcp_plugin=False)
