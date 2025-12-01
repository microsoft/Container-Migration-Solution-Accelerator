# Local Development Setup Guide

This guide provides comprehensive instructions for setting up the Container Migration Solution Accelerator for local development across Windows, Linux, and macOS platforms.

## Step 1: Quick Start by Platform

### Windows Development

#### Option 1: Native Windows (PowerShell)

```powershell
# Prerequisites: Install Python 3.12+ and Git
winget install Python.Python.3.12
winget install Git.Git

# Clone and setup
git clone https://github.com/microsoft/Container-Migration-Solution-Accelerator.git
cd Container-Migration-Solution-Accelerator/src/processor

# Install uv and setup environment
pip install uv
uv venv .venv
.\.venv\Scripts\Activate.ps1
uv sync --python 3.12 --link-mode=copy

# Configure environment
Copy-Item .env.example .env
# Edit .env with your Azure configuration
```

#### Option 2: Windows with WSL2 (Recommended)

```bash
# Install WSL2 first (run in PowerShell as Administrator):
# wsl --install -d Ubuntu

# Then in WSL2 Ubuntu terminal:
sudo apt update && sudo apt install python3.12 python3.12-venv git curl -y

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Setup project (same as Linux)
git clone https://github.com/microsoft/Container-Migration-Solution-Accelerator.git
cd Container-Migration-Solution-Accelerator/src/processor
uv venv .venv
source .venv/bin/activate
uv sync --python 3.12
```

### Linux Development

#### Ubuntu/Debian

```bash
# Install prerequisites
sudo apt update && sudo apt install python3.12 python3.12-venv git curl -y

# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Clone and setup
git clone https://github.com/microsoft/Container-Migration-Solution-Accelerator.git
cd Container-Migration-Solution-Accelerator/src/processor
uv venv .venv
source .venv/bin/activate
uv sync --python 3.12

# Configure
cp .env.example .env
nano .env  # Edit with your configuration
```

#### RHEL/CentOS/Fedora

```bash
# Install prerequisites
sudo dnf install python3.12 python3.12-devel git curl gcc -y

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Setup (same as above)
git clone https://github.com/microsoft/Container-Migration-Solution-Accelerator.git
cd Container-Migration-Solution-Accelerator/src/processor
uv venv .venv
source .venv/bin/activate
uv sync --python 3.12
```

### macOS Development

```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install prerequisites
brew install python@3.12 uv git

# Clone and setup
git clone https://github.com/microsoft/Container-Migration-Solution-Accelerator.git
cd Container-Migration-Solution-Accelerator/src/processor
uv venv .venv
source .venv/bin/activate
uv sync --python 3.12

# Configure
cp .env.example .env
nano .env  # Edit with your configuration
```

## Step 2: UI (Web App) Setup & Run Instructions

The UI is located under:

```
container-migration-solution-accelerator/src/frontend
```

Follow these steps to run the UI locally.

### 1. Install Node.js (v18+ Recommended)

#### Windows (winget)

```powershell
winget install OpenJS.NodeJS.LTS
```

#### macOS (Homebrew)

```bash
brew install node
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt install nodejs npm
```

### 2. Install UI Dependencies

```bash
cd container-migration-solution-accelerator/src/ui
npm install
```

### 3. Configure UI Environment Variables

Create a `.env` file in the `src/frontend` directory:

```bash
# Copy the example file
cp .env.example .env  # Linux/macOS
# or
Copy-Item .env.example .env  # Windows PowerShell
```

Edit the `.env` file with your Azure AD configuration:

```bash
# Required: Your Azure AD app registration client ID
VITE_APP_WEB_CLIENT_ID=your-client-id-here

# Required: Your Azure AD tenant authority
VITE_APP_WEB_AUTHORITY=https://login.microsoftonline.com/your-tenant-id

# Optional: Redirect URLs (defaults to current origin)
VITE_APP_REDIRECT_URL=http://localhost:5173
VITE_APP_POST_REDIRECT_URL=http://localhost:5173

# Required: Scopes for login and token acquisition
VITE_APP_WEB_SCOPE=api://your-api-id/access_as_user
VITE_APP_API_SCOPE=api://your-backend-api-id/User.Read

# API URL (for when backend is available)
VITE_API_URL=http://localhost:8000/api
```

**Note**: You'll need to configure Azure AD App Registration to get these values. See [ConfigureAppAuthentication.md](ConfigureAppAuthentication.md) for details.

### 4. Build the UI

```bash
npm run build
```

### 5. Start Development Server

```bash
npm run dev
```

The app will start at:

```
http://localhost:5173
```

(or whichever port Vite assigns)

## Step 3: Environment Configuration

### Azure Authentication Setup

Before configuring environment variables, authenticate with Azure:

```bash
# Login to Azure CLI
az login

# Set your subscription
az account set --subscription "your-subscription-id"

# Verify authentication
az account show
```

### Required Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
APP_CONFIGURATION_URL=https://[Your app configuration service name].azconfig.io
```
For getting above APP_CONFIGURATION_URL navigate to your resourse group and select resource with prefic `appcs-` and refer below image.
![local_developement_setup_1](local_developement_setup_1.png)

### Platform-Specific Configuration

#### Windows PowerShell

```powershell
# Set execution policy if needed
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Environment variables (alternative to .env file)
$env:APP_CONFIGURATION_URL = "https://[Your app configuration service name].azconfig.io"
```

#### Windows Command Prompt

```cmd
rem Set environment variables
set APP_CONFIGURATION_URL=https://[Your app configuration service name].azconfig.io

rem Activate virtual environment
.venv\Scripts\activate.bat
```

#### Linux/macOS Bash/Zsh
```bash
# Add to ~/.bashrc or ~/.zshrc for persistence
export APP_CONFIGURATION_URL="https://[Your app configuration service name].azconfig.io"

# Or use .env file (recommended)
source .env  # if you want to load manually
```

## Step 4: Development Tools Setup

### Visual Studio Code (Recommended)

#### Required Extensions

```json
{
    "recommendations": [
        "ms-python.python",
        "ms-python.pylint",
        "ms-python.black-formatter",
        "ms-python.isort",
        "ms-vscode-remote.remote-wsl",
        "ms-vscode-remote.remote-containers",
        "redhat.vscode-yaml",
        "ms-vscode.azure-account",
        "ms-python.mypy-type-checker"
    ]
}
```

#### Settings Configuration

Create `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "./.venv/bin/python",
    "python.terminal.activateEnvironment": true,
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false,
    "files.associations": {
        "*.yaml": "yaml",
        "*.yml": "yaml"
    }
}
```

## Troubleshooting

### Common Issues

#### Python Version Issues

```bash
# Check available Python versions
python3 --version
python3.12 --version

# If python3.12 not found, install it:
# Ubuntu: sudo apt install python3.12
# macOS: brew install python@3.12
# Windows: winget install Python.Python.3.12
```

#### Virtual Environment Issues

```bash
# Recreate virtual environment
rm -rf .venv  # Linux/macOS
# or Remove-Item -Recurse .venv  # Windows PowerShell

uv venv .venv
# Activate and reinstall
source .venv/bin/activate  # Linux/macOS
# or .\.venv\Scripts\Activate.ps1  # Windows
uv sync --python 3.12
```

#### Permission Issues (Linux/macOS)

```bash
# Fix ownership of files
sudo chown -R $USER:$USER .

# Fix uv permissions
chmod +x ~/.local/bin/uv
```

#### Windows-Specific Issues

```powershell
# PowerShell execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Long path support (Windows 10 1607+, run as Administrator)
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force

# SSL certificate issues
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org uv
```

### Environment Variable Issues

```bash
# Check environment variables are loaded
env | grep AZURE  # Linux/macOS
Get-ChildItem Env:AZURE*  # Windows PowerShell

# Validate .env file format
cat .env | grep -v '^#' | grep '='  # Should show key=value pairs
```

## Step 5: Next Steps

1. **Configure Your Environment**: Follow the platform-specific setup instructions
2. **Explore the Codebase**: Start with `src/main_service.py` and examine the agent architecture
3. **Customize Agents**: Follow [CustomizeExpertAgents.md](CustomizeExpertAgents.md)
4. **Extend Platform Support**: Follow [ExtendPlatformSupport.md](ExtendPlatformSupport.md)

## Related Documentation

- [Deployment Guide](DeploymentGuide.md) - Production deployment instructions
- [Technical Architecture](TechnicalArchitecture.md) - System architecture overview
- [Extending Platform Support](ExtendPlatformSupport.md) - Adding new platform support
- [Configuring MCP Servers](ConfigureMCPServers.md) - MCP server configuration
- [Multi-Agent Orchestration](MultiAgentOrchestration.md) - Agent collaboration patterns
