from abc import ABC, abstractmethod
from typing import Type, TypeVar, overload

from pydantic import BaseModel, Field
from semantic_kernel.agents import (
    Agent,
    AgentThread,
    AssistantAgentThread,
    AzureAIAgent,
    AzureAIAgentThread,
    AzureAssistantAgent,
)

from libs.base.KernelAgent import semantic_kernel_agent
from libs.base.SKBase import SKBaseModel

# TypeVar bound to BaseModel to enforce Pydantic model types
T = TypeVar("T", bound=BaseModel)


class SKLogicBase(ABC, SKBaseModel):
    kernel_agent: semantic_kernel_agent | None = Field(default=None)
    agent: Agent | AzureAssistantAgent | AzureAIAgent | None = Field(default=None)
    thread: AgentThread | AssistantAgentThread | AzureAIAgentThread | None = Field(
        default=None
    )

    def __init__(
        self,
        kernel_agent: semantic_kernel_agent,
        system_prompt: str | None = None,
        response_format: Type[T] | None = None,
        **data,
    ):
        super().__init__(**data)
        self.kernel_agent = kernel_agent
        # Type bounded 'BaseModel'
        self.response_format = response_format
        self.system_prompt = system_prompt
        self._init_agent()

    @staticmethod
    def _validate_response_format(response_format: Type[T] | None) -> bool:
        """
        Validate that response_format is a Pydantic BaseModel class.

        Args:
            response_format: The response format to validate

        Returns:
            bool: True if valid, False otherwise

        Raises:
            TypeError: If response_format is not a BaseModel class
        """
        if response_format is None:
            return True

        if not isinstance(response_format, type):
            raise TypeError(
                f"response_format must be a class, got {type(response_format).__name__}"
            )

        if not issubclass(response_format, BaseModel):
            raise TypeError(
                f"response_format must be a Pydantic BaseModel subclass, got {response_format.__name__}"
            )

        return True

    async def _init_agent_async(self):
        """
        This method should be overridden in subclasses to initialize the agent.
        It is called during the creation of the instance.
        """
        raise NotImplementedError("This method should be overridden in subclasses")

    def _init_agent(self):
        """
        This method should be overridden in subclasses to initialize the agent.
        """
        raise NotImplementedError("This method should be overridden in subclasses")

    async def execute(func_params: dict[str, any]):
        raise NotImplementedError("Execute method not implemented")

    @overload
    async def execute_thread(
        self,
        user_input: str,
        response_format: None = None,
        thread: AgentThread | AssistantAgentThread | AzureAIAgentThread = None,
    ) -> tuple[str, AgentThread | AssistantAgentThread | AzureAIAgentThread]:
        """When response_format is None, returns string response."""
        ...

    @overload
    async def execute_thread(
        self,
        user_input: str,
        response_format: Type[T],
        thread: AgentThread | AssistantAgentThread | AzureAIAgentThread = None,
    ) -> tuple[T, AgentThread | AssistantAgentThread | AzureAIAgentThread]:
        """When response_format is provided, returns typed Pydantic BaseModel response."""
        ...

    @abstractmethod
    async def execute_thread(
        self,
        user_input: str,
        response_format: Type[T] | None = None,
        thread: AgentThread | AssistantAgentThread | AzureAIAgentThread = None,
    ) -> tuple[str | T, AgentThread | AssistantAgentThread | AzureAIAgentThread]:
        raise NotImplementedError("Execute thread method not implemented")

    @classmethod
    async def create(cls, kernel_agent: semantic_kernel_agent, **data):
        instance = cls(kernel_agent=kernel_agent, **data)
        await instance._init_agent_async()
        return instance
