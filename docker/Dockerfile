# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first for better layer caching
COPY pyproject.toml ./
RUN uv sync --no-install-project --no-dev || true

# Copy the rest of the project
COPY . .

# Resolve and install the project itself
RUN uv sync --no-dev || true

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "app.main"]
