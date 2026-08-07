"""Storage Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions so
new collectors, serializers, and persistence policies plug in without
modification (Open/Closed). DI binds the ``Default*`` / ``InMemory*`` concretes
to these keys (Dependency Inversion).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from storage.context import StorageContext
from storage.models import (
    StorageBatch,
    StorageMetrics,
    StorageRecord,
    StorageRequest,
    StorageResult,
)

__all__ = [
    "Collector",
    "Serializer",
    "PersistencePlanner",
    "StorageMetricsCalculator",
    "StorageRegistry",
    "StorageManager",
    "StorageEngine",
]


@runtime_checkable
class Collector(Protocol):
    """Builds a storage batch from a context (stateless)."""

    def collect(self, context: StorageContext) -> StorageBatch: ...


@runtime_checkable
class Serializer(Protocol):
    """Serializes immutable storage items; never applies changes (stateless)."""

    def serialize(
        self, batch: StorageBatch, context: StorageContext
    ) -> StorageBatch: ...


@runtime_checkable
class PersistencePlanner(Protocol):
    """Produces deterministic, immutable storage requests from a batch (stateless)."""

    def plan(
        self, batch: StorageBatch, context: StorageContext
    ) -> tuple[StorageRequest, ...]: ...


@runtime_checkable
class StorageMetricsCalculator(Protocol):
    """Derives storage metrics from a record (stateless)."""

    def calculate(self, record: StorageRecord) -> StorageMetrics: ...


@runtime_checkable
class StorageRegistry(Protocol):
    """Thread-safe store that owns the running records (never creates them)."""

    def register(self, record: StorageRecord) -> None: ...
    def unregister(self, record_id: str) -> None: ...
    def get(self, record_id: str) -> StorageRecord: ...
    def exists(self, record_id: str) -> bool: ...
    def list(self) -> list[StorageRecord]: ...
    def clear(self) -> None: ...


@runtime_checkable
class StorageManager(Protocol):
    """Processes one input atomically and publishes events."""

    async def store(self, context: StorageContext) -> StorageResult: ...


@runtime_checkable
class StorageEngine(Protocol):
    """Public entry point coordinating storage."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def store(self, context: StorageContext) -> StorageResult: ...
