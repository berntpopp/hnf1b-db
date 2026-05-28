# mcp/Dockerfile
# Development Dockerfile for HNF1B MCP Server
# Single-stage build with dev dependencies for local development

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv - PIN TO SPECIFIC VERSION for reproducible builds
COPY --from=ghcr.io/astral-sh/uv:0.5.10 /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies including dev group (better layer caching)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --group dev

# Copy application source
COPY src ./src

# Install project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --group dev

# Set PATH to include the virtualenv for proper module imports
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1

EXPOSE 8788

# Run the MCP server via the installed console script
CMD ["hnf1b-mcp"]
