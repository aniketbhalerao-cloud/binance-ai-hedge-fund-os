"""Background Workers Framework — deterministic, immutable worker requests.

Consumes standardized outputs produced by the existing system (storage
requests, report objects, notification requests, monitoring reports, and
schedule requests, assembled into a :class:`WorkerContext`), collects a
batch, plans it into job entries, and produces deterministic worker requests
and metrics. The Registry owns the running :class:`WorkerRecord`; the
Manager loads it, processes one input atomically, and writes back a new
immutable record. It publishes worker events on the shared event bus, is
exchange-independent, and **only plans and dispatches domain objects** — it
never connects to Binance or any exchange, executes a background job, opens
a socket, executes a trade, modifies a strategy, agent, or portfolio, trains
a model, or modifies any other framework. New collectors, planners, and
dispatch policies plug in without changing the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from workers.collector import DefaultCollector
from workers.context import WorkerContext
from workers.dispatcher import DefaultDispatcher
from workers.engine import DefaultWorkerEngine
from workers.events import (
    JobsCollected,
    JobsQueued,
    RequestsDispatched,
    WorkerCancelled,
    WorkerCompleted,
    WorkerErrorOccurred,
    WorkerEvent,
    WorkerMetricsUpdated,
    WorkerSnapshotCreated,
    WorkerStarted,
)
from workers.exceptions import (
    CollectionError,
    DispatchError,
    MetricsError,
    PlanningError,
    RegistryError,
    WorkerCancelledError,
    WorkerError,
)
from workers.interfaces import (
    Collector,
    Dispatcher,
    Planner,
    WorkerEngine,
    WorkerManager,
    WorkerMetricsCalculator,
    WorkerRegistry,
)
from workers.manager import DefaultWorkerManager
from workers.metrics import DefaultWorkerMetrics
from workers.models import (
    SUPPORTED_WORKER_QUEUES,
    JobBatch,
    JobEntry,
    JobSource,
    WorkerHistory,
    WorkerMetrics,
    WorkerParameters,
    WorkerRecord,
    WorkerRequest,
    WorkerResult,
    WorkerResultStatus,
    WorkerSnapshot,
)
from workers.planner import DefaultPlanner
from workers.registry import InMemoryWorkerRegistry
from workers.state import WorkerState

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "WorkerContext",
    "WorkerState",
    "WorkerResultStatus",
    "SUPPORTED_WORKER_QUEUES",
    # models
    "WorkerParameters",
    "JobSource",
    "JobEntry",
    "JobBatch",
    "WorkerRequest",
    "WorkerHistory",
    "WorkerRecord",
    "WorkerMetrics",
    "WorkerSnapshot",
    "WorkerResult",
    # interfaces
    "Collector",
    "Planner",
    "Dispatcher",
    "WorkerMetricsCalculator",
    "WorkerRegistry",
    "WorkerManager",
    "WorkerEngine",
    # implementations
    "DefaultCollector",
    "DefaultPlanner",
    "DefaultDispatcher",
    "DefaultWorkerMetrics",
    "InMemoryWorkerRegistry",
    "DefaultWorkerManager",
    "DefaultWorkerEngine",
    # events
    "WorkerEvent",
    "WorkerStarted",
    "JobsCollected",
    "JobsQueued",
    "RequestsDispatched",
    "WorkerSnapshotCreated",
    "WorkerMetricsUpdated",
    "WorkerCompleted",
    "WorkerCancelled",
    "WorkerErrorOccurred",
    # exceptions
    "WorkerError",
    "CollectionError",
    "PlanningError",
    "DispatchError",
    "MetricsError",
    "RegistryError",
    "WorkerCancelledError",
    # wiring
    "register_workers",
]


def register_workers(container: Container) -> None:
    """Register the Background Workers Framework services into a DI container.

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
    container.register_class(WorkerMetricsCalculator, DefaultWorkerMetrics)
    container.register_class(WorkerRegistry, InMemoryWorkerRegistry)

    def _build_manager(resolver: Resolver) -> DefaultWorkerManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultWorkerManager(
            resolver.resolve(EventBus),
            resolver.resolve(WorkerRegistry),
            resolver.resolve(Collector),
            resolver.resolve(Planner),
            resolver.resolve(Dispatcher),
            resolver.resolve(WorkerMetricsCalculator),
            logger=logger,
        )

    container.register_singleton(DefaultWorkerManager, _build_manager)
    container.register_singleton(
        WorkerManager, lambda r: r.resolve(DefaultWorkerManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultWorkerEngine:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultWorkerEngine(
            resolver.resolve(WorkerManager), logger=logger
        )

    container.register_singleton(DefaultWorkerEngine, _build_engine)
    container.register_singleton(
        WorkerEngine, lambda r: r.resolve(DefaultWorkerEngine)
    )
