# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Orchestrator for the design step.

This module renders the design prompt, prepares MCP tools (including Mermaid),
and runs a `GroupChatOrchestrator` to produce `Design_ExtendedBooleanResult`.
"""

from pathlib import Path
from typing import Any, Callable, MutableMapping, Sequence

from agent_framework import (
    MCPStdioTool,
    MCPStreamableHTTPTool,
    ToolProtocol,
)

from libs.agent_framework.agent_info import AgentInfo
from libs.agent_framework.groupchat_orchestrator import (
    AgentResponse,
    GroupChatOrchestrator,
)
from libs.base.orchestrator_base import OrchestrationResult, OrchestratorBase
from libs.mcp_server.MCPBlobIOTool import get_blob_file_mcp
from libs.mcp_server.MCPMermaidTool import get_mermaid_mcp
from utils.datetime_util import get_current_timestamp_utc
from utils.prompt_util import TemplateUtility

from ...analysis.models.step_output import Analysis_BooleanExtendedResult
from ...design.models.step_output import (
    Design_ExtendedBooleanResult,
)


class DesignOrchestrator(
    OrchestratorBase[Analysis_BooleanExtendedResult, Design_ExtendedBooleanResult]
):
    """
    Orchestrator for the Design step.
    """

    def __init__(self, app_context=None):
        """Create a new orchestrator bound to an application context."""
        super().__init__(app_context)
        self.step_name = "Design"

    async def execute(
        self, task_param: Analysis_BooleanExtendedResult = None
    ) -> OrchestrationResult[Design_ExtendedBooleanResult]:
        """Execute the design step using the upstream analysis output."""
        if task_param is None:
            raise ValueError("task_param cannot be None")
        self.task_param = task_param

        if not self.initialized:
            await self.initialize(process_id=task_param.output.process_id)

        # mem0_memory_manager = self.app_context.get_service(Mem0AsyncMemoryManager)

        current_folder = Path(__file__).parent

        process_id = task_param.output.process_id
        prompt = TemplateUtility.render_from_file(
            str(current_folder / "prompt_task.txt"),
            source_file_folder=f"{process_id}/source",
            output_file_folder=f"{process_id}/converted",
            container_name="processes",
            current_timestamp=get_current_timestamp_utc(),
        )

        async with (
            self.mcp_tools[0],
            self.mcp_tools[1],
            self.mcp_tools[2],
            self.mcp_tools[3],
        ):
            orchestrator = GroupChatOrchestrator[
                Analysis_BooleanExtendedResult, Design_ExtendedBooleanResult
            ](
                name="DesignOrchestrator",
                process_id=task_param.output.process_id,
                participants=self.agents,
                memory_client=None,
                result_output_format=Design_ExtendedBooleanResult,
            )

            orchestration_result = await orchestrator.run_stream(
                input_data=prompt,
                on_agent_response=self.on_agent_response,
                on_workflow_complete=self.on_orchestration_complete,
                on_agent_response_stream=self.on_agent_response_stream,
            )
            return orchestration_result

    async def prepare_mcp_tools(
        self,
    ) -> (
        ToolProtocol
        | Callable[..., Any]
        | MutableMapping[str, Any]
        | Sequence[ToolProtocol | Callable[..., Any] | MutableMapping[str, Any]]
    ):
        """Create and return the MCP tools used by design agents."""
        # Create MCP tools (not connected yet)
        ms_doc_mcp_tool = MCPStreamableHTTPTool(
            name="Microsoft Learn MCP", url="https://learn.microsoft.com/api/mcp"
        )
        fetch_mcp_tool = MCPStdioTool(
            name="Fetch MCP Tool", command="uvx", args=["mcp-server-fetch"]
        )

        blob_io_mcp_tool = get_blob_file_mcp()
        mermaid_mcp_tool = get_mermaid_mcp()

        return [
            ms_doc_mcp_tool,
            fetch_mcp_tool,
            blob_io_mcp_tool,
            mermaid_mcp_tool,
        ]

    async def prepare_agent_infos(self) -> list[Any]:
        """Build the list of agent descriptors participating in design."""
        agent_infos = []

        # Load platform experts from a registry (config-driven).
        registry_dir = Path(__file__).parent
        registry_path = registry_dir / "platform_registry.json"

        # Base directory containing the shared agent prompt files.
        agent_dir = Path(__file__).parent.parent

        for expert in self.load_platform_registry(str(registry_path)):
            agent_name = expert.get("agent_name")
            prompt_file = expert.get("prompt_file")
            if not isinstance(agent_name, str) or not agent_name.strip():
                continue
            if not isinstance(prompt_file, str) or not prompt_file.strip():
                continue

            prompt_path = agent_dir / "agents" / prompt_file
            instruction = self.read_prompt_file(str(prompt_path))

            expert_info = AgentInfo(
                agent_name=agent_name,
                agent_instruction=instruction,
                tools=self.mcp_tools,
            )
            expert_info.render(current_timestamp=get_current_timestamp_utc())
            agent_infos.append(expert_info)

        # Azure-side specialist remains always available.
        aks_instruction = self.read_prompt_file(agent_dir / "agents/prompt_aks.txt")
        aks_agent_info = AgentInfo(
            agent_name="AKS Expert",
            agent_instruction=aks_instruction,
            tools=self.mcp_tools,
        )
        aks_agent_info.render(
            process_id=self.task_param.output.process_id,
            container_name="processes",
            source_file_folder=f"{self.task_param.output.process_id}/source",
            output_file_folder=f"{self.task_param.output.process_id}/converted",
            workspace_file_folder=f"{self.task_param.output.process_id}/workspace",
            current_timestamp=get_current_timestamp_utc(),
        )
        agent_infos.append(aks_agent_info)

        # Read Chief Architect instructions from text file
        architect_instruction = self.read_prompt_file(
            agent_dir / "agents/prompt_architect.txt"
        )

        chief_architect_agent_info = AgentInfo(
            agent_name="Chief Architect",
            agent_instruction=architect_instruction,
            tools=self.mcp_tools,
        )

        chief_architect_agent_info.render(
            process_id=self.task_param.output.process_id,
            container_name="processes",
            source_file_folder=f"{self.task_param.output.process_id}/source",
            output_file_folder=f"{self.task_param.output.process_id}/converted",
            workspace_file_folder=f"{self.task_param.output.process_id}/workspace",
            current_timestamp=get_current_timestamp_utc(),
        )

        agent_infos.append(chief_architect_agent_info)

        coordinator_instruction = self.read_prompt_file(
            registry_dir / "prompt_coordinator.txt"
        )
        coordinator_agent_info = AgentInfo(
            agent_name="Coordinator",
            agent_instruction=coordinator_instruction,
            # Coordinator must be able to (1) read/verify the saved design_result.md from Blob
            # and (2) validate Mermaid blocks in the saved markdown before terminating.
            tools=[self.mcp_tools[2], self.mcp_tools[3]],  # Blob IO + Mermaid
        )

        # Render coordinator prompt with the current participant list.
        # participant_names = [ai.agent_name for ai in agent_infos] + ["Coordinator"]
        participant_names = [ai.agent_name for ai in agent_infos]
        valid_participants_block = "\n".join(
            [f'- "{name}"' for name in participant_names]
        )
        coordinator_agent_info.render(
            process_id=self.task_param.output.process_id,
            container_name="processes",
            source_file_folder=f"{self.task_param.output.process_id}/source",
            output_file_folder=f"{self.task_param.output.process_id}/converted",
            workspace_file_folder=f"{self.task_param.output.process_id}/workspace",
            current_timestamp=get_current_timestamp_utc(),
            step_name="Design",
            step_objective="Design Azure architecture and service mappings for migration based on analysis results",
            participants=", ".join(participant_names),
            valid_participants=valid_participants_block,
        )
        agent_infos.append(coordinator_agent_info)

        # ResultGenerator: Generates structured Design_ExtendedBooleanResult AFTER GroupChat completes
        result_generator_instruction = """
    You are a Result Generator.

    ROLE & RESPONSIBILITY (do not exceed scope):
    - You do NOT decide whether the step succeeded/failed and you do NOT introduce new blockers.
    - The step outcome has already happened via stakeholder discussion and coordinator termination.
    - Your only job is to serialize the final outcome into the required schema exactly.

    RULES:
    - Output MUST be valid JSON only (no markdown, no prose).
    - Do NOT call tools.
    - Do NOT verify file existence.
    - Do NOT add new requirements.
    - Only summarize what participants explicitly said/did.
    - Keep `reason` short (one sentence).

    WHAT TO DO:
    1) Review the conversation (excluding the Coordinator).
    2) Extract the final, agreed design summary, key decisions, and the expected output artifact paths.
    3) Emit JSON that conforms exactly to `Design_ExtendedBooleanResult`.
"""
        result_generator_info = AgentInfo(
            agent_name="ResultGenerator",
            agent_instruction=result_generator_instruction,
            tools=self.mcp_tools,
        )
        agent_infos.append(result_generator_info)

        return agent_infos

    async def on_agent_response(self, response: AgentResponse):
        """Forward a completed agent response to base hooks (telemetry, logging)."""
        # print(f"[{response.timestamp}] :{response.agent_name}: {response.message} | Tool Calls: {response.tool_calls}")
        await super().on_agent_response(response)

    async def on_orchestration_complete(
        self, result: OrchestrationResult[Design_ExtendedBooleanResult]
    ):
        """Handle orchestration completion (console summary)."""
        print("*" * 40)
        print("Design Orchestration complete.")
        print(f"Elapsed: {result.execution_time_seconds:.2f}s")
        print(f"Final Result: {result}")
        print("*" * 40)

    async def on_agent_response_stream(self, response):
        """Forward streaming agent output to base hooks."""
        await super().on_agent_response_stream(response)
