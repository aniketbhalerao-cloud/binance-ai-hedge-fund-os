"""Execution Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions so
future executors (Binance/Zerodha/paper/backtest adapters) plug in without
modification (Open/Closed).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from execution.context import ExecutionContext
from execution.models import (
    ExecutionRequest,
    ExecutionResult,
    ExecutionRoute,
    ExecutionValidationResult,
)

__all__ = [
    "ExecutionExecutor",
    "ExecutionValidator",
    "ExecutionRouter",
    "ExecutionManager",
    "ExecutionEngine",
]


@runtime_checkable
class ExecutionExecutor(Protocol):
    """Coordinates an execution request into a result (no broker calls)."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult: ...


@runtime_checkable
class ExecutionValidator(Protocol):
    """Validates an execution request's integrity, state, and routing metadata."""

    def validate(self, request: ExecutionRequest) -> ExecutionValidationResult: ...


@runtime_checkable
class ExecutionRouter(Protocol):
    """Prepares execution routing metadata for a validated request."""

    def route(self, request: ExecutionRequest) -> ExecutionRoute: ...


@runtime_checkable
class ExecutionManager(Protocol):
    """Coordinates validator → executor → router and publishes events."""

    async def process(self, context: ExecutionContext) -> ExecutionResult: ...


@runtime_checkable
class ExecutionEngine(Protocol):
    """Public entry point coordinating the execution-management process."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def process(self, context: ExecutionContext) -> ExecutionResult: ...
