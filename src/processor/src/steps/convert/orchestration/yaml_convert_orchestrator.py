# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

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
from libs.mcp_server.MCPDatetimeTool import get_datetime_mcp
from steps.convert.models.step_output import Yaml_ExtendedBooleanResult
from steps.design.models.step_output import Design_ExtendedBooleanResult
from utils.prompt_util import TemplateUtility


class YamlConvertOrchestrator(
    OrchestratorBase[Design_ExtendedBooleanResult, Yaml_ExtendedBooleanResult]
):
    """Orchestrator for the YAML Convert step."""

    def __init__(self, app_context=None):
        super().__init__(app_context)

    async def execute(
        self, task_param: Design_ExtendedBooleanResult | None = None
    ) -> OrchestrationResult[Yaml_ExtendedBooleanResult]:
        if task_param is None:
            raise ValueError("task_param cannot be None")
        if not task_param.process_id:
            raise ValueError(
                "Design_ExtendedBooleanResult.process_id is required for Convert step"
            )

        self.task_param = task_param

        if not self.initialized:
            await self.initialize(process_id=task_param.process_id)

        current_folder = Path(__file__).parent
        process_id = task_param.process_id

        prompt = TemplateUtility.render_from_file(
            str(current_folder / "prompt_task.txt"),
            source_file_folder=f"{process_id}/source",
            output_file_folder=f"{process_id}/output",
            workspace_file_folder=f"{process_id}/workspace",
            container_name="processes",
        )

        async with (
            self.mcp_tools[0],
            self.mcp_tools[1],
            self.mcp_tools[2],
            self.mcp_tools[3],
        ):
            orchestrator = GroupChatOrchestrator[
                Design_ExtendedBooleanResult, Yaml_ExtendedBooleanResult
            ](
                name="YamlConvertOrchestrator",
                process_id=process_id,
                participants=self.agents,
                memory_client=None,
                max_seconds=900,
                result_output_format=Yaml_ExtendedBooleanResult,
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
        ms_doc_mcp_tool = MCPStreamableHTTPTool(
            name="Microsoft Learn MCP", url="https://learn.microsoft.com/api/mcp"
        )
        fetch_mcp_tool = MCPStdioTool(
            name="Fetch MCP Tool", command="uvx", args=["mcp-server-fetch"]
        )
        blob_io_mcp_tool = get_blob_file_mcp()
        datetime_mcp_tool = get_datetime_mcp()

        return [ms_doc_mcp_tool, fetch_mcp_tool, blob_io_mcp_tool, datetime_mcp_tool]

    async def prepare_agent_infos(self) -> list[Any]:
        if self.mcp_tools is None:
            raise ValueError("MCP tools must be prepared before agent infos.")

        agent_infos: list[AgentInfo] = []

        repo_root = Path(__file__).resolve().parents[3]

        # Step-local prompts for Convert (preferred).
        convert_agents_dir = repo_root / "steps" / "convert" / "agents"
        yaml_expert_prompt = convert_agents_dir / "prompt_yaml_expert.txt"
        qa_prompt = convert_agents_dir / "prompt_qa_engineer.txt"
        aks_prompt = convert_agents_dir / "prompt_aks_expert.txt"
        azure_architect_prompt = convert_agents_dir / "prompt_azure_architect.txt"
        architect_prompt = convert_agents_dir / "prompt_architect.txt"

        # Define Parameters to be filled up in template
        render_params = {
            "process_id": self.task_param.process_id,
            "container_name": "processes",
            "source_file_folder": f"{self.task_param.process_id}/source",
            "output_file_folder": f"{self.task_param.process_id}/output",
            "workspace_file_folder": f"{self.task_param.process_id}/workspace",
        }

        yaml_expert_info = AgentInfo(
            agent_name="YAML Expert",
            agent_instruction=self.read_prompt_file(str(yaml_expert_prompt)),
            tools=self.mcp_tools,
        )
        yaml_expert_info.render(**render_params)
        agent_infos.append(yaml_expert_info)

        aks_agent_info = AgentInfo(
            agent_name="AKS Expert",
            agent_instruction=self.read_prompt_file(str(aks_prompt)),
            tools=self.mcp_tools,
        )
        aks_agent_info.render(**render_params)
        agent_infos.append(aks_agent_info)

        azure_architect_info = AgentInfo(
            agent_name="Azure Architect",
            agent_instruction=self.read_prompt_file(str(azure_architect_prompt)),
            tools=self.mcp_tools,
        )
        azure_architect_info.render(**render_params)
        agent_infos.append(azure_architect_info)

        qa_agent_info = AgentInfo(
            agent_name="QA Engineer",
            agent_instruction=self.read_prompt_file(str(qa_prompt)),
            tools=self.mcp_tools,
        )
        qa_agent_info.render(**render_params)
        agent_infos.append(qa_agent_info)

        chief_architect_agent_info = AgentInfo(
            agent_name="Chief Architect",
            agent_instruction=self.read_prompt_file(str(architect_prompt)),
            tools=self.mcp_tools,
        )
        chief_architect_agent_info.render(**render_params)
        agent_infos.append(chief_architect_agent_info)

        # Coordinator
        coordinator_instruction = self.read_prompt_file(
            str(Path(__file__).parent / "prompt_coordinator.txt")
        )
        coordinator_agent_info = AgentInfo(
            agent_name="Coordinator",
            agent_instruction=coordinator_instruction,
            tools=self.mcp_tools[2],  # Blob IO tool only
        )
        participant_names = [ai.agent_name for ai in agent_infos]
        valid_participants_block = "\n".join([
            f'- "{name}"' for name in participant_names
        ])
        coordinator_agent_info.render(
            **render_params,
            step_name="Convert",
            step_objective="Convert source Kubernetes YAML manifests into AKS-ready manifests and produce a conversion report",
            participants=", ".join(participant_names),
            valid_participants=valid_participants_block,
        )
        agent_infos.append(coordinator_agent_info)

        # Result generator
        result_generator_instruction = """
    You are a Result Generator.

    ROLE & RESPONSIBILITY (do not exceed scope):
    - You do NOT decide whether the step succeeded/failed and you do NOT introduce new blockers.
    - The step outcome has already happened via stakeholder discussion and coordinator termination.
    - Your only job is to serialize the final outcome into the required schema exactly.

    RULES:
    - Output MUST be valid JSON only.
    - Do NOT call tools.
    - Do NOT verify file existence.
    - Do NOT invent missing files, blockers, or metrics.
    - Only summarize what participants explicitly stated.
    - Keep `reason` short (one sentence).

    WHAT TO DO:
    1) Review the conversation (excluding the Coordinator).
    2) Extract conversion results (converted files, concerns, metrics, and report path) as stated.
    3) Emit JSON that conforms exactly to `Yaml_ExtendedBooleanResult`.
"""
        result_generator_info = AgentInfo(
            agent_name="ResultGenerator",
            agent_instruction=result_generator_instruction,
            tools=self.mcp_tools,
        )
        agent_infos.append(result_generator_info)

        return agent_infos

    async def on_agent_response(self, response: AgentResponse):
        await super().on_agent_response(response)

    async def on_orchestration_complete(
        self, result: OrchestrationResult[Yaml_ExtendedBooleanResult]
    ):
        print("*" * 40)
        print("Yaml Convert Orchestration complete.")
        print(f"Elapsed: {result.execution_time_seconds:.2f}s")
        print(f"Final Result: {result}")
        print("*" * 40)

    async def on_agent_response_stream(self, response):
        await super().on_agent_response_stream(response)
