"""
YAML Step Orchestration Module

This module demonstrates phase-specific agent selection for YAML
You are coordinating the {{step_name}} step of Azure Kubernetes migration.
Step objective: {{step_objective}}

**IMPORTANT - USE MCP TOOLS FOR ACCURATE DATA**:
- **Use datetime MCP tool** for ALL timestamp generation (avoid hardcoded dates)
- **Use Microsoft Docs MCP tool** to lookup current AKS configuration syntax and Azure resource specifications
- **Use blob storage MCP tools** to read source files and save converted YAML configurations

You have concluded the YAML conversion discussion with technical consensus.
Provide a structured report aligned with Yaml_ExtendedBooleanResult format:sion.
The YAML phase focuses on technical implementation with validation,
requiring a different agent mix than Analysis or Design phases.

Classes:
    YamlStepGroupChatManager: Specialized group chat manager for YAML step
    YamlOrchestrator: Factory for creating YAML step orchestrations with conversion-focused agents
"""

import logging
import re
import unicodedata

from semantic_kernel.agents import GroupChatOrchestration
from semantic_kernel.agents.orchestration.group_chat import (
    MessageResult,
    StringResult,
)
from semantic_kernel.connectors.ai.prompt_execution_settings import (
    PromptExecutionSettings,
)
from semantic_kernel.contents import AuthorRole, ChatHistory, ChatMessageContent

from agents.azure_expert.agent_info import get_agent_info as azure_expert
from agents.qa_engineer.agent_info import get_agent_info as qa_engineer
from agents.technical_writer.agent_info import get_agent_info as technical_writer

# Import specific agents for YAML phase - notice the different selection!
from agents.yaml_expert.agent_info import get_agent_info as yaml_expert

# Import YAML result models
from libs.steps.orchestration.models.yaml_result import (
    Yaml_ExtendedBooleanResult,
)
from utils.agent_selection_parser import parse_agent_selection_safely

# Import telemetry utilities
from utils.chat_completion_retry import (
    get_chat_message_content_with_retry,
    get_orchestration_retry_config,
)

from .base_orchestrator import StepGroupChatOrchestrator, StepSpecificGroupChatManager

logger = logging.getLogger(__name__)


# YAML step prompt templates
YAML_TERMINATION_PROMPT = """
You are coordinating the {{step_name}} step of Azure Kubernetes migration.
Objective: {{step_objective}}

Source folder : {{source_file_folder}}
Output folder : {{output_file_folder}}

**MANDATORY DUAL OUTPUT REQUIREMENTS**:
1. **Create comprehensive `file_converting_result.md` file** in {{output_file_folder}} (for human consumption)
2. **Return structured JSON data** (for next step processing)

**REQUIRED MARKDOWN REPORT STRUCTURE** (`file_converting_result.md`):
The file_converting_result.md file must contain the following sections in markdown format:

## YAML Conversion Summary
- Total files converted: [number]
- Overall conversion accuracy: [percentage]
- Conversion completion status: [Complete/Partial]

## File Conversion Details
[Table format listing each source file, converted file, status, and accuracy]

## Multi-Dimensional Analysis
### Network Conversion
[Assessment of network-related conversions]

### Security Conversion
[Assessment of security-related conversions]

### Storage Conversion
[Assessment of storage-related conversions]

### Compute Conversion
[Assessment of compute-related conversions]

## Azure Enhancements Applied
[List of Azure-specific optimizations and improvements]

## Quality Validation Results
[QA verification findings and validation status]

## Expert Insights
[Summary of insights from YAML Expert, Azure Expert, and QA Engineer]

**CRITICAL REQUIREMENT: ALL MANDATORY EXECUTION STEPS MUST BE COMPLETED**

**MANDATORY STEPS VERIFICATION BEFORE TERMINATION**:
1. **Step 1 Completed**: Source files discovered using blob operations tool
2. **Step 2 Completed**: Each file read and converted to Azure format
3. **Step 3 Completed**: All converted files saved to output folder using blob operations tool
4. **Step 4 MANDATORY**: QA verification performed - output folder checked, file count verified, content quality checked
5. **Step 5 Completed**: Conversion report (`file_converting_result.md`) created and saved

**AGENT ROLE ASSIGNMENTS FOR MANDATORY STEPS**:
- **YAML Expert**: Steps 1-3 (Discovery, Conversion, Saving) - Lead technical implementation
- **Azure Expert**: Step 2 (Conversion) - Provide Azure-specific guidance and optimization
- **QA Engineer**: Step 4 (Verification) - MANDATORY verification of all saved files
- **Technical Writer**: Step 5 (Reporting) - Create and save comprehensive conversion report (`file_converting_result.md`)

**QA VERIFICATION REQUIREMENTS (MANDATORY FOR SUCCESS)**:
- QA Engineer MUST verify: check for the presence of all expected output files in the output folder
- QA Engineer MUST confirm: Each converted file exists in output folder
- QA Engineer MUST validate: File content is properly converted Azure YAML format
- QA Engineer MUST report: Specific file names, paths, and verification status

**CRITICAL REQUIREMENT: COMPLETE DATA POPULATION MANDATORY**
You MUST populate ALL fields in the Yaml_ExtendedBooleanResult structure. Incomplete responses will be rejected.

**IMPORTANT - USE MCP TOOLS FOR ACCURATE DATA**:
- **Use datetime MCP tool(datetime_service)** for ALL timestamp generation (avoid hardcoded dates)
- **Use blob storage MCP tools (azure_blob_io_service)** to read actual file content for analysis
- **Use Microsoft Docs MCP tool(microsoft_docs_service)** to verify Azure service compatibility

**MANDATORY BLOB VERIFICATION BEFORE TERMINATION**:
Before concluding files are missing, agents MUST:
1. **Use `list_blobs_in_container()` with correct container and folder path**
3. **Use `find_blobs()` with wildcard patterns** (*.yaml, *.yml) to search comprehensively
4. **Check both direct folder paths and recursive searches** to ensure thorough discovery
5. **Report the EXACT blob commands used and their results** in the conversation

**NEVER assume files are missing without explicit blob tool verification**

TERMINATION DECISION CRITERIA:

TERMINATE WITH SUCCESS when:
- **ALL 5 MANDATORY STEPS COMPLETED**: Discovery, conversion, saving, QA verification, and reporting
- **QA VERIFICATION PASSED**: QA Engineer confirmed all files saved and accessible in output folder
- **DUAL OUTPUT COMPLETED**:
  - Markdown report (`file_converting_result.md`) created and saved to output folder
  - JSON response structure prepared for next step processing
- **ALL MANDATORY FIELDS PROPERLY POPULATED**: Every required field contains meaningful content
- All source YAML files have been successfully converted to Azure-compatible format
- Conversion accuracy meets quality standards for each file
- Azure-specific enhancements have been applied where appropriate
- Multi-dimensional analysis completed (network, security, storage, compute)
- Expert consensus achieved on all conversion quality and validation
- **Files have been ACTUALLY SAVED and VERIFIED using blob tools**
- **🤝 EXPERT COLLABORATION ACHIEVED**: Evidence of consensus-based conversion decisions
  - YAML Expert, Azure Expert, and QA Engineer collaboration documented
  - Technical conflicts resolved through collaborative consensus building
  - Conversion quality validated through collective expert agreement
  - Final results represent collaborative technical intelligence, not individual decisions

**MANDATORY FIELD VALIDATION** (ALL FIELDS REQUIRED FOR SUCCESS):
✅ result: MUST be true (NOT NULL)
✅ reason: MUST be detailed completion reason including QA verification status (NOT NULL/empty)
✅ termination_output: MUST contain complete YamlOutput structure with:
  ✅ converted_files: MUST be complete list with ALL conversion details, each file having:
     - source_file: actual file name (NOT template/placeholder)
     - converted_file: actual converted file name (NOT template/placeholder)
     - conversion_status: "success" or specific status (NOT NULL/empty)
     - accuracy_rating: actual percentage (NOT NULL/placeholder)
     - concerns: actual concerns or empty array (NOT NULL)
     - azure_enhancements: actual enhancements or empty array (NOT NULL)
  ✅ multi_dimensional_analysis: ALL four dimensions (network, security, storage, compute) with complete analysis (NOT NULL/empty)
  ✅ overall_conversion_metrics: ALL metrics populated with actual numbers (NOT NULL/placeholder)
  ✅ conversion_quality: ALL quality aspects with actual assessments (NOT NULL/empty)
  ✅ summary: Comprehensive summary including QA verification results (NOT NULL/empty/placeholder)
  ✅ expert_insights: List of actual contributions including QA verification details (NOT NULL/empty)
  ✅ conversion_report_file: Full path to actual `file_converting_result.md` report file saved to output folder (NOT NULL/placeholder)
✅ termination_type: MUST be "soft_completion"
✅ blocking_issues: MUST be empty array for success

**FIELD VALIDATION RULES**:
- NO fields can be null, undefined, or empty strings
- NO placeholder content like "TBD", "TODO", "template", "example"
- Arrays can be empty BUT must represent actual analysis results
- File names must be ACTUAL discovered files, not templates
- Percentages and numbers must be real calculated values
- QA verification details must be included in summary and expert_insights

TERMINATE WITH FAILURE when:
- **QA VERIFICATION FAILED**: Files not found in output folder or inaccessible
- **MANDATORY STEPS INCOMPLETE**: Any of the 5 required steps not completed
- **After comprehensive blob tool verification**, source files are confirmed missing from ALL possible locations
- Critical files cannot be converted to valid Azure format
- Conversion accuracy falls below acceptable standards
- Essential Azure compatibility requirements cannot be met
- Expert consensus cannot be achieved on conversion quality

**CONTINUE PROCESSING when**:
- **QA verification not yet performed** - QA Engineer must check output folder and converted files
- **Files not yet saved** - Conversion work in progress but files not saved to blob storage
- Agents report files are missing but have NOT used comprehensive blob tool verification
- Initial blob searches failed but alternative paths haven't been tried
- Blob operations need retries due to transient errors
- Conversion work is in progress but not yet complete

**MANDATORY: When terminating with FAILURE due to missing files, you MUST include:**
- **Exact blob commands tried** (list_blobs_in_container, find_blobs, etc.)
- **All folder paths searched** (source, workspace, output folders)
- **Container names and folder patterns used**
- **Specific error messages from blob operations**
- **Evidence that comprehensive search was performed using MCP blob tools**

**MANDATORY: When terminating with SUCCESS, you MUST populate EVERY field in Yaml_ExtendedBooleanResult:**
- You must get confirmation from QA Engineer about terminating with SUCCESS
- QA Engineer must verify all converted files has been saved in the output folder
- result: true
- reason: "Detailed completion reason including QA verification status"
- termination_output: MUST contain complete YamlOutput structure with:
  - converted_files: Complete list with ALL conversion details (source_file, converted_file, conversion_status, accuracy_rating, concerns, azure_enhancements)
  - multi_dimensional_analysis: ALL four dimensions (network, security, storage, compute) with complete DimensionalAnalysis
  - overall_conversion_metrics: ALL metrics (total_files, successful_conversions, failed_conversions, overall_accuracy, azure_compatibility)
  - conversion_quality: ALL quality aspects (azure_best_practices, security_hardening, performance_optimization, production_readiness)
  - summary: Comprehensive summary string including QA verification results
  - expert_insights: List of key contributions from participating experts INCLUDING QA verification details
  - conversion_report_file: Full path to conversion report
- termination_type: "soft_completion"
- blocking_issues: [] (empty array for success)

TERMINATE WITH FAILURE when:
- Critical files cannot be converted to valid Azure format
- Conversion accuracy falls below acceptable standards
- Essential Azure compatibility requirements cannot be met
- Expert consensus cannot be achieved on conversion quality

**MANDATORY: When terminating with FAILURE, you MUST still populate ALL fields:**
- result: false
- reason: "Specific failure reason including QA verification status"
- termination_output: null (only for failures)
- termination_type: "hard_blocked", "hard_error", or "hard_timeout"
- blocking_issues: Specific blocking issues that prevent completion

CONTINUE CONVERSION when:
- YAML conversion work is actively progressing
- Expert collaboration is ongoing with productive conversion improvements
- Quality validation and enhancement work is in development
- **ANY MANDATORY FIELD IS MISSING OR INCOMPLETE**
- **ANY FIELD CONTAINS PLACEHOLDER CONTENT** (TBD, TODO, template names, etc.)
- QA verification has not been completed or confirmed
- Files have not been verified as saved in output folder
- **Dual output not completed**:
  - Conversion report (`file_converting_result.md`) has not been generated and saved to output folder
  - JSON response structure not ready for next step processing
- Technical Writer has not yet created the comprehensive conversion report

**CRITICAL: DO NOT TERMINATE WITH SUCCESS IF ANY REQUIRED FIELD IS INCOMPLETE OR CONTAINS PLACEHOLDER CONTENT**

**VALIDATION REQUIREMENT**: Your response MUST include complete data for ALL required fields. Partial or incomplete responses will cause pipeline failures.

**🚨 CRITICAL: USE ACTUAL DISCOVERED FILES ONLY**
❌ DO NOT use template names like "deployment.yaml", "service.yaml"
✅ MUST use actual discovered file names from analysis step
✅ Reference files found in source blob storage operations
✅ Source file names MUST match actual discovered files (NOT examples)

**CRITICAL: RESPOND WITH VALID JSON ONLY**

Example SUCCESS response:
{
  "result": true,
  "reason": "All 5 mandatory steps completed. QA verification passed. Dual output completed: markdown report saved and JSON response prepared. 4 YAML files converted to Azure format with 95% accuracy.",
  "termination_output": {
    "converted_files": [
      {
        "source_file": "[ACTUAL_DISCOVERED_FILE_NAME]",
        "converted_file": "[AZURE_CONVERTED_FILE_NAME]",
        "conversion_status": "Success",
        "accuracy_rating": "95%",
        "concerns": [],
        "azure_enhancements": ["AKS optimizations", "Azure networking"]
      }
    ],
    "multi_dimensional_analysis": {
      "network_analysis": {...},
      "security_analysis": {...},
      "storage_analysis": {...},
      "compute_analysis": {...}
    },
    "overall_conversion_metrics": {...},
    "conversion_quality": {...},
    "summary": "All YAML files successfully converted and verified by QA Engineer. Comprehensive conversion report generated.",
    "expert_insights": ["YAML Expert: Conversions completed", "QA Engineer: All files verified", "Technical Writer: Conversion report created"],
    "conversion_report_file": "{{output_file_folder}}/file_converting_result.md"
  },
  "termination_type": "soft_completion",
  "blocking_issues": []
}

Example CONTINUE response:
{
  "result": false,
  "reason": "QA verification not yet performed. Conversion report (file_converting_result.md) not yet created. Field validation check: [LIST INCOMPLETE FIELDS FROM CHECKLIST ABOVE]",
  "termination_output": null,
  "termination_type": "soft_completion",
  "blocking_issues": ["incomplete_qa_verification", "missing_conversion_report", "incomplete_field_population"]
}

Example FAILURE response:
{
  "result": false,
  "reason": "QA verification failed. No converted files found in output folder despite agents claiming success.",
  "termination_output": null,
  "termination_type": "hard_blocked",
  "blocking_issues": ["Files not saved to output folder", "QA verification failed"]
}

**TERMINATION VALIDATION CHECKLIST**:
□ Source file names match actual discovered files (NOT template examples)
□ No hardcoded names like "deployment.yaml" or "service.yaml" used
□ File names verified through actual blob storage operations
□ QA Engineer confirmed file existence and content quality

NEVER respond with plain text. JSON ONLY.

Respond with structured termination decision using complete Yaml_ExtendedBooleanResult format.
All conversions must be Azure-compatible and validated.
"""

YAML_SELECTION_PROMPT = """
You are coordinating the {{step_name}} step for {{step_objective}}.
Available participants: {{participants}}

**IMPORTANT**: Before any agent reports that files are missing, they MUST use comprehensive blob search strategies:

**MANDATORY BLOB SEARCH PROTOCOL**:
1. **Use `list_blobs_in_container(container_name, folder_path, recursive=True)` with exact process folder**
2. **Try alternative folder patterns**: source/, workspace/, output/, root level
3. **Use `find_blobs(pattern, container_name, folder_path)` with wildcards**: *.yaml, *.yml, *deployment*, *service*

4. **Report the EXACT blob commands used and their results**

**NEVER select an agent to conclude files are missing unless they have used ALL these search methods**

FOCUSED CONVERSION TEAM APPROACH:
Rotate between technical specialists to achieve high-quality YAML conversion:

- YAML_Expert: Leads technical conversion and format validation with deep YAML expertise - **MUST use comprehensive blob search before reporting files missing**
- Azure_Expert: Ensures Azure compatibility and applies platform-specific best practices - **MUST verify storage access and permissions thoroughly**
- QA_Engineer: Validates conversion accuracy, quality standards, and production readiness - **MUST perform final verification of all search attempts**
- Technical_Writer: Creates comprehensive conversion reports and documentation - **MUST save file_converting_result.md report after QA verification**

SELECTION PRIORITY:
1. **First Priority**: Select agents who will perform thorough blob verification using multiple search patterns
2. Ensure ALL conversion specialists contribute their technical expertise
3. Achieve comprehensive Azure compatibility through focused technical work
4. Build consensus on conversion accuracy and quality validation
5. Create validated, production-ready Azure YAML configurations

**Agent Selection Rules**:
- If files reported missing but comprehensive search not performed → Select agent to do thorough verification
- If one search method failed → Select agent to try alternative patterns and locations
- If blob access issues → Select Azure_Expert to troubleshoot storage permissions
- Only after comprehensive verification → Proceed with conversion or escalation

Select the next participant who can provide the most valuable technical conversion contribution or perform necessary blob verification.

**CRITICAL - RESPONSE FORMAT**:
Respond with ONLY the participant name from this exact list:
- YAML_Expert
- Azure_Expert
- QA_Engineer
- Technical_Writer

CORRECT Response Examples:
✅ "QA_Engineer"
✅ "Azure_Expert"

INCORRECT Response Examples:
❌ "Selected QA_Engineer as the next participant to..."
❌ "I choose Azure_Expert because..."
❌ "Next participant: QA_Engineer"

Respond with the participant name only - no explanations, no prefixes, no additional text.
"""

YAML_RESULT_FILTER_PROMPT = """
Summarize the key findings and insights from the YAML conversion step.
"""

# YAML_RESULT_FILTER_PROMPT = """
# You are coordinating the {{step_name}} step of Azure Kubernetes migration.
# Step objective: {{step_objective}}

# You have concluded the YAML conversion discussion with expert consensus.
# Provide a structured report aligned with Yaml_ExtendedBooleanResult format:

# {
#     "result": ["Success" or "Fail"],
#     "reason": "[Explanation for the result - why conversion succeeded or failed]",
#     "termination_output": {
#         "converted_files": [
#             {
#                 "source_file": "[original source file name]",
#                 "converted_file": "[Azure converted file name]",
#                 "conversion_status": "[Success, Partial, or Failed]",
#                 "accuracy_rating": "[percentage like 95%]",
#                 "concerns": ["list of any conversion concerns"],
#                 "azure_enhancements": ["Azure-specific enhancements applied"]
#             }
#         ],
#         "multi_dimensional_analysis": {
#             "network_analysis": {
#                 "complexity": "[Low, Medium, or High]",
#                 "converted_components": ["list of network components converted"],
#                 "azure_optimizations": "[Azure networking optimizations applied]",
#                 "concerns": ["network conversion concerns"],
#                 "success_rate": "[network conversion success percentage]"
#             },
#             "security_analysis": {
#                 "complexity": "[Low, Medium, or High]",
#                 "converted_components": ["list of security components converted"],
#                 "azure_optimizations": "[Azure security optimizations applied]",
#                 "concerns": ["security conversion concerns"],
#                 "success_rate": "[security conversion success percentage]"
#             },
#             "storage_analysis": {
#                 "complexity": "[Low, Medium, or High]",
#                 "converted_components": ["list of storage components converted"],
#                 "azure_optimizations": "[Azure storage optimizations applied]",
#                 "concerns": ["storage conversion concerns"],
#                 "success_rate": "[storage conversion success percentage]"
#             },
#             "compute_analysis": {
#                 "complexity": "[Low, Medium, or High]",
#                 "converted_components": ["list of compute components converted"],
#                 "azure_optimizations": "[Azure compute optimizations applied]",
#                 "concerns": ["compute conversion concerns"],
#                 "success_rate": "[compute conversion success percentage]"
#             }
#         },
#         "overall_conversion_metrics": {
#             "total_files": "[total number of files processed]",
#             "successful_conversions": "[number of successful conversions]",
#             "failed_conversions": "[number of failed conversions]",
#             "overall_accuracy": "[overall accuracy percentage]",
#             "azure_compatibility": "[Azure compatibility percentage]"
#         },
#         "conversion_quality": {
#             "azure_best_practices": "[Azure best practices implementation status]",
#             "security_hardening": "[Security hardening implementation status]",
#             "performance_optimization": "[Performance optimization status]",
#             "production_readiness": "[Production readiness assessment]"
#         },
#         "summary": "[comprehensive summary of YAML conversion completion]",
#         "expert_insights": ["key contributions from all participating experts"],
#         "conversion_report_file": "[path to conversion report file]"
#     },
#     "termination_type": "[soft_completion, hard_blocked, hard_error, or hard_timeout]",
#     "blocking_issues": ["specific issues if hard terminated, empty array if successful"]
# }

# REQUIREMENTS:
# - Include ALL converted files with complete conversion details and accuracy ratings
# - Document multi-dimensional analysis across network, security, storage, compute
# - Capture insights from focused conversion team (YAML Expert, Azure Expert, QA Engineer)
# - Align with Yaml_ExtendedBooleanResult model structure
# """


class YamlStepGroupChatManager(StepSpecificGroupChatManager):
    """
    Group chat manager specialized for YAML Step.

    Focus: Configuration file conversion, YAML generation, validation
    Agents: YAML Expert (lead), Azure Expert, QA Engineer
    """

    final_termination_result: Yaml_ExtendedBooleanResult | None = None

    async def should_terminate(
        self, chat_history: ChatHistory
    ) -> Yaml_ExtendedBooleanResult:
        """Determine if YAML step is complete."""
        # Track termination evaluation start
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name="Conversation_Manager",
            action="evaluating_termination",
            message_preview="Evaluating if YAML conversion is complete",
        )

        should_terminate = await super().should_terminate(chat_history)
        if should_terminate.result:
            # Track early termination from base class
            await self.telemetry.update_agent_activity(
                process_id=self.process_context.get("process_id"),
                agent_name="Conversation_Manager",
                action="early_termination",
                message_preview="YAML conversation terminated by base class logic",
            )
            # Convert BooleanResult to Yaml_ExtendedBooleanResult
            return Yaml_ExtendedBooleanResult(
                result=should_terminate.result,
                reason=should_terminate.reason,
            )

        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(
                    YAML_TERMINATION_PROMPT,
                    source_file_folder=self.process_context["analysis_result"][
                        "source_file_folder"
                    ],
                    output_file_folder=self.process_context["design_result"][
                        "output_file_folder"
                    ],
                ),
            ),
        )

        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content="Determine if YAML conversion and validation is complete.",
            ),
        )

        # Apply smart truncation before API call to preserve context
        self._smart_truncate_chat_history(chat_history)
        # self._smart_truncate_chat_history_with_token_limit(
        #     chat_history,
        #     max_total_tokens=10000,  # Increased by 50%: 5000 * 1.5 = 7500
        #     max_messages=5,  # Increased by 50%: 2 * 1.5 = 3
        #     max_tokens_per_message=2000,  # Increased by 50%: 200 * 1.5 = 300
        # )

        response = await get_chat_message_content_with_retry(
            self.service,
            chat_history,
            settings=PromptExecutionSettings(
                response_format=Yaml_ExtendedBooleanResult
            ),
            config=get_orchestration_retry_config(),
            operation_name="should_terminate",
        )

        termination_with_reason = Yaml_ExtendedBooleanResult.model_validate_json(
            self._safe_get_content(response)
        )

        # Track termination decision
        if termination_with_reason.result:
            await self.telemetry.update_agent_activity(
                process_id=self.process_context.get("process_id"),
                agent_name="Conversation_Manager",
                action="conversation_completed",
                message_preview=f"YAML conversation completed: {termination_with_reason.reason}",
            )

            self.final_termination_result = termination_with_reason
        else:
            await self.telemetry.update_agent_activity(
                process_id=self.process_context.get("process_id"),
                agent_name="Conversation_Manager",
                action="conversation_continuing",
                message_preview=f"YAML conversation continues: {termination_with_reason.reason}",
            )

        return termination_with_reason

    async def select_next_agent(
        self,
        chat_history: ChatHistory,
        participant_descriptions: dict[str, str],
    ) -> StringResult:
        """Select next agent for YAML step."""
        # Track agent responses first (from base class)
        await super().select_next_agent(chat_history, participant_descriptions)

        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(
                    YAML_SELECTION_PROMPT,
                    participants="\n".join(
                        [f"{k}: {v}" for k, v in participant_descriptions.items()]
                    ),
                ),
            ),
        )

        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content="Select the next participant for YAML conversion step.",
            ),
        )

        # Apply smart truncation before API call to preserve context
        self._smart_truncate_chat_history(chat_history)
        # self._smart_truncate_chat_history_with_token_limit(
        #     chat_history,
        #     max_total_tokens=10000,  # Increased by 50%: 5000 * 1.5 = 7500
        #     max_messages=5,  # Increased by 50%: 2 * 1.5 = 3
        #     max_tokens_per_message=2000,  # Increased by 50%: 200 * 1.5 = 300
        # )

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
            step_name="YAML",
            valid_agents=list(participant_descriptions.keys()),
        )

        # Clean up participant name if it contains extra text
        selected_agent = participant_name_with_reason.result.strip()
        
        # CRITICAL: Safety check for invalid agent names that should never be returned
        invalid_agent_names = ["Success", "Complete", "Terminate", "Finished", "Done", "End", "Yes", "No", "True", "False"]
        if selected_agent in invalid_agent_names:
            logger.error(f"[AGENT_SELECTION] Invalid agent name '{selected_agent}' detected from response: '{response.content}'")
            logger.error(f"[AGENT_SELECTION] This indicates a prompt confusion issue - using fallback")
            # Force fallback to YAML_Expert as a safe default for YAML step
            selected_agent = "YAML_Expert"
            participant_name_with_reason = StringResult(
                result="YAML_Expert", 
                reason=f"Fallback selection due to invalid response: '{participant_name_with_reason.result}'"
            )

        # Remove invisible Unicode characters that can cause matching issues
        # Remove zero-width characters and normalize Unicode
        selected_agent = unicodedata.normalize("NFKC", selected_agent)
        selected_agent = re.sub(
            r"[\u200B-\u200D\uFEFF\u2060]", "", selected_agent
        )  # Remove invisible chars
        selected_agent = re.sub(
            r"[^\w_]", "", selected_agent
        )  # Keep only word chars and underscore
        selected_agent = selected_agent.strip()

        # Remove common prefixes that might be added by the AI
        prefixes_to_remove = [
            "Select ",
            "Selected ",  # Past tense
            "I select ",  # First person
            "I selected ",  # First person past tense
            "Choose ",  # Alternative verb
            "Chosen ",  # Alternative past tense
            "Next participant selected: ",
            "Next participant: ",
            "Selected participant: ",
            "Participant: ",
            "The next participant is ",  # Declarative form
            "Next: ",  # Short form
        ]

        for prefix in prefixes_to_remove:
            if selected_agent.startswith(prefix):
                selected_agent = selected_agent[len(prefix) :].strip()
                break

        # Additional pattern matching for complex selections like "Select EKS_Expert as the next..."

        # Enhanced pattern to extract participant name from various response formats
        selection_pattern = r"^(?:(?:I\s+)?(?:Select(?:ed)?|Choose|Chosen)\s+)?(\w+)(?:\s+(?:as\s+the\s+next\s+participant|to\s+perform|for).*)?$"
        match = re.match(selection_pattern, selected_agent, re.IGNORECASE)
        if match:
            potential_participant = match.group(1)
            # Only use this if it matches one of our known participants
            if potential_participant in participant_descriptions:
                selected_agent = potential_participant

        for prefix in prefixes_to_remove:
            if selected_agent.startswith(prefix):
                selected_agent = selected_agent[len(prefix) :].strip()
                break

        print("*********************")
        print(f"Original response: '{participant_name_with_reason.result}'")
        print(f"Cleaned participant: '{selected_agent}'")
        print(f"Available participants: {list(participant_descriptions.keys())}")
        print(f"Reason: {participant_name_with_reason.reason}.")
        print("*********************")

        # Track agent selection in telemetry
        selection_reason = participant_name_with_reason.reason
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name="Conversation_Manager",
            action="agent_selected",
            message_preview=f"Selected {selected_agent} for YAML conversion: {selection_reason}",
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
        """Filter and summarize YAML step results."""
        # Track start of results filtering
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name="Conversation_Manager",
            action="yaml_results_filtering_started",
            message_preview="Starting YAML results filtering and summarization",
        )

        if not chat_history.messages:
            raise RuntimeError("No messages in the chat history.")
            raise RuntimeError("No messages in the chat history.")

        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(YAML_RESULT_FILTER_PROMPT),
            ),
        )

        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content="Please summarize the YAML conversion step results with file conversion details.",
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
            action="yaml_results_filtering_completed",
            message_preview=f"YAML results filtering completed: {len(string_with_reason.result)} characters summarized",
        )

        return MessageResult(
            result=ChatMessageContent(
                role=AuthorRole.ASSISTANT, content=string_with_reason.result
            ),
            reason=string_with_reason.reason,
        )


class YamlOrchestrator(StepGroupChatOrchestrator):
    """
    Orchestrator specifically for YAML step operations.

    AGENT SELECTION STRATEGY FOR YAML PHASE:
    This demonstrates how YAML phase has different agent focus than Design or Analysis.

    YAML Phase Agents (Implementation-focused):
    - YAML Expert: PRIMARY LEAD - Configuration conversion, YAML generation
    - Azure Expert: Azure-specific YAML patterns and configurations
    - QA Engineer: Validation, testing, quality assurance

    Notice: No Chief Architect (design is done) or platform experts (source analysis is done)
    This phase is focused on technical implementation and validation.
    """

    async def create_yaml_orchestration_with_context(
        self, mcp_context, process_context, agent_response_callback=None, telemetry=None
    ) -> GroupChatOrchestration:
        """
        Create group chat orchestration for YAML Step with provided MCP context from step.

        This method allows the step to pass its own MCP context to ensure agents have proper MCP tool access.

        Args:
            mcp_context: The MCP context created by the step
            process_context: The process context for the migration
            agent_response_callback: Optional callback for agent responses

        Returns:
            GroupChatOrchestration with agents created in the provided MCP context
        """
        self.logger.info(
            "[CONFIG] Creating YAML Step Group Chat Orchestration with step's MCP context..."
        )

        try:
            self.logger.info("[TOOLS] Creating agents with step's MCP context")
            orchestration = await self._create_yaml_agents(
                mcp_context=mcp_context,
                process_context=process_context,
                agent_response_callback=agent_response_callback,
                telemetry=telemetry,
            )
            return orchestration
        except Exception as e:
            self.logger.error(
                f"[FAILED] Failed to create YAML orchestration with context: {e}"
            )
            raise RuntimeError(f"YAML orchestration creation failed: {e}") from e

    async def _create_yaml_agents(
        self, mcp_context, process_context, agent_response_callback=None, telemetry=None
    ) -> GroupChatOrchestration:
        """
        Create YAML-specific agent team.

        This demonstrates PHASE-SPECIFIC AGENT CONTROL for implementation:
        - Focus on technical execution rather than design
        - Emphasis on validation and quality
        - Different expertise mix than design phase
        """
        agents = []

        # YAML Expert - PRIMARY LEAD for YAML phase
        # Handles configuration conversion, YAML generation, best practices
        agent_yaml = await mcp_context.create_agent(
            agent_config=yaml_expert(phase="yaml").render(**self.process_context),
            service_id="default",
        )
        agents.append(agent_yaml)

        # Azure Expert - Azure-specific configuration guidance
        # Provides Azure YAML patterns, service configurations, best practices
        agent_azure = await mcp_context.create_agent(
            agent_config=azure_expert(phase="yaml").render(**self.process_context),
            service_id="default",
        )
        agents.append(agent_azure)

        # QA Engineer - Validation and testing focus
        # Validates converted YAML files, ensures quality, tests configurations
        agent_qa = await mcp_context.create_agent(
            agent_config=qa_engineer(phase="yaml").render(**self.process_context),
            service_id="default",
        )
        agents.append(agent_qa)

        # Technical Writer - Report generation and documentation
        # Creates conversion reports, documents the migration process
        agent_writer = await mcp_context.create_agent(
            agent_config=technical_writer(phase="yaml").render(**self.process_context),
            service_id="default",
        )
        agents.append(agent_writer)

        # Notice: Different agent selection than Design phase:
        # - No Chief Architect (design decisions are done)
        # - No platform experts (source analysis is complete)
        # - Focus on YAML Expert + QA validation + Technical Writing

        # Create YAML-specific orchestration
        orchestration = GroupChatOrchestration(
            members=agents,
            manager=YamlStepGroupChatManager(
                step_name="YAML",
                step_objective="Convert configurations to Azure YAML and validate",
                service=self.kernel_agent.kernel.services["default"],
                max_rounds=100,  # YAML conversion needs adequate rounds for file-by-file processing
                process_context=process_context,
                telemetry=telemetry,
            ),
            agent_response_callback=agent_response_callback,  # ✅ Pass callback as constructor parameter
        )

        return orchestration
