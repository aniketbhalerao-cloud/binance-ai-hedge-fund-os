"""Dashboard Framework — deterministic presentation of the running system.

Consumes standardized outputs produced by the existing system (strategy,
performance, optimization, and monitoring readings, assembled into a
:class:`DashboardContext`), aggregates a view, composes it, and produces
deterministic widgets and metrics. The Registry owns the running
:class:`DashboardRecord`; the Manager loads it, processes one input atomically, and
writes back a new immutable record. It publishes dashboard events on the shared
event bus, is exchange-independent, and **only presents** — it never renders to a
real display, modifies a strategy, agent, or portfolio, trains a model, or makes a
network/provider call. New aggregators, composers, and widget policies plug in
without changing the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from dashboard.aggregator import DefaultAggregator
from dashboard.composer import DefaultComposer
from dashboard.context import DashboardContext
from dashboard.engine import DefaultDashboardEngine
from dashboard.events import (
    DashboardCancelled,
    DashboardCompleted,
    DashboardComposed,
    DashboardErrorOccurred,
    DashboardEvent,
    DashboardMetricsUpdated,
    DashboardSnapshotCreated,
    DashboardStarted,
    DashboardViewCreated,
    WidgetsGenerated,
)
from dashboard.exceptions import (
    AggregationError,
    CompositionError,
    DashboardCancelledError,
    DashboardError,
    MetricsError,
    RegistryError,
    WidgetError,
)
from dashboard.interfaces import (
    Aggregator,
    Composer,
    DashboardEngine,
    DashboardManager,
    DashboardMetricsCalculator,
    DashboardRegistry,
    WidgetGenerator,
)
from dashboard.manager import DefaultDashboardManager
from dashboard.metrics import DefaultDashboardMetrics
from dashboard.models import (
    DashboardHistory,
    DashboardMetrics,
    DashboardParameters,
    DashboardRecord,
    DashboardResult,
    DashboardResultStatus,
    DashboardSnapshot,
    DashboardSource,
    DashboardView,
    Panel,
    Widget,
)
from dashboard.registry import InMemoryDashboardRegistry
from dashboard.state import DashboardState
from dashboard.widgets import DefaultWidgets
from events.bus import EventBus

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "DashboardContext",
    "DashboardState",
    "DashboardResultStatus",
    # models
    "DashboardParameters",
    "DashboardSource",
    "Panel",
    "DashboardView",
    "Widget",
    "DashboardHistory",
    "DashboardRecord",
    "DashboardMetrics",
    "DashboardSnapshot",
    "DashboardResult",
    # interfaces
    "Aggregator",
    "Composer",
    "WidgetGenerator",
    "DashboardMetricsCalculator",
    "DashboardRegistry",
    "DashboardManager",
    "DashboardEngine",
    # implementations
    "DefaultAggregator",
    "DefaultComposer",
    "DefaultWidgets",
    "DefaultDashboardMetrics",
    "InMemoryDashboardRegistry",
    "DefaultDashboardManager",
    "DefaultDashboardEngine",
    # events
    "DashboardEvent",
    "DashboardStarted",
    "DashboardViewCreated",
    "DashboardComposed",
    "WidgetsGenerated",
    "DashboardSnapshotCreated",
    "DashboardMetricsUpdated",
    "DashboardCompleted",
    "DashboardCancelled",
    "DashboardErrorOccurred",
    # exceptions
    "DashboardError",
    "AggregationError",
    "CompositionError",
    "WidgetError",
    "MetricsError",
    "RegistryError",
    "DashboardCancelledError",
    # wiring
    "register_dashboard",
]


def register_dashboard(container: Container) -> None:
    """Register the Dashboard Framework services into a DI container.

    Registers the stateless aggregator/composer/widgets/metrics, the thread-safe
    registry, the manager, and the engine as singletons, bound to their
    abstractions (Dependency Inversion). ``EventBus`` is registered on demand;
    ``LoggerFactory`` is injected only if already registered. The framework never
    instantiates a model, provider, or network client.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(Aggregator, DefaultAggregator)
    container.register_class(Composer, DefaultComposer)
    container.register_class(WidgetGenerator, DefaultWidgets)
    container.register_class(DashboardMetricsCalculator, DefaultDashboardMetrics)
    container.register_class(DashboardRegistry, InMemoryDashboardRegistry)

    def _build_manager(resolver: Resolver) -> DefaultDashboardManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultDashboardManager(
            resolver.resolve(EventBus),
            resolver.resolve(DashboardRegistry),
            resolver.resolve(Aggregator),
            resolver.resolve(Composer),
            resolver.resolve(WidgetGenerator),
            resolver.resolve(DashboardMetricsCalculator),
            logger=logger,
        )

    container.register_singleton(DefaultDashboardManager, _build_manager)
    container.register_singleton(
        DashboardManager, lambda r: r.resolve(DefaultDashboardManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultDashboardEngine:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultDashboardEngine(
            resolver.resolve(DashboardManager), logger=logger
        )

    container.register_singleton(DefaultDashboardEngine, _build_engine)
    container.register_singleton(
        DashboardEngine, lambda r: r.resolve(DefaultDashboardEngine)
    )
