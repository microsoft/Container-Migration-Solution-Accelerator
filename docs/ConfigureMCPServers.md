# Configuring MCP Servers

This guide explains how to configure and customize Model Context Protocol (MCP) servers for the Container Migration Solution Accelerator. The solution uses MCP to extend AI agent capabilities with external tools, services, and data sources through a standardized protocol.

## Overview

The Container Migration Solution Accelerator implements a sophisticated MCP architecture that separates client plugins from server implementations, enabling secure, scalable, and maintainable tool integration for AI agents.

### MCP Architecture Benefits

- **Process Isolation**: Each MCP server runs in its own process for security and stability
- **Language Flexibility**: Servers can be implemented in different languages while maintaining compatibility
- **Scalability**: Independent server processes can be scaled based on demand
- **Maintainability**: Clear separation between client interface and server implementation
- **Security**: Isolated execution prevents tool interference and provides better error containment

## MCP Architecture in the Solution

### Integration Patterns

The solution integrates MCP through multiple patterns:

- **Stdio Plugins**: Local MCP servers spawned as subprocesses (blob, file, datetime operations)
- **HTTP Plugins**: Remote MCP servers accessed via HTTP (Microsoft documentation)
- **Context Management**: Unified context sharing across all expert agents
- **Tool Discovery**: Dynamic tool registration and capability discovery
- **Error Handling**: Robust error handling with fallback mechanisms

### MCP Server Structure

```text
src/plugins/mcp_server/
├── __init__.py
├── MCPBlobIOPlugin.py      # Azure Blob Storage operations - MCP Server Client
├── MCPDatetimePlugin.py    # Date/time utilities - MCP Server Client
├── MCPMicrosoftDocs.py     # Microsoft documentation API - MCP Server Client
├── mcp_blob_io_operation/  # Blob storage MCP Server Implementation (FastMCP)
│   ├── credential_util.py
│   └── mcp_blob_io_operation.py
└── mcp_datetime/           # Datetime utilities MCP Server Implementation (FastMCP)
    └── mcp_datetime.py
```

**Architecture Notes:**

- **Client Plugin Files**: Main MCP client plugins that connect to MCP servers via Semantic Kernel
- **Server Implementation Folders**: Contains the actual FastMCP server implementations that provide the tools
- **Credential Utilities**: Shared authentication and credential management for Azure services
- **Process Architecture**: Client plugins spawn server processes using `uv run` for isolated execution

## Available MCP Servers

### 1. Azure Blob Storage Server (MCPBlobIOPlugin.py)

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

The server supports multiple authentication methods through environment variables:

```bash
# Option 1: Azure Storage Account with DefaultAzureCredential (Recommended)
STORAGE_ACCOUNT_NAME=your_storage_account_name

# Option 2: Connection String (Alternative)
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...

# Option 3: Storage Account with Access Key (Not recommended for production)
STORAGE_ACCOUNT_NAME=your_storage_account_name
STORAGE_ACCOUNT_KEY=your_storage_account_key
```

**Authentication Methods:**
1. **DefaultAzureCredential** (Recommended for production):
   - Uses managed identity in Azure environments
   - Uses Azure CLI credentials for local development
   - Requires `STORAGE_ACCOUNT_NAME` environment variable

2. **Connection String**:
   - Requires `AZURE_STORAGE_CONNECTION_STRING` environment variable
   - Contains embedded authentication information

3. **Account Key**:
   - Requires both `STORAGE_ACCOUNT_NAME` and `STORAGE_ACCOUNT_KEY`
   - Not recommended for production environments

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

### 2. Microsoft Docs Server (MCPMicrosoftDocs.py)

**Service Name:** `microsoft_docs_service`

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
- **Type:** MCPStreamableHttpPlugin
- **Requirements:** semantic-kernel with MCP support

**Available Tools:**
- `microsoft_docs_search()`: Semantic search against Microsoft documentation
- `microsoft_docs_fetch()`: Fetch complete documentation pages in markdown format

### 3. Datetime Utilities Server (MCPDatetimePlugin.py)

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
# - Microsoft Docs Server (HTTP connection)
```

### Integration in Migration Process

The MCP servers integrate into the migration workflow as follows:

1. **Analysis Phase**:
   - `azure_blob_io_service`: Read source Kubernetes configurations
   - `microsoft_docs_service`: Research Azure best practices
   - `datetime_service`: Timestamp analysis reports

2. **Design Phase**:
   - `azure_blob_io_service`: Save architecture designs
   - `microsoft_docs_service`: Validate Azure service capabilities
   - `datetime_service`: Track design timestamps

3. **Conversion Phase**:
   - `azure_blob_io_service`: Save converted YAML configurations
   - `azure_blob_io_service`: Generate configuration comparisons
   - `datetime_service`: Track conversion timestamps

4. **Documentation Phase**:
   - `azure_blob_io_service`: Save migration reports
   - `azure_blob_io_service`: Generate migration documentation
   - `datetime_service`: Create migration timeline

### Agent-to-MCP Mapping

Each expert agent uses specific MCP servers:

| Agent                   | Primary MCP Servers  | Use Cases                                           |
| ----------------------- | -------------------- | --------------------------------------------------- |
| **Technical Architect** | blob, docs, datetime | Architecture analysis, best practices research      |
| **Azure Expert**        | blob, docs, datetime | Azure-specific optimizations, service documentation |
| **EKS/GKE Expert**      | blob, docs, datetime | Source platform analysis, migration patterns        |
| **YAML Expert**         | blob, docs, datetime       | Configuration conversion, YAML validation           |
| **QA Engineer**         | blob, docs, datetime       | Quality assurance, testing validation               |
| **Technical Writer**    | blob, docs, datetime       | Documentation generation, report creation           |

## Creating Custom MCP Servers with Semantic Kernel

The solution uses Semantic Kernel's MCP connectors to integrate with MCP servers. There are two main patterns for adding custom MCP servers:

### Pattern 1: Stdio-based MCP Servers (Local Processes)

This pattern is used for local MCP servers that run as separate processes (like the blob and datetime servers).

#### Step 1: Create the MCP Server Implementation

Create a FastMCP server implementation:

```python
# src/plugins/mcp_server/mcp_custom_service/mcp_custom_service.py

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

#### Step 2: Create the Semantic Kernel Plugin

Create a client plugin that connects to your MCP server:

```python
# src/plugins/mcp_server/MCPCustomServicePlugin.py

import os
from pathlib import Path

def get_custom_service_plugin():
    """
    Create an MCP plugin for Custom Service Operations.
    Cross-platform compatible for Windows, Linux, and macOS.

    Returns:
        MCPStdioPlugin: Configured Custom Service MCP plugin

    Raises:
        RuntimeError: If MCP setup validation fails
    """
    try:
        # Lazy import to avoid hanging during module import
        from semantic_kernel.connectors.mcp import MCPStdioPlugin

        return MCPStdioPlugin(
            name="custom_service",
            description="MCP plugin for Custom Service Operations",
            command="uv",
            args=[
                f"--directory={str(Path(os.path.dirname(__file__)).joinpath('mcp_custom_service'))}",
                "run",
                "mcp_custom_service.py",
            ],
            env=dict(os.environ),  # Pass environment variables if needed
        )
    except ImportError as e:
        print(f"MCP support not available: {e}")
        return None
```

### Pattern 2: HTTP-based MCP Servers (Remote Services)

This pattern is used for remote MCP servers accessible via HTTP (like the Microsoft Docs server).

#### Step 1: Create the HTTP Plugin

```python
# src/plugins/mcp_server/MCPRemoteServicePlugin.py

try:
    from semantic_kernel.connectors.mcp import MCPStreamableHttpPlugin
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    MCPStreamableHttpPlugin = None

def get_remote_service_plugin():
    """
    Create an MCP Streamable HTTP Plugin for remote service access.

    Available tools:
    - remote_search: Search remote service
    - remote_fetch: Fetch data from remote service

    Returns:
        MCPStreamableHttpPlugin: Configured plugin for remote MCP Server, or None if MCP not available
    """
    if not MCP_AVAILABLE or MCPStreamableHttpPlugin is None:
        return None

    return MCPStreamableHttpPlugin(
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
cd src/plugins/mcp_server/mcp_blob_io_operation
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

# Check semantic-kernel MCP support
python -c "from semantic_kernel.connectors.mcp import MCPStreamableHttpPlugin; print('MCP support available')"
```

**Connection Checklist:**
- ✅ Internet connectivity available
- ✅ No firewall blocking HTTP requests
- ✅ Semantic Kernel with MCP support installed

For additional information, refer to:

- [Technical Architecture](TechnicalArchitecture.md)
- [Multi-Agent Orchestration Approach](MultiAgentOrchestration.md)
- [MCP Server Implementation Guide](MCPServerGuide.md)
- [Deployment Guide](DeploymentGuide.md)
