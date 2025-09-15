# Extending Platform Support

This guide explains how to extend the Container Migration Solution Accelerator to support additional source platforms beyond EKS and GKE, and provides comprehensive setup instructions for different development environments including Windows, Linux, and macOS.

## Overview

The solution is designed with a modular architecture that makes it relatively straightforward to add support for new container platforms. This guide covers the process of adding support for platforms like:

- Red Hat OpenShift
- Docker Swarm
- Azure Container Instances (ACI)
- Nomad
- Rancher
- VMware Tanzu
- Cloud Foundry
- Custom orchestration platforms

## Platform Support Architecture

### Current Platform Support

The solution currently supports:

- **Amazon EKS**: Full migration support with AWS-specific service mapping
- **Google GKE**: Complete GKE to AKS transformation capabilities
- **Generic Kubernetes**: Basic Kubernetes workload migration

### Platform Detection System

The platform detection is handled through:

1. **Configuration Analysis**: Scanning YAML files for platform-specific resources
2. **Expert Agent Selection**: Choosing appropriate expert agents based on detected platform
3. **Transformation Mapping**: Applying platform-specific transformation rules

## Adding New Platform Support

### Real-World Example: Adding Red Hat OpenShift Support

To illustrate the complete process, let's walk through adding Red Hat OpenShift support step-by-step:

#### Example Platform Analysis (Step 1)

```markdown
## OpenShift Platform Analysis

**Platform Name**: Red Hat OpenShift Container Platform
**Version Support**: 4.10+
**Core Technologies**: Kubernetes, CRI-O, OVN-Kubernetes, Red Hat Enterprise Linux CoreOS

**Unique Resources:**
- Routes (`route.openshift.io/v1`) - OpenShift's ingress mechanism
- DeploymentConfigs (`deploymentconfig.apps.openshift.io/v1`) - Enhanced deployments with triggers
- ImageStreams (`imagestream.image.openshift.io/v1`) - Image repository abstraction
- BuildConfigs (`buildconfig.build.openshift.io/v1`) - Source-to-Image (S2I) builds
- Security Context Constraints (SCCs) - Pod security policies
- Projects - Kubernetes namespaces with additional RBAC

**Service Ecosystem:**
- Container registry: Integrated registry with ImageStreams
- Networking: Routes, NetworkPolicy, Multus CNI
- Storage: Dynamic provisioning with multiple CSI drivers
- Monitoring: Built-in Prometheus and Grafana
- Security: Integrated OAuth, RBAC, SCCs

**Migration Challenges:**
- Routes → Azure Application Gateway ingress mapping
- BuildConfigs → Azure DevOps/GitHub Actions pipeline conversion
- ImageStreams → Azure Container Registry integration
- SCCs → Pod Security Standards migration
- OpenShift-specific operators → Azure service equivalents
```

#### Example Agent Creation (Step 2)

```bash
# Create OpenShift expert directory
mkdir src/agents/openshift_expert

# Create agent files
touch src/agents/openshift_expert/agent_info.py
touch src/agents/openshift_expert/prompt-analysis.txt
touch src/agents/openshift_expert/prompt-design.txt
touch src/agents/openshift_expert/prompt-yaml.txt
touch src/agents/openshift_expert/prompt-documentation.txt
```

```python
# src/agents/openshift_expert/agent_info.py
from agents.agent_info_util import MigrationPhase, load_prompt_text
from utils.agent_builder import AgentType, agent_info

def get_agent_info(phase: MigrationPhase | str | None = None) -> agent_info:
    """Get OpenShift Expert agent info with optional phase-specific prompt."""
    return agent_info(
        agent_name="OpenShift_Expert",
        agent_type=AgentType.ChatCompletionAgent,
        agent_description="Red Hat OpenShift expert specializing in container platform migration to Azure Kubernetes Service with deep knowledge of Routes, DeploymentConfigs, ImageStreams, and OpenShift operators.",
        agent_instruction=load_prompt_text(phase=phase),
    )
```

#### How Platform Detection Really Works

Your codebase uses **intelligent multi-agent conversation** for platform detection, not explicit detection classes. Here's how it actually works:

```python
# Real platform detection flow (from analysis_orchestration.py)
# 1. Multi-agent team collaborates: Technical Architect + EKS Expert + GKE Expert
# 2. Agents examine YAML files and discuss findings through conversation
# 3. Expert consensus emerges through collaborative analysis
# 4. Result captured in termination_output.platform_detected

# Current agent team structure (analysis_orchestration.py):
from agents.technical_architect.agent_info import get_agent_info as architect_agent
from agents.eks_expert.agent_info import get_agent_info as eks_expert  
from agents.gke_expert.agent_info import get_agent_info as gke_expert

# Agent creation with phase-specific prompts:
architect_config = architect_agent(phase=MigrationPhase.ANALYSIS)
eks_config = eks_expert(phase=MigrationPhase.ANALYSIS)
gke_config = gke_expert(phase=MigrationPhase.ANALYSIS)

# Result structure:
platform_detected: str = Field(description="Platform detected (EKS or GKE only)")
confidence_score: str = Field(description="Confidence score for platform detection (e.g., '95%')")
```

#### Adding New Platform Expert to Agent Team

To add OpenShift support, you would register the new expert in the analysis orchestration:

```python
# In analysis_orchestration.py, add import:
from agents.openshift_expert.agent_info import get_agent_info as openshift_expert

# In _create_analysis_agents method, add OpenShift expert:
openshift_config = openshift_expert(phase=MigrationPhase.ANALYSIS).render(
    **self.process_context
)
agent_openshift = await mcp_context.create_agent(openshift_config)
agents.append(agent_openshift)

# The multi-agent conversation will then include:
# - Technical Architect (orchestrates analysis)
# - EKS Expert (recognizes AWS/EKS patterns)
# - GKE Expert (recognizes GCP/GKE patterns)  
# - OpenShift Expert (recognizes OpenShift-specific patterns)
```

### Step-by-Step Implementation Guide

### Step 1: Analyze Platform Characteristics

Before adding support, analyze the target platform:

```markdown
## Platform Analysis Template

**Platform Name**: [e.g., OpenShift]
**Version Support**: [e.g., 4.x]
**Core Technologies**: [e.g., Kubernetes, CRI-O, OVN]

**Unique Resources:**
- Custom Resource Definitions (CRDs)
- Platform-specific resource types
- Networking constructs
- Storage classes and provisioners

**Service Ecosystem:**
- Container registry integration
- Networking solutions
- Storage solutions
- Monitoring and logging
- Security features

**Migration Challenges:**
- Platform-specific configurations
- Proprietary extensions
- Networking differences
- Storage considerations
- Security model differences
```

### Step 2: Create Platform-Specific Expert Agent

Create a specialized expert agent for the new platform:

```bash
# Create agent directory
mkdir src/agents/platform_name_expert

# Create required files
touch src/agents/platform_name_expert/agent_info.py
touch src/agents/platform_name_expert/prompt-analysis.txt
touch src/agents/platform_name_expert/prompt-design.txt
touch src/agents/platform_name_expert/prompt-yaml.txt
touch src/agents/platform_name_expert/prompt-documentation.txt
```

Example agent structure based on existing codebase:

```python
# src/agents/new_platform_expert/agent_info.py

from agents.agent_info_util import MigrationPhase, load_prompt_text
from utils.agent_builder import AgentType, agent_info

def get_agent_info(phase: MigrationPhase | str | None = None) -> agent_info:
    """Get New Platform Expert agent info with optional phase-specific prompt.

    Args:
        phase (MigrationPhase | str | None): Migration phase ('analysis', 'design', 'yaml', 'documentation').
                              If provided, loads phase-specific prompt.
    """
    return agent_info(
        agent_name="NewPlatform_Expert",
        agent_type=AgentType.ChatCompletionAgent,
        agent_description="Platform expert specializing in [Platform Name] with expertise in Kubernetes migration initiatives.",
        agent_instruction=load_prompt_text(phase=phase),
    )

# Note: Create prompt files in the same directory:
# - prompt-analysis.txt
# - prompt-design.txt
# - prompt-yaml.txt
# - prompt-documentation.txt
```

### Step 3: Integrate with Existing Orchestration

Add your new platform expert to the existing orchestration logic:

```python
# Integration with existing analysis orchestration
# Reference: src/libs/steps/orchestration/analysis_orchestration.py

# When adding platform detection, integrate with the existing
# analysis orchestration structure that includes:
# - Technical Architect (chief architect)
# - EKS Expert
# - GKE Expert
# - Your new platform expert

# Follow the existing pattern of phase-specific agent loading
# that uses MigrationPhase enum values
```

**Note:** The current codebase uses a sophisticated orchestration system with `GroupChatOrchestration` and phase-specific prompts. Platform detection logic should be integrated with the existing analysis orchestration rather than creating new standalone classes.


### Step 4: Update Agent Registration

When adding new platform support, ensure proper agent registration in the orchestration system:

```python
# Follow the existing pattern in analysis_orchestration.py
# which imports agents like:
from agents.eks_expert.agent_info import get_agent_info as eks_expert
from agents.gke_expert.agent_info import get_agent_info as gke_expert
from agents.technical_architect.agent_info import get_agent_info as architect_agent

# Add your new platform expert:
from agents.your_platform_expert.agent_info import get_agent_info as your_platform_expert
```

**Note:** The current codebase follows the Semantic Kernel Process Framework with specialized orchestration for each migration phase. Platform-specific logic should integrate with the existing `StepGroupChatOrchestrator` and `GroupChatOrchestration` patterns.

### Step 5: Update the Analysis Orchestration

Integrate your new platform expert into the actual analysis orchestration:

```python
# In src/libs/steps/orchestration/analysis_orchestration.py
# Add import for your new expert:
from agents.openshift_expert.agent_info import get_agent_info as openshift_expert

# In the _create_analysis_agents method, add your expert to the agent team:
async def _create_analysis_agents(self, mcp_context, process_context, agent_response_callback=None, telemetry=None):
    agents = []
    
    # Technical Architect (orchestrates the analysis)
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
    
    # Add your new platform expert
    openshift_config = openshift_expert(phase=MigrationPhase.ANALYSIS).render(**self.process_context)
    agent_openshift = await mcp_context.create_agent(openshift_config)
    agents.append(agent_openshift)

    return GroupChatOrchestration(members=agents, manager=AnalysisStepGroupChatManager(...))
```

**Key Points:**
- Each expert gets phase-specific prompts through `MigrationPhase.ANALYSIS`
- Agents are created with the MCP context for tool access
- The `render(**self.process_context)` provides runtime context to agents

### Step 6: Implement Platform-Specific Prompts

Create detailed prompts for each migration phase:

#### Analysis Phase Prompt

```text
# OpenShift Expert - Analysis Phase

You are an OpenShift expert with deep knowledge of Red Hat OpenShift Container Platform and its migration to Azure Kubernetes Service.

## Your Role in Analysis Phase

**Primary Objectives:**
1. **OpenShift Resource Detection**: Identify all OpenShift-specific resources and configurations
2. **Complexity Assessment**: Evaluate migration complexity for OpenShift workloads
3. **Dependency Analysis**: Map OpenShift operators and dependencies
4. **Azure Readiness**: Assess readiness for Azure migration

**OpenShift-Specific Analysis:**
- **Routes**: Analyze OpenShift Routes and ingress patterns
- **DeploymentConfigs**: Evaluate deployment configurations and triggers
- **ImageStreams**: Assess image management and registry usage
- **BuildConfigs**: Analyze Source-to-Image (S2I) build processes
- **Operators**: Inventory installed operators and their Azure equivalents
- **Security Context Constraints (SCCs)**: Review security policies
- **Projects**: Analyze OpenShift project structure and RBAC

**Migration Complexity Factors:**
- Custom operators without Azure equivalents
- Complex build pipelines and S2I dependencies
- Extensive use of OpenShift-specific networking
- Custom security context constraints
- Integration with Red Hat ecosystem services

**Expected Deliverables:**
- Complete inventory of OpenShift-specific resources
- Migration complexity assessment with detailed rationale
- Dependency mapping and Azure service recommendations
- Initial transformation strategy and approach
```

#### Design Phase Prompt

```text
# OpenShift Expert - Design Phase

Transform OpenShift workloads to Azure-native architectures following Azure Well-Architected Framework principles.

## Your Role in Design Phase

**Primary Objectives:**
1. **Service Transformation**: Map OpenShift services to Azure equivalents
2. **Architecture Optimization**: Design Azure-optimized architectures
3. **Security Model**: Adapt OpenShift security to Azure security patterns
4. **Integration Strategy**: Design integration with Azure services

**OpenShift to Azure Service Mapping:**
- **OpenShift Routes** → Azure Application Gateway + Ingress Controller
- **ImageStreams** → Azure Container Registry
- **BuildConfigs** → Azure DevOps Pipelines
- **OpenShift Operators** → Azure services or community operators
- **OpenShift Monitoring** → Azure Monitor + Prometheus
- **OpenShift Logging** → Azure Monitor Logs

**Architecture Design Considerations:**
- Replace OpenShift Projects with Kubernetes Namespaces + Azure RBAC
- Implement Pod Security Standards instead of Security Context Constraints
- Design Azure AD integration for authentication and authorization
- Plan Azure Key Vault integration for secrets management
- Design Azure Monitor integration for comprehensive observability

**Expected Deliverables:**
- Detailed Azure architecture design
- Service mapping and transformation strategy
- Security model and RBAC design
- Integration patterns with Azure services
```

### Step 6: Test Your Platform Expert

Test your new platform expert using the existing testing patterns:

```python
# tests/unit/test_openshift_expert.py

import pytest
from agents.openshift_expert.agent_info import get_agent_info
from agents.agent_info_util import MigrationPhase

class TestOpenShiftExpert:
    """Test OpenShift expert agent following existing patterns"""

    def test_agent_info_structure(self):
        """Test that agent info follows the standard structure"""
        agent_info = get_agent_info()
        
        # Verify required attributes exist
        assert hasattr(agent_info, 'agent_name')
        assert hasattr(agent_info, 'agent_type') 
        assert hasattr(agent_info, 'agent_description')
        assert hasattr(agent_info, 'agent_instruction')
        
        # Verify agent name matches expected pattern
        assert agent_info.agent_name == "OpenShift_Expert"
        
    def test_phase_specific_prompts(self):
        """Test that phase-specific prompts are loaded correctly"""
        # Test each migration phase
        for phase in MigrationPhase:
            agent_info = get_agent_info(phase=phase)
            assert agent_info.agent_instruction is not None
            assert len(agent_info.agent_instruction) > 0
            
    def test_analysis_phase_prompt(self):
        """Test analysis phase specific functionality"""
        agent_info = get_agent_info(phase=MigrationPhase.ANALYSIS)
        
        # Verify the prompt contains OpenShift-specific content
        prompt = agent_info.agent_instruction.lower()
        assert "openshift" in prompt or "route" in prompt
        
# Run tests using existing test framework:
# uv run python -m pytest tests/unit/test_openshift_expert.py -v
```

## Troubleshooting Platform Extensions

### Common Issues

1. **Incomplete Platform Detection**
   - Add more signature patterns
   - Improve confidence scoring
   - Handle edge cases and variations

2. **Transformation Failures**
   - Validate transformation logic thoroughly
   - Handle missing or optional fields
   - Provide fallback transformations

3. **Performance Issues**
   - Optimize detection algorithms
   - Cache transformation results
   - Parallelize processing where possible

## Next Steps

For additional information, refer to:

- [Adding Custom Expert Agents](CustomizeExpertAgents.md)
- [Customizing Migration Prompts](CustomizeMigrationPrompts.md)
- [Technical Architecture](TechnicalArchitecture.md)
- [Multi-Agent Orchestration Approach](MultiAgentOrchestration.md)
