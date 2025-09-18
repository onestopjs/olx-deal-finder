# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

# Install system dependencies
RUN apt-get update \ 
    && apt-get install -y --no-install-recommends \ 
        curl \ 
        build-essential \ 
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager) and create a virtualenv
RUN pip install --no-cache-dir uv

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Sync dependencies (respect the lockfile)
RUN uv sync --frozen --no-dev

# Copy the rest of the application code
COPY . .

# Expose FastAPI default port
EXPOSE 8000

# Run the server with uvicorn via uv (uses the created virtualenv)
CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]


