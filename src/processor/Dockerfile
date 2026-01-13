# Use Azure Linux Python 3.12 image as base
FROM mcr.microsoft.com/azurelinux/base/python:3.12

# Set environment variables for Python and UV
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_NO_CACHE=1

# Set working directory
WORKDIR /app

# Install system dependencies and UV using tdnf (Azure Linux package manager)
RUN tdnf update -y && tdnf install -y \
    tar \
    ca-certificates \
    shadow-utils \
    && tdnf clean all \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

# Copy pyproject.toml and uv.lock first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies using UV
RUN uv sync --frozen --python 3.12 --prerelease=allow

# Copy the entire source code
COPY src/ ./src/

# Create a non-root user for security and fix permissions
RUN useradd --create-home --shell /bin/bash gsauser && \
    chown -R gsauser:gsauser /app && \
    chmod -R 755 /app

# Switch to non-root user and install UV for user
USER gsauser
ENV PATH="/home/gsauser/.local/bin:$PATH"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Environment variables for queue service configuration (can be overridden)
ENV APP_CONFIGURATION_URL=""

# Expose port for controller api
EXPOSE 8080

# Simple command - let Docker handle restarts
CMD ["uv", "run", "--prerelease=allow", "python", "src/main_service.py"]
