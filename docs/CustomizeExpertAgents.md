# Adding Custom Expert Agents

This guide explains how to add custom expert agents to the Container Migration Solution Accelerator to extend platform support or add specialized expertise.

## Overview

The solution uses a multi-agent orchestration pattern where specialized expert agents collaborate through Agent Framework orchestrations (including group chat). You can add custom agents to support additional cloud platforms, specialized workloads, or domain-specific expertise.

## Current Expert Agent Architecture

### Existing Agents

The solution includes these expert agents:

- **Technical Architect**: Overall architecture analysis and design decisions
- **Azure Architect / AKS Expert**: Azure-specific optimizations and Well-Architected Framework compliance
- **GKE Expert**: Google Kubernetes Engine specific knowledge and migration patterns
- **EKS Expert**: Amazon Elastic Kubernetes Service expertise and AWS-to-Azure translations
- **QA Engineer**: Validation, testing strategies, and quality assurance
- **YAML Expert**: Configuration transformation and syntax optimization

### Agent Structure

In the current processor implementation, “expert agents” are configured primarily through:

- **Prompt files** under each step’s `agents/` folder
- **Registry/config** (analysis only) to select platform experts dynamically
- **Step orchestrators** that construct `AgentInfo` objects and run group chat

## Adding a New Expert Agent

### Step 1: Add prompt file(s)

Add your expert prompt file to the step(s) it should participate in:

- Analysis: `src/processor/src/steps/analysis/agents/`
- Design: `src/processor/src/steps/design/agents/`
- YAML conversion: `src/processor/src/steps/convert/agents/`
- Documentation: `src/processor/src/steps/documentation/agents/`

Use the existing prompt files in those folders as templates.

### Step 2: Register the expert

Analysis experts are loaded dynamically from:

- `src/processor/src/steps/analysis/orchestration/platform_registry.json`

Add your expert there to have it participate in the analysis phase.

For other phases, add an `AgentInfo(...)` entry in the relevant step orchestrator’s `prepare_agent_infos()` implementation.

### Step 4: Register the Agent

Add your agent to the appropriate step orchestrator so it participates in the group-chat collaboration for that phase.

#### Update Step Orchestrators

The processor uses step-level orchestrators under:

- `src/processor/src/steps/analysis/orchestration/`
- `src/processor/src/steps/design/orchestration/`
- `src/processor/src/steps/convert/orchestration/`
- `src/processor/src/steps/documentation/orchestration/`

Each orchestrator builds its agent set using `AgentInfo` objects and runs a `GroupChatOrchestrator`.

**Analysis phase (platform experts)** is registry-driven via:

- `src/processor/src/steps/analysis/orchestration/platform_registry.json`

To add a new analysis expert:

1. Add a new prompt file under `src/processor/src/steps/analysis/agents/`
2. Add an entry to `platform_registry.json` pointing at the prompt file and desired `agent_name`

For other phases, add a new `AgentInfo(...)` entry in the relevant orchestrator’s `prepare_agent_infos()` implementation.

Minimal example (pattern used in the codebase):

```python
from libs.agent_framework.agent_info import AgentInfo

expert_info = AgentInfo(
    agent_name="YourCustomExpert",
    agent_instruction=instruction_text,
    tools=self.mcp_tools,
)
```

Your implementation uses **phase-specific agent selection**, meaning you can include your agent in specific phases only:

- **Analysis Phase**: Include if your agent helps with platform detection
- **Design Phase**: Include if your agent provides Azure architecture guidance
- **YAML Phase**: Include if your agent helps with configuration transformation
- **Documentation Phase**: Include if your agent contributes to documentation

Follow the same pattern for YAML and Documentation orchestrators as needed.

### Step 5: Test the Custom Agent

1. **Unit Testing**: Create unit tests for your agent's functionality
2. **Integration Testing**: Test the agent within the full orchestration flow
3. **Validation**: Verify the agent produces expected outputs and collaborates effectively

## Best Practices for Custom Agents

### Agent Design Guidelines

1. **Single Responsibility**: Each agent should have a clear, focused expertise area
2. **Collaboration**: Design agents to work well with existing agents
3. **Consistency**: Follow established patterns and naming conventions
4. **Documentation**: Provide clear instructions and expected behaviors

### Prompt Engineering Tips

1. **Specificity**: Be specific about the agent's role and responsibilities
2. **Context**: Provide sufficient context for the agent's expertise domain
3. **Examples**: Include examples of expected inputs and outputs
4. **Collaboration**: Define how the agent should interact with other agents

### Performance Considerations

1. **Token Efficiency**: Optimize prompts for token usage
2. **Response Quality**: Balance prompt length with response quality
3. **Execution Time**: Consider the impact on overall processing time
4. **Resource Usage**: Monitor memory and CPU usage during orchestration

## Advanced Customization

### Conditional Agent Participation

The actual implementation supports conditional agent inclusion. Study the existing orchestrator files to understand how agents are selectively included in different phases:

- Analysis phase focuses on platform detection experts
- Design phase emphasizes Azure architecture experts
- YAML phase includes transformation specialists
- Documentation phase involves technical writers

Refer to the actual orchestration implementations in `src/processor/src/steps/**/orchestration/` for patterns.

## Troubleshooting

### Common Issues

1. **Agent Not Participating**: Check agent registration in orchestrator
2. **Poor Response Quality**: Review and refine agent prompts
3. **Token Limit Exceeded**: Optimize prompt length and complexity
4. **Integration Conflicts**: Ensure agent collaborates well with existing agents

### Debugging Tips

1. **Enable Verbose Logging**: Use detailed logging to trace agent interactions
2. **Test Individual Agents**: Test agents in isolation before integration
3. **Monitor Token Usage**: Track token consumption for optimization
4. **Validate Outputs**: Ensure agent outputs meet expected formats

## Examples

Study the existing expert prompts and orchestrators in your codebase for real patterns:

- Prompt files: `src/processor/src/steps/**/agents/`
- Analysis expert registry: `src/processor/src/steps/analysis/orchestration/platform_registry.json`
- Orchestrators: `src/processor/src/steps/**/orchestration/`

These provide tested patterns for implementing custom expert agents in your migration solution.

## Next Steps

1. **Review Existing Agents**: Study the existing agent implementations for patterns
2. **Plan Your Agent**: Define the specific expertise and responsibilities
3. **Implement Step by Step**: Start with a prompt file, then add registry/orchestrator integration
4. **Test Thoroughly**: Validate the agent works well in the full orchestration flow
5. **Document Your Agent**: Create documentation for future maintenance and extension

For additional help with custom agent development, refer to:

- [Multi-Agent Orchestration Approach](MultiAgentOrchestration.md)
- [Processor Workflow Implementation](ProcessFrameworkGuide.md)
- [Technical Architecture](TechnicalArchitecture.md)
