# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import logging
from abc import abstractmethod
from typing import Any, Callable, Generic, MutableMapping, Sequence, TypeVar

from agent_framework import ChatAgent, ManagerSelectionResponse, ToolProtocol

from libs.agent_framework.agent_builder import AgentBuilder
from libs.agent_framework.agent_framework_helper import ClientType
from libs.agent_framework.agent_info import AgentInfo
from libs.agent_framework.azure_openai_response_retry import RateLimitRetryConfig
from libs.agent_framework.groupchat_orchestrator import (
    AgentResponse,
    AgentResponseStream,
    OrchestrationResult,
)
from utils.agent_telemetry import TelemetryManager
from utils.console_util import format_agent_message

from .agent_base import AgentBase

TaskParamT = TypeVar("TaskParamT")
ResultT = TypeVar("ResultT")


class OrchestratorBase(AgentBase, Generic[TaskParamT, ResultT]):
    def __init__(self, app_context=None):
        super().__init__(app_context)
        self.step_name = "OrchestratorBase"
        self.initialized = False

    def is_console_summarization_enabled(self) -> bool:
        """Return True if console summarization (extra LLM call per turn) is enabled.

        Summarization is purely for operator readability and does not affect artifacts.
        Default is disabled for performance.
        """
        return False
        # return os.getenv("MIGRATION_CONSOLE_SUMMARY", "0").strip().lower() in {
        #     "1",
        #     "true",
        #     "yes",
        #     "y",
        #     "on",
        # }

    async def initialize(self, process_id: str):
        self.mcp_tools: (
            ToolProtocol
            | Callable[..., Any]
            | MutableMapping[str, Any]
            | Sequence[ToolProtocol | Callable[..., Any] | MutableMapping[str, Any]]
        ) = await self.prepare_mcp_tools()
        self.agentinfos = await self.prepare_agent_infos()
        self.agents = await self.create_agents(self.agentinfos, process_id=process_id)
        self.initialized = True

    def load_platform_registry(self, registry_path: str) -> list[dict[str, Any]]:
        with open(registry_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        experts = data.get("experts")
        if not isinstance(experts, list):
            raise ValueError(
                f"Invalid platform registry: missing 'experts' list in {registry_path}"
            )
        return experts

    def read_prompt_file(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    @abstractmethod
    async def execute(
        self, task_param: TaskParamT = None
    ) -> OrchestrationResult[ResultT]:
        pass

    @abstractmethod
    async def prepare_mcp_tools(
        self,
    ) -> (
        ToolProtocol
        | Callable[..., Any]
        | MutableMapping[str, Any]
        | Sequence[ToolProtocol | Callable[..., Any] | MutableMapping[str, Any]]
    ):
        pass

    @abstractmethod
    async def prepare_agent_infos(self) -> list[AgentInfo]:
        """Prepare agent information list for workflow"""
        pass


    async def create_agents(
        self, agent_infos: list[AgentInfo], process_id: str
    ) -> list[ChatAgent]:
        agents = dict[str, ChatAgent]()
        agent_client = await self.get_client(thread_id=process_id)
        for agent_info in agent_infos:
            builder = (
                AgentBuilder(agent_client)
                .with_name(agent_info.agent_name)
                .with_instructions(agent_info.agent_instruction)
            )

            # Only attach tools when provided. (Coordinator should typically have none.)
            if agent_info.tools is not None:
                builder = (
                    builder.with_tools(agent_info.tools)
                    .with_temperature(0.0)
                )

            if agent_info.agent_name == "Coordinator":
                # Routing-only: keep deterministic and small.
                builder = (
                    builder.with_temperature(0.0)
                    .with_response_format(ManagerSelectionResponse)
                    .with_tools(agent_info.tools)  # for checking file existence
                )
            elif agent_info.agent_name == "ResultGenerator":
                # Structured JSON generation; deterministic and bounded.
                builder = (
                    builder.with_temperature(0.0)
                    .with_tool_choice("none")
                )
            agent = builder.build()
            agents[agent_info.agent_name] = agent

        return agents

    # Create Client Cache. keep one client per process_id (thread_id)
    _client_cache: dict[str, Any] = {}

    async def get_client(self, thread_id: str = None):
        # Check client Cache
        if thread_id and thread_id in self._client_cache:
            return self._client_cache[thread_id]
        else:
            client = self.agent_framework_helper.create_client(
                client_type=ClientType.AzureOpenAIResponseWithRetry,
                endpoint=self.agent_framework_helper.settings.get_service_config(
                    "default"
                ).endpoint,
                deployment_name=self.agent_framework_helper.settings.get_service_config(
                    "default"
                ).chat_deployment_name,
                api_version=self.agent_framework_helper.settings.get_service_config(
                    "default"
                ).api_version,
                thread_id=thread_id,
                retry_config=RateLimitRetryConfig(
                    max_retries=5, base_delay_seconds=3.0, max_delay_seconds=60.0
                ),
            )
            self._client_cache[thread_id] = client
            return client

    async def get_summarizer(self):
        # Check Client Cache
        if "summarizer" in self._client_cache:
            agent_client = self._client_cache["summarizer"]
        else:
            # agent_client = self.agent_framework_helper.create_client(
            #     client_type=ClientType.AzureOpenAIChatCompletion,
            #     endpoint=self.agent_framework_helper.settings.get_service_config(
            #         "PHI4"
            #     ).endpoint,
            #     deployment_name=self.agent_framework_helper.settings.get_service_config(
            #         "PHI4"
            #     ).chat_deployment_name,
            #     api_version=self.agent_framework_helper.settings.get_service_config(
            #         "PHI4"
            #     ).api_version,
            # )

            agent_client = await self.agent_framework_helper.get_client_async("default")
            self._client_cache["summarizer"] = agent_client

        summarizer_agent = (
            AgentBuilder(agent_client)
            .with_name("Summarizer")
            .with_instructions(
                """
                Your task is to provide clear and brief summaries of the given input.
                You should say like a guy who is participating migration project.
                Though passed string may be json or structured format, your response should be a concise verbal speaking.
                Use "I" statements where appropriate.
                Don't speak over 300 words.
                """
            )
            .build()
        )
        return summarizer_agent

    async def on_agent_response(self, response: AgentResponse):
        logging.info(
            f"[{response.timestamp}] :{response.agent_name}: {response.message}"
        )
        # print(f"{response.agent_name}: {response.message}")

        # Get Telemetry Manager
        telemetry: TelemetryManager = await self.app_context.get_service_async(
            TelemetryManager
        )

        if response.agent_name == "Coordinator":
            # print different information. from Coordinator's response structure
            try:
                response_dict = json.loads(response.message)
                coordinator_response = ManagerSelectionResponse.model_validate(
                    response_dict
                )

                # Hard Detect Phase Information from Coordinator's instruction - use regex ("PHASE X xxxx:")
                # X is number and xxxx is description

                if coordinator_response.instruction:
                    import re

                    # Parse phase number + optional description from instructions like:
                    # "PHASE 4 INTEGRATION & SIGN-OFF UPDATE PREP: ..."
                    # "PHASE 0 TRIAGE: ..."
                    phase_match = re.search(
                        r"\bPHASE\s+(?P<num>\d+)(?:\s+(?P<desc>[^:]+?))?(?:\s*:|$)",
                        coordinator_response.instruction,
                        flags=re.IGNORECASE,
                    )
                    if phase_match:
                        phase_number = (phase_match.group("num") or "").strip()
                        phase_desc = (phase_match.group("desc") or "").strip()

                        phase_desc = re.sub(r"\s+", " ", phase_desc)
                        if phase_desc:
                            # Keep UI-friendly: avoid extremely long phase strings.
                            if len(phase_desc) > 80:
                                phase_desc = phase_desc[:77].rstrip() + "..."
                            phase_label = f"PHASE {phase_number} - {phase_desc}"
                        else:
                            phase_label = f"PHASE {phase_number}"

                        await telemetry.transition_to_phase(
                            process_id=self.task_param.process_id,
                            step=self.step_name,
                            phase=phase_label if phase_label else "Processing...",
                        )

                if not coordinator_response.finish:
                    if self.is_console_summarization_enabled():
                        try:
                            summarizer_agent = await self.get_summarizer()
                            summarized_response = await summarizer_agent.run(
                                f"speak as {response.agent_name} : {coordinator_response.instruction} to {coordinator_response.selected_participant}"
                            )
                            print(
                                f"{response.agent_name}: {summarized_response.text} ({response.elapsed_time:.2f}s)\n\n"
                            )
                            await telemetry.update_agent_activity(
                                process_id=self.task_param.process_id,
                                agent_name=response.agent_name,
                                action="speaking",
                                message_preview=summarized_response.text,
                                full_message=response.message,
                            )
                        except Exception as e:
                            logging.error(f"Error in summarization: {e}")
                            print(f"{response.agent_name}: {response.message}\n\n")
                    else:
                        # print(
                        #     f"{response.agent_name}: {coordinator_response.selected_participant} ← {coordinator_response.instruction} ({response.elapsed_time:.2f}s)\n\n"
                        # )
                        # use format_agent_message
                        print(
                            format_agent_message(
                                name=response.agent_name,
                                content=f"{response.agent_name}: {coordinator_response.selected_participant} ← {coordinator_response.instruction}",
                                timestamp=f"{response.elapsed_time:.2f}s",
                            )
                        )

                        await telemetry.update_agent_activity(
                            process_id=self.task_param.process_id,
                            agent_name=response.agent_name,
                            action="speaking",
                            message_preview=f"{coordinator_response.selected_participant} <- {coordinator_response.instruction}",
                            full_message=response.message,
                        )

            except Exception:
                # something wrong with deserialization, ignore
                pass
        elif response.agent_name == "ResultGenerator":
            print("Step results has been generated")
        else:
            # print(f"{response.agent_name}: {response.message} ({response.elapsed_time:.2f}s)\n\n")
            if self.is_console_summarization_enabled():
                try:
                    summarizer_agent = await self.get_summarizer()
                    summarized_response = await summarizer_agent.run(
                        f"speak as {response.agent_name} : {response.message}"
                    )
                    print(
                        f"{response.agent_name}: {summarized_response.text} ({response.elapsed_time:.2f}s)\n\n"
                    )

                    await telemetry.update_agent_activity(
                        process_id=self.task_param.process_id,
                        agent_name=response.agent_name,
                        action="responded",
                        message_preview=summarized_response.text,
                    )

                except Exception as e:
                    logging.error(f"Error in summarization: {e}")
                    print(f"{response.agent_name}: {response.message}\n\n")
            else:
                # print(
                #     f"{response.agent_name}: {response.message} ({response.elapsed_time:.2f}s)\n\n"
                # )
                print(
                    format_agent_message(
                        name=response.agent_name,
                        content=f"{response.agent_name}: {response.message}",
                        timestamp=f"{response.elapsed_time:.2f}s",
                    )
                )

                await telemetry.update_agent_activity(
                    process_id=self.task_param.process_id,
                    agent_name=response.agent_name,
                    action="responded",
                    message_preview=response.message,
                )

    async def on_agent_response_stream(self, response: AgentResponseStream):
        telemetry: TelemetryManager = await self.app_context.get_service_async(
            TelemetryManager
        )

        if response.response_type == "message":
            # GroupChatOrchestrator emits this when an agent starts streaming a new message.
            # print(f"{response.agent_name} is thinking...\n")
            print(
                format_agent_message(
                    name=response.agent_name,
                    content=f"{response.agent_name} is thinking...",
                    timestamp="",
                )
            )

            await telemetry.update_agent_activity(
                process_id=self.task_param.process_id,
                agent_name=response.agent_name,
                action="thinking",
            )
            return

        if response.response_type == "tool_call":
            tool_name = response.tool_name or "<unknown tool>"

            args = response.arguments
            if args is None:
                args_preview = ""
            else:
                try:
                    args_preview = json.dumps(args, ensure_ascii=False)
                except Exception:
                    args_preview = str(args)

            if len(args_preview) > 50:
                args_preview = args_preview[:50] + "..."

            preview_suffix = f"({args_preview})" if args_preview else "()"
            # print(f"{response.agent_name} is invoking {tool_name}{preview_suffix}...\n")
            print(
                format_agent_message(
                    name=response.agent_name,
                    content=f"{response.agent_name} is invoking {tool_name}{preview_suffix}...",
                    timestamp="",
                )
            )

            await telemetry.update_agent_activity(
                process_id=self.task_param.process_id,
                agent_name=response.agent_name,
                action="analyzing",
                tool_name=f"{tool_name} {args_preview}".strip(),
                tool_used=True,
            )
            return
