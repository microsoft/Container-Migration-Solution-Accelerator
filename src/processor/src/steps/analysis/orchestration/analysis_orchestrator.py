import logging
from pathlib import Path
from typing import Any, Callable, MutableMapping, Sequence

from agent_framework import MCPStdioTool, MCPStreamableHTTPTool, ToolProtocol

from libs.agent_framework.agent_info import AgentInfo
from libs.agent_framework.groupchat_orchestrator import (
    AgentResponse,
    AgentResponseStream,
    GroupChatOrchestrator,
    OrchestrationResult,
)
from libs.base.orchestrator_base import OrchestratorBase
from libs.mcp_server.MCPBlobIOTool import get_blob_file_mcp
from libs.mcp_server.MCPDatetimeTool import get_datetime_mcp
from utils.prompt_util import TemplateUtility

from ..models.step_output import Analysis_BooleanExtendedResult
from ..models.step_param import Analysis_TaskParam


class AnalysisOrchestrator(
    OrchestratorBase[
        Analysis_TaskParam, OrchestrationResult[Analysis_BooleanExtendedResult]
    ]
):
    def __init__(self, app_context=None):
        super().__init__(app_context)

    async def execute(
        self, task_param: Analysis_TaskParam = None
    ) -> OrchestrationResult[Analysis_BooleanExtendedResult]:
        if task_param is None:
            raise ValueError("task_param cannot be None")
        self.task_param = task_param

        if not self.initialized:
            await self.initialize(process_id=task_param.process_id)

        # Get Current Folder
        current_folder = Path(__file__).parent

        prompt = TemplateUtility.render_from_file(
            str(current_folder / "prompt_task.txt"), **task_param.model_dump()
        )

        async with (
            self.mcp_tools[0],
            self.mcp_tools[1],
            self.mcp_tools[2],
            self.mcp_tools[3],
        ):
            orchestrator = GroupChatOrchestrator[str, Analysis_BooleanExtendedResult](
                name="AnalysisOrchestrator",
                process_id=task_param.process_id,
                participants=self.agents,
                memory_client=None,
                result_output_format=Analysis_BooleanExtendedResult,
            )

            orchestration_result = await orchestrator.run_stream(
                input_data=prompt,
                on_agent_response=self.on_agent_response,
                on_agent_response_stream=self.on_agent_response_stream,
                on_workflow_complete=self.on_orchestration_complete,
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
        # Create MCP tools (not connected yet)
        ms_doc_mcp_tool = MCPStreamableHTTPTool(
            name="Microsoft Learn MCP", url="https://learn.microsoft.com/api/mcp"
        )
        fetch_mcp_tool = MCPStdioTool(
            name="Fetch MCP Tool", command="uvx", args=["mcp-server-fetch"]
        )
        blob_io_mcp_tool = get_blob_file_mcp()
        datetime_mcp_tool = get_datetime_mcp()

        return [ms_doc_mcp_tool, fetch_mcp_tool, blob_io_mcp_tool, datetime_mcp_tool]

    async def prepare_agent_infos(self) -> list[AgentInfo]:
        if self.mcp_tools is None:
            raise ValueError("MCP tools must be prepared before agent infos.")

        """Define all agents for analysis"""
        agent_infos = list[AgentInfo]()

        # steps\analysis
        agent_dir = Path(__file__).parent.parent

        # Load platform experts from a registry (config-driven).
        registry_dir = Path(__file__).parent
        registry_path = registry_dir / "platform_registry.json"

        for expert in self.load_platform_registry(str(registry_path)):
            agent_name = expert.get("agent_name")
            prompt_file = expert.get("prompt_file")
            if not isinstance(agent_name, str) or not agent_name.strip():
                continue
            if not isinstance(prompt_file, str) or not prompt_file.strip():
                continue

            # steps\analysis\agents
            prompt_path = agent_dir / "agents" / prompt_file
            instruction = self.read_prompt_file(str(prompt_path))

            expert_info = AgentInfo(
                agent_name=agent_name,
                agent_instruction=instruction,
                tools=self.mcp_tools,
            )
            expert_info.render(**self.task_param.model_dump())
            agent_infos.append(expert_info)

        # Azure-side specialist remains always available.
        aks_instruction = self.read_prompt_file(agent_dir / "agents/prompt_aks.txt")
        aks_agent_info = AgentInfo(
            agent_name="AKS Expert",
            agent_instruction=aks_instruction,
            tools=self.mcp_tools,
        )
        aks_agent_info.render(**self.task_param.model_dump())
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

        chief_architect_agent_info.render(**self.task_param.model_dump())

        agent_infos.append(chief_architect_agent_info)

        coordinator_instruction = self.read_prompt_file(
            registry_dir / "prompt_coordinator.txt"
        )
        coordinator_agent_info = AgentInfo(
            agent_name="Coordinator",
            agent_instruction=coordinator_instruction,
            tools=self.mcp_tools[2],  # Blob IO tool only
        )

        # Render coordinator prompt with the current participant list.
        participant_names = [ai.agent_name for ai in agent_infos]
        valid_participants_block = "\n".join([
            f'- "{name}"' for name in participant_names
        ])
        coordinator_agent_info.render(
            **self.task_param.model_dump(),
            step_name="Analysis",
            step_objective="ChiefArchitect creates foundation analysis, platform experts enhance with specialization",
            participants=", ".join(participant_names),
            valid_participants=valid_participants_block,
        )
        agent_infos.append(coordinator_agent_info)

        # ResultGenerator: serializes the completed conversation into the output schema.
        result_generator_instruction = """
    You are a Result Generator.

    ROLE & RESPONSIBILITY (do not exceed scope):
    - You do NOT decide whether the step succeeded/failed and you do NOT introduce new blockers.
    - The step outcome has already happened via stakeholder discussion and coordinator termination.
    - Your only job is to serialize the final outcome into the required schema exactly.

    STRICT JSON RULES:
    - Output MUST be valid JSON only (no markdown, no prose).
    - Do NOT call tools.
    - Do NOT verify file existence.
    - Do NOT invent termination codes or blockers.

    HARD-TERMINATION SERIALIZATION RULE (IMPORTANT):
    - Set `is_hard_terminated=true` ONLY if a participant explicitly provided a hard-termination decision with a termination code
      from this exact set: NO_YAML_FILES, NO_KUBERNETES_CONTENT, ALL_CORRUPTED, SECURITY_POLICY_VIOLATION, RAI_POLICY_VIOLATION, PROFANITY_DETECTED, MIXED_PLATFORM_DETECTED.
    - If hard-terminated, `blocking_issues` must be a list of those exact codes ONLY (no extra explanation text inside the list).

        EVIDENCE PRESERVATION (when hard-terminated):
        - The `reason` MUST include a short **Evidence** section listing which file(s) triggered the termination and what was detected.
        - NEVER include secret values (tokens/passwords/private keys/base64 blobs). For Secrets, include only key names + resource metadata.

    WHAT TO DO:
    1) Review the conversation (excluding the Coordinator).
    2) Extract the final agreed facts and any explicit PASS/FAIL sign-offs exactly as stated.
    3) Emit JSON that conforms exactly to `Analysis_ExtendedBooleanResult`.
    """
        result_generator_info = AgentInfo(
            agent_name="ResultGenerator",
            agent_instruction=result_generator_instruction,
            tools=self.mcp_tools,
        )
        result_generator_info.render(**self.task_param.model_dump())
        agent_infos.append(result_generator_info)

        return agent_infos

    async def on_agent_response(self, response: AgentResponse):
        await super().on_agent_response(response)

    async def on_orchestration_complete(
        self, result: OrchestrationResult[Analysis_BooleanExtendedResult]
    ):
        logging.info("Analysis Orchestration complete.")
        logging.info(f"Elapsed: {result.execution_time_seconds:.2f}s")

        print("*" * 40)
        print("Analysis Orchestration complete.")
        print(f"Elapsed: {result.execution_time_seconds:.2f}s")
        print(f"Final Result: {result}")
        print("*" * 40)

    async def on_agent_response_stream(self, response: AgentResponseStream):
        await super().on_agent_response_stream(response)
