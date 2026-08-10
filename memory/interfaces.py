"""Memory Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions
so new collectors, planners, and dispatch policies plug in without
modification (Open/Closed). DI binds the ``Default*`` / ``InMemory*``
concretes to these keys (Dependency Inversion).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from memory.context import MemoryContext
from memory.models import (
    MemoryBatch,
    MemoryMetrics,
    MemoryRecord,
    MemoryRequest,
    MemoryResult,
)

__all__ = [
    "Collector",
    "Planner",
    "Dispatcher",
    "MemoryMetricsCalculator",
    "MemoryRegistry",
    "MemoryManager",
    "MemoryEngine",
]


@runtime_checkable
class Collector(Protocol):
    """Builds a memory batch from a context (stateless)."""

    def collect(self, context: MemoryContext) -> MemoryBatch: ...


@runtime_checkable
class Planner(Protocol):
    """Plans memory entries; never applies changes (stateless)."""

    def plan(self, batch: MemoryBatch, context: MemoryContext) -> MemoryBatch: ...


@runtime_checkable
class Dispatcher(Protocol):
    """Produces deterministic, immutable memory requests from a batch (stateless)."""

    def dispatch(
        self, batch: MemoryBatch, context: MemoryContext
    ) -> tuple[MemoryRequest, ...]: ...


@runtime_checkable
class MemoryMetricsCalculator(Protocol):
    """Derives memory metrics from a record (stateless)."""

    def calculate(self, record: MemoryRecord) -> MemoryMetrics: ...


@runtime_checkable
class MemoryRegistry(Protocol):
    """Thread-safe store that owns the running records (never creates them)."""

    def register(self, record: MemoryRecord) -> None: ...
    def unregister(self, record_id: str) -> None: ...
    def get(self, record_id: str) -> MemoryRecord: ...
    def exists(self, record_id: str) -> bool: ...
    def list(self) -> list[MemoryRecord]: ...
    def clear(self) -> None: ...


@runtime_checkable
class MemoryManager(Protocol):
    """Processes one input atomically and publishes events."""

    async def remember(self, context: MemoryContext) -> MemoryResult: ...


@runtime_checkable
class MemoryEngine(Protocol):
    """Public entry point coordinating memory planning."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def remember(self, context: MemoryContext) -> MemoryResult: ...
