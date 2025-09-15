FROM mcr.microsoft.com/azurelinux/base/python:3.12 

WORKDIR /app

# Install system dependencies and UV using tdnf (Azure Linux package manager)
RUN tdnf update -y && tdnf install -y \
    tar \
    ca-certificates \
    shadow-utils \
    && tdnf clean all \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

# Copy only the dependency files first (for better Docker layer caching)
COPY pyproject.toml uv.lock ./

# Install the application dependencies.
RUN uv sync --frozen --no-cache --prerelease=allow --python 3.12

# Copy only the app folder from src
COPY src/app .

# Run the application.
CMD [".venv/bin/uvicorn", "main:app", "--port", "80", "--host", "0.0.0.0", "--workers", "4"]