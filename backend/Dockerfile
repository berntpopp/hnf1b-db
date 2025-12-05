FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies (including migration tools for data import)
RUN uv sync --frozen --group migration

# Copy application code
COPY . .

# Fix line endings (Windows CRLF → Unix LF) and make executable
RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh

# Set PATH to include the virtualenv for proper module imports
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app"

# Expose port
EXPOSE 8000

# Use entrypoint script for initialization
ENTRYPOINT ["./docker-entrypoint.sh"]

# Default command - run uvicorn with reload for development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
