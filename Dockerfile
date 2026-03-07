# syntax=docker/dockerfile:1

FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /bin/uv

WORKDIR /app

# System deps for asyncpg/psycopg compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (production only, no dev extras)
ENV UV_COMPILE_BYTECODE=1
RUN uv sync --no-dev --frozen

# Copy application code
COPY src/ src/

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD .venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run application
CMD [".venv/bin/uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
