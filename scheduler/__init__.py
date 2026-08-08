"""Scheduler Framework — deterministic, immutable schedule requests from the system.

Consumes standardized outputs produced by the existing system (storage
requests, report objects, notification requests, monitoring reports, and
optimization plans, assembled into a :class:`SchedulerContext`), collects a
batch, plans it into schedule entries, and produces deterministic schedule
requests and metrics. The Registry owns the running :class:`SchedulerRecord`;
the Manager loads it, processes one input atomically, and writes back a new
immutable record. It publishes scheduler events on the shared event bus, is
exchange-independent, and **only plans and dispatches domain objects** — it
never connects to Binance or any exchange, executes a scheduled job, opens a
socket, executes a trade, modifies a strategy, agent, or portfolio, trains a
model, or modifies any other framework. New collectors, planners, and
dispatch policies plug in without changing the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from scheduler.collector import DefaultCollector
from scheduler.context import SchedulerContext
from scheduler.dispatcher import DefaultDispatcher
from scheduler.engine import DefaultSchedulerEngine
from scheduler.events import (
    RequestsDispatched,
    ScheduleCollected,
    SchedulePlanned,
    SchedulerCancelled,
    SchedulerCompleted,
    SchedulerErrorOccurred,
    SchedulerEvent,
    SchedulerMetricsUpdated,
    SchedulerSnapshotCreated,
    SchedulerStarted,
)
from scheduler.exceptions import (
    CollectionError,
    DispatchError,
    MetricsError,
    PlanningError,
    RegistryError,
    SchedulerCancelledError,
    SchedulerError,
)
from scheduler.interfaces import (
    Collector,
    Dispatcher,
    Planner,
    SchedulerEngine,
    SchedulerManager,
    SchedulerMetricsCalculator,
    SchedulerRegistry,
)
from scheduler.manager import DefaultSchedulerManager
from scheduler.metrics import DefaultSchedulerMetrics
from scheduler.models import (
    SUPPORTED_SCHEDULE_CADENCES,
    ScheduleBatch,
    ScheduleEntry,
    ScheduleRequest,
    SchedulerHistory,
    SchedulerMetrics,
    SchedulerParameters,
    SchedulerRecord,
    SchedulerResult,
    SchedulerResultStatus,
    SchedulerSnapshot,
    ScheduleSource,
)
from scheduler.planner import DefaultPlanner
from scheduler.registry import InMemorySchedulerRegistry
from scheduler.state import SchedulerState

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "SchedulerContext",
    "SchedulerState",
    "SchedulerResultStatus",
    "SUPPORTED_SCHEDULE_CADENCES",
    # models
    "SchedulerParameters",
    "ScheduleSource",
    "ScheduleEntry",
    "ScheduleBatch",
    "ScheduleRequest",
    "SchedulerHistory",
    "SchedulerRecord",
    "SchedulerMetrics",
    "SchedulerSnapshot",
    "SchedulerResult",
    # interfaces
    "Collector",
    "Planner",
    "Dispatcher",
    "SchedulerMetricsCalculator",
    "SchedulerRegistry",
    "SchedulerManager",
    "SchedulerEngine",
    # implementations
    "DefaultCollector",
    "DefaultPlanner",
    "DefaultDispatcher",
    "DefaultSchedulerMetrics",
    "InMemorySchedulerRegistry",
    "DefaultSchedulerManager",
    "DefaultSchedulerEngine",
    # events
    "SchedulerEvent",
    "SchedulerStarted",
    "ScheduleCollected",
    "SchedulePlanned",
    "RequestsDispatched",
    "SchedulerSnapshotCreated",
    "SchedulerMetricsUpdated",
    "SchedulerCompleted",
    "SchedulerCancelled",
    "SchedulerErrorOccurred",
    # exceptions
    "SchedulerError",
    "CollectionError",
    "PlanningError",
    "DispatchError",
    "MetricsError",
    "RegistryError",
    "SchedulerCancelledError",
    # wiring
    "register_scheduler",
]


def register_scheduler(container: Container) -> None:
    """Register the Scheduler Framework services into a DI container.

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
    container.register_class(SchedulerMetricsCalculator, DefaultSchedulerMetrics)
    container.register_class(SchedulerRegistry, InMemorySchedulerRegistry)

    def _build_manager(resolver: Resolver) -> DefaultSchedulerManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultSchedulerManager(
            resolver.resolve(EventBus),
            resolver.resolve(SchedulerRegistry),
            resolver.resolve(Collector),
            resolver.resolve(Planner),
            resolver.resolve(Dispatcher),
            resolver.resolve(SchedulerMetricsCalculator),
            logger=logger,
        )

    container.register_singleton(DefaultSchedulerManager, _build_manager)
    container.register_singleton(
        SchedulerManager, lambda r: r.resolve(DefaultSchedulerManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultSchedulerEngine:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultSchedulerEngine(
            resolver.resolve(SchedulerManager), logger=logger
        )

    container.register_singleton(DefaultSchedulerEngine, _build_engine)
    container.register_singleton(
        SchedulerEngine, lambda r: r.resolve(DefaultSchedulerEngine)
    )
