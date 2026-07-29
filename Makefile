.DEFAULT_GOAL := help
.PHONY: help install run lint format test typecheck clean docker-build docker-up docker-down

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies with uv
	uv sync

run: ## Run the application entrypoint
	uv run python -m app.main

lint: ## Lint the codebase with ruff
	uv run ruff check .

format: ## Format the codebase with ruff
	uv run ruff format .

typecheck: ## Run static type checks with mypy
	uv run mypy .

test: ## Run the test suite
	uv run pytest

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

docker-build: ## Build the Docker image
	docker compose build

docker-up: ## Start the stack with docker compose
	docker compose up -d

docker-down: ## Stop the stack
	docker compose down
