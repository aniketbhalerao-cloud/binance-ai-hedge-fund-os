"""Memory Framework — deterministic, immutable memory requests from the system.

Consumes standardized outputs produced by the existing system (agent
decisions, learning records, report objects, and storage requests, assembled
into a :class:`MemoryContext`), collects a batch, plans it into memory
entries, and produces deterministic memory requests and metrics. The
Registry owns the running :class:`MemoryRecord`; the Manager loads it,
processes one input atomically, and writes back a new immutable record. It
publishes memory events on the shared event bus, is exchange-independent,
and **only plans and dispatches domain objects** — it never connects to
Binance or any exchange, calls an AI provider, computes an embedding,
accesses a vector database, writes to a database, writes a file, opens a
socket, executes a trade, modifies a strategy, agent, or portfolio, trains a
model, or modifies any other framework. New collectors, planners, and
dispatch policies plug in without changing the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from memory.collector import DefaultCollector
from memory.context import MemoryContext
from memory.dispatcher import DefaultDispatcher
from memory.engine import DefaultMemoryEngine
from memory.events import (
    EntriesCollected,
    EntriesPlanned,
    MemoryCancelled,
    MemoryCompleted,
    MemoryErrorOccurred,
    MemoryEvent,
    MemoryMetricsUpdated,
    MemorySnapshotCreated,
    MemoryStarted,
    RequestsDispatched,
)
from memory.exceptions import (
    CollectionError,
    DispatchError,
    MemoryCancelledError,
    MemoryError,
    MetricsError,
    PlanningError,
    RegistryError,
)
from memory.interfaces import (
    Collector,
    Dispatcher,
    MemoryEngine,
    MemoryManager,
    MemoryMetricsCalculator,
    MemoryRegistry,
    Planner,
)
from memory.manager import DefaultMemoryManager
from memory.metrics import DefaultMemoryMetrics
from memory.models import (
    SUPPORTED_MEMORY_SCOPES,
    MemoryBatch,
    MemoryEntry,
    MemoryHistory,
    MemoryMetrics,
    MemoryParameters,
    MemoryRecord,
    MemoryRequest,
    MemoryResult,
    MemoryResultStatus,
    MemorySnapshot,
    MemorySource,
)
from memory.planner import DefaultPlanner
from memory.registry import InMemoryMemoryRegistry
from memory.state import MemoryState

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "MemoryContext",
    "MemoryState",
    "MemoryResultStatus",
    "SUPPORTED_MEMORY_SCOPES",
    # models
    "MemoryParameters",
    "MemorySource",
    "MemoryEntry",
    "MemoryBatch",
    "MemoryRequest",
    "MemoryHistory",
    "MemoryRecord",
    "MemoryMetrics",
    "MemorySnapshot",
    "MemoryResult",
    # interfaces
    "Collector",
    "Planner",
    "Dispatcher",
    "MemoryMetricsCalculator",
    "MemoryRegistry",
    "MemoryManager",
    "MemoryEngine",
    # implementations
    "DefaultCollector",
    "DefaultPlanner",
    "DefaultDispatcher",
    "DefaultMemoryMetrics",
    "InMemoryMemoryRegistry",
    "DefaultMemoryManager",
    "DefaultMemoryEngine",
    # events
    "MemoryEvent",
    "MemoryStarted",
    "EntriesCollected",
    "EntriesPlanned",
    "RequestsDispatched",
    "MemorySnapshotCreated",
    "MemoryMetricsUpdated",
    "MemoryCompleted",
    "MemoryCancelled",
    "MemoryErrorOccurred",
    # exceptions
    "MemoryError",
    "CollectionError",
    "PlanningError",
    "DispatchError",
    "MetricsError",
    "RegistryError",
    "MemoryCancelledError",
    # wiring
    "register_memory",
]


def register_memory(container: Container) -> None:
    """Register the Memory Framework services into a DI container.

    Registers the stateless collector/planner/dispatcher/metrics, the
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
    container.register_class(Planner, DefaultPlanner)
    container.register_class(Dispatcher, DefaultDispatcher)
    container.register_class(MemoryMetricsCalculator, DefaultMemoryMetrics)
    container.register_class(MemoryRegistry, InMemoryMemoryRegistry)

    def _build_manager(resolver: Resolver) -> DefaultMemoryManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultMemoryManager(
            resolver.resolve(EventBus),
            resolver.resolve(MemoryRegistry),
            resolver.resolve(Collector),
            resolver.resolve(Planner),
            resolver.resolve(Dispatcher),
            resolver.resolve(MemoryMetricsCalculator),
            logger=logger,
        )

    container.register_singleton(DefaultMemoryManager, _build_manager)
    container.register_singleton(
        MemoryManager, lambda r: r.resolve(DefaultMemoryManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultMemoryEngine:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultMemoryEngine(
            resolver.resolve(MemoryManager), logger=logger
        )

    container.register_singleton(DefaultMemoryEngine, _build_engine)
    container.register_singleton(
        MemoryEngine, lambda r: r.resolve(DefaultMemoryEngine)
    )
