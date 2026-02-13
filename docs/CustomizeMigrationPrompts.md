# Customizing Migration Prompts

This guide explains how to customize the migration prompts used by expert agents to tailor the solution for specific organizational needs, platforms, or migration patterns.

## Overview

The Container Migration Solution Accelerator uses a step-based prompt engineering system with per-agent prompts plus per-step orchestration templates (task + coordinator). You can customize these prompts to:

- Adapt to specific organizational standards and requirements
- Support additional platforms or technologies
- Implement custom migration patterns and best practices
- Integrate with existing tools and processes

## Prompt Architecture

### Step-Based Prompt System (v2)

Prompts are organized per step (analysis/design/convert/documentation). Each step uses **three** prompt layers:

1. **Task prompt template** (`prompt_task.txt`): the main step instruction given to the orchestrator.
2. **Agent instruction prompts** (`agents/prompt_*.txt`): role/persona prompts for each participating agent.
3. **Coordinator routing prompt** (`prompt_coordinator.txt`): enforces sequencing, sign-off rules, and termination criteria.

In addition, some steps use a **platform registry** (`platform_registry.json`) to select platform experts dynamically.

The canonical layout looks like:

```text
src/processor/src/steps/<step>/
├── agents/
│   ├── prompt_*.txt                # Agent instruction prompts
│   └── ...
└── orchestration/
    ├── prompt_task.txt             # Step task template (rendered with variables)
    ├── prompt_coordinator.txt      # Coordinator routing/sign-off rules
    └── platform_registry.json      # (analysis/design/documentation only)
```

### Template Variables

The step task template is rendered at runtime using `{{variable}}` placeholders (for example `{{process_id}}`, `{{container_name}}`, `{{source_file_folder}}`, `{{output_file_folder}}`, `{{workspace_file_folder}}`).

## Customizing Existing Prompts

### Step 1: Identify Target Prompts

Locate the prompt files you want to customize:

- Analysis step prompts: [src/processor/src/steps/analysis/](../src/processor/src/steps/analysis/)
- Design step prompts: [src/processor/src/steps/design/](../src/processor/src/steps/design/)
- Convert step prompts: [src/processor/src/steps/convert/](../src/processor/src/steps/convert/)
- Documentation step prompts: [src/processor/src/steps/documentation/](../src/processor/src/steps/documentation/)

Note: prompt filenames can differ by step (for example, the AKS agent prompt is [src/processor/src/steps/analysis/agents/prompt_aks.txt](../src/processor/src/steps/analysis/agents/prompt_aks.txt) in analysis, but [src/processor/src/steps/convert/agents/prompt_aks_expert.txt](../src/processor/src/steps/convert/agents/prompt_aks_expert.txt) in convert).

```bash
# List all agent prompt files
find src/processor/src/steps -path "*/agents/*" -name "prompt*.txt"

# List orchestration templates (task + coordinator)
find src/processor/src/steps -path "*/orchestration/*" -name "prompt_*.txt" -o -name "prompt_task.txt" -o -name "prompt_coordinator.txt"

# Example output:
# src/processor/src/steps/analysis/agents/prompt_architect.txt
# src/processor/src/steps/convert/agents/prompt_yaml_expert.txt
# src/processor/src/steps/documentation/agents/prompt_technical_writer.txt
# src/processor/src/steps/analysis/orchestration/prompt_task.txt
# src/processor/src/steps/analysis/orchestration/prompt_coordinator.txt
```

### Step 2: Backup Original Prompts

Create backups before customization:

```bash
# Create backup directory
mkdir src/processor/src/steps/backups

# Backup specific prompts
cp src/processor/src/steps/analysis/agents/prompt_architect.txt src/processor/src/steps/backups/

# (Recommended) also backup orchestration templates you plan to change
cp src/processor/src/steps/analysis/orchestration/prompt_task.txt src/processor/src/steps/backups/
cp src/processor/src/steps/analysis/orchestration/prompt_coordinator.txt src/processor/src/steps/backups/
```

### Step 3: Customize Prompt Content

Edit the prompt files to include your customizations:

```text
# Example: Customizing AKS Expert prompt (Analysis step)

# File: src/processor/src/steps/analysis/agents/prompt_aks.txt

# AKS Expert - Analysis Step (CUSTOMIZED FOR ORGANIZATION)

You are an Azure solution architect with expertise in enterprise migrations and deep knowledge of Azure Well-Architected Framework principles.

## ORGANIZATIONAL REQUIREMENTS
- **Compliance**: All solutions must meet SOC 2 Type II requirements
- **Security**: Implement Zero Trust security model
- **Cost Optimization**: Target 30% cost reduction from current platform
- **Naming Convention**: Follow company naming standards (env-app-region-001)

## Your Role in the Analysis Step

**Primary Objectives:**
1. **Platform Assessment**: Evaluate source platform compatibility with Azure
2. **Architecture Analysis**: Assess current architecture patterns and Azure readiness
3. **Well-Architected Review**: Apply Azure Well-Architected Framework principles
4. **Cost Analysis**: Provide preliminary cost estimates and optimization opportunities

[Continue with existing prompt content...]
```

### Step 3b: Customize the Step Task Template (if needed)

The step task template is often the highest-leverage place to customize deliverables, report structure, sign-off format, and hard-termination rules.

- Analysis task template: [src/processor/src/steps/analysis/orchestration/prompt_task.txt](../src/processor/src/steps/analysis/orchestration/prompt_task.txt)
- Design task template: [src/processor/src/steps/design/orchestration/prompt_task.txt](../src/processor/src/steps/design/orchestration/prompt_task.txt)
- Convert task template: [src/processor/src/steps/convert/orchestration/prompt_task.txt](../src/processor/src/steps/convert/orchestration/prompt_task.txt)
- Documentation task template: [src/processor/src/steps/documentation/orchestration/prompt_task.txt](../src/processor/src/steps/documentation/orchestration/prompt_task.txt)

If you edit these files, keep the `{{...}}` placeholders intact unless you are also updating the orchestrator/runtime to provide new values.

### Step 3c: Customize Coordinator Routing Rules (advanced)

The coordinator prompt controls routing and completion rules (for example sign-off gating and hard termination). Customize with care:

- Analysis coordinator rules: [src/processor/src/steps/analysis/orchestration/prompt_coordinator.txt](../src/processor/src/steps/analysis/orchestration/prompt_coordinator.txt)
- Design coordinator rules: [src/processor/src/steps/design/orchestration/prompt_coordinator.txt](../src/processor/src/steps/design/orchestration/prompt_coordinator.txt)
- Convert coordinator rules: [src/processor/src/steps/convert/orchestration/prompt_coordinator.txt](../src/processor/src/steps/convert/orchestration/prompt_coordinator.txt)
- Documentation coordinator rules: [src/processor/src/steps/documentation/orchestration/prompt_coordinator.txt](../src/processor/src/steps/documentation/orchestration/prompt_coordinator.txt)

Small wording changes here can change when the workflow terminates or which agents get selected.

### Step 3d: Customize Platform Expert Selection (registry-driven steps)

For steps that load platform experts from a registry, update the registry to add/remove experts or adjust selection signals:

- Analysis registry: [src/processor/src/steps/analysis/orchestration/platform_registry.json](../src/processor/src/steps/analysis/orchestration/platform_registry.json)
- Design registry: [src/processor/src/steps/design/orchestration/platform_registry.json](../src/processor/src/steps/design/orchestration/platform_registry.json)
- Documentation registry: [src/processor/src/steps/documentation/orchestration/platform_registry.json](../src/processor/src/steps/documentation/orchestration/platform_registry.json)

Each entry points to an agent prompt file under that step’s `agents/` folder.

### Step 4: Add Organization-Specific Context

Include your organization's specific requirements:

```text
## ORGANIZATION-SPECIFIC REQUIREMENTS

**Security Requirements:**
- All data encryption at rest and in transit
- Private endpoints for all Azure services
- Azure AD integration for all authentication
- Network segmentation following company security model

**Compliance Requirements:**
- GDPR compliance for EU data residency
- SOC 2 Type II audit trail requirements
- Financial services regulatory compliance (if applicable)
- Industry-specific compliance standards

**Technical Standards:**
- Infrastructure as Code using Terraform/Bicep
- GitOps deployment patterns with Azure DevOps
- Monitoring with Azure Monitor and custom dashboards
- Backup and disaster recovery per company RTO/RPO standards

**Cost Management:**
- Resource tagging for cost allocation
- Azure Cost Management budget alerts
- Reserved instance recommendations
- Resource optimization monitoring
```

## Common Customization Patterns

### 1. Industry-Specific Requirements

#### Healthcare (HIPAA Compliance)

```text
## HEALTHCARE COMPLIANCE REQUIREMENTS

**HIPAA Security Requirements:**
- All PHI data encrypted with Azure Key Vault managed keys
- Network isolation with private endpoints
- Audit logging for all data access
- Access controls with Azure AD conditional access

**Technical Requirements:**
- Dedicated HSM for key management
- Regional data residency enforcement
- Business Associate Agreement (BAA) compliant services only
- Comprehensive audit trail with Azure Monitor
```

#### Financial Services

```text
## FINANCIAL SERVICES REQUIREMENTS

**Regulatory Compliance:**
- PCI DSS compliance for payment data
- SOX compliance for financial reporting systems
- Regional data sovereignty requirements
- Real-time fraud detection capabilities

**Security Requirements:**
- Multi-factor authentication mandatory
- Privileged access management (PAM)
- Network segmentation and micro-segmentation
- Real-time security monitoring and alerting
```

### 2. Platform-Specific Customizations

#### EKS to AKS Migration Patterns

```text
## EKS-SPECIFIC MIGRATION PATTERNS

**AWS Service Mapping:**
- EKS → Azure Kubernetes Service (AKS)
- ALB → Azure Application Gateway
- EBS → Azure Disk Storage
- EFS → Azure Files
- ECR → Azure Container Registry
- CloudWatch → Azure Monitor

**Configuration Transformations:**
- AWS IAM Roles → Azure Workload Identity
- AWS Secrets Manager → Azure Key Vault
- AWS Parameter Store → Azure App Configuration
- VPC → Azure Virtual Network
```

### 3. Tool Integration Customizations

#### GitOps Integration

```text
## GITOPS INTEGRATION REQUIREMENTS

**Azure DevOps Integration:**
- All infrastructure defined in Azure DevOps repos
- Pipeline-based deployment with approval gates
- Automated testing in staging environments
- Production deployment requires manual approval

**ArgoCD Integration:**
- GitOps deployment patterns for application workloads
- Multi-cluster management with ArgoCD
- Application deployment automation
- Configuration drift detection and remediation
```

## Best Practices for Prompt Customization

### 1. Maintain Consistency

- Use consistent terminology across all prompts
- Follow established formatting patterns
- Maintain consistent instruction styles

### 2. Keep Context Relevant

- Include only relevant organizational requirements
- Avoid overly specific details that may not apply broadly
- Balance specificity with flexibility

### 3. Test Thoroughly

- Test prompts with various input scenarios
- Validate outputs meet organizational requirements
- Monitor performance impact of customizations

### 4. Document Changes

- Maintain change logs for prompt modifications
- Document rationale for customizations
- Track performance impact of changes

### 5. Version Control

- Use version control for prompt files
- Tag stable prompt versions
- Implement rollback procedures

## Troubleshooting Common Issues

### Issue 1: Prompt Too Long

**Problem**: Prompt exceeds token limits
**Solution**:

- Break down complex prompts into sections
- Use prompt templates with dynamic insertion
- Prioritize most important requirements

### Issue 2: Inconsistent Responses

**Problem**: Agent responses vary significantly
**Solution**:

- Add more specific constraints and examples
- Use structured output formats
- Implement response validation

### Issue 3: Missing Context

**Problem**: Agent lacks sufficient context for decisions
**Solution**:

- Enhance prompts with more background information
- Add examples of expected inputs and outputs
- Include decision criteria and constraints

## Examples

### Example 1: Custom Security Requirements

```text
## ENTERPRISE SECURITY REQUIREMENTS

**Zero Trust Architecture:**
- Verify every user and device explicitly
- Use least privilege access principles
- Assume breach and verify continuously

**Security Controls:**
- Multi-factor authentication required
- Conditional access policies enforced
- Privileged Identity Management (PIM) enabled
- Just-in-time access for administrative tasks

**Compliance Requirements:**
- All resources must be tagged for compliance tracking
- Data classification and protection policies applied
- Audit logs retained for 7 years minimum
- Regular security assessments and penetration testing
```

### Example 2: Cost Optimization Focus

```text
## COST OPTIMIZATION REQUIREMENTS

**Cost Targets:**
- Achieve 30% cost reduction from current platform
- Implement automated cost monitoring and alerting
- Use Azure Hybrid Benefit for Windows licenses
- Maximize use of reserved instances and spot instances

**Resource Optimization:**
- Right-size all compute resources based on utilization
- Implement auto-scaling for variable workloads
- Use Azure Storage tiers for cost optimization
- Implement resource scheduling for non-production environments

**Monitoring and Governance:**
- Set up cost allocation tags for chargeback
- Implement budget alerts and automatic actions
- Regular cost optimization reviews with stakeholders
- Track and report on cost optimization metrics
```

## Next Steps

1. **Identify Customization Needs**: Assess your organization's specific requirements
2. **Plan Customizations**: Prioritize prompt customizations based on impact
3. **Implement Gradually**: Start with high-impact, low-risk customizations
4. **Test and Validate**: Thoroughly test customized prompts
5. **Monitor and Iterate**: Continuously monitor and improve prompt performance

For additional information, refer to:

- [Adding Custom Expert Agents](CustomizeExpertAgents.md)
- [Multi-Agent Orchestration Approach](MultiAgentOrchestration.md)
- [Technical Architecture](TechnicalArchitecture.md)
