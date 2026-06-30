# Extending Platform Support

This guide explains how to extend the Container Migration Solution Accelerator to support additional source Kubernetes platforms/distributions (including enterprise and on-prem/self-managed environments), and provides comprehensive setup instructions for different development environments including Windows, Linux, and macOS.

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
- **Google GKE/Anthos**: GKE/Anthos to AKS transformation capabilities
- **Red Hat OpenShift**: OpenShift-aware analysis and migration guidance
- **Rancher (RKE/RKE2/K3s)**: Rancher-aware analysis and migration guidance
- **VMware Tanzu (TKG/TKGS)**: Tanzu-aware analysis and migration guidance
- **Self-managed / On-prem Kubernetes**: On-prem-aware analysis and migration guidance
- **Generic Kubernetes**: Baseline Kubernetes workload migration

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
# Add an OpenShift expert prompt for the analysis step
touch src/processor/src/steps/analysis/agents/prompt_openshift.txt

# Register it so it can be selected during analysis
edit src/processor/src/steps/analysis/orchestration/platform_registry.json
```

For other phases, add corresponding prompt files under:

- [src/processor/src/steps/design/agents/](../src/processor/src/steps/design/agents/)
- [src/processor/src/steps/convert/agents/](../src/processor/src/steps/convert/agents/)
- [src/processor/src/steps/documentation/agents/](../src/processor/src/steps/documentation/agents/)

#### How Platform Detection Really Works

Your codebase uses **intelligent multi-agent conversation** for platform detection, not explicit detection classes. Here's how it actually works:

```python
# Real platform detection flow (from analysis_orchestration.py)
# 1. Multi-agent team collaborates: Technical Architect + one or more platform experts (registry-driven)
# 2. Agents examine YAML files and discuss findings through conversation
# 3. Expert consensus emerges through collaborative analysis
# 4. Result captured in termination_output.platform_detected

# Current agent team structure (analysis_orchestrator.py):
# - Technical Architect (orchestrates analysis)
# - Platform experts loaded from `platform_registry.json` (e.g., EKS, GKE/Anthos, OpenShift, Rancher, Tanzu, OnPremK8s)

# Result structure:
platform_detected: str = Field(description="Platform detected (e.g., EKS/GKE/OpenShift/Rancher/Tanzu/OnPremK8s)")
confidence_score: str = Field(description="Confidence score for platform detection (e.g., '95%')")
```

#### Adding New Platform Expert to Agent Team

To add OpenShift support, you would register the new expert in the analysis orchestration:

```python
# Add an OpenShift expert prompt file under:
#   src/processor/src/steps/analysis/agents/
#
# Then add a registry entry under:
#   src/processor/src/steps/analysis/orchestration/platform_registry.json
#
# The analysis orchestrator loads experts from the registry and constructs AgentInfo
# participants with MCP tools, then runs the group chat orchestration.

# The multi-agent conversation will then include:
# - Technical Architect (orchestrates analysis)
# - One or more platform experts selected via registry signals
#   (e.g., EKS, GKE/Anthos, OpenShift, Rancher, Tanzu, OnPremK8s)
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
# Add a new prompt file for your platform expert (analysis step)
touch src/processor/src/steps/analysis/agents/prompt_<platform>_expert.txt

# Register the expert for analysis selection
edit src/processor/src/steps/analysis/orchestration/platform_registry.json
```

Create or customize the prompt file content to cover detection signals, key resources, migration challenges, and Azure mapping guidance.

### Step 3: Integrate with Existing Orchestration

Add your new platform expert to the existing orchestration logic:

```python
# Integration with existing analysis orchestration
# Reference: src/processor/src/steps/analysis/orchestration/analysis_orchestrator.py
# Platform experts for analysis are configured via:
#   src/processor/src/steps/analysis/orchestration/platform_registry.json
```

**Note:** Platform detection should be integrated into the existing analysis step orchestration rather than creating a new standalone pipeline.


### Step 4: Update Agent Registration

When adding new platform support, ensure proper agent registration in the orchestration system:

For the analysis phase, register your new platform expert by:

1. Adding a new prompt file under [src/processor/src/steps/analysis/agents/](../src/processor/src/steps/analysis/agents/)
2. Adding an entry to [src/processor/src/steps/analysis/orchestration/platform_registry.json](../src/processor/src/steps/analysis/orchestration/platform_registry.json)

For other phases, update the relevant step orchestrator’s `prepare_agent_infos()` to include a new `AgentInfo`.

**Note:** The current codebase uses an Agent Framework workflow with step-level group-chat orchestration. Platform-specific logic should integrate with the existing step orchestrators (analysis/design/yaml/documentation) and their group-chat patterns, rather than introducing a new end-to-end pipeline.

### Step 5: Update the Analysis Orchestration

Integrate your new platform expert into the actual analysis orchestration:

```python
# In src/processor/src/steps/analysis/orchestration/analysis_orchestrator.py
# Platform experts are loaded from platform_registry.json.
# Add a new registry entry pointing to your prompt file, e.g.:
# {
#   "agent_name": "OpenShift Expert",
#   "prompt_file": "prompt-openshift-expert.txt"
# }
```

**Key Points:**

- Analysis experts are loaded from [src/processor/src/steps/analysis/orchestration/platform_registry.json](../src/processor/src/steps/analysis/orchestration/platform_registry.json) (config-driven)
- Each agent gets MCP tool access via the step orchestrator’s `self.mcp_tools`
- Prompts are rendered from files under the step’s `agents/` directory

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
# src/processor/src/tests/unit/test_platform_registry.py

import json
from pathlib import Path


def test_platform_registry_entry_exists():
    registry_path = Path("src/processor/src/steps/analysis/orchestration/platform_registry.json")
    data = json.loads(registry_path.read_text(encoding="utf-8"))

    # Example: ensure an OpenShift expert is registered
    assert any("openshift" in (item.get("agent_name", "").lower()) for item in data)


def test_platform_prompt_file_exists():
    prompt_path = Path("src/processor/src/steps/analysis/agents/prompt_openshift.txt")
    assert prompt_path.exists()
    assert "openshift" in prompt_path.read_text(encoding="utf-8").lower()


# Run tests using existing test framework:
# uv run --prerelease=allow python -m pytest src/processor/src/tests/unit -v
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
