# Agentic Architecture - Container Migration Solution Accelerator

Based on your actual implementation, here's the comprehensive agentic architecture that mirrors the style of your reference image:

## Architecture Overview

```mermaid
flowchart LR
    %% Top-level orchestration + telemetry
    TELEM[Agent and Process Status\nReal-time telemetry]
    COSMOS[(Cosmos DB\ntelemetry/state)]
    PROC[Process Orchestration\nAgent Framework WorkflowBuilder]

    TELEM --> COSMOS
    PROC --- TELEM

    %% Step lanes (match the README image layout)
    subgraph STEP1["Step 1: Analysis"]
        direction TB
        S1EXEC[Analysis Executor]
        S1ORCH[Analysis Chat Orchestrator\nGroupChatOrchestrator]
        S1AGENTS["Analysis Agents\nChief Architect\nAKS Expert\nPlatform Experts (EKS/GKE/...)\nCoordinator"]
        S1EXEC --> S1ORCH --> S1AGENTS
    end

    subgraph STEP2["Step 2: Design"]
        direction TB
        S2EXEC[Design Executor]
        S2ORCH[Design Chat Orchestrator\nGroupChatOrchestrator]
        S2AGENTS["Design Agents\nChief Architect\nAzure Architect\nAKS Expert\nPlatform Experts (EKS/GKE/...)\nCoordinator"]
        S2EXEC --> S2ORCH --> S2AGENTS
    end

    subgraph STEP3["Step 3: YAML Conversion"]
        direction TB
        S3EXEC[Convert Executor]
        S3ORCH[YAML Chat Orchestrator\nGroupChatOrchestrator]
        S3AGENTS["YAML Converting Agents\nYAML Expert\nAzure Architect\nAKS Expert\nQA Engineer\nChief Architect\nCoordinator"]
        S3EXEC --> S3ORCH --> S3AGENTS
    end

    subgraph STEP4["Step 4: Documentation"]
        direction TB
        S4EXEC[Documentation Executor]
        S4ORCH[Documentation Chat Orchestrator\nGroupChatOrchestrator]
        S4AGENTS["Documentation Agents\nTechnical Writer\nAzure Architect\nAKS Expert\nChief Architect\nPlatform Experts (EKS/GKE/...)\nCoordinator"]
        S4EXEC --> S4ORCH --> S4AGENTS
    end

    %% Step sequencing
    PROC --> STEP1
    STEP1 -->|Analysis Result| STEP2
    STEP2 -->|Design Result| STEP3
    STEP3 -->|YAML Converting Result| STEP4

    %% MCP tools
    subgraph MCPTOOLS["MCP Server Tools"]
        direction LR
        BLOB[Azure Blob IO Operation]
        DT[Datetime Utility]
        DOCS[Microsoft Learn MCP]
        FETCH[Fetch MCP Tool]
        MERMAID[Mermaid Validation]
        YINV[YAML Inventory]
    end

    STEP1 --- MCPTOOLS
    STEP2 --- MCPTOOLS
    STEP3 --- MCPTOOLS
    STEP4 --- MCPTOOLS

    %% External systems
    STORAGE[(Azure Blob Storage)]
    LEARN[(Microsoft Learn\nMCP Server)]

    BLOB --> STORAGE
    DOCS --> LEARN

    %% Style (keep minimal; Mermaid defaults render consistently)
    style PROC fill:#111827,color:#ffffff,stroke:#111827
    style MCPTOOLS fill:#f8fafc,stroke:#94a3b8
    style STORAGE fill:#e0f2fe,stroke:#0284c7
    style COSMOS fill:#e0f2fe,stroke:#0284c7
    style LEARN fill:#ffffff,stroke:#94a3b8
```

## Agent Specialization by Phase

### Analysis Phase Agents

- **Technical Architect**: Leads overall analysis strategy and coordination
- **EKS Expert**: Identifies AWS EKS-specific patterns and configurations
- **GKE Expert**: Identifies Google GKE-specific patterns and configurations

### Design Phase Agents

- **Technical Architect**: Defines migration architecture patterns
- **Azure Architect**: Designs Azure service mappings and optimizations
- **AKS Expert**: Ensures AKS-specific conventions and constraints are applied
- **EKS Expert**: Provides source platform context for AWS workloads
- **GKE Expert**: Provides source platform context for GCP workloads

### YAML Conversion Phase Agents

- **YAML Expert**: Performs configuration transformations and syntax optimization
- **Azure Architect**: Ensures Azure service integration and compliance
- **AKS Expert**: Ensures converted manifests align with AKS expectations
- **QA Engineer**: Validates converted configurations and tests
- **Technical Writer**: Documents conversion decisions and generates reports

### Documentation Phase Agents

- **Technical Architect**: Provides architectural documentation and migration summary
- **Azure Architect**: Documents Azure-specific configurations and optimizations
- **AKS Expert**: Documents AKS-focused implementation guidance and caveats
- **EKS/GKE Experts**: Document source platform analysis and transformation logic
- **QA Engineer**: Provides validation reports and testing documentation
- **Technical Writer**: Creates comprehensive migration documentation

## Data Flow Architecture

### Input Processing

1. **Web app** creates a migration request
2. **Queue worker service** receives the migration request from **Azure Storage Queue**
3. **Migration Processor** runs the end-to-end workflow (analysis → design → yaml → documentation)

### Step Execution Pattern

Each step follows this pattern:

![execution pattern](./images/readme/execution_pattern.png)

### Storage Integration

- **Source Files**: Read from Azure Blob Storage via MCP Blob Operations
- **Working Files**: All processing files managed through Azure Blob Storage
- **Output Files**: Generated configurations and reports saved to Azure Blob Storage
- **Telemetry**: Agent interactions and process metrics stored in Azure Cosmos DB

### MCP Server Integration

All agents have access to Model Context Protocol (MCP) servers via Microsoft Agent Framework tool abstractions:

- **Blob Operations**: File reading/writing to Azure Blob Storage
- **Microsoft Docs**: Azure documentation lookup and best practices
- **DateTime Utilities**: Timestamp generation and time-based operations
- **Fetch**: URL fetching for validation (e.g., verifying references)
- **YAML Inventory**: Enumerate converted YAML objects for runbooks

## Key Architectural Principles

### Single Responsibility

Each step has a focused objective:

- Analysis: Platform detection and file discovery
- Design: Azure architecture and service mapping
- YAML: Configuration transformation and validation
- Documentation: Comprehensive report generation

### Event-Driven Orchestration

Steps are executed as a directed workflow (with start node and edges) using the Agent Framework workflow engine.
The processor emits workflow/executor events for observability and telemetry.

### Multi-Agent Collaboration

Within each step, specialized agents collaborate through group chat orchestration:

- Structured conversation patterns
- Domain expertise contribution
- Consensus building on decisions
- Quality validation and review

### Evaluation and Quality Checks

The processor uses multiple quality signals to reduce regressions and increase reliability:

- **Typed step outputs**: workflow executors and orchestrators exchange typed models per step (analysis → design → yaml → documentation).
- **QA sign-offs**: the QA agent focuses on validation steps and flags missing/unsafe transformations.
- **Tool-backed validation**: steps can call validation tools via MCP (e.g., Mermaid validation, YAML inventory grounding, docs lookups).
- **Unit tests**: processor unit tests live under `src/processor/src/tests/unit/`.

### Tool-Enabled Intelligence

Agents access external capabilities through MCP servers:

- Cloud storage integration
- Documentation lookup
- Time-based operations

### Observability & Monitoring

Comprehensive tracking throughout the process:

- Agent interaction telemetry
- Process execution metrics
- Error handling and recovery
- Performance optimization data

## File Location Mapping

```text
src/processor/src/
├── main_service.py                             # Queue worker entry point
├── services/queue_service.py                   # Azure Storage Queue consumer
├── services/control_api.py                     # Control API (health/kill)
├── services/process_control.py                 # Process control store/manager
├── steps/migration_processor.py                # WorkflowBuilder + step chaining
├── steps/analysis/workflow/analysis_executor.py
├── steps/design/workflow/design_executor.py
├── steps/convert/workflow/yaml_convert_executor.py
└── steps/documentation/
    ├── orchestration/documentation_orchestrator.py
    ├── workflow/documentation_executor.py
    └── agents/                                  # Agent prompt files
```

## Summary

This architecture implements a sophisticated agentic system that combines:

- **Microsoft Agent Framework Workflow** for structured workflow execution
- **Multi-Agent Group Chat Orchestration** for domain expertise collaboration
- **Model Context Protocol (MCP)** for tool integration and external system access
- **Azure Cloud Services** for scalable storage and data management
- **Event-Driven Architecture** for loose coupling and reliability

The result is a robust, scalable, and extensible migration solution that leverages the collective intelligence of specialized AI agents working in concert to solve complex container migration challenges.
