"""
Design Step Orchestration Module

This module demonstrates how to control agent selection per phaseYou are coordinating the {{step_name}} step of Azure Kubernetes     "incomplete_reason": "Verified missing source data using MCP tools: check_blob_exists('analysis_result.md') returned False, list_blobs_in_container(source_folder) showed 0 files. Cannot design Azure architecture without source platform analysis.",
    "missing_information": [
      "Source platform analysis (verified: analysis_result.md not found)",
      "Configuration files (verified: source folder empty)",
      "Platform complexity data (confirmed: no analysis output available)"
    ]ion.
Step objective: {{step_objective}}

**IMPORTANT - USE MCP TOOLS FOR ACCURATE DATA**:
- **Use datetime MCP tool** for ALL timestamp generation (avoid hardcoded dates)
- **Use Microsoft Docs MCP tool** to lookup current Azure service information, pricing, and best practices
- **Use blob storage MCP tools** to save design artifacts and access source analysis

You have concluded the design discussion with architectural consensus.
Provide a structured report aligned with Design_ExtendedBooleanResult format:ch orchestrator can specify exactly which agents participate in that phase,
allowing for focused collaboration based on the step's objectives.

Classes:
    DesignStepGroupChatManager: Specialized group chat manager for design step
    DesignOrchestrator: Factory for creating design step orchestrations with custom agent selection
"""

import logging

from semantic_kernel.agents import GroupChatOrchestration
from semantic_kernel.agents.orchestration.group_chat import (
    MessageResult,
    StringResult,
)
from semantic_kernel.connectors.ai.prompt_execution_settings import (
    PromptExecutionSettings,
)
from semantic_kernel.contents import AuthorRole, ChatHistory, ChatMessageContent

# Import specific agents for Design phase
from agents.azure_expert.agent_info import get_agent_info as azure_expert
from agents.eks_expert.agent_info import get_agent_info as eks_expert
from agents.gke_expert.agent_info import get_agent_info as gke_expert
from agents.technical_architect.agent_info import get_agent_info as architect_agent

# Import telemetry utilities
from libs.steps.orchestration.models.design_result import (
    Design_ExtendedBooleanResult,
)
from utils.agent_selection_parser import parse_agent_selection_safely
from utils.chat_completion_retry import (
    get_chat_message_content_with_retry,
    get_orchestration_retry_config,
)

from .base_orchestrator import StepGroupChatOrchestrator, StepSpecificGroupChatManager

logger = logging.getLogger(__name__)


# Design step prompt templates
DESIGN_TERMINATION_PROMPT = """
Coordinate {{step_name}} step: {{step_objective}}

**MANDATORY DUAL OUTPUT REQUIREMENTS**:
1. **Create comprehensive `design_result.md` file** in {{output_file_folder}} (for human consumption)
2. **Return structured JSON data** (for next step processing)

**REQUIRED MARKDOWN REPORT STRUCTURE** (`design_result.md`):
The design_result.md file must contain the following sections in markdown format:

## Azure Architecture Design Summary
- Source platform: [detected platform]
- Target Azure platform: [AKS/other services]
- Design completion status: [Complete/Partial]

## Selected Azure Services
[Detailed list of chosen Azure services with justification]

## Architecture Decisions
[Key design decisions with rationale and trade-offs considered]

## Migration Strategy
[High-level migration approach and phases]

## Security and Compliance
[Security considerations and compliance requirements]

## Performance and Scalability
[Performance expectations and scaling strategy]

## Cost Considerations
[Cost analysis and optimization recommendations]

## Expert Insights
[Summary of insights from Technical Architect and Azure Expert]

**ANALYSIS TASK**: Review the expert conversation and extract the final design results.

source folder : {{source_file_folder}}
output folder : {{output_file_folder}}

**EXTRACTION INSTRUCTIONS**:
Look through the conversation for agent responses that contain the design completion JSON format with these fields:
- result: "Success" or "Fail"
- summary: comprehensive architecture design summary
- azure_services: array of selected Azure services
- architecture_decisions: array of key design decisions with rationale
- outputs: array of generated files with descriptions

TERMINATE SUCCESS when:
- Any agent (Azure_Expert, Chief_Architect) has provided a complete JSON response with all required fields
- **ALL MANDATORY FIELDS are properly populated with meaningful content**
- The JSON contains non-empty arrays for azure_services, architecture_decisions, and outputs
- The result field is set to "Success"
- **DUAL OUTPUT COMPLETED**:
  - Markdown report (`design_result.md`) created and saved to output folder
  - JSON response structure prepared for next step processing
- **🔴 MANDATORY FILE VERIFICATION**: `design_result.md` generated and verified in {{output_file_folder}}
  - Use `list_blobs_in_container()` to confirm file exists in output folder
  - Use `read_blob_content()` to verify content is properly generated
  - **NO FILES, NO PASS**: Step cannot complete without verified file generation
- **🤝 EXPERT COLLABORATION ACHIEVED**: Evidence of consensus-based design decisions
  - Technical Architect and Azure Expert collaboration documented
  - Conflicting recommendations resolved through consensus building
  - Design represents collective expert intelligence, not individual decisions

**MANDATORY FIELD VALIDATION** (ALL FIELDS REQUIRED FOR SUCCESS):
✅ result: MUST be "Success" or "Fail" (NOT NULL/empty)
✅ summary: MUST be comprehensive architecture design summary (NOT NULL/empty/placeholder)
✅ azure_services: MUST be non-empty array of selected Azure services (NOT NULL/empty)
✅ architecture_decisions: MUST be non-empty array of key design decisions with rationale (NOT NULL/empty)
✅ outputs: MUST be non-empty array of generated files with descriptions (NOT NULL/empty)

**FIELD VALIDATION RULES**:
- NO fields can be null, undefined, or empty strings
- Arrays MUST contain at least one meaningful entry (no empty arrays for success)
- Summary must be detailed and comprehensive (no "TBD", "TODO", or placeholder text)
- Each array entry must have meaningful content and proper structure

TERMINATE FAILURE when:
- Agents explicitly indicate failure or blocking issues
- Critical Azure service selections cannot be determined after full discussion
- Expert consensus indicates the design cannot be completed

CONTINUE when:
- No agent has provided the complete JSON termination format yet
- **ANY REQUIRED FIELD IS MISSING OR INCOMPLETE**
- Architecture design discussions are actively progressing
- Agents are still working toward consensus
- JSON response exists but contains empty arrays or placeholder content
- **Dual output not completed**:
  - Design document (`design_result.md`) has not been generated and saved to output folder
  - JSON response structure not ready for next step processing

**CRITICAL: DO NOT TERMINATE WITH SUCCESS IF ANY REQUIRED FIELD IS INCOMPLETE OR CONTAINS PLACEHOLDER CONTENT**

**CRITICAL: EXTRACT THE EXACT JSON PROVIDED BY AGENTS**
If you find a complete design JSON response from any agent in the conversation, extract it exactly and format as:

```json
{
  "result": true,
  "reason": "Design step completed - found complete design JSON from [agent_name]",
  "termination_output": {
    [PASTE THE EXACT AGENT JSON HERE - DO NOT MODIFY]
  },
  "termination_type": "soft_completion",
  "blocking_issues": []
}
```

**IF NO COMPLETE JSON FOUND**, continue the conversation:
```json
{
  "result": false,
  "reason": "Design in progress - agents have not yet provided complete design JSON format",
  "termination_output": null,
  "termination_type": "soft_completion",
  "blocking_issues": []
}
```

**IF EXPLICIT FAILURE DETECTED**, terminate with failure:
```json
{
  "result": true,
  "reason": "Design failed - agents indicated blocking issues",
  "termination_output": {
    "result": "Fail",
    "summary": "Design could not be completed due to [specific reason from agents]",
    "azure_services": [],
    "architecture_decisions": [],
    "outputs": [],
    "incomplete_reason": "[extract reason from agent responses]",
    "missing_information": ["[extract missing items from agent responses]"]
  },
  "termination_type": "hard_blocked",
  "blocking_issues": ["[extract blocking issues from agent responses]"]
}
```

**CRITICAL: YOUR JOB IS TO EXTRACT, NOT CREATE**
- DO NOT create new JSON content
- DO NOT modify agent-provided JSON
- DO NOT add your own architecture decisions
- EXTRACT exactly what agents provided
- If agents provided good JSON → extract it
- If agents didn't provide JSON yet → continue conversation
- If agents indicated failure → extract their failure reasoning

RESPOND WITH VALID JSON ONLY.
"""

DESIGN_SELECTION_PROMPT = """
You are coordinating the {{step_name}} step for {{step_objective}}.
Available participants: {{participants}}

FOCUSED ARCHITECTURE TEAM APPROACH:
Rotate between architectural specialists to build comprehensive Azure design:

- Chief_Architect: Provides strategic oversight and architectural validation
- Azure_Expert: Leads Azure service selection and best practices implementation
- EKS_Expert: Provides source platform context for accurate mapping from EKS to Azure (ONLY if source platform is EKS)
- GKE_Expert: Offers source platform context for accurate mapping from GKE to Azure (ONLY if source platform is GKE)

**PLATFORM-AWARE SELECTION RULES**:
- **Check analysis results** for platform detection (EKS vs GKE)
- **Only select the matching platform expert** for source platform insights
- **Do not select non-matching platform expert** who should be in quiet mode
- Example: If analysis determined EKS → Only select EKS_Expert, avoid selecting GKE_Expert

SELECTION PRIORITY:
1. Ensure ALL relevant architectural experts contribute their specialized knowledge
2. Include ONLY the platform expert matching the detected source platform
3. Build comprehensive Azure architecture through focused collaboration
4. Achieve expert consensus on all major architectural components
5. Create detailed design ready for technical implementation

**CRITICAL - RESPONSE FORMAT**:
Respond with ONLY the participant name from this exact list:
- Chief_Architect
- Azure_Expert
- EKS_Expert
- GKE_Expert

CORRECT Response Examples:
✅ "Chief_Architect"
✅ "Azure_Expert"
✅ "EKS_Expert"
✅ "GKE_Expert"

INCORRECT Response Examples:
❌ "Select Chief_Architect as the next participant to..."
❌ "I choose Azure_Expert because..."
❌ "Next participant: EKS_Expert"
❌ "Success"
❌ "Complete"
❌ "Terminate"

Respond with the participant name only - no explanations, no prefixes, no additional text.
"""
DESIGN_RESULT_FILTER_PROMPT = """
Summarize the key findings and insights from the design step.
"""
# DESIGN_RESULT_FILTER_PROMPT = """
# You are coordinating the {{step_name}} step of Azure Kubernetes migration.
# Step objective: {{step_objective}}

# You have concluded the design discussion with expert consensus.
# Provide a structured report aligned with Design_ExtendedBooleanResult format:

# {
#     "result": ["Success" or "Fail"],
#     "reason": "[Explanation for the result - why design succeeded or failed]",
#     "termination_output": {
#         "result": "[Success or Fail - matches main result]",
#         "summary": "[comprehensive Azure architecture design summary]",
#         "azure_services": ["complete list of recommended Azure services"],
#         "architecture_decisions": ["key architecture decisions with rationale"],
#         "outputs": [
#             {
#                 "file": "[Design document or architecture file path]",
#                 "description": "[Description of design output file]"
#             }
#         ]
#     },
#     "termination_type": "[soft_completion, hard_blocked, hard_error, or hard_timeout]",
#     "blocking_issues": ["specific issues if hard terminated, empty array if successful"]
# }

# REQUIREMENTS:
# - Include ALL Azure services selected during architectural design
# - Document key decisions made by focused architecture team collaboration
# - Create and save ONE comprehensive design document: "design_result.md" with all information
# - List ONLY actually saved files in outputs array (typically just design_result.md)
# - Do NOT include files you haven't created or saved using blob MCP tools
# - Align with Design_ExtendedBooleanResult model structure
# """


class DesignStepGroupChatManager(StepSpecificGroupChatManager):
    """
    Group chat manager specialized for Design Step.

    Focus: Azure architecture design, service mapping, recommendations
    Agents: Chief Architect (lead), Azure Expert, platform experts for context
    """

    final_termination_result: Design_ExtendedBooleanResult | None = None

    async def should_terminate(
        self, chat_history: ChatHistory
    ) -> Design_ExtendedBooleanResult:
        """Determine if design step is complete."""
        # Track termination evaluation start
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name="Conversation_Manager",
            action="evaluating_termination",
            message_preview="Evaluating if design is complete",
        )

        should_terminate = await super().should_terminate(chat_history)

        if should_terminate.result:
            # Track early termination from base class
            await self.telemetry.update_agent_activity(
                process_id=self.process_context.get("process_id"),
                agent_name="Conversation_Manager",
                action="early_termination",
                message_preview="Design conversation terminated by base class logic",
            )
            # Convert BooleanResult to Design_ExtendedBooleanResult
            return Design_ExtendedBooleanResult(
                result=should_terminate.result,
                reason=should_terminate.reason,
            )

        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(
                    DESIGN_TERMINATION_PROMPT,
                    source_file_folder=self.process_context["analysis_result"][
                        "source_file_folder"
                    ],
                    output_file_folder=self.process_context["analysis_result"][
                        "output_file_folder"
                    ],
                    container_name=self.process_context["analysis_result"][
                        "container_name"
                    ],
                ),
            ),
        )

        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content="Determine if Azure architecture design and service mapping is complete.",
            ),
        )

        # Apply optimized truncation before API call to preserve context and reduce tokens
        self._smart_truncate_chat_history(chat_history)
        # self._smart_truncate_chat_history_with_token_limit(
        #     chat_history,
        #     max_total_tokens=6000,  # Optimized: Balanced for design evaluation
        #     max_messages=8,  # Optimized: Sufficient for context
        #     max_tokens_per_message=750,  # Optimized: Balanced per message
        # )

        response = await get_chat_message_content_with_retry(
            self.service,
            chat_history,
            settings=PromptExecutionSettings(
                response_format=Design_ExtendedBooleanResult
            ),
            config=get_orchestration_retry_config(),
            operation_name="should_terminate",
        )

        termination_with_reason = Design_ExtendedBooleanResult.model_validate_json(
            self._safe_get_content(response)
        )

        # Track termination decision
        if termination_with_reason.result:
            await self.telemetry.update_agent_activity(
                process_id=self.process_context.get("process_id"),
                agent_name="Conversation_Manager",
                action="conversation_completed",
                message_preview=f"Design conversation completed: {termination_with_reason.reason}",
            )

            self.final_termination_result = termination_with_reason
        else:
            await self.telemetry.update_agent_activity(
                process_id=self.process_context.get("process_id"),
                agent_name="Conversation_Manager",
                action="conversation_continuing",
                message_preview=f"Design conversation continues: {termination_with_reason.reason}",
            )

        return termination_with_reason

    async def select_next_agent(
        self,
        chat_history: ChatHistory,
        participant_descriptions: dict[str, str],
    ) -> StringResult:
        # Track agent responses first (from base class)
        await super().select_next_agent(chat_history, participant_descriptions)

        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(
                    DESIGN_SELECTION_PROMPT,
                    participants="\n".join(
                        [f"{k}: {v}" for k, v in participant_descriptions.items()]
                    ),
                ),
            ),
        )

        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content="Select the next participant for design step.",
            ),
        )

        # Apply smart truncation before API call to preserve context

        # self._smart_truncate_chat_history_with_token_limit(
        #     chat_history,
        #     max_total_tokens=5000,  # Increased by 50%: 5000 * 1.5 = 7500
        #     max_messages=5,  # Increased by 50%: 2 * 1.5 = 3
        #     max_tokens_per_message=500,  # Increased by 50%: 200 * 1.5 = 300
        # )
        self._smart_truncate_chat_history(chat_history)

        response = await get_chat_message_content_with_retry(
            self.service,
            chat_history,
            settings=PromptExecutionSettings(response_format=StringResult),
            config=get_orchestration_retry_config(),
            operation_name="select_next_agent",
        )

        if not response or not response.content:
            raise RuntimeError("No response content received for agent selection")

        participant_name_with_reason = parse_agent_selection_safely(
            response.content,
            step_name="Design",
            valid_agents=list(participant_descriptions.keys()),
        )

        # Clean up participant name if it contains extra text
        selected_agent = participant_name_with_reason.result.strip()
        
        # CRITICAL: Safety check for invalid agent names that should never be returned
        invalid_agent_names = ["Success", "Complete", "Terminate", "Finished", "Done", "End", "Yes", "No", "True", "False"]
        if selected_agent in invalid_agent_names:
            logger.error(f"[AGENT_SELECTION] Invalid agent name '{selected_agent}' detected from response: '{response.content}'")
            logger.error(f"[AGENT_SELECTION] This indicates a prompt confusion issue - using fallback")
            # Force fallback to Chief_Architect as a safe default
            selected_agent = "Chief_Architect"
            participant_name_with_reason = StringResult(
                result="Chief_Architect", 
                reason=f"Fallback selection due to invalid response: '{participant_name_with_reason.result}'"
            )

        # Remove common prefixes that might be added by the AI
        prefixes_to_remove = [
            "Select ",
            "Selected ",
            "I select ",
            "I choose ",
            "Let me select ",
            "I will select ",
            "Next participant selected: ",
            "Next participant: ",
            "Selected participant: ",
            "Participant: ",
        ]

        for prefix in prefixes_to_remove:
            if selected_agent.startswith(prefix):
                selected_agent = selected_agent[len(prefix) :].strip()
                break

        # Enhanced pattern to extract participant name from various response formats
        import re

        # Enhanced pattern to match various AI response formats
        selection_patterns = [
            r"^(?:Select\s+|Selected\s+|I\s+select\s+|I\s+choose\s+|Let\s+me\s+select\s+|I\s+will\s+select\s+)?(\w+)(?:\s+as\s+the\s+next\s+participant.*)?$",
            r"(\w+)\s+(?:as\s+the\s+next\s+participant|should\s+be\s+next|for\s+the\s+next\s+step)",
            r"Next:\s*(\w+)",
            r"Agent:\s*(\w+)",
        ]

        for pattern in selection_patterns:
            match = re.match(pattern, selected_agent, re.IGNORECASE)
            if match:
                potential_participant = match.group(1)
                # Only use this if it matches one of our known participants
                if potential_participant in participant_descriptions:
                    selected_agent = potential_participant
                    break

        print("*********************")
        print(f"Next participant: {selected_agent}")
        print(f"Reason: {participant_name_with_reason.reason}.")
        print("*********************")

        # Track agent selection in telemetry
        selection_reason = participant_name_with_reason.reason
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name="Conversation_Manager",
            action="agent_selected",
            message_preview=f"Selected {selected_agent} for design: {selection_reason}",
        )
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name=selected_agent,
            action="selected_for_turn",
            message_preview=f"Selected to speak next: {selection_reason}",
        )

        if selected_agent in participant_descriptions:
            return StringResult(
                result=selected_agent, reason=participant_name_with_reason.reason
            )

        raise RuntimeError(
            f"Unknown participant selected: '{selected_agent}' (original: '{participant_name_with_reason.result}'). Available participants: {list(participant_descriptions.keys())}"
        )

    async def filter_results(
        self,
        chat_history: ChatHistory,
    ) -> MessageResult:
        """Filter and summarize design step results."""
        # Track start of results filtering
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name="Conversation_Manager",
            action="design_results_filtering_started",
            message_preview="Starting design results filtering and summarization",
        )

        if not chat_history.messages:
            raise RuntimeError("No messages in the chat history.")
            raise RuntimeError("No messages in the chat history.")

        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(DESIGN_RESULT_FILTER_PROMPT),
            ),
        )

        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content="Please summarize the design step results with Azure architecture and service recommendations.",
            ),
        )

        # Apply smart truncation before API call to preserve context
        self._smart_truncate_chat_history(chat_history)
        # self._smart_truncate_chat_history_with_token_limit(
        #     chat_history,
        #     max_total_tokens=5000,  # Increased by 50%: 5000 * 1.5 = 7500
        #     max_messages=5,  # Increased by 50%: 2 * 1.5 = 3
        #     max_tokens_per_message=500,  # Increased by 50%: 200 * 1.5 = 300
        # )

        response = await get_chat_message_content_with_retry(
            self.service,
            chat_history,
            settings=PromptExecutionSettings(response_format=StringResult),
            config=get_orchestration_retry_config(),
            operation_name="filter_results",
        )

        if not response or not response.content:
            raise RuntimeError("No response content received for filter results")

        string_with_reason = StringResult.model_validate_json(response.content)

        # Track successful results filtering completion
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name="Conversation_Manager",
            action="design_results_filtering_completed",
            message_preview=f"Design results filtering completed: {len(string_with_reason.result)} characters summarized",
        )

        return MessageResult(
            result=ChatMessageContent(
                role=AuthorRole.ASSISTANT, content=string_with_reason.result
            ),
            reason=string_with_reason.reason,
        )


class DesignOrchestrator(StepGroupChatOrchestrator):
    """
    Orchestrator specifically for Design step operations.

    AGENT SELECTION STRATEGY FOR DESIGN PHASE:
    This demonstrates how each phase can control its agent participation.

    Design Phase Agents:
    - Chief Architect: Architectural oversight and design validation
    - Azure Expert: PRIMARY LEAD - Azure services, architecture patterns, best practices
    - EKS Expert: Source platform insights for migration context (optional)
    - GKE Expert: Source platform insights for migration context (optional)

    This is different from Analysis phase which might focus more on Chief Architect leadership,
    or YAML phase which would emphasize YAML Expert + QA Engineer collaboration.
    """

    async def create_design_orchestration_with_context(
        self, mcp_context, process_context, agent_response_callback=None, telemetry=None
    ) -> GroupChatOrchestration:
        """
        Create group chat orchestration for Design Step with provided MCP context from step.

        This method allows the step to pass its own MCP context to ensure agents have proper MCP tool access.

        Args:
            mcp_context: The MCP context created by the step
            process_context: The process context for the migration
            agent_response_callback: Optional callback for agent responses

        Returns:
            GroupChatOrchestration with agents created in the provided MCP context
        """
        self.logger.info(
            "[ART] Creating Design Step Group Chat Orchestration with step's MCP context..."
        )

        try:
            self.logger.info("[TOOLS] Creating agents with step's MCP context")
            orchestration = await self._create_design_agents(
                mcp_context=mcp_context,
                process_context=process_context,
                agent_response_callback=agent_response_callback,
                telemetry=telemetry,
            )
            return orchestration
        except Exception as e:
            self.logger.error(
                f"[FAILED] Failed to create design orchestration with context: {e}"
            )
            raise RuntimeError(f"Design orchestration creation failed: {e}") from e

    async def _create_design_agents(
        self, mcp_context, process_context, agent_response_callback=None, telemetry=None
    ) -> GroupChatOrchestration:
        """
        Create Design-specific agent team.

        This method demonstrates PHASE-SPECIFIC AGENT CONTROL:
        - Different phases can include different agents
        - Different phases can prioritize different agent roles
        - Agent selection is tailored to phase objectives
        """
        agents = []

        # Chief Architect - Architecture oversight and validation
        # In Design phase: Provides oversight and ensures architectural soundness
        agent_architect = await mcp_context.create_agent(
            agent_config=architect_agent(phase="design").render(**self.process_context),
            service_id="default",
        )
        agents.append(agent_architect)

        # Azure Expert - PRIMARY LEAD for Design phase
        # In Design phase: Leads the architecture design, recommends Azure services
        agent_azure = await mcp_context.create_agent(
            agent_config=azure_expert(phase="design").render(**self.process_context),
            service_id="default",
        )
        agents.append(agent_azure)

        # Platform experts - Provide source platform context for design decisions
        # In Design phase: Help translate source requirements to Azure architecture

        # Note: In a real implementation, you might conditionally include these
        # based on detected source platform from Analysis phase
        agent_eks = await mcp_context.create_agent(
            agent_config=eks_expert(phase="design").render(**self.process_context),
            service_id="default",
        )
        agents.append(agent_eks)

        agent_gke = await mcp_context.create_agent(
            agent_config=gke_expert(phase="design").render(**self.process_context),
            service_id="default",
        )
        agents.append(agent_gke)

        # Notice: No QA Engineer or YAML Expert in Design phase
        # This shows how each phase can have its own focused agent team

        # Create design-specific orchestration
        orchestration = GroupChatOrchestration(
            members=agents,
            manager=DesignStepGroupChatManager(
                step_name="Design",
                step_objective="Design Azure architecture and service mappings for migration",
                service=self.kernel_agent.kernel.services["default"],
                max_rounds=100,
                process_context=process_context,
                telemetry=telemetry,  # Design needs more rounds for architecture decisions and collaboration
            ),
            agent_response_callback=agent_response_callback,
        )

        return orchestration
