"""
Analysis Step Orchestration for Migration Process.

This module provides specialized orchestration for the Analysis step:
- File discovery and platform detection
- Chief Architect leads the analysis
- Platform experts (EKS, GKE) provide source identification
- Azure expert provides migration context

Following SK Process Framework best practices:
- Focused on analysis step responsibility
            ChatMessageContent(
                role=AuthorRole.USER,
                # "Select the next participant for analysis step.",
            ),
        )

        # EXTREME truncation to prevent context length errors
        # With 3,389 function tokens, we need to be even more aggressive
        self._smart_truncate_chat_history_with_token_limit(
            chat_history,
            max_total_tokens=3000,  # Optimized: Reduced for cost efficiency
            max_messages=8,         # Optimized: Reasonable message count
            max_tokens_per_message=400,  # Optimized: Reduced to 400 tokens per message
        )nation criteria
- Expert agent coordination
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

from agents.agent_info_util import MigrationPhase
from agents.eks_expert.agent_info import get_agent_info as eks_expert
from agents.gke_expert.agent_info import get_agent_info as gke_expert
from agents.technical_architect.agent_info import get_agent_info as architect_agent
from libs.steps.orchestration.base_orchestrator import (
    StepGroupChatOrchestrator,
    StepSpecificGroupChatManager,
)
from libs.steps.orchestration.models.analysis_result import (
    Analysis_ExtendedBooleanResult,
)
from utils.agent_selection_parser import parse_agent_selection_safely
from utils.chat_completion_retry import (
    get_chat_message_content_with_retry,
    get_orchestration_retry_config,
)

logger = logging.getLogger(__name__)


# Hard Termination Reason Categories
class AnalysisHardTerminationReasons:
    """Constants for hard termination blocking issues in Analysis step."""

    NO_YAML_FILES = "NO_YAML_FILES"
    NO_KUBERNETES_CONTENT = "NO_KUBERNETES_CONTENT"
    ALL_CORRUPTED = "ALL_CORRUPTED"
    SECURITY_POLICY_VIOLATION = "SECURITY_POLICY_VIOLATION"
    RAI_POLICY_VIOLATION = "RAI_POLICY_VIOLATION"
    NOT_EKS_GKE_PLATFORM = "NOT_EKS_GKE_PLATFORM"


# Analysis step prompt templates
ANALYSIS_TERMINATION_PROMPT = """
Coordinate {{step_name}}: {{step_objective}}

source folder : {{source_file_folder}}
output folder : {{output_file_folder}}

**USE MCP TOOLS**: datetime_service, azure_blob_io_service, microsoft_docs_service

🔒 **CHIEF ARCHITECT HARD TERMINATION AUTHORITY WITH ANTI-ECHOING** 🔒

**MANDATORY INDEPENDENT VERIFICATION BEFORE ANY HARD TERMINATION:**

Chief Architect has AUTHORITY to make immediate hard termination decisions for OBVIOUS cases, BUT you MUST independently verify ALL findings using MCP tools.

❌ NEVER echo other agents' file discovery results
❌ NEVER terminate based on "agent consensus" without verification
❌ NEVER reference other agents' unverified claims in termination decisions
✅ ALWAYS execute your own MCP tool verification for termination
✅ ALWAYS include your tool outputs in termination reasoning
✅ ALWAYS base hard termination decisions on YOUR independent analysis

**IMMEDIATE HARD TERMINATION SCENARIOS** (Chief Architect Authority):

1. **NO_YAML_FILES**: Zero files with .yaml/.yml extensions found
2. **NO_KUBERNETES_CONTENT**: No files contain required 'apiVersion' + 'kind' fields
3. **ALL_CORRUPTED**: All uploaded files are unreadable or corrupted
4. **SECURITY_POLICY_VIOLATION**: Files contain sensitive information (passwords, keys, PII)
5. **RAI_POLICY_VIOLATION**: Content violates responsible AI policies
6. **NOT_EKS_GKE_PLATFORM**: Valid Kubernetes files but no AWS/GCP cloud provider indicators

**INDEPENDENT VERIFICATION CHECKLIST FOR HARD TERMINATION:**
□ Execute list_blobs_in_container({{container_name}}, {{source_file_folder}}) yourself
□ Execute find_blobs("*.yaml", {{container_name}}, {{source_file_folder}}) yourself
□ Execute find_blobs("*.yml", {{container_name}}, {{source_file_folder}}) yourself
□ Execute read_blob_content() for sample files yourself
□ Verify content claims with direct file analysis yourself
□ Document YOUR MCP tool outputs in termination reasoning

**EXPERT CONSULTATION REQUIRED FOR COMPLEX SCENARIOS:**
- Mixed valid/invalid files requiring expert judgment
- Uncertain platform indicators needing specialist assessment
- Partial Kubernetes content requiring expert evaluation
- Security/RAI concerns needing detailed expert analysis

TERMINATE SUCCESS when:
- Platform identified (EKS/GKE) with high confidence
- All YAML/JSON files discovered, catalogued, and analyzed
- Expert consensus on platform and complete file analysis
- **🔴 MANDATORY FILE VERIFICATION**: `analysis_result.md` generated and verified in {{output_file_folder}}
  - Use `list_blobs_in_container()` to confirm file exists in output folder
  - Use `read_blob_content()` to verify content is properly generated
  - **NO FILES, NO PASS**: Step cannot complete without verified file generation

TERMINATE FAILURE when:
- Technical errors prevent access/operations
- Critical system failures or timeouts
- **HARD TERMINATION**: Any of the 6 obvious scenarios confirmed by independent verification

CONTINUE when:
- Platform uncertain but files exist
- File discovery in progress
- Expert collaboration ongoing
- ANY files show "TBD" or incomplete analysis
- Analysis result file NOT generated
- **ANY MANDATORY FIELD IS MISSING OR NULL**

**MANDATORY FIELD VALIDATION** (ALL FIELDS REQUIRED FOR SUCCESS):
✅ platform_detected: MUST be "EKS", "GKE", or "No Platform - No Files Found" (NOT NULL/empty)
✅ confidence_score: MUST be percentage like "95%" or "N/A - No Files" (NOT NULL/empty)
✅ files_discovered: MUST be complete array OR empty with explanation (NOT NULL)
✅ complexity_analysis: MUST be full object OR empty with explanation (NOT NULL)
✅ migration_readiness: MUST be full object OR empty with explanation (NOT NULL)
✅ expert_insights: MUST contain key contributions from ALL experts (NOT NULL/empty)
✅ analysis_file: MUST be exact path to analysis_result.md (NOT NULL/empty)

**FIELD VALIDATION RULES**:
- NO fields can be null, undefined, or empty strings
- Arrays can be empty BUT must have explanation in the reason field
- Objects can be empty BUT must have explanation in the reason field
- String fields must contain meaningful content (no "TBD", "TODO", or placeholder text)

**CRITICAL: DO NOT TERMINATE WITH SUCCESS IF ANY REQUIRED FIELD IS INCOMPLETE**

**CRITICAL: RESPOND WITH VALID JSON ONLY**

**EVIDENCE-BASED HARD TERMINATION FORMAT** (when is_hard_terminated=true):
{
  "result": true,
  "reason": "INDEPENDENT VERIFICATION: [Your MCP tool commands and actual outputs] + [Your file analysis findings] + [Detailed user remediation guidance]",
  "is_hard_terminated": true,
  "termination_type": "hard_blocked",
  "blocking_issues": ["VERIFIED_ISSUE_CODE"],
  "termination_output": null
}

**HARD TERMINATION REASONING REQUIREMENTS:**
✅ File Analysis: "Executed list_blobs_in_container() - found X files: [list with analysis]"
✅ YAML Verification: "Executed find_blobs('*.yaml') - [actual results]"
✅ Content Analysis: "Executed read_blob_content() on [files] - [specific findings]"
✅ Platform Assessment: "Analyzed content for EKS/GCP indicators - [detailed findings]"
✅ Remediation Steps: "To resolve: 1. [specific action] 2. [specific action] 3. [specific action]"

Example HARD TERMINATION response:
{
  "result": true,
  "reason": "INDEPENDENT VERIFICATION: Executed list_blobs_in_container() and found 3 files: config.txt, readme.md, data.json. Executed find_blobs('*.yaml') returned empty - no YAML files detected. Executed read_blob_content('config.txt') - contains application configuration with no 'apiVersion' or 'kind' fields. BLOCKING ISSUE: NO_KUBERNETES_CONTENT - Zero Kubernetes manifests found for migration analysis. REMEDIATION: 1. Upload YAML files with 'apiVersion: apps/v1' and 'kind: Deployment/Service/ConfigMap' 2. Ensure files contain valid Kubernetes resource definitions 3. Include at least one workload resource for platform detection.",
  "is_hard_terminated": true,
  "termination_type": "hard_blocked",
  "blocking_issues": ["NO_KUBERNETES_CONTENT"],
  "termination_output": null
}

Example SUCCESS response:
{
  "result": true,
  "reason": "Platform identified as EKS with 95% confidence. All files analyzed.",
  "termination_output": {
    "platform_detected": "EKS",
    "confidence_score": "95%",
    "files_discovered": [...],
    ...
  },
  "termination_type": "soft_completion",
  "blocking_issues": []
}

Example CONTINUE response:
{
  "result": false,
  "reason": "Still awaiting file discovery and platform analysis.",
  "termination_output": null,
  "termination_type": "soft_completion",
  "blocking_issues": []
}

NEVER respond with plain text. JSON ONLY.

Only terminate AFTER agents use MCP tools for file discovery and complete analysis.
"""

ANALYSIS_SELECTION_PROMPT = """
Coordinate {{step_name}}: {{step_objective}}
Available: {{participants}}

PLATFORM DETECTION APPROACH:
- Chief_Architect: Strategic oversight and platform detection coordination
- EKS_Expert: EKS configurations analysis (ACTIVE until platform determined)
- GKE_Expert: GKE patterns analysis (ACTIVE until platform determined)

**PLATFORM DETECTION RULES**:
PHASE 1 - Platform Detection: Both EKS and GKE experts actively participate
PHASE 2 - Post Detection: Only the matching platform expert continues
- If EKS detected → Only select EKS_Expert for platform-specific tasks
- If GKE detected → Only select GKE_Expert for platform-specific tasks
- Non-matching expert should be in quiet mode after platform determination

SELECTION PRIORITY:
1. Platform detection and consensus → All experts contribute
2. Post platform detection → Only matching expert participates
3. Complete file analysis with focused platform expertise

**CRITICAL - RESPONSE FORMAT**:
Respond with ONLY the participant name from this exact list:
- Chief_Architect
- EKS_Expert
- GKE_Expert

CORRECT Response Examples:
✅ "Chief_Architect"
✅ "EKS_Expert"
✅ "GKE_Expert"

INCORRECT Response Examples:
❌ "Select Chief_Architect as the next participant to..."
❌ "I choose EKS_Expert because..."
❌ "Next participant: GKE_Expert"
❌ "Success"
❌ "Complete"
❌ "Terminate"

Respond with the participant name only - no explanations, no prefixes, no additional text.
"""

ANALYSIS_RESULT_FILTER_PROMPT = """
Summarize the key findings and insights from the analysis step.
"""

# ANALYSIS_RESULT_FILTER_PROMPT = """
# You are coordinating the {{step_name}} step of Azure Kubernetes migration.
# Step objective: {{step_objective}}

# **IMPORTANT - USE MCP TOOLS FOR ACCURATE DATA**:
# - **Use datetime MCP tool** for ALL timestamp generation (avoid hardcoded dates)
# - **Use blob storage MCP tools** to read actual file content for analysis
# - **Use Microsoft Docs MCP tool** to verify Azure service compatibility

# You have concluded the analysis discussion with expert consensus.
# Provide a structured report aligned with Analysis_ExtendedBooleanResult format:

# {
#     "result": ["Success" or "Fail"],
#     "reason": "[Explanation for the result - why analysis succeeded or failed]",
#     "termination_output": {
#         "platform_detected": "[EKS or GKE - definitive identification only]",
#         "confidence_score": "[percentage like 95%]",
#         "files_discovered": [
#             {
#                 "filename": "[discovered YAML file name]",
#                 "type": "[Deployment, Service, ConfigMap, etc.]",
#                 "complexity": "[Low, Medium, or High]",
#                 "azure_mapping": "[corresponding Azure service/resource]"
#             }
#         ],
#         "complexity_analysis": {
#             "network_complexity": "[network complexity assessment with details]",
#             "security_complexity": "[security complexity assessment with details]",
#             "storage_complexity": "[storage complexity assessment with details]",
#             "compute_complexity": "[compute complexity assessment with details]"
#         },
#         "migration_readiness": {
#             "overall_score": "[overall migration readiness score]",
#             "concerns": ["list of migration concerns"],
#             "recommendations": ["list of migration recommendations"]
#         },
#         "summary": "[comprehensive summary of analysis completion]",
#         "expert_insights": ["key contributions from all participating experts"],
#         "analysis_file": "[path to generated analysis result file]"
#     },
#     "termination_type": "[soft_completion, hard_blocked, hard_error, or hard_timeout]",
#     "blocking_issues": ["specific issues if hard terminated, empty array if successful"]
# }

# REQUIREMENTS:
# - Platform must be definitively EKS or GKE (no mixed classifications)
# - Include ALL discovered files with complete FileType details
# - Capture insights from focused analysis team (Architect, EKS Expert, GKE Expert, Azure Expert, Writer)
# - Align with Analysis_ExtendedBooleanResult model structure
# """


class AnalysisStepGroupChatManager(StepSpecificGroupChatManager):
    """
    Group chat manager specialized for Analysis Step.

    Focus: File discovery, platform detection, initial assessment
    Agents: Chief (lead), EKS Expert, GKE Expert, Azure Expert
    """

    final_termination_result: Analysis_ExtendedBooleanResult | None = None

    async def should_terminate(
        self, chat_history: ChatHistory
    ) -> Analysis_ExtendedBooleanResult:
        """Determine if analysis step is complete."""
        # Track termination evaluation start
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name="Conversation_Manager",
            action="evaluating_termination",
            message_preview="Evaluating if analysis is complete",
        )

        should_terminate = await super().should_terminate(chat_history)

        if should_terminate.result:
            # Track early termination from base class
            await self.telemetry.update_agent_activity(
                process_id=self.process_context.get("process_id"),
                agent_name="Conversation_Manager",
                action="early_termination",
                message_preview="Analysis conversation terminated by base class logic",
            )
            # Convert BooleanResult to Analysis_ExtendedBooleanResult
            return Analysis_ExtendedBooleanResult(
                result=should_terminate.result,
                reason=should_terminate.reason,
            )

        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(
                    ANALYSIS_TERMINATION_PROMPT,
                    source_file_folder=self.process_context["source_file_folder"],
                    output_file_folder=self.process_context["output_file_folder"],
                ),
            ),
        )

        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content="Determine if file discovery and platform analysis is complete.",
            ),
        )

        # Optimized truncation to prevent context length errors while maintaining efficiency
        self._smart_truncate_chat_history(chat_history)
        # self._smart_truncate_chat_history_with_token_limit(
        #     chat_history,
        #     max_total_tokens=6000,  # Optimized: Balanced for termination analysis
        #     max_messages=8,  # Optimized: Sufficient for context
        #     max_tokens_per_message=750,  # Optimized: Balanced per message
        # )

        # response = await get_chat_message_content_with_retry(
        #     self.service,
        #     chat_history,
        #     settings=PromptExecutionSettings(
        #         response_format=Analysis_ExtendedBooleanResult
        #     )
        # )
        response = await get_chat_message_content_with_retry(
            self.service,
            chat_history,
            settings=PromptExecutionSettings(
                response_format=Analysis_ExtendedBooleanResult
            ),
            config=get_orchestration_retry_config(),
            operation_name="should_terminate",
        )

        if not response or not response.content:
            raise RuntimeError("No response content received for termination check")

        termination_with_reason = Analysis_ExtendedBooleanResult.model_validate_json(
            response.content
        )

        recent_message: ChatMessageContent | None = (
            chat_history.messages[-1] if chat_history.messages else None
        )

        if recent_message is not None:
            print("*********************")
            print(
                f"Recent message: role :{recent_message.role}, content: {recent_message.content}"
            )
            print("*********************")

        print(
            f"Should terminate: {termination_with_reason.result}\nReason: {termination_with_reason.reason}."
        )
        print("*********************")

        # Track termination decision
        if termination_with_reason.result:
            await self.telemetry.update_agent_activity(
                process_id=self.process_context.get("process_id"),
                agent_name="Conversation_Manager",
                action="conversation_completed",
                message_preview=f"Analysis conversation completed: {termination_with_reason.reason}",
            )

            self.final_termination_result = termination_with_reason
        else:
            await self.telemetry.update_agent_activity(
                process_id=self.process_context.get("process_id"),
                agent_name="Conversation_Manager",
                action="conversation_continuing",
                message_preview=f"Analysis conversation continues: {termination_with_reason.reason}",
            )

        return termination_with_reason

        # return BooleanResult.model_validate_json(self._safe_get_content(response))

    async def select_next_agent(
        self,
        chat_history: ChatHistory,
        participant_descriptions: dict[str, str],
    ) -> StringResult:
        """Select next agent for analysis step."""
        # Track agent responses first (from base class)
        await super().select_next_agent(chat_history, participant_descriptions)

        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(
                    ANALYSIS_SELECTION_PROMPT,
                    participants="\n".join(
                        [f"{k}: {v}" for k, v in participant_descriptions.items()]
                    ),
                ),
            ),
        )

        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content="""Now select the next participant to speak.
                        Don't pass over to next agent when current agent is still thinking or processing.
                        let him make his work continue with give him a chance to speak again.
                        but don't let him take too long, we need to keep the conversation moving in that case.
                        """,
                # "Select the next participant for analysis step.",
            ),
        )

        # EXTREME truncation to prevent context length errors
        # With 3,389 function tokens, we need to be even more aggressive

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
            step_name="Analysis",
            valid_agents=list(participant_descriptions.keys()),
        )

        logger.info(
            f"[AGENT_SELECTION] Raw AI response: '{participant_name_with_reason.result}'"
        )
        logger.info(
            f"[AGENT_SELECTION] Available participants: {list(participant_descriptions.keys())}"
        )

        # Clean up participant name if it contains extra text
        selected_agent = participant_name_with_reason.result.strip()

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
                    logger.info(
                        f"[AGENT_SELECTION] Extracted participant from pattern: '{potential_participant}'"
                    )
                    selected_agent = potential_participant
                    break

        logger.info(f"[AGENT_SELECTION] Final selected agent: '{selected_agent}'")

        print("*********************")
        print(f"Next participant: {selected_agent}")
        print(f"Reason: {participant_name_with_reason.reason}.")
        print("*********************")

        # Track agent selection in telemetry
        selection_reason = participant_name_with_reason.reason
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name="Conversation_Manager",
            action="expert_selection",
            message_preview=f"Selected {selected_agent} for analysis: {selection_reason}",
        )
        # Mark agent as selected but not yet speaking - they'll be marked as speaking when they actually respond
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
        # return StringResult.model_validate_json(self._safe_get_content(response))

    async def filter_results(
        self,
        chat_history: ChatHistory,
    ) -> MessageResult:
        """Filter and summarize analysis step results."""
        # Track start of results filtering
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name="Conversation_Manager",
            action="analysis_results_filtering_started",
            message_preview="Starting analysis results filtering and summarization",
        )

        if not chat_history.messages:
            raise RuntimeError("No messages in the chat history.")
            raise RuntimeError("No messages in the chat history.")

        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(ANALYSIS_RESULT_FILTER_PROMPT),
            ),
        )

        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content="Please summarize the analysis step results with platform detection and file discovery.",
            ),
        )

        # EXTREME truncation to prevent context length errors
        # With 3,389 function tokens, we need to be even more aggressive
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
            operation_name="filter_results",
        )

        if not response or not response.content:
            raise RuntimeError("No response content received for filter results")

        string_with_reason = StringResult.model_validate_json(response.content)

        # Track successful results filtering completion
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name="Conversation_Manager",
            action="analysis_results_filtering_completed",
            message_preview=f"Analysis results filtering completed: {len(string_with_reason.result)} characters summarized",
        )

        return MessageResult(
            result=ChatMessageContent(
                role=AuthorRole.ASSISTANT, content=string_with_reason.result
            ),
            reason=string_with_reason.reason,
        )


class AnalysisOrchestrator(StepGroupChatOrchestrator):
    """Orchestrator specifically for Analysis step operations."""

    async def create_analysis_orchestration_with_context(
        self, mcp_context, process_context, agent_response_callback=None, telemetry=None
    ) -> GroupChatOrchestration:
        """
        Create group chat orchestration for Analysis Step with provided MCP context from step.

        This method allows the step to pass its own MCP context to ensure agents have proper MCP tool access.

        Args:
            mcp_context: The MCP context created by the step
            process_context: Process context data
            agent_response_callback: Optional callback for agent responses

        Returns:
            GroupChatOrchestration with agents created in the provided MCP context
        """
        self.logger.info(
            "[SEARCH] Creating Analysis Step Group Chat Orchestration with step's MCP context..."
        )

        try:
            self.logger.info("[TOOLS] Creating agents with step's MCP context")
            orchestration = await self._create_analysis_agents(
                mcp_context, process_context, agent_response_callback, telemetry
            )
            return orchestration
        except Exception as e:
            self.logger.error(
                f"[FAILED] Failed to create analysis orchestration with context: {e}"
            )
            raise RuntimeError(f"Analysis orchestration creation failed: {e}") from e

    async def _create_analysis_agents(
        self, mcp_context, process_context, agent_response_callback=None, telemetry=None
    ) -> GroupChatOrchestration:
        """Helper method to create analysis agents with task-local MCP context."""
        # Create focused agent team for analysis
        agents = []

        self.logger.info(
            "[SEARCH] Creating analysis agents with task-local MCP context"
        )

        # Chief Architect - leads analysis
        architect_config = architect_agent(phase=MigrationPhase.ANALYSIS).render(
            **self.process_context
        )
        agent_architect = await mcp_context.create_agent(architect_config)
        agents.append(agent_architect)

        # Platform experts for source detection
        eks_config = eks_expert(phase=MigrationPhase.ANALYSIS).render(
            **self.process_context
        )
        agent_eks = await mcp_context.create_agent(eks_config)
        agents.append(agent_eks)

        gke_config = gke_expert(phase=MigrationPhase.ANALYSIS).render(
            **self.process_context
        )
        agent_gke = await mcp_context.create_agent(gke_config)
        agents.append(agent_gke)

        # # Azure expert for context
        # azure_config = azure_expert(phase=MigrationPhase.ANALYSIS).render(
        #     **self.process_context
        # )
        # agent_azure = await mcp_context.create_agent(azure_config)
        # agents.append(agent_azure)

        # # Technical Writer
        # writer_config = technical_writer_agent(phase=MigrationPhase.ANALYSIS).render(
        #     **self.process_context
        # )
        # agent_writer = await mcp_context.create_agent(writer_config)
        # agents.append(agent_writer)

        orchestration = GroupChatOrchestration(
            members=agents,
            manager=AnalysisStepGroupChatManager(
                step_name="Analysis",
                step_objective="Discover source files and identify platform type",
                service=self.kernel_agent.kernel.services["default"],
                max_rounds=50,  # Reduced from 50 to prevent token overflow while still allowing thorough analysis
                process_context=self.process_context,
                telemetry=telemetry,
            ),
            agent_response_callback=agent_response_callback,  # ✅ Pass callback as constructor parameter
        )

        return orchestration
