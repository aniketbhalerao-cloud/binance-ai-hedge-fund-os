"""Model Provider Gateway Framework interfaces.

Protocols only — no implementations. Components depend on these
abstractions so new collectors, planners, and routing policies plug in
without modification (Open/Closed). DI binds the ``Default*`` /
``InMemory*`` concretes to these keys (Dependency Inversion).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from model_gateway.context import ModelGatewayContext
from model_gateway.models import (
    ModelGatewayMetrics,
    ModelGatewayResult,
    ModelInvocationBatch,
    ModelInvocationRecord,
    ModelInvocationRequest,
)

__all__ = [
    "Collector",
    "Planner",
    "Dispatcher",
    "ModelGatewayMetricsCalculator",
    "ModelGatewayRegistry",
    "ModelGatewayManager",
    "ModelGatewayEngine",
]


@runtime_checkable
class Collector(Protocol):
    """Builds a model invocation batch from a context (stateless)."""

    def collect(self, context: ModelGatewayContext) -> ModelInvocationBatch: ...


@runtime_checkable
class Planner(Protocol):
    """Plans model invocation entries; never applies changes (stateless)."""

    def plan(
        self, batch: ModelInvocationBatch, context: ModelGatewayContext
    ) -> ModelInvocationBatch: ...


@runtime_checkable
class Dispatcher(Protocol):
    """Produces deterministic, immutable model invocation requests (stateless)."""

    def dispatch(
        self, batch: ModelInvocationBatch, context: ModelGatewayContext
    ) -> tuple[ModelInvocationRequest, ...]: ...


@runtime_checkable
class ModelGatewayMetricsCalculator(Protocol):
    """Derives model gateway metrics from a record (stateless)."""

    def calculate(self, record: ModelInvocationRecord) -> ModelGatewayMetrics: ...


@runtime_checkable
class ModelGatewayRegistry(Protocol):
    """Thread-safe store that owns the running records (never creates them)."""

    def register(self, record: ModelInvocationRecord) -> None: ...
    def unregister(self, record_id: str) -> None: ...
    def get(self, record_id: str) -> ModelInvocationRecord: ...
    def exists(self, record_id: str) -> bool: ...
    def list(self) -> list[ModelInvocationRecord]: ...
    def clear(self) -> None: ...


@runtime_checkable
class ModelGatewayManager(Protocol):
    """Processes one input atomically and publishes events."""

    async def invoke(self, context: ModelGatewayContext) -> ModelGatewayResult: ...


@runtime_checkable
class ModelGatewayEngine(Protocol):
    """Public entry point coordinating model invocation planning."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def invoke(self, context: ModelGatewayContext) -> ModelGatewayResult: ...
