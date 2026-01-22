# Multi-Agent Orchestration Approach

This guide provides an in-depth look at the multi-agent orchestration system used by the Container Migration Solution Accelerator, including design principles, agent collaboration patterns, and implementation details.

## Overview

The Container Migration Solution Accelerator uses a multi-agent orchestration approach built on Microsoft Agent Framework group chat orchestration (`GroupChatOrchestrator`). This enables multiple specialized agents to collaborate per migration step (analysis/design/yaml/documentation), bringing domain expertise and quality gates to each phase.

## Agent Roles

### Platform Experts (Source Kubernetes)

Platform experts provide source-platform-specific context and are selected dynamically based on platform signals detected during analysis (registry-driven). Built-in examples include **EKS**, **GKE/Anthos**, **OpenShift**, **Rancher (RKE/RKE2/K3s)**, **VMware Tanzu**, and **self-managed/on-prem Kubernetes**.

### EKS Expert

- **Role**: Amazon EKS migration expertise
- **Responsibilities**:
  - EKS workload analysis
  - AWS service mapping (IAM/IRSA, ELB/ALB patterns, EBS/EFS)
  - AWS-to-Azure translations

### GKE Expert

- **Role**: Google GKE migration expertise
- **Responsibilities**:
  - GKE workload analysis
  - Google Cloud service mapping
  - Container migration from GCR
  - Network policy transformation
  - Identity and access management

### OpenShift Expert

- **Role**: Red Hat OpenShift migration expertise
- **Responsibilities**:
  - OpenShift resource detection (Routes, SCC, Operators)
  - OpenShift-to-AKS mapping guidance

### Rancher Expert

- **Role**: Rancher/RKE migration expertise
- **Responsibilities**:
  - Rancher-managed cluster patterns (Fleet, Projects/RBAC)
  - GitOps and multi-cluster management mapping

### Tanzu Expert

- **Role**: VMware Tanzu/TKG migration expertise
- **Responsibilities**:
  - Tanzu/TKG-specific identity and networking patterns
  - Migration considerations for vSphere integration

### OnPremK8s Expert

- **Role**: Self-managed/on-prem Kubernetes migration expertise
- **Responsibilities**:
  - Common on-prem dependencies (ingress/LB, storage, identity)
  - On-prem-to-AKS modernization considerations

### 3. Quality and Documentation Agents

#### QA Engineer

- **Role**: Quality assurance and validation
- **Responsibilities**:
  - Migration plan validation
  - Test strategy development
  - Quality gate definition
  - Risk identification
  - Compliance verification

#### Technical Writer

- **Role**: Documentation quality and structure
- **Responsibilities**:
  - Documentation organization
  - Technical writing standards
  - User guide creation
  - Process documentation
  - Knowledge base maintenance

### 4. Specialized Technical Agents

#### YAML Expert

- **Role**: Configuration syntax and optimization
- **Responsibilities**:
  - YAML syntax validation and optimization
  - Configuration best practices
  - Resource optimization
  - Template standardization
  - Schema validation

## Orchestration Patterns

### 1. Step Orchestrators (Agent Framework)

Each migration step owns an orchestrator class responsible for:

- Preparing MCP tools required by the step (e.g., Blob IO, Microsoft Learn, Fetch)
- Loading and rendering agent prompt files
- Running the multi-agent conversation via `GroupChatOrchestrator`

Example (simplified; see `src/processor/src/steps/*/orchestration/*_orchestrator.py` under [src/processor/src/steps/](../src/processor/src/steps/)):

```python
from libs.agent_framework.groupchat_orchestrator import GroupChatOrchestrator


class SomeStepOrchestrator:
    async def execute(self, task_param):
        prompt = self.render_step_prompt(task_param)
        tools = await self.prepare_mcp_tools()
        agents = await self.prepare_agent_infos(task_param, tools)

        # MCP tools are async context managers; keep them open for the duration
        async with (tools[0], tools[1], tools[2]):
            orchestrator = GroupChatOrchestrator(
                name="SomeStepOrchestrator",
                process_id=task_param.process_id,
                participants=agents,
                memory_client=None,
                result_output_format=SomeStepResultModel,
            )

            return await orchestrator.run_stream(
                input_data=prompt,
                on_agent_response=self.on_agent_response,
                on_workflow_complete=self.on_orchestration_complete,
                on_agent_response_stream=self.on_agent_response_stream,
            )
```

### 2. MCP Tool Integration

The processor integrates MCP servers as Agent Framework tools. Typical tools include:

- `Microsoft Learn MCP` (HTTP)
- `Fetch MCP Tool` (stdio)
- `azure_blob_io_service` (Blob IO operations; internal MCP wrapper)
- `datetime_service` (timestamps/time-window logic)
- `yaml_inventory_service` (ground runbooks in real converted objects)

### 3. Platform-Specific Experts (Registry Driven)

Some steps dynamically include platform experts based on signals (e.g., EKS, GKE, OpenShift). The registry-driven approach keeps this extensible.

## Key Takeaways

This orchestration model enables reliable step-by-step collaboration:

- Step orchestrators prepare tools and prompts, then run a `GroupChatOrchestrator` per phase
- MCP servers are exposed as Agent Framework tools
- Platform experts are selected via a registry to keep extensions modular
- Quality gates require PASS/FAIL sign-offs before the workflow proceeds


This multi-agent orchestration approach provides a sophisticated, extensible foundation for complex container migration scenarios while maintaining clean separation of concerns and robust error handling.

## Summary

The Container Migration Solution Accelerator's multi-agent orchestration system demonstrates:

- **Specialized Agent Architecture**: Each agent brings domain-specific expertise to the migration process
- **Phase-Based Collaboration**: Structured workflows with clear handoffs between migration phases
- **Robust Resource Management**: TaskGroup-safe MCP context management and intelligent memory handling
- **Comprehensive Telemetry**: Complete tracking of agent activities and migration progress
- **Extensible Design**: Modular architecture supporting new platforms and agent types

This approach ensures reliable, scalable container migrations while maintaining high quality through collaborative AI expertise.
