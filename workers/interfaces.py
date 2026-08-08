"""Background Workers Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions
so new collectors, planners, and dispatch policies plug in without
modification (Open/Closed). DI binds the ``Default*`` / ``InMemory*``
concretes to these keys (Dependency Inversion).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from workers.context import WorkerContext
from workers.models import (
    JobBatch,
    WorkerMetrics,
    WorkerRecord,
    WorkerRequest,
    WorkerResult,
)

__all__ = [
    "Collector",
    "Planner",
    "Dispatcher",
    "WorkerMetricsCalculator",
    "WorkerRegistry",
    "WorkerManager",
    "WorkerEngine",
]


@runtime_checkable
class Collector(Protocol):
    """Builds a job batch from a context (stateless)."""

    def collect(self, context: WorkerContext) -> JobBatch: ...


@runtime_checkable
class Planner(Protocol):
    """Plans job entries; never applies changes (stateless)."""

    def plan(self, batch: JobBatch, context: WorkerContext) -> JobBatch: ...


@runtime_checkable
class Dispatcher(Protocol):
    """Produces deterministic, immutable worker requests from a batch (stateless)."""

    def dispatch(
        self, batch: JobBatch, context: WorkerContext
    ) -> tuple[WorkerRequest, ...]: ...


@runtime_checkable
class WorkerMetricsCalculator(Protocol):
    """Derives worker metrics from a record (stateless)."""

    def calculate(self, record: WorkerRecord) -> WorkerMetrics: ...


@runtime_checkable
class WorkerRegistry(Protocol):
    """Thread-safe store that owns the running records (never creates them)."""

    def register(self, record: WorkerRecord) -> None: ...
    def unregister(self, record_id: str) -> None: ...
    def get(self, record_id: str) -> WorkerRecord: ...
    def exists(self, record_id: str) -> bool: ...
    def list(self) -> list[WorkerRecord]: ...
    def clear(self) -> None: ...


@runtime_checkable
class WorkerManager(Protocol):
    """Processes one input atomically and publishes events."""

    async def enqueue(self, context: WorkerContext) -> WorkerResult: ...


@runtime_checkable
class WorkerEngine(Protocol):
    """Public entry point coordinating background worker planning."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def enqueue(self, context: WorkerContext) -> WorkerResult: ...
