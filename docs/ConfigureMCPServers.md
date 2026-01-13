# Configuring MCP Servers

This guide explains how to configure and customize Model Context Protocol (MCP) servers for the Container Migration Solution Accelerator. The solution uses MCP to extend AI agent capabilities with external tools, services, and data sources through a standardized protocol.

## Overview

The Container Migration Solution Accelerator implements a sophisticated MCP architecture that separates Agent Framework MCP tools (clients) from server implementations, enabling secure, scalable, and maintainable tool integration for AI agents.

### MCP Architecture Benefits

- **Process Isolation**: Each MCP server runs in its own process for security and stability
- **Language Flexibility**: Servers can be implemented in different languages while maintaining compatibility
- **Scalability**: Independent server processes can be scaled based on demand
- **Maintainability**: Clear separation between client interface and server implementation
- **Security**: Isolated execution prevents tool interference and provides better error containment

## MCP Architecture in the Solution

### Integration Patterns

The solution integrates MCP through multiple patterns:

- **Stdio Tools**: Local MCP servers spawned as subprocesses (fetch, blob, datetime, mermaid validation, YAML inventory)
- **HTTP Tools**: Remote MCP servers accessed via HTTP (Microsoft Learn documentation)
- **Context Management**: Unified context sharing across all expert agents
- **Tool Discovery**: Dynamic tool registration and capability discovery
- **Error Handling**: Robust error handling with fallback mechanisms

### MCP Server Structure

```text
src/processor/src/libs/mcp_server/
├── __init__.py
├── MCPBlobIOTool.py        # Azure Blob Storage MCP tool wrapper
├── MCPDatetimeTool.py      # Date/time utilities MCP tool wrapper
├── MCPMicrosoftDocs.py     # Microsoft Learn MCP tool wrapper (HTTP)
├── MCPMermaidTool.py       # Mermaid validation MCP tool wrapper
├── MCPYamlInventoryTool.py # YAML inventory MCP tool wrapper
├── blob_io_operation/      # Blob storage FastMCP server implementation
├── datetime/               # Datetime FastMCP server implementation
├── mermaid/                # Mermaid FastMCP server implementation
└── yaml_inventory/         # YAML inventory FastMCP server implementation
```

**Architecture Notes:**

- **Tool Wrapper Files**: Agent Framework MCP tools (stdio/http) used by agents and orchestrators
- **Server Implementation Folders**: FastMCP server implementations that provide the tool endpoints
- **Credential Utilities**: Shared authentication and credential management for Azure services
- **Process Architecture**: MCP tools spawn server processes using `uv run`/`uvx` for isolated execution

The processor also uses a standard Fetch MCP server (installed/executed via `uvx mcp-server-fetch`) that is not implemented in this repository.

## Available MCP Servers

### 1. Azure Blob Storage Server (MCPBlobIOTool.py)

**Service Name:** `azure_blob_io_service`

Provides integration with Azure Blob Storage using FastMCP framework:

**Capabilities:**

- Blob upload and download operations
- Container management and listing
- File metadata operations
- Storage account integration
- Folder structure creation and management
- Blob existence verification
- Storage account information retrieval

**Environment Configuration:**

The server supports these authentication methods through environment variables:

```bash
# Option 1: Azure Storage Account with DefaultAzureCredential (Recommended)
STORAGE_ACCOUNT_NAME=your_storage_account_name

# Option 2: Connection String (Alternative)
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
```

**Authentication Methods:**

1. **DefaultAzureCredential** (Recommended):
    - Uses managed identity in Azure environments
    - Uses Azure CLI credentials for local development
    - Requires `STORAGE_ACCOUNT_NAME`

2. **Connection String** (Development alternative):
    - Requires `AZURE_STORAGE_CONNECTION_STRING`

**Available Tools:**

- `save_content_to_blob()`: Save content to Azure Blob Storage
- `read_blob_content()`: Read blob content as text
- `check_blob_exists()`: Verify blob existence with metadata
- `delete_blob()`: Delete individual blobs
- `list_blobs_in_container()`: List blobs with filtering options
- `create_container()`: Create new storage containers
- `delete_container()`: Delete entire containers
- `move_blob()`: Move/rename blobs between containers
- `copy_blob()`: Copy blobs within or across containers
- `find_blobs()`: Search blobs using wildcard patterns

### 2. Microsoft Learn Docs Server (HTTP)

**Tool Name:** `Microsoft Learn MCP`

Provides Microsoft documentation integration through HTTP-based MCP connection:  
GitHub Microsoft Docs MCP Server - [MicrosoftDocs/mcp](https://github.com/microsoftdocs/mcp)  

**Capabilities:**

- Microsoft Learn documentation access
- Azure service documentation retrieval
- Semantic search across Microsoft documentation
- Complete documentation page fetching
- Best practices and examples lookup
- API reference integration

**Environment Configuration:**

No environment variables required. Uses HTTP connection to Microsoft's public MCP server.

**Connection Details:**

- **Protocol:** HTTP-based MCP connection
- **URL:** `https://learn.microsoft.com/api/mcp`
- **Type:** `MCPStreamableHTTPTool`
- **Requirements:** Agent Framework MCP tool support

**Available Tools:**

- `microsoft_docs_search()`: Semantic search against Microsoft documentation
- `microsoft_docs_fetch()`: Fetch complete documentation pages in markdown format

### 3. Fetch Server (stdio)

**Tool Name:** `Fetch MCP Tool`

Provides generic URL fetch capabilities via a standard MCP server.

**Capabilities:**

- Fetch public HTTP(S) content when Microsoft Learn MCP is not sufficient
- Lightweight web retrieval for validation and cross-checking

**Environment Configuration:**

No environment variables required.

**Runtime Requirements:**

- `uvx` available in PATH
- Fetch server executable: `uvx mcp-server-fetch`

### 4. Datetime Utilities Server (MCPDatetimeTool.py)

**Service Name:** `datetime_service`

Provides date and time operations using FastMCP framework:

**Capabilities:**

- Current timestamp generation in multiple formats
- Date and time parsing and formatting
- Time zone conversions and handling
- Duration calculations and comparisons
- Migration timeline tracking
- Report timestamp management
- Relative time calculations

**Environment Configuration:**

No environment variables required. Uses system time and optional timezone libraries.

**Optional Dependencies:**

- **pytz**: Enhanced timezone support (recommended)
- **zoneinfo**: Python 3.9+ timezone support (fallback)

**Timezone Support:**

- Default timezone: UTC
- Supported aliases: PT, ET, MT, CT, PST, PDT, EST, EDT, MST, MDT, CST, CDT
- Full timezone names supported when pytz or zoneinfo available

**Available Tools:**

- `get_current_timestamp()`: Get current timestamp in various formats
- `format_datetime()`: Format datetime strings
- `convert_timezone()`: Convert between timezones
- `calculate_duration()`: Calculate time differences
- `parse_datetime()`: Parse datetime strings
- `get_relative_time()`: Calculate relative time descriptions

### 5. Mermaid Validation Server (MCPMermaidTool.py)

**Service Name:** `mermaid_service`

Provides Mermaid diagram validation and best-effort auto-fixing using FastMCP.

**Capabilities:**

- Validate Mermaid snippets generated during design documentation
- Best-effort normalization and fixing for common Mermaid formatting issues
- Validate/fix Mermaid blocks embedded in Markdown

**Environment Configuration:**

No environment variables required.

**Available Tools:**

- `validate_mermaid()`: Validate Mermaid code (heuristic)
- `fix_mermaid()`: Normalize and best-effort fix Mermaid code
- `validate_mermaid_in_markdown()`: Validate Mermaid blocks inside Markdown
- `fix_mermaid_in_markdown()`: Fix Mermaid blocks inside Markdown

### 6. YAML Inventory Server (MCPYamlInventoryTool.py)

**Service Name:** `yaml_inventory_service`

Generates a deterministic inventory for converted Kubernetes YAML manifests and writes the inventory back to Azure Blob Storage.

**Capabilities:**

- Scan converted YAML/YML blobs under a given folder path
- Extract `apiVersion`, `kind`, `metadata.name`, `metadata.namespace`
- Group resources into a suggested apply order (deterministic)
- Write a `converted_yaml_inventory.json` artifact to Blob Storage

**Environment Configuration:**

Uses the same Azure Blob Storage environment variables as the Blob server:

```bash
STORAGE_ACCOUNT_NAME=your_storage_account_name
# or
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
```

**Available Tools:**

- `generate_converted_yaml_inventory()`: Generate and write an inventory JSON for YAML blobs in blob storage

## Complete MCP Configuration Setup

### Environment Setup Example

Here's a complete example of setting up all MCP servers for the migration solution:

```bash
# Azure Blob Storage Configuration (Required)
export STORAGE_ACCOUNT_NAME="migrationstorageacct"

# Alternative: Use connection string for development
# export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=..."

# No additional environment variables needed for:
# - DateTime Server (system time)
# - Microsoft Learn MCP (HTTP connection)
# - Fetch MCP Tool (stdio)
# - Mermaid Server (stdio)
```

### Integration in Migration Process

The MCP servers integrate into the migration workflow as follows:

1. **Analysis Phase**:
   - `azure_blob_io_service`: Read source Kubernetes configurations
    - `Microsoft Learn MCP`: Research Azure best practices
    - `Fetch MCP Tool`: Fetch supporting references as needed
   - `datetime_service`: Timestamp analysis reports

2. **Design Phase**:
   - `azure_blob_io_service`: Save architecture designs
    - `Microsoft Learn MCP`: Validate Azure service capabilities
    - `Fetch MCP Tool`: Fetch supporting references as needed
   - `datetime_service`: Track design timestamps
    - `mermaid_service`: Validate/fix Mermaid diagrams in design outputs

3. **Conversion Phase**:
   - `azure_blob_io_service`: Save converted YAML configurations
   - `azure_blob_io_service`: Generate configuration comparisons
    - `Fetch MCP Tool`: Fetch supporting references as needed
   - `datetime_service`: Track conversion timestamps

4. **Documentation Phase**:
   - `azure_blob_io_service`: Save migration reports
   - `azure_blob_io_service`: Generate migration documentation
    - `yaml_inventory_service`: Generate converted YAML inventory for runbooks
    - `Fetch MCP Tool`: Fetch supporting references as needed
   - `datetime_service`: Create migration timeline

### Agent-to-MCP Mapping

Each expert agent uses specific MCP servers:

| Agent                   | MCP Tools Available                                  | Use Cases                                                        |
| ----------------------- | ---------------------------------------------------- | --------------------------------------------------------------- |
| **Technical Architect** | docs, fetch, blob, datetime                           | Architecture analysis, best practices research                   |
| **Azure Architect**     | docs, fetch, blob, datetime                           | Azure-specific optimizations, service documentation              |
| **EKS/GKE Expert**      | docs, fetch, blob, datetime                           | Source platform analysis, migration patterns                     |
| **YAML Expert**         | docs, fetch, blob, datetime                           | Configuration conversion, YAML validation                        |
| **QA Engineer**         | docs, fetch, blob, datetime                           | Quality assurance, testing validation                            |
| **Technical Writer**    | docs, fetch, blob, datetime, yaml-inventory (doc step) | Documentation generation, runbook artifacts, report creation     |

## Creating Custom MCP Servers (FastMCP + Agent Framework tools)

The processor integrates MCP servers as **Agent Framework tools**. There are two main patterns for adding custom MCP servers:

### Pattern 1: Stdio-based MCP Servers (Local Processes)

This pattern is used for local MCP servers that run as separate processes (like the blob and datetime servers).

#### Step 1: Create the MCP Server Implementation

Create a FastMCP server implementation:

```python
# src/processor/src/libs/mcp_server/custom_service/mcp_custom_service.py

from fastmcp import FastMCP

mcp = FastMCP(
    name="custom_service",
    instructions="Custom service operations for specialized tasks."
)

@mcp.tool()
def custom_operation(
    parameter1: str,
    parameter2: str | None = None,
) -> str:
    """Perform custom operation.

    Args:
        parameter1: Primary parameter for the operation
        parameter2: Optional secondary parameter

    Returns:
        Success message with operation results
    """
    try:
        # Implement your custom logic here
        result = f"Custom operation completed with {parameter1}"
        if parameter2:
            result += f" and {parameter2}"

        return f"[SUCCESS] {result}"
    except Exception as e:
        return f"[FAILED] Custom operation failed: {str(e)}"

if __name__ == "__main__":
    mcp.run()
```

#### Step 2: Create an Agent Framework tool wrapper

Create a wrapper that exposes your FastMCP server as an Agent Framework tool:

```python
# src/processor/src/libs/mcp_server/MCPCustomServiceTool.py

import os
from pathlib import Path

from agent_framework import MCPStdioTool

def get_custom_service_mcp() -> MCPStdioTool:
    """Create and return a stdio MCP tool for the custom FastMCP server."""

    server_dir = Path(__file__).parent / "custom_service"
    return MCPStdioTool(
        name="custom_service",
        command="uv",
        args=[
            f"--directory={server_dir}",
            "run",
            "mcp_custom_service.py",
        ],
        env=dict(os.environ),
    )
```

### Pattern 2: HTTP-based MCP Servers (Remote Services)

This pattern is used for remote MCP servers accessible via HTTP (like the Microsoft Docs server).

#### Step 1: Create the HTTP tool wrapper

```python
# src/processor/src/libs/mcp_server/MCPRemoteService.py

from agent_framework import MCPStreamableHTTPTool

def get_remote_service_mcp() -> MCPStreamableHTTPTool:
    """
    Create an MCP Streamable HTTP tool for remote service access.

    Available tools:
    - remote_search: Search remote service
    - remote_fetch: Fetch data from remote service

    Returns:
        MCPStreamableHTTPTool: Configured tool for the remote MCP server
    """
    return MCPStreamableHTTPTool(
        name="remote_service",
        description="Access Remote Service",
        url="https://your-remote-service.com/api/mcp",
    )
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Azure Blob Storage Authentication Issues

**Symptoms:**

- `[FAILED] AZURE STORAGE AUTHENTICATION FAILED` messages
- Agents unable to save or read blob content

**Solutions:**

```bash
# Check environment variables
echo $STORAGE_ACCOUNT_NAME
echo $AZURE_STORAGE_CONNECTION_STRING

# Verify Azure CLI authentication
az account show
az storage account list

# Test blob access directly
az storage blob list --account-name $STORAGE_ACCOUNT_NAME --container-name default
```

**Authentication Checklist:**

- ✅ `STORAGE_ACCOUNT_NAME` environment variable set
- ✅ Azure CLI authenticated (`az login`)
- ✅ Storage account exists and accessible
- ✅ Proper RBAC permissions (Storage Blob Data Contributor)

#### 2. MCP Server Process Issues

**Symptoms:**

- Timeout errors when calling MCP tools
- Server not responding to tool calls

**Solutions:**

```bash
# Check if UV is available
uv --version

# Test MCP server directly
cd src/processor/src/libs/mcp_server/blob_io_operation
uv run mcp_blob_io_operation.py

# Check Python environment
python --version
which python
```

**Process Checklist:**

- ✅ UV package manager installed
- ✅ Python 3.12+ available
- ✅ Virtual environment activated
- ✅ Required dependencies installed

#### 3. Microsoft Docs Server Connection Issues

**Symptoms:**

- Documentation search returns no results
- HTTP connection timeouts

**Solutions:**

```bash
# Test HTTP connectivity
curl -I https://learn.microsoft.com/api/mcp

# Check Agent Framework MCP support
python -c "from agent_framework import MCPStreamableHTTPTool; print('MCP support available')"
```

**Connection Checklist:**

- ✅ Internet connectivity available
- ✅ No firewall blocking HTTP requests
- ✅ Agent Framework dependencies installed (see `src/processor/pyproject.toml`)

For additional information, refer to:

- [Technical Architecture](TechnicalArchitecture.md)
- [Multi-Agent Orchestration Approach](MultiAgentOrchestration.md)
- [MCP Server Implementation Guide](MCPServerGuide.md)
- [Deployment Guide](DeploymentGuide.md)
