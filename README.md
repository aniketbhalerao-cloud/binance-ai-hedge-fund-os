# Binance AI Hedge Fund OS

An institutional-grade, modular operating system for an AI-driven trading fund on
Binance. This repository currently contains **Task 1 — project scaffolding only**.
No trading logic is implemented yet.

> ⚠️ **Status:** Scaffolding. All modules are intentionally empty placeholders.

## Requirements

- Python **3.12**
- [uv](https://github.com/astral-sh/uv) for dependency management
- Docker + Docker Compose (optional, for containerized runs)

## Getting Started

```bash
# Install dependencies (creates .venv and resolves the lockfile)
uv sync

# Copy the environment template and fill in your values
cp .env.example .env

# Run the application entrypoint
uv run python -m app.main
```

Or use the Makefile shortcuts:

```bash
make install   # uv sync
make run       # run the app entrypoint
make lint      # run ruff
make format    # format with ruff
make test      # run the test suite
make docker-up # start the stack with docker compose
```

## Project Structure

```
binance-ai-hedge-fund-os/
├── app/            # Application entrypoint and wiring
├── agents/         # AI agents (research, execution, risk, etc.)
├── core/           # Cross-cutting primitives: constants, logging, exceptions
├── config/         # Settings and configuration loading
├── database/       # Persistence layer and models
├── execution/      # Order routing and execution
├── strategies/     # Trading strategies
├── risk/           # Risk management and limits
├── memory/         # Long/short-term memory for agents
├── dashboard/      # Web dashboard / UI
├── api/            # Public/internal API layer
├── backtesting/    # Backtesting engine
├── paper_trading/  # Paper trading environment
├── monitoring/     # Metrics, alerting, observability
├── tests/          # Test suite
├── docs/           # Documentation
├── scripts/        # Operational and dev scripts
└── docker/         # Dockerfiles and container assets
```

## License

Distributed under the terms of the [MIT License](LICENSE).
