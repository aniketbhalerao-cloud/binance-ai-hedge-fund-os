"""Storage Framework — deterministic, immutable storage requests from the system.

Consumes standardized outputs produced by the existing system (reporting,
notification, dashboard, monitoring, and performance analytics readings,
assembled into a :class:`StorageContext`), collects a batch, serializes it into
storage items, and produces deterministic storage requests and metrics. The
Registry owns the running :class:`StorageRecord`; the Manager loads it,
processes one input atomically, and writes back a new immutable record. It
publishes storage events on the shared event bus, is exchange-independent, and
**only serializes and plans domain objects** — it never connects to a database,
executes SQL, writes a file, uploads an object, accesses cloud storage, opens a
socket, executes a trade, modifies a strategy, agent, or portfolio, trains a
model, or modifies any other framework. New collectors, serializers, and
persistence policies plug in without changing the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from storage.collector import DefaultCollector
from storage.context import StorageContext
from storage.engine import DefaultStorageEngine
from storage.events import (
    RequestsPlanned,
    StorageCancelled,
    StorageCollected,
    StorageCompleted,
    StorageErrorOccurred,
    StorageEvent,
    StorageMetricsUpdated,
    StorageSerialized,
    StorageSnapshotCreated,
    StorageStarted,
)
from storage.exceptions import (
    CollectionError,
    MetricsError,
    PersistenceError,
    RegistryError,
    SerializationError,
    StorageCancelledError,
    StorageError,
)
from storage.interfaces import (
    Collector,
    PersistencePlanner,
    Serializer,
    StorageEngine,
    StorageManager,
    StorageMetricsCalculator,
    StorageRegistry,
)
from storage.manager import DefaultStorageManager
from storage.metrics import DefaultStorageMetrics
from storage.models import (
    SUPPORTED_STORAGE_TARGETS,
    StorageBatch,
    StorageHistory,
    StorageItem,
    StorageMetrics,
    StorageParameters,
    StorageRecord,
    StorageRequest,
    StorageResult,
    StorageResultStatus,
    StorageSnapshot,
    StorageSource,
)
from storage.persistence_planner import DefaultPersistencePlanner
from storage.registry import InMemoryStorageRegistry
from storage.serializer import DefaultSerializer
from storage.state import StorageState

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "StorageContext",
    "StorageState",
    "StorageResultStatus",
    "SUPPORTED_STORAGE_TARGETS",
    # models
    "StorageParameters",
    "StorageSource",
    "StorageItem",
    "StorageBatch",
    "StorageRequest",
    "StorageHistory",
    "StorageRecord",
    "StorageMetrics",
    "StorageSnapshot",
    "StorageResult",
    # interfaces
    "Collector",
    "Serializer",
    "PersistencePlanner",
    "StorageMetricsCalculator",
    "StorageRegistry",
    "StorageManager",
    "StorageEngine",
    # implementations
    "DefaultCollector",
    "DefaultSerializer",
    "DefaultPersistencePlanner",
    "DefaultStorageMetrics",
    "InMemoryStorageRegistry",
    "DefaultStorageManager",
    "DefaultStorageEngine",
    # events
    "StorageEvent",
    "StorageStarted",
    "StorageCollected",
    "StorageSerialized",
    "RequestsPlanned",
    "StorageSnapshotCreated",
    "StorageMetricsUpdated",
    "StorageCompleted",
    "StorageCancelled",
    "StorageErrorOccurred",
    # exceptions
    "StorageError",
    "CollectionError",
    "SerializationError",
    "PersistenceError",
    "MetricsError",
    "RegistryError",
    "StorageCancelledError",
    # wiring
    "register_storage",
]


def register_storage(container: Container) -> None:
    """Register the Storage Framework services into a DI container.

    Registers the stateless collector/serializer/planner/metrics, the
    thread-safe registry, the manager, and the engine as singletons, bound to
    their abstractions (Dependency Inversion). ``EventBus`` is registered on
    demand; ``LoggerFactory`` is injected only if already registered. The
    framework never instantiates a model, provider, or network client.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(Collector, DefaultCollector)
    container.register_class(Serializer, DefaultSerializer)
    container.register_class(PersistencePlanner, DefaultPersistencePlanner)
    container.register_class(StorageMetricsCalculator, DefaultStorageMetrics)
    container.register_class(StorageRegistry, InMemoryStorageRegistry)

    def _build_manager(resolver: Resolver) -> DefaultStorageManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultStorageManager(
            resolver.resolve(EventBus),
            resolver.resolve(StorageRegistry),
            resolver.resolve(Collector),
            resolver.resolve(Serializer),
            resolver.resolve(PersistencePlanner),
            resolver.resolve(StorageMetricsCalculator),
            logger=logger,
        )

    container.register_singleton(DefaultStorageManager, _build_manager)
    container.register_singleton(
        StorageManager, lambda r: r.resolve(DefaultStorageManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultStorageEngine:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultStorageEngine(
            resolver.resolve(StorageManager), logger=logger
        )

    container.register_singleton(DefaultStorageEngine, _build_engine)
    container.register_singleton(
        StorageEngine, lambda r: r.resolve(DefaultStorageEngine)
    )
