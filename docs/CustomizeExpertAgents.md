# Adding Custom Expert Agents

This guide explains how to add custom expert agents to the Container Migration Solution Accelerator to extend platform support or add specialized expertise.

## Overview

The solution uses a multi-agent orchestration pattern where specialized expert agents collaborate through Semantic Kernel GroupChat patterns. You can add custom agents to support additional cloud platforms, specialized workloads, or domain-specific expertise.

## Current Expert Agent Architecture

### Existing Agents

The solution includes these expert agents:

- **Technical Architect**: Overall architecture analysis and design decisions
- **Azure Expert**: Azure-specific optimizations and Well-Architected Framework compliance
- **GKE Expert**: Google Kubernetes Engine specific knowledge and migration patterns
- **EKS Expert**: Amazon Elastic Kubernetes Service expertise and AWS-to-Azure translations
- **QA Engineer**: Validation, testing strategies, and quality assurance
- **YAML Expert**: Configuration transformation and syntax optimization

### Agent Structure

Each expert agent consists of:
- **Agent Info File**: Defines agent metadata and capabilities (`agent_info.py`)
- **Prompt Files**: Specialized prompts for different phases
  - `prompt-analysis.txt`: Analysis phase prompts
  - `prompt-design.txt`: Design phase prompts
  - `prompt-documentation.txt`: Documentation phase prompts
  - `prompt-yaml.txt`: YAML conversion phase prompts

## Adding a New Expert Agent

### Step 1: Create Agent Directory

Create a new directory under `src/agents/` for your custom agent:

```bash
mkdir src/agents/your_custom_expert
```

### Step 2: Create Agent Info File

Create `src/agents/your_custom_expert/agent_info.py` following the existing pattern:

```python
from agents.agent_info_util import AgentInfo

def get_agent_info() -> AgentInfo:
    return AgentInfo(
        name="YourCustomExpert",
        description="Expert in your specialized domain with deep knowledge of platform-specific patterns and migration strategies",
        instructions="""
        You are a specialized expert in [YOUR DOMAIN]. Your role is to:

        1. **Domain Analysis**: Analyze configurations specific to your platform/domain
        2. **Migration Patterns**: Identify platform-specific migration challenges and solutions
        3. **Best Practices**: Apply domain-specific best practices and optimizations
        4. **Integration Guidance**: Provide guidance on integrating with Azure services

        **Key Responsibilities:**
        - Identify domain-specific configuration patterns
        - Recommend migration strategies and transformations
        - Validate configurations against domain best practices
        - Provide expert insights for documentation

        **Communication Style:**
        - Be specific and technical in your analysis
        - Reference domain-specific documentation and patterns
        - Provide actionable recommendations
        - Collaborate effectively with other expert agents
        """,
        agent_name="YourCustomExpert",
        agent_instructions_token_count=200  # Approximate token count
    )
```

### Step 3: Create Specialized Prompts

#### Analysis Phase Prompt
Create `src/agents/your_custom_expert/prompt-analysis.txt`:

```
# Your Custom Expert - Analysis Phase

You are a specialized expert in [YOUR DOMAIN] with deep knowledge of platform-specific configuration patterns, migration challenges, and Azure integration strategies.

## Your Role in Analysis Phase

**Primary Objectives:**
1. **Domain Detection**: Identify configurations specific to your platform/domain
2. **Complexity Assessment**: Evaluate migration complexity for your domain
3. **Pattern Recognition**: Identify domain-specific patterns and dependencies
4. **Initial Recommendations**: Provide preliminary migration guidance

**Analysis Focus Areas:**
- Platform-specific configuration patterns
- Domain-specific networking, storage, or compute requirements
- Integration points and dependencies
- Security and compliance considerations
- Performance and scalability factors

**Expected Deliverables:**
- Domain-specific configuration analysis
- Migration complexity assessment
- Preliminary transformation recommendations
- Integration considerations for Azure

**Collaboration Guidelines:**
- Work closely with Technical Architect for overall strategy
- Coordinate with Azure Expert for Azure-specific optimizations
- Support QA Engineer with domain-specific validation requirements
```

#### Design Phase Prompt
Create `src/agents/your_custom_expert/prompt-design.txt`:

```
# Your Custom Expert - Design Phase

You are responsible for transforming domain-specific configurations to Azure-optimized architectures following Azure Well-Architected Framework principles.

## Your Role in Design Phase

**Primary Objectives:**
1. **Architecture Transformation**: Design Azure-native architectures for your domain
2. **Service Mapping**: Map domain-specific services to Azure equivalents
3. **Optimization Strategy**: Apply Azure optimizations for your domain
4. **Integration Design**: Design integration patterns with Azure services

**Design Focus Areas:**
- Azure service selection and configuration
- Network architecture and connectivity patterns
- Storage and data management strategies
- Security and identity integration
- Monitoring and observability design

**Azure Well-Architected Principles:**
- **Reliability**: Design for high availability and disaster recovery
- **Security**: Implement defense-in-depth security strategies
- **Cost Optimization**: Optimize resource utilization and costs
- **Operational Excellence**: Design for monitoring and automation
- **Performance Efficiency**: Optimize for performance and scalability

**Expected Deliverables:**
- Detailed Azure architecture design
- Service mapping and configuration recommendations
- Integration patterns and connectivity design
- Cost optimization recommendations
```

#### YAML Conversion Phase Prompt
Create `src/agents/your_custom_expert/prompt-yaml.txt`:

```
# Your Custom Expert - YAML Conversion Phase

You are responsible for converting domain-specific configurations to Azure Kubernetes Service (AKS) compatible YAML with platform-specific optimizations.

## Your Role in YAML Conversion

**Primary Objectives:**
1. **Configuration Transformation**: Convert domain configs to AKS-compatible YAML
2. **Azure Integration**: Integrate with Azure services (Key Vault, Monitor, etc.)
3. **Security Hardening**: Apply Azure security best practices
4. **Optimization**: Optimize for Azure performance and cost

**Conversion Focus Areas:**
- Workload Identity integration for secure service access
- Azure Key Vault integration for secrets management
- Azure Monitor integration for observability
- Network policies and security contexts
- Resource quotas and limits optimization
- Storage class mapping to Azure disk types

**Azure-Specific Transformations:**
- Convert service accounts to Workload Identity
- Map persistent volumes to Azure disk storage classes
- Transform ingress to Azure Application Gateway or nginx
- Convert monitoring to Azure Monitor/Prometheus
- Apply Azure security policies and contexts

**Expected Deliverables:**
- Fully converted AKS-compatible YAML files
- Azure service integration configurations
- Security and networking optimizations
- Performance and cost optimization recommendations
```

#### Documentation Phase Prompt
Create `src/agents/your_custom_expert/prompt-documentation.txt`:

```
# Your Custom Expert - Documentation Phase

You are responsible for creating comprehensive documentation for domain-specific migration decisions, transformations, and recommendations.

## Your Role in Documentation

**Primary Objectives:**
1. **Migration Documentation**: Document all domain-specific transformation decisions
2. **Expert Insights**: Provide detailed analysis and recommendations
3. **Implementation Guidance**: Create actionable implementation instructions
4. **Best Practices**: Document domain-specific best practices for Azure

**Documentation Focus Areas:**
- Domain-specific migration challenges and solutions
- Azure service integration patterns and configurations
- Security and compliance considerations
- Performance optimization recommendations
- Operational guidance and monitoring strategies

**Documentation Structure:**
- **Executive Summary**: High-level migration overview and recommendations
- **Technical Analysis**: Detailed technical assessment and transformation decisions
- **Implementation Guide**: Step-by-step implementation instructions
- **Best Practices**: Domain-specific Azure best practices
- **Troubleshooting**: Common issues and resolution strategies

**Expected Deliverables:**
- Comprehensive migration documentation
- Implementation guides and runbooks
- Best practices and recommendations
- Technical decision rationale and justifications
```

### Step 4: Register the Agent

Add your agent to the orchestration configuration. You need to modify the orchestrator files to include your new agent.

**Note**: The actual implementation uses the existing orchestration pattern. Here's how to add your agent:

#### Import Your Agent

Add the import statement in the orchestrator file where you want to include your agent:

```python
# Add this import alongside existing agent imports
from agents.your_custom_expert.agent_info import get_agent_info as your_custom_expert
```

#### Update Orchestrator Methods

Based on the actual implementation in `src/libs/steps/orchestration/`, add your agent to the appropriate `_create_*_agents` methods:

**Analysis Orchestrator** (`src/libs/steps/orchestration/analysis_orchestration.py`):
```python
async def _create_analysis_agents(
    self, mcp_context, process_context, agent_response_callback=None, telemetry=None
) -> GroupChatOrchestration:
    """Helper method to create analysis agents with task-local MCP context."""
    agents = []

    # Chief Architect - leads analysis
    architect_config = architect_agent(phase=MigrationPhase.ANALYSIS).render(**self.process_context)
    agent_architect = await mcp_context.create_agent(architect_config)
    agents.append(agent_architect)

    # Platform experts for source detection
    eks_config = eks_expert(phase=MigrationPhase.ANALYSIS).render(**self.process_context)
    agent_eks = await mcp_context.create_agent(eks_config)
    agents.append(agent_eks)

    gke_config = gke_expert(phase=MigrationPhase.ANALYSIS).render(**self.process_context)
    agent_gke = await mcp_context.create_agent(gke_config)
    agents.append(agent_gke)

    # Add your custom expert
    custom_config = your_custom_expert(phase=MigrationPhase.ANALYSIS).render(**self.process_context)
    agent_custom = await mcp_context.create_agent(custom_config)
    agents.append(agent_custom)

    orchestration = GroupChatOrchestration(
        members=agents,
        manager=AnalysisStepGroupChatManager(
            step_name="Analysis",
            step_objective="Discover source files and identify platform type",
            service=self.kernel_agent.kernel.services["default"],
            max_rounds=50,
            process_context=self.process_context,
            telemetry=telemetry,
        ),
        agent_response_callback=agent_response_callback,
    )

    return orchestration
```
**Design Orchestrator**: Follow the same pattern for Design and other orchestrators based on your requirements and the existing implementation patterns in `src/libs/steps/orchestration/design_orchestration.py`.

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

Refer to the actual orchestration implementations in `src/libs/steps/orchestration/` for patterns.

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

Study the existing expert agent implementations in your codebase for real patterns:

- `src/agents/azure_expert/agent_info.py` - Azure service expertise
- `src/agents/eks_expert/agent_info.py` - EKS platform knowledge
- `src/agents/gke_expert/agent_info.py` - GKE platform expertise
- `src/agents/technical_architect/agent_info.py` - Architecture oversight
- `src/agents/qa_engineer/agent_info.py` - Quality assurance patterns
- `src/agents/yaml_expert/agent_info.py` - Configuration transformation

These provide tested patterns for implementing custom expert agents in your migration solution.

## Next Steps

1. **Review Existing Agents**: Study the existing agent implementations for patterns
2. **Plan Your Agent**: Define the specific expertise and responsibilities
3. **Implement Step by Step**: Start with agent info, then add prompts and integration
4. **Test Thoroughly**: Validate the agent works well in the full orchestration flow
5. **Document Your Agent**: Create documentation for future maintenance and extension

For additional help with custom agent development, refer to:

- [Multi-Agent Orchestration Approach](MultiAgentOrchestration.md)
- [Process Framework Implementation](ProcessFrameworkGuide.md)
- [Technical Architecture](TechnicalArchitecture.md)
