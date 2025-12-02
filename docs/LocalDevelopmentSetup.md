# Local Development Setup Guide

This guide provides comprehensive instructions for setting up the Container Migration Solution Accelerator for local development across Windows and Linux platforms.

**Note**: This project uses separate `.env` files in the processor (`src/processor`), backend API (`src/backend-api/src/app`), and frontend (`src/frontend`) directories, each with different configuration requirements. When copying `.env` samples, always navigate to the particular folder first before copying the values.

## Step 1: Prerequisites - Install Required Tools

### Windows Development

#### Option 1: Native Windows (PowerShell)

```powershell
# Install Python 3.12+ and Git
winget install Python.Python.3.12
winget install Git.Git

# Install Node.js for frontend
winget install OpenJS.NodeJS.LTS

# Install uv package manager
pip install uv
```

#### Option 2: Windows with WSL2 (Recommended)

```bash
# Install WSL2 first (run in PowerShell as Administrator):
# wsl --install -d Ubuntu

# Then in WSL2 Ubuntu terminal:
sudo apt update && sudo apt install python3.12 python3.12-venv git curl nodejs npm -y

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

### Linux Development

#### Ubuntu/Debian

```bash
# Install prerequisites
sudo apt update && sudo apt install python3.12 python3.12-venv git curl nodejs npm -y

# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

#### RHEL/CentOS/Fedora

```bash
# Install prerequisites
sudo dnf install python3.12 python3.12-devel git curl gcc nodejs npm -y

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

### Clone the Repository

```bash
git clone https://github.com/microsoft/Container-Migration-Solution-Accelerator.git
cd Container-Migration-Solution-Accelerator
```

## Step 2: Development Tools Setup

### Visual Studio Code (Recommended)

#### Required Extensions

Create `.vscode/extensions.json` in the workspace root:

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

VS Code will prompt you to install these recommended extensions when you open the workspace.

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

## Step 3: Azure Authentication Setup

Before configuring services, authenticate with Azure:

```bash
# Login to Azure CLI
az login

# Set your subscription
az account set --subscription "your-subscription-id"

# Verify authentication
az account show
```

### Get Azure App Configuration URL

Navigate to your resource group and select the resource with prefix `appcs-` to get the configuration URL:

```bash
APP_CONFIGURATION_URL=https://[Your app configuration service name].azconfig.io
```

For reference, see the image below:
![local_developement_setup_1](./images/local_development_setup_1.png)

## Step 4: Processor Setup & Run Instructions

The Processor handles the actual migration logic and can run in two modes:
- **Queue-based mode** (`main_service.py`): Processes migration requests from Azure Storage Queue (production)
- **Direct execution mode** (`main.py`): Runs migrations directly without queue (development/testing)

### 4.1. Navigate to Processor Directory

```bash
cd src/processor
```

### 4.2. Configure Processor Environment Variables

Set the Azure App Configuration URL in your environment or create a `.env` file at the processor root:

```bash
APP_CONFIGURATION_URL=https://[Your app configuration service name].azconfig.io
```

### 4.3. Install Processor Dependencies

```bash
# Create and activate virtual environment
uv venv .venv

# Activate virtual environment
source .venv/bin/activate  # Linux/WSL2
# or
.\.venv\Scripts\Activate.ps1  # Windows PowerShell

# Install dependencies
uv sync --python 3.12
```

### 4.4. Run the Processor

#### Option A: Direct Execution Mode (Development/Testing)

Run migrations directly without queue infrastructure:

```bash
cd src
python main.py
```

This mode is useful for:
- Local development and testing
- Running single migrations
- Debugging migration logic

#### Option B: Queue-Based Mode (Production)

Process migration requests from Azure Storage Queue:

```bash
cd src
python main_service.py
```

This mode provides:
- Concurrent processing with multiple workers
- Automatic retry logic with exponential backoff
- Horizontal scalability
- Production-ready error handling

## Step 5: Backend API Setup & Run Instructions

The Backend API provides REST endpoints for the frontend and handles API requests.

### 5.1. Navigate to Backend API Directory

```bash
cd ../../backend-api
```

### 5.2. Configure Backend API Environment Variables

Create a `.env` file in the `src/backend-api/src/app` directory:

```bash
cd src/app

# Copy the example file
cp .env.example .env  # Linux
# or
Copy-Item .env.example .env  # Windows PowerShell
```

Edit the `.env` file with your Azure configuration values.

### 5.3. Install Backend API Dependencies

```bash
# Navigate back to backend-api root
cd ../..

# Create and activate virtual environment
uv venv .venv

# Activate virtual environment
source .venv/bin/activate  # Linux/WSL2
# or
.\.venv\Scripts\Activate.ps1  # Windows PowerShell

# Install dependencies
uv sync --python 3.12
```

### 5.4. Run the Backend API

```bash
# Make sure you're in the backend-api/src/app directory
cd src/app

# Run with uvicorn
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The Backend API will start at:
- API: `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`

## Step 6: Frontend (UI) Setup & Run Instructions

The UI is located under `src/frontend`.

### 6.1. Navigate to Frontend Directory

```bash
cd ../../frontend
```

### 6.2. Install UI Dependencies

```bash
npm install
```

### 6.3. Configure UI Environment Variables

Create a `.env` file in the `src/frontend` directory:

```bash
# Copy the example file
cp .env.example .env  # Linux
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

### 6.4. Build the UI

```bash
npm run build
```

### 6.5. Start Development Server

```bash
npm run dev
```

The app will start at:

```
http://localhost:5173
```

(or whichever port Vite assigns)

## Troubleshooting

### Common Issues

#### Python Version Issues

```bash
# Check available Python versions
python3 --version
python3.12 --version

# If python3.12 not found, install it:
# Ubuntu: sudo apt install python3.12
# Windows: winget install Python.Python.3.12
```

#### Virtual Environment Issues

```bash
# Recreate virtual environment
rm -rf .venv  # Linux
# or Remove-Item -Recurse .venv  # Windows PowerShell

uv venv .venv
# Activate and reinstall
source .venv/bin/activate  # Linux
# or .\.venv\Scripts\Activate.ps1  # Windows
uv sync --python 3.12
```

#### Permission Issues (Linux)

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
env | grep AZURE  # Linux
Get-ChildItem Env:AZURE*  # Windows PowerShell

# Validate .env file format
cat .env | grep -v '^#' | grep '='  # Should show key=value pairs
```

## Step 7: Next Steps

Once all services are running (as configured in Steps 4-6), you can:

1. **Access the Application**: Open `http://localhost:5173` in your browser to explore the frontend UI
2. **Try a Sample Workflow**: Follow [SampleWorkflow.md](SampleWorkflow.md) for a guided walkthrough of the migration process
3. **Explore the Codebase**: Start with `src/processor/src/main_service.py` to understand the agent architecture
4. **Customize Agents**: Follow [CustomizeExpertAgents.md](CustomizeExpertAgents.md) to modify agent behavior
5. **Extend Platform Support**: Follow [ExtendPlatformSupport.md](ExtendPlatformSupport.md) to add new cloud platforms

## Related Documentation

- [Deployment Guide](DeploymentGuide.md) - Production deployment instructions
- [Technical Architecture](TechnicalArchitecture.md) - System architecture overview
- [Extending Platform Support](ExtendPlatformSupport.md) - Adding new platform support
- [Configuring MCP Servers](ConfigureMCPServers.md) - MCP server configuration
- [Multi-Agent Orchestration](MultiAgentOrchestration.md) - Agent collaboration patterns
