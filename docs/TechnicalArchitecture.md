# Technical Architecture

This document provides a comprehensive technical overview of the Container Migration Solution Accelerator architecture, including system components, data flows, and integration patterns.

## Overview

The Container Migration Solution Accelerator is built on a modern, cloud-native, queue-driven architecture that leverages artificial intelligence, multi-agent orchestration, and the Model Context Protocol (MCP) to automate container platform migrations to Azure.

## High-Level Architecture

```mermaid
graph TB
    UI[Frontend UI] --> API[Backend API]
    API --> Q[Azure Storage Queue]

    subgraph Processor[Processor (Queue Worker)]
        QW[Queue Worker]
        WF[Agent Framework Workflow\nanalysis → design → yaml → docs]
        CA[Control API]
        PC[Process Control Store]
        QW --> WF
        CA --> PC
    end

    Q --> QW

    subgraph Tools[Tools (MCP + local tools)]
        Blob[Blob IO]
        Docs[Microsoft Docs]
        Mermaid[Mermaid]
        Datetime[Datetime]
        YamlInv[YAML Inventory]
    end

    subgraph External[External Services]
        ST[Azure Blob Storage]
        Models[Azure OpenAI / Azure AI Foundry Models]
    end

    WF --> Tools
    Blob --> ST
    Docs --> Models
```


## Core Components (Processor)

### 1. Queue Worker

The processor runs as a queue-driven worker in hosted scenarios.

**Responsibilities:**

- Poll Azure Storage Queue for jobs
- Validate/deserialize request payloads
- Execute the Agent Framework workflow
- Persist artifacts and emit telemetry

**Implementation Locations:**

- [src/processor/src/main_service.py](../src/processor/src/main_service.py)
- [src/processor/src/services/queue_service.py](../src/processor/src/services/queue_service.py)

**Operational Notes:**

- The queue worker is intentionally simple; behavior such as retries and DLQ are controlled by the queue configuration/patterns and service logic.

### 2. Control API + Process Control

The processor exposes a lightweight control surface for health and termination.

**Implementation Locations:**

- [src/processor/src/services/control_api.py](../src/processor/src/services/control_api.py)
- [src/processor/src/services/process_control.py](../src/processor/src/services/process_control.py)

### 3. Workflow Engine (Microsoft Agent Framework)

The migration pipeline is defined as an Agent Framework workflow built via `WorkflowBuilder` and executed step-by-step.

**Execution Order:**

- analysis → design → yaml → documentation

**Implementation Location:**

- [src/processor/src/steps/migration_processor.py](../src/processor/src/steps/migration_processor.py)

### 4. Multi-Agent Orchestration

Steps that require multi-agent reasoning use a group chat style orchestrator.

**Key Concepts:**

- Coordinator agent manages turn-taking and termination
- Platform experts contribute source-platform-specific guidance
- Result generator consolidates structured outputs

**Implementation Locations:**

- [src/processor/src/libs/agent_framework/groupchat_orchestrator.py](../src/processor/src/libs/agent_framework/groupchat_orchestrator.py)
- [src/processor/src/libs/agent_framework/agent_builder.py](../src/processor/src/libs/agent_framework/agent_builder.py)
- [src/processor/src/libs/agent_framework/agent_info.py](../src/processor/src/libs/agent_framework/agent_info.py)
- Platform expert registry: [src/processor/src/steps/analysis/orchestration/platform_registry.json](../src/processor/src/steps/analysis/orchestration/platform_registry.json)

### 5. MCP Tool Integration (Agent Framework Tools)

Tools are exposed to agents using Agent Framework tool abstractions, including MCP.

**Processor MCP tools:**

- [src/processor/src/libs/mcp_server/MCPBlobIOTool.py](../src/processor/src/libs/mcp_server/MCPBlobIOTool.py)
- [src/processor/src/libs/mcp_server/MCPMicrosoftDocs.py](../src/processor/src/libs/mcp_server/MCPMicrosoftDocs.py)
- [src/processor/src/libs/mcp_server/MCPMermaidTool.py](../src/processor/src/libs/mcp_server/MCPMermaidTool.py)
- [src/processor/src/libs/mcp_server/MCPDatetimeTool.py](../src/processor/src/libs/mcp_server/MCPDatetimeTool.py)
- [src/processor/src/libs/mcp_server/MCPYamlInventoryTool.py](../src/processor/src/libs/mcp_server/MCPYamlInventoryTool.py)

## Technology Stack (Processor)

### Core

- Microsoft Agent Framework (workflow + orchestration)
- Python 3.12+
- asyncio
- aiohttp (control API)

### AI

- Azure OpenAI / Azure AI Foundry models (project-dependent)
- Model Context Protocol (MCP) for tool access

### Azure SDKs

- Azure Storage Queue (job intake)
- Azure Storage Blob (artifact IO)
- Azure Identity (auth)

### Dev/Ops

- uv (dependency management)
- Docker (containerized execution)
- pytest (tests)

For additional technical details, refer to:

- [Multi-Agent Orchestration Approach](MultiAgentOrchestration.md)
- [MCP Server Implementation Guide](MCPServerGuide.md)
- [Deployment Guide](DeploymentGuide.md)
