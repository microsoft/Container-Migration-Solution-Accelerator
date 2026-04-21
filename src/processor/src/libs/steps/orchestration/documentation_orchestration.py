"""
Documentation Step Orchestration Module

This module demonstrates the final phase agent selection for documentation generation.
The Documentation phase focuses on reporting and validation,
requiring writers and reviewers rather than technical implementers.

Classes:
    DocumentationStepGroupChatManager: Specialized group chat manager for documentation step
    DocumentationOrchestrator: Factory for creating documentation orchestrations with reporting focus
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

from agents.azure_expert.agent_info import get_agent_info as azure_expert
from agents.eks_expert.agent_info import get_agent_info as eks_expert
from agents.gke_expert.agent_info import get_agent_info as gke_expert
from agents.qa_engineer.agent_info import get_agent_info as qa_engineer
from agents.technical_architect.agent_info import get_agent_info as architect_agent

# Import specific agents for Documentation phase - comprehensive expert collaboration
from agents.technical_writer.agent_info import get_agent_info as technical_writer
from utils.agent_selection_parser import parse_agent_selection_safely

# Import telemetry utilities
from utils.chat_completion_retry import (
    get_chat_message_content_with_retry,
    get_orchestration_retry_config,
)

from .base_orchestrator import StepGroupChatOrchestrator, StepSpecificGroupChatManager
from .models.documentation_result import Documentation_ExtendedBooleanResult

logger = logging.getLogger(__name__)


# Documentation step prompt templates
DOCUMENTATION_TERMINATION_PROMPT = """
You are coordinating the {{step_name}} step of Azure Kubernetes migration using Sequential Authority pattern.
Objective: {{step_objective}}

**🚨🔥 SEQUENTIAL AUTHORITY WORKFLOW - DOCUMENTATION PHASE 🔥🚨**

**🎯 SEQUENTIAL AUTHORITY WORKFLOW**:
1. **Foundation Leader (Technical Writer)**: Execute ALL MCP operations, create migration_report.md, coordinate comprehensive report
2. **Enhancement Specialist (Azure Expert)**: Enhance with Azure-specific insights and optimizations WITHOUT redundant MCP calls
3. **Final Validator (Chief Architect)**: Validate executive readiness and technical consistency WITHOUT re-reading files
4. **Documentation Specialist (QA Engineer)**: Ensure quality and completeness WITHOUT redundant content operations

**� EFFICIENCY ENFORCEMENT**:
- ONLY Technical Writer should execute MCP operations (read_blob_content for previous step files, save_content_to_blob for migration_report.md)
- Azure Expert enhances WITHOUT redundant file reading
- Chief Architect validates WITHOUT re-accessing previous files
- QA Engineer ensures quality WITHOUT redundant content operations
- Expected ~75% reduction in redundant MCP operations compared to parallel collaboration

**�🚨 CRITICAL AI LIMITATION REMINDER 🚨**:
- **AI cannot certify production readiness** - Only human experts can make deployment decisions
- **All outputs are recommendations only** - Require human validation before implementation
- **Use advisory language** - "should", "recommended", "suggested" rather than "certified", "approved", "ready"
- **Include disclaimers** - All reports must clearly state they are AI-generated recommendations

**MANDATORY DUAL OUTPUT REQUIREMENTS**:
1. **Create comprehensive `migration_report.md` file** in {{output_file_folder}} (for human consumption)
2. **Return structured JSON data** (for completion tracking and automation)

**SEQUENTIAL AUTHORITY TERMINATION RULES**:

TERMINATE SUCCESS when:
- Technical Writer (Foundation Leader) completed comprehensive report creation with all MCP operations
- Azure Expert (Enhancement Specialist) enhanced with Azure-specific insights
- Chief Architect (Final Validator) validated executive readiness and consistency
- QA Engineer (Documentation Specialist) ensured quality and completeness
- **🔴 MANDATORY FILE VERIFICATION**: `migration_report.md` generated and verified by Technical Writer
  - Technical Writer uses `list_blobs_in_container()` to confirm file exists in output folder
  - Technical Writer uses `read_blob_content()` to verify content is properly generated
  - **NO FILES, NO PASS**: Step cannot complete without verified file generation by foundation leader

TERMINATE FAILURE when:
- Technical errors prevent access/operations
- Critical system failures or timeouts
- Previous step files missing or corrupted (verified by Technical Writer)

CONTINUE when:
- Technical Writer (Foundation Leader) report creation not completed
- Azure Expert (Enhancement Specialist) enhancement not completed
- Chief Architect (Final Validator) validation not completed
- QA Engineer (Documentation Specialist) quality review not completed
- Migration report file NOT generated or incomplete
- **ANY MANDATORY FIELD IS MISSING OR NULL**

**REQUIRED MARKDOWN REPORT STRUCTURE** (`migration_report.md`):
The migration_report.md file must contain the following sections in markdown format:

**🚨 MANDATORY MARKDOWN FORMATTING RULES:**
- **Professional Table Format**: All tables must use proper markdown syntax with aligned columns
- **Cell Content Limits**: Maximum 50 characters per table cell for readability
- **Consistent Status Icons**: Use ✅ for success, ⚠️ for warnings, ❌ for failures
- **Proper Headers**: Use ## for main sections, ### for subsections
- **Code Blocks**: Use ```yaml or ```json for configuration examples
- **Executive Readability**: Tables must be scannable for executive review

## Executive Summary
- Migration overview and outcomes
- Key success metrics and completion status
- Overall recommendations
- Don't add Table of contents

## Platform Analysis Summary
- Source platform details and complexity assessment
- Target Azure architecture decisions

## File Conversion Results
**MANDATORY TABLE FORMAT** - Use proper markdown table syntax for readability:

| Source File | Target File | Status | Accuracy | Issues |
|------------|-------------|---------|----------|--------|
| app.yaml | app-aks.yaml | ✅ Complete | 95% | None |
| svc.yaml | svc-aks.yaml | ⚠️ Partial | 88% | Minor config adjustments needed |

**CRITICAL TABLE FORMATTING REQUIREMENTS:**
- Maximum 50 characters per cell for professional readability
- Use status icons: ✅ Complete, ⚠️ Partial, ❌ Failed
- Include accuracy percentages (e.g., "95%", "88%")
- Keep issues column concise and actionable
- Ensure proper markdown table syntax with aligned pipes

- Detailed conversion statistics and quality metrics
- Per-file conversion status and accuracy

## Azure Architecture Design
- Selected Azure services and rationale
- Architecture decisions and trade-offs

## Expert Collaboration Summary
- Participating experts and their contributions
- Consensus-building process and outcomes

## Quality Validation Results
- QA verification findings and validation status
- Migration guidance assessment

## Next Steps and Recommendations
- Post-migration activities and operational guidance
- Deployment procedures and best practices

**CRITICAL REQUIREMENT: COMPLETE DATA POPULATION MANDATORY**
You MUST populate ALL fields in the Documentation_ExtendedBooleanResult structure. Incomplete responses will be rejected.

TERMINATION DECISION CRITERIA:

The Technical Writer leads documentation with comprehensive expert collaboration. Analyze the conversation to determine if the documentation step should terminate.

TERMINATE WITH SUCCESS when:
- Chief Architect has reviewed and provided feedback on all documentation content in migration report
- Chief Architect must confirm the file generated and saved in converted file folder
- **🔴 FOUNDATION LEADER DATA COMPLETENESS VERIFICATION**: Technical Writer personally validates data quality
  - Technical Writer reads migration_report.md content using `read_blob_content()`
  - Technical Writer verifies aggregated_results contain complete synthesis of all previous step outputs (Analysis, Design, YAML)
  - Technical Writer verifies expert_collaboration data captures meaningful insights from all participating domain experts
  - Technical Writer verifies process_metrics accurately reflect the entire migration workflow performance
  - Technical Writer confirms all critical documentation data fields contain executive-ready content for final deliverable
  - **DATA QUALITY GATE**: Technical Writer must explicitly state "Data completeness verified for final migration deliverable" before termination
- **🔴 FILE CONTENT COMPLETENESS VERIFICATION**: Technical Writer validates file generation quality
  - Technical Writer uses `list_blobs_in_container()` to confirm migration_report.md exists in output folder
  - Technical Writer uses `read_blob_content()` to verify migration report contains comprehensive executive summary, technical details, and operational guidance
  - Technical Writer confirms file content includes complete synthesis of all previous step deliverables and actionable migration guidance
  - Technical Writer validates documentation meets professional standards and provides complete migration project closure
  - **FILE QUALITY GATE**: Technical Writer must explicitly state "File content completeness verified for executive delivery" before termination
- **DUAL OUTPUT COMPLETED**:
  - Comprehensive migration report (`migration_report.md`) generated and saved to output folder
  - JSON response structure prepared for completion tracking and automation
- **ALL MANDATORY FIELDS ARE PROPERLY POPULATED WITH MEANINGFUL CONTENT**
- All previous phase results (analysis, design, conversion) are fully integrated and summarized
- Executive summary with quantified outcomes and success metrics is complete
- Technical documentation covers all architectural decisions and implementation details
- Deployment procedures and operational guidance are fully documented
- Quality validation provides recommendations for documentation standards
- Technical Writer confirms documentation completion with expert consensus
- All expert insights from domain specialists are captured and integrated
- Migration report file is successfully saved and accessible
- Documentation provides recommendations and guidance for migration projects
- **🔴 MANDATORY FILE VERIFICATION**: `migration_report.md` generated and verified in {{output_file_folder}}
  - Use `list_blobs_in_container()` to confirm file exists in output folder
  - Use `read_blob_content()` to verify content is properly generated
  - **NO FILES, NO PASS**: Step cannot complete without verified file generation

**MANDATORY FIELD VALIDATION** (ALL FIELDS REQUIRED FOR SUCCESS):
✅ result: MUST be true (NOT NULL)
✅ reason: MUST be detailed completion reason (NOT NULL/empty/placeholder)
✅ termination_output: MUST contain complete DocumentationOutput structure with:
  ✅ aggregated_results: MUST have ALL fields with meaningful content:
     - executive_summary: detailed summary (NOT NULL/empty/placeholder)
     - total_files_processed: actual number (NOT NULL/zero/placeholder)
     - overall_success_rate: actual percentage (NOT NULL/placeholder)
     - platform_detected: actual platform (NOT NULL/empty)
     - conversion_accuracy: actual percentage (NOT NULL/placeholder)
     - documentation_completeness: actual assessment (NOT NULL/empty)
     - migration_guidance: actual assessment (NOT NULL/empty)
  ✅ generated_files: MUST have ALL fields with meaningful content:
     - documentation: array of actual files (NOT NULL/empty/template names)
     - total_files_generated: actual count (NOT NULL/zero)
  ✅ expert_collaboration: MUST have ALL fields with meaningful content:
     - participating_experts: actual expert list (NOT NULL/empty)
     - consensus_achieved: true/false (NOT NULL)
     - expert_insights: actual insights (NOT NULL/empty/placeholder)
     - quality_validation: actual validation results (NOT NULL/empty)
  ✅ process_metrics: MUST have ALL fields with actual values (NOT NULL/placeholder)
✅ termination_type: MUST be "soft_completion"
✅ blocking_issues: MUST be empty array for success

**FIELD VALIDATION RULES**:
- NO fields can be null, undefined, or empty strings
- NO placeholder content like "TBD", "TODO", "template", "example"
- Numbers must be actual calculated values, not zeros or placeholders
- Arrays must contain meaningful entries, not template or example data
- All assessments must be based on actual analysis, not generic text

TERMINATE WITH FAILURE when:
- Critical information from previous phases cannot be accessed or integrated
- Documentation generation encounters persistent technical or access issues
- Required migration report sections are incomplete after reasonable attempts
- Expert consensus cannot be achieved on documentation content or quality
- Professional documentation standards cannot be met due to data or process limitations

**MANDATORY: When terminating with FAILURE, you MUST still populate ALL required fields:**
- result: false
- reason: "Specific failure reason"
- termination_output: null (only for failures)
- termination_type: "hard_blocked", "hard_error", or "hard_timeout"
- blocking_issues: Specific blocking issues that prevent completion

CONTINUE DOCUMENTATION when:
- Report generation is in progress but not yet complete
- Integration of previous phase results is ongoing
- Expert collaboration and consensus-building is still active
- Quality review and validation processes are underway
- Additional documentation sections or refinements are being developed
- Agents are actively working on comprehensive migration documentation
- **🔴 FOUNDATION LEADER DATA VERIFICATION INCOMPLETE**: Technical Writer has not confirmed data completeness
  - Aggregated results contain placeholder content, missing data from previous steps, or lack comprehensive synthesis
  - Expert collaboration data is incomplete, missing domain expert insights, or lacks meaningful consensus documentation
  - Process metrics contain placeholder values or do not accurately reflect the migration workflow performance
  - Data quality verification statement "Data completeness verified for final migration deliverable" not provided by Technical Writer
- **🔴 FILE CONTENT VERIFICATION INCOMPLETE**: Technical Writer has not confirmed file content completeness
  - Migration report file has not been verified to exist using `list_blobs_in_container()`
  - File content has not been validated using `read_blob_content()` to ensure comprehensive documentation quality
  - Documentation content lacks executive summary, technical details, or operational guidance required for final deliverable
  - File quality verification statement "File content completeness verified for executive delivery" not provided by Technical Writer
- **Dual output not completed**:
  - Migration report (`migration_report.md`) has not been generated and saved to output folder
  - JSON response structure not ready for completion tracking

**VALIDATION REQUIREMENT**: Your response MUST include complete data for ALL required fields. Partial or incomplete responses will cause pipeline failures.

**CRITICAL: RESPOND WITH VALID JSON ONLY**

Example SUCCESS response:
{
  "result": true,
  "reason": "Dual output completed: comprehensive migration report saved and JSON response prepared. Technical Writer confirmed documentation completion with expert consensus.",
  "termination_output": {
    "aggregated_results": {
      "executive_summary": "[migration summary for this process]",
      "total_files_processed": [total files processed],
      "overall_success_rate": "[over all success rate]",
      "platform_detected": "[detected platform]",
      "conversion_accuracy": "[conversion accuracy]",
      "documentation_completeness": "[document completeness]",
      "migration_guidance": "[recommendations provided]"
    },
    "generated_files": {
      "documentation": [all of generated report and yaml files that you have verified exist in blob storage],
      "total_files_generated": "[CALCULATE: sum of lengths of analysis, design, yaml, and documentation arrays]"
    },
    "expert_collaboration": {
      "participating_experts": [participants who contributed],
      "consensus_achieved": [consensus status],
      "expert_insights": [all expert insights contributed],
      "quality_validation": "[documentation quality validation status]"
    },
    "process_metrics": {
      "platform_detected": "[detected platform]",
      "conversion_accuracy": "[conversion accuracy]",
      "documentation_completeness": "[document completeness]",
      "migration_guidance": "[recommendations provided]"
    }
  },
  "termination_type": "[soft_completion or other types]",
  "blocking_issues": [an array of specific blocking issues]
}

Example CONTINUE response:
{
  "result": false,
  "reason": "Migration report generation in progress. Field validation check: [LIST INCOMPLETE FIELDS FROM CHECKLIST ABOVE]",
  "termination_output": null,
  "termination_type": "soft_completion",
  "blocking_issues": ["incomplete_field_population", "pending_expert_collaboration"]
}

Example FAILURE response:
{
  "result": false,
  "reason": "Critical information from previous phases cannot be accessed. Documentation generation blocked.",
  "termination_output": null,
  "termination_type": "hard_blocked",
  "blocking_issues": ["Cannot access analysis results", "Conversion data incomplete"]
}

NEVER respond with plain text. JSON ONLY.

Respond with structured termination decision using Documentation_ExtendedBooleanResult format
"""

DOCUMENTATION_SELECTION_PROMPT = """
You are coordinating the {{step_name}} step for {{step_objective}}.
Available participants: {{participants}}

SEQUENTIAL AUTHORITY WORKFLOW APPROACH:
Execute foundation → enhancement → validation workflow:

- Technical_Writer: FOUNDATION LEADER - Establishes authoritative documentation foundation and coordinates comprehensive report creation
- Azure_Expert: ENHANCEMENT SPECIALIST - Enhances foundation with Azure deployment/operations insights ONLY when assigned by Technical Writer
- Chief_Architect: ENHANCEMENT SPECIALIST - Provides strategic oversight enhancements ONLY when assigned by Technical Writer
- QA_Engineer: ENHANCEMENT SPECIALIST - Adds quality validation insights ONLY when assigned by Technical Writer
- EKS_Expert: ENHANCEMENT SPECIALIST - Provides EKS migration considerations ONLY when assigned by Technical Writer (ONLY if source platform is EKS)
- GKE_Expert: ENHANCEMENT SPECIALIST - Offers GKE cross-platform best practices ONLY when assigned by Technical Writer (ONLY if source platform is GKE)

**PLATFORM-AWARE SELECTION RULES**:
- **Check analysis results** for platform detection (EKS vs GKE)
- **Only select the matching platform expert** for platform-specific documentation enhancement
- **Do not select non-matching platform expert** who should be in quiet mode
- Example: If analysis determined GKE → Only select GKE_Expert, avoid selecting EKS_Expert

SELECTION PRIORITY:
1. Technical Writer establishes authoritative documentation foundation as Foundation Leader
2. Expert enhancement when assigned by Technical Writer for specialized domain insights
3. Complete comprehensive migration documentation through Sequential Authority workflow

**Agent Selection Rules (Sequential Authority)**:
- Start with Technical_Writer to establish authoritative documentation foundation
- Select Expert when Technical_Writer assigns them for specialized domain enhancement
- Follow Sequential Authority workflow: Foundation → Enhancement → Completion

Select the next participant who can provide the most valuable documentation contribution.

**CRITICAL - RESPONSE FORMAT**:
Respond with a JSON object containing the participant name in the 'result' field:

**VALID PARTICIPANT NAMES ONLY**:
- "Technical_Writer"
- "Azure_Expert"
- "Chief_Architect"
- "QA_Engineer"
- "EKS_Expert"
- "GKE_Expert"

**DO NOT USE THESE INVALID VALUES**:
- "Success", "Complete", "Terminate", "Finish" are NOT participant names

CORRECT Response Examples:
✅ {"result": "Technical_Writer", "reason": "Foundation establishment and comprehensive report creation required"}
✅ {"result": "Azure_Expert", "reason": "Azure deployment enhancement assigned by Technical Writer"}
✅ {"result": "Chief_Architect", "reason": "Strategic oversight enhancement assigned by Technical Writer"}
✅ {"result": "QA_Engineer", "reason": "Quality validation enhancement assigned by Technical Writer"}
✅ {"result": "EKS_Expert", "reason": "EKS migration enhancement assigned by Technical Writer"}
✅ {"result": "GKE_Expert", "reason": "GKE cross-platform enhancement assigned by Technical Writer"}

INCORRECT Response Examples:
❌ "Technical_Writer" (missing JSON format)
❌ {"result": "Success", "reason": "..."} (Success is not a valid participant name)
❌ {"result": "Select Technical_Writer", "reason": "..."} (extra text in result field)
❌ {"result": "Complete", "reason": "..."} (Complete is not a valid participant name)

think carefully. **Respond with valid JSON only in the format: {"result": "participant_name", "reason": "explanation"}**.
"""
DOCUMENTATION_RESULT_FILTER_PROMPT = """
You are coordinating the {{step_name}} step of Azure Kubernetes migration.
Step objective: {{step_objective}}

You have just concluded the documentation discussion.
Please summarize the documentation results and provide a structured report that aligns with the comprehensive generated_files collection format:

**CRITICAL - MANDATORY FILE VERIFICATION BEFORE REPORTING**:
- **NEVER LIST A FILE UNLESS YOU HAVE VERIFIED IT EXISTS** using blob storage MCP tools
- **ALWAYS use list_blobs_in_container()** to verify each file exists before including it in the report
- **ALWAYS use read_blob_content()** to verify file content before describing it
- **Use datetime MCP tool(datetime_service)** for ALL timestamp generation (avoid hardcoded dates)
- **Microsoft Docs MCP Strategic Documentation Research**:
  1. **SEARCH**: Use `microsoft_docs_search` for Azure migration guides, best practices, service documentation
  2. **FETCH**: Use `microsoft_docs_fetch` on search URLs for complete migration procedures and reference links
  3. **Documentation Purpose**: Comprehensive Azure service references, complete configuration guides, official Microsoft links

**MANDATORY FILE VERIFICATION PROCESS**:
1. **Before listing ANY file in GeneratedFilesCollection, you MUST**:
   - Call `list_blobs_in_container(container_name={{container_name}}, folder_path=[appropriate_folder])` to verify it exists
   - Call `read_blob_content(blob_name=[file_name], container_name={{container_name}}, folder_path=[folder_path])` to verify content
2. **If a file mentioned in conversation does NOT exist in blob storage**: DO NOT include it in the report
3. **Only include files that you have successfully verified exist and have readable content**
4. **If no files exist in a category (analysis/design/yaml/documentation)**: Return empty array [] for that category

**ANTI-HALLUCINATION RULES**:
- NEVER create fictional file names like "gke_to_aks_expert_insights.md"
- NEVER assume files exist based on conversation mentions alone
- NEVER include placeholder or example file names in the final report
- EVERY file listed must be verified to exist through explicit blob operations
- If you cannot verify a file exists, exclude it completely from the report

{
    "Result": ["Success" or "Fail"],
    "Summary": "[Summary of the documentation generation process and expert collaboration outcomes]",
    "GeneratedFilesCollection": {
        "analysis": [
            {
                "file_name": "[VERIFIED analysis file name - only if file exists]",
                "file_type": "[source_analysis, requirements, etc.]",
                "content_summary": "[brief summary of ACTUAL analysis findings from verified file content]",
                "key_findings": ["list of key discoveries from ACTUAL file content"],
                "source_platform": "[EKS, GKE, etc.]",
                "analysis_depth": "[Comprehensive, Detailed, Basic]"
            }
        ],
        "design": [
            {
                "file_name": "[VERIFIED design file name - only if file exists]",
                "file_type": "[architecture_design, migration_plan, etc.]",
                "content_summary": "[brief summary of ACTUAL design specifications from verified file content]",
                "azure_services": ["list of Azure services covered in ACTUAL file"],
                "design_patterns": ["list of design patterns implemented in ACTUAL file"],
                "security_considerations": ["list of security aspects covered in ACTUAL file"]
            }
        ],
        "yaml": [
            {
                "source_file": "[VERIFIED original file name - only if file exists]",
                "converted_file": "[VERIFIED Azure converted file name - only if file exists]",
                "conversion_status": "[Success, Partial, Failed based on ACTUAL file verification]",
                "accuracy_rating": "[percentage based on ACTUAL file comparison]",
                "concerns": ["list of any conversion concerns from ACTUAL file analysis"],
                "azure_enhancements": ["list of Azure-specific enhancements added to ACTUAL file"],
                "file_type": "[deployment, service, configmap, etc.]",
                "complexity_score": "[Low, Medium, High based on ACTUAL file complexity]"
            }
        ],
        "documentation": [
            {
                "file_name": "[VERIFIED documentation file name - only if file exists]",
                "file_type": "[migration_report, deployment_guide, etc.]",
                "content_summary": "[brief summary of ACTUAL document contents from verified file]",
                "target_audience": "[technical_teams, operations, management, etc.]",
                "document_sections": ["list of main document sections from ACTUAL file"],
                "technical_level": "[Advanced, Intermediate, Basic based on ACTUAL content]"
            }
        ],
        "total_files_generated": "[ACTUAL count of verified files across all phases]"
    },
    "ExpertCollaboration": {
        "participating_experts": ["list of experts who contributed"],
        "consensus_achieved": ["Yes or No"],
        "expert_insights": ["list of key expert contributions"],
        "quality_validation": ["QA Engineer validation status"]
    },
    "ProcessMetrics": {
        "platform_detected": "[EKS or GKE]",
        "conversion_accuracy": "[overall accuracy percentage]",
        "documentation_completeness": "[percentage complete]",
        "migration_guidance": "[Yes or No]"
    }
}

**🔢 CRITICAL: total_files_generated CALCULATION RULE**:
The `total_files_generated` field MUST be the exact count of all files across ALL phases:
- Count files in analysis array: len(analysis)
- Count files in design array: len(design)
- Count files in yaml array: len(yaml)
- Count files in documentation array: len(documentation)
- Sum all four counts: analysis + design + yaml + documentation
- Example: if analysis=[1 file], design=[2 files], yaml=[3 files], documentation=[1 file], then total_files_generated = 7
- NEVER use hardcoded values like 3 or 28
- ONLY count verified files that actually exist in blob storage

CRITICAL REMINDERS:
- **FILE VERIFICATION IS MANDATORY**: Every file mentioned must be verified to exist through blob storage operations
- **NO FICTIONAL FILES**: Do not include any files that do not actually exist in blob storage
- **CONTENT-BASED DESCRIPTIONS**: All summaries and descriptions must be based on actual file content, not conversation speculation
- **Empty arrays are acceptable**: If no files exist in a category, return empty array [] rather than fictional entries
"""


class DocumentationStepGroupChatManager(StepSpecificGroupChatManager):
    """
    Group chat manager specialized for Documentation Step.

    Focus: Report generation, migration documentation, final summary
    Agents: Technical Writer (lead), Chief Architect, QA Engineer
    """

    final_termination_result: Documentation_ExtendedBooleanResult | None = None

    async def should_terminate(
        self, chat_history: ChatHistory
    ) -> Documentation_ExtendedBooleanResult:
        """Determine if documentation step is complete."""
        # Track termination evaluation start
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name="Conversation_Manager",
            action="evaluating_termination",
            message_preview="Evaluating if documentation generation is complete",
        )

        should_terminate = await super().should_terminate(chat_history)
        if should_terminate.result:
            # Track early termination from base class
            await self.telemetry.update_agent_activity(
                process_id=self.process_context.get("process_id"),
                agent_name="Conversation_Manager",
                action="early_termination",
                message_preview="Documentation conversation terminated by base class logic",
            )
            # Convert BooleanResult to Documentation_ExtendedBooleanResult
            return Documentation_ExtendedBooleanResult(
                result=should_terminate.result,
                reason=should_terminate.reason,
            )

        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(DOCUMENTATION_TERMINATION_PROMPT),
            ),
        )

        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content="Determine if migration documentation and reports are complete.",
            ),
        )

        # Apply smart truncation before API call to preserve context
        # Extended limit for comprehensive migration documentation
        self._smart_truncate_chat_history(chat_history)
        # self._smart_truncate_chat_history(chat_history)
        # self._smart_truncate_chat_history_with_token_limit(
        #     chat_history,
        #     max_total_tokens=8500,  # Increased by 50%: 5000 * 1.5 = 7500
        #     max_messages=5,  # Increased by 50%: 2 * 1.5 = 3
        #     max_tokens_per_message=1000,  # Increased by 50%: 200 * 1.5 = 300
        # )

        response = await get_chat_message_content_with_retry(
            self.service,
            chat_history,
            settings=PromptExecutionSettings(
                response_format=Documentation_ExtendedBooleanResult
            ),
            config=get_orchestration_retry_config(),
            operation_name="should_terminate",
        )

        if not response or not response.content:
            raise RuntimeError("No response content received for termination check")

        termination_with_reason = (
            Documentation_ExtendedBooleanResult.model_validate_json(response.content)
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
                message_preview=f"Documentation conversation completed: {termination_with_reason.reason}",
            )

            self.final_termination_result = termination_with_reason
        else:
            await self.telemetry.update_agent_activity(
                process_id=self.process_context.get("process_id"),
                agent_name="Conversation_Manager",
                action="conversation_continuing",
                message_preview=f"Documentation conversation continues: {termination_with_reason.reason}",
            )

        return termination_with_reason

    async def select_next_agent(
        self,
        chat_history: ChatHistory,
        participant_descriptions: dict[str, str],
    ) -> StringResult:
        """Select next agent for documentation step."""
        # Track agent responses first (from base class)
        await super().select_next_agent(chat_history, participant_descriptions)

        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(
                    DOCUMENTATION_SELECTION_PROMPT,
                    participants="\n".join(
                        [f"{k}: {v}" for k, v in participant_descriptions.items()]
                    ),
                ),
            ),
        )

        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content="Select the next participant for documentation step.",
            ),
        )

        # Apply smart truncation before API call to preserve context
        # Extended limit for comprehensive migration documentation
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
            operation_name="select_next_agent",
        )

        participant_name_with_reason = parse_agent_selection_safely(
            self._safe_get_content(response),
            step_name="Documentation",
            valid_agents=list(participant_descriptions.keys()),
        )

        logger.info(
            f"[AGENT_SELECTION] Raw AI response: '{self._safe_get_content(response)}'"
        )
        logger.info(
            f"[AGENT_SELECTION] Parsed agent: '{participant_name_with_reason.result}'"
        )
        logger.info(
            f"[AGENT_SELECTION] Available participants: {list(participant_descriptions.keys())}"
        )

        # Clean up participant name if it contains extra text
        selected_agent = participant_name_with_reason.result.strip()

        print("*********************")
        print(f"Original response: '{self._safe_get_content(response)}'")
        print(f"Parsed agent: '{participant_name_with_reason.result}'")
        print(f"Final selected agent: '{selected_agent}'")
        print(f"Available participants: {list(participant_descriptions.keys())}")
        print(f"Reason: {participant_name_with_reason.reason}")
        print("*********************")

        # Track agent selection in telemetry
        selection_reason = participant_name_with_reason.reason
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name="Conversation_Manager",
            action="agent_selected",
            message_preview=f"Selected {selected_agent} for documentation: {selection_reason}",
        )
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name=selected_agent,
            action="selected_for_turn",
            message_preview=f"Selected to speak next: {selection_reason}",
        )

        # Validate selected agent exists in participants
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
        """Filter and summarize documentation step results."""
        # Track start of results filtering
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name="Conversation_Manager",
            action="documentation_results_filtering_started",
            message_preview="Starting documentation results filtering and summarization",
        )

        if not chat_history.messages:
            raise RuntimeError("No messages in the chat history.")

        chat_history.messages.insert(
            0,
            ChatMessageContent(
                role=AuthorRole.SYSTEM,
                content=await self._render_prompt(DOCUMENTATION_RESULT_FILTER_PROMPT),
            ),
        )

        chat_history.add_message(
            ChatMessageContent(
                role=AuthorRole.USER,
                content="Please summarize the documentation step results with generated reports and validation status.",
            ),
        )

        # Apply smart truncation before API call to preserve context
        # Extended limit for comprehensive migration documentation
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

        string_with_reason = StringResult.model_validate_json(
            self._safe_get_content(response)
        )

        # Track successful results filtering completion
        await self.telemetry.update_agent_activity(
            process_id=self.process_context.get("process_id"),
            agent_name="Conversation_Manager",
            action="documentation_results_filtering_completed",
            message_preview=f"Documentation results filtering completed: {len(string_with_reason.result)} characters summarized",
        )

        return MessageResult(
            result=ChatMessageContent(
                role=AuthorRole.ASSISTANT, content=string_with_reason.result
            ),
            reason=string_with_reason.reason,
        )


class DocumentationOrchestrator(StepGroupChatOrchestrator):
    """
    Orchestrator for collaborative Documentation step with comprehensive expert consensus.

    UPDATED AGENT SELECTION STRATEGY FOR TRUE EXPERT COLLABORATION:
    This enables comprehensive expert consensus rather than architect-driven documentation.

    Documentation Phase Agents (Consensus-focused):
    - Technical Writer: COORDINATION LEAD - Facilitates documentation but relies on expert input
    - Chief Architect: Strategic oversight and high-level validation
    - Azure Expert: Azure operational procedures, deployment guidance, troubleshooting
    - EKS Expert: Source platform considerations, migration challenges, platform-specific knowledge
    - GKE Expert: Cross-platform insights, additional best practices perspective
    - QA Engineer: Quality assurance, final validation, completeness checking

    KEY IMPROVEMENT: ALL domain experts now participate to provide their specialized perspectives,
    ensuring comprehensive migration documentation with true collaborative consensus.
    """

    async def create_documentation_orchestration_with_context(
        self, mcp_context, process_context, agent_response_callback=None, telemetry=None
    ) -> GroupChatOrchestration:
        """
        Create group chat orchestration for Documentation Step with provided MCP context from step.

        This method allows the step to pass its own MCP context to ensure agents have proper MCP tool access.

        Args:
            mcp_context: The MCP context created by the step
            process_context: The process context for the migration
            agent_response_callback: Optional callback for agent responses

        Returns:
            GroupChatOrchestration with agents created in the provided MCP context
        """
        self.logger.info(
            "[NOTES] Creating Documentation Step Group Chat Orchestration with step's MCP context..."
        )

        try:
            self.logger.info("[TOOLS] Creating agents with step's MCP context")
            orchestration = await self._create_documentation_agents(
                mcp_context, process_context, agent_response_callback, telemetry
            )
            return orchestration
        except Exception as e:
            self.logger.error(
                f"[FAILED] Failed to create documentation orchestration with context: {e}"
            )
            raise RuntimeError(
                f"Documentation orchestration creation failed: {e}"
            ) from e

    async def _create_documentation_agents(
        self, mcp_context, process_context, agent_response_callback=None, telemetry=None
    ) -> GroupChatOrchestration:
        """
        Create Documentation-specific agent team with comprehensive expert collaboration.

        UPDATED STRATEGY FOR TRUE EXPERT CONSENSUS:
        - All domain experts participate to provide specialized perspectives
        - Technical Writer coordinates but experts provide their domain insights
        - Consensus-driven approach rather than architect-only driven
        - Each expert contributes their specialized knowledge to comprehensive documentation
        """
        agents = []

        # Technical Writer - COORDINATION LEAD for Documentation phase
        # Coordinates documentation but relies on expert consensus and input
        agent_writer = await mcp_context.create_agent(
            technical_writer(phase="documentation").render(
                **self.process_context["analysis_result"]
            )
        )
        agents.append(agent_writer)

        # Chief Architect - Strategic oversight and review
        # Provides high-level architecture guidance and validation
        agent_architect = await mcp_context.create_agent(
            architect_agent(phase="documentation").render(
                **self.process_context["analysis_result"]
            )
        )
        agents.append(agent_architect)

        # Azure Expert - Azure-specific operational and best practices input
        # Provides Azure operational procedures, troubleshooting, deployment guidance
        agent_azure = await mcp_context.create_agent(
            azure_expert(phase="documentation").render(
                **self.process_context["analysis_result"]
            )
        )
        agents.append(agent_azure)

        # EKS Expert - Source platform migration considerations
        # Provides source platform expertise, migration challenges, platform-specific procedures
        agent_eks = await mcp_context.create_agent(
            eks_expert(phase="documentation").render(
                **self.process_context["analysis_result"]
            )
        )
        agents.append(agent_eks)

        # GKE Expert - Cross-platform insights and best practices
        # Provides additional platform perspective and cross-platform best practices
        agent_gke = await mcp_context.create_agent(
            gke_expert(phase="documentation").render(
                **self.process_context["analysis_result"]
            )
        )
        agents.append(agent_gke)

        # QA Engineer - Final quality assurance and validation
        # Validates documentation quality, ensures all requirements are captured
        agent_qa = await mcp_context.create_agent(
            qa_engineer(phase="documentation").render(
                **self.process_context["analysis_result"]
            )
        )
        agents.append(agent_qa)

        # CONSENSUS-DRIVEN DOCUMENTATION APPROACH:
        # - All domain experts contribute their specialized perspectives
        # - Technical Writer facilitates but doesn't dominate
        # - Each expert provides their domain-specific insights for comprehensive documentation
        # - True collaborative consensus rather than single-expert driven

        # Create comprehensive collaborative orchestration
        orchestration = GroupChatOrchestration(
            members=agents,
            manager=DocumentationStepGroupChatManager(
                step_name="Documentation",
                step_objective="Generate comprehensive migration documentation with expert consensus",
                service=self.kernel_agent.kernel.services["default"],
                max_rounds=100,  # Documentation needs most rounds for comprehensive report generation
                process_context=process_context,
                telemetry=telemetry,
            ),
            agent_response_callback=agent_response_callback,  # ✅ Pass callback as constructor parameter
        )

        return orchestration
