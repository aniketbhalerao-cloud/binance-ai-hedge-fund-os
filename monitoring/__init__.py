"""Monitoring Framework — deterministic health observation of the running system.

Consumes standardized signals produced by the existing system (strategy, agent,
performance, and optimization readings, assembled into a :class:`MonitoringContext`),
collects a health report, evaluates it, and produces deterministic alerts and
metrics. The Registry owns the running :class:`MonitoringRecord`; the Manager loads
it, processes one input atomically, and writes back a new immutable record. It
publishes monitoring events on the shared event bus, is exchange-independent, and
**only observes** — it never sends an alert, modifies a strategy, agent, or
portfolio, trains a model, or makes a network/provider call. New collectors,
diagnostics, and alerting policies plug in without changing the framework
(Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from monitoring.alerts import DefaultAlerts
from monitoring.context import MonitoringContext
from monitoring.diagnostics import DefaultDiagnostics
from monitoring.engine import DefaultMonitoringEngine
from monitoring.events import (
    AlertsGenerated,
    HealthEvaluated,
    HealthReportCreated,
    MonitoringCancelled,
    MonitoringCompleted,
    MonitoringErrorOccurred,
    MonitoringEvent,
    MonitoringMetricsUpdated,
    MonitoringSnapshotCreated,
    MonitoringStarted,
)
from monitoring.exceptions import (
    AlertError,
    CollectionError,
    EvaluationError,
    MetricsError,
    MonitoringCancelledError,
    MonitoringError,
    RegistryError,
)
from monitoring.health import DefaultHealth
from monitoring.interfaces import (
    AlertGenerator,
    Collector,
    Evaluator,
    MonitoringEngine,
    MonitoringManager,
    MonitoringMetricsCalculator,
    MonitoringRegistry,
)
from monitoring.manager import DefaultMonitoringManager
from monitoring.metrics import DefaultMonitoringMetrics
from monitoring.models import (
    Alert,
    HealthCheck,
    HealthReport,
    MonitoredComponent,
    MonitoringHistory,
    MonitoringMetrics,
    MonitoringParameters,
    MonitoringRecord,
    MonitoringResult,
    MonitoringResultStatus,
    MonitoringSnapshot,
)
from monitoring.registry import InMemoryMonitoringRegistry
from monitoring.state import MonitoringState

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "MonitoringContext",
    "MonitoringState",
    "MonitoringResultStatus",
    # models
    "MonitoringParameters",
    "MonitoredComponent",
    "HealthCheck",
    "HealthReport",
    "Alert",
    "MonitoringHistory",
    "MonitoringRecord",
    "MonitoringMetrics",
    "MonitoringSnapshot",
    "MonitoringResult",
    # interfaces
    "Collector",
    "Evaluator",
    "AlertGenerator",
    "MonitoringMetricsCalculator",
    "MonitoringRegistry",
    "MonitoringManager",
    "MonitoringEngine",
    # implementations
    "DefaultHealth",
    "DefaultDiagnostics",
    "DefaultAlerts",
    "DefaultMonitoringMetrics",
    "InMemoryMonitoringRegistry",
    "DefaultMonitoringManager",
    "DefaultMonitoringEngine",
    # events
    "MonitoringEvent",
    "MonitoringStarted",
    "HealthReportCreated",
    "HealthEvaluated",
    "AlertsGenerated",
    "MonitoringSnapshotCreated",
    "MonitoringMetricsUpdated",
    "MonitoringCompleted",
    "MonitoringCancelled",
    "MonitoringErrorOccurred",
    # exceptions
    "MonitoringError",
    "CollectionError",
    "EvaluationError",
    "AlertError",
    "MetricsError",
    "RegistryError",
    "MonitoringCancelledError",
    # wiring
    "register_monitoring",
]


def register_monitoring(container: Container) -> None:
    """Register the Monitoring Framework services into a DI container.

    Registers the stateless collector/evaluator/alerts/metrics, the thread-safe
    registry, the manager, and the engine as singletons, bound to their
    abstractions (Dependency Inversion). ``EventBus`` is registered on demand;
    ``LoggerFactory`` is injected only if already registered. The framework never
    instantiates a model, provider, or network client.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(Collector, DefaultHealth)
    container.register_class(Evaluator, DefaultDiagnostics)
    container.register_class(AlertGenerator, DefaultAlerts)
    container.register_class(
        MonitoringMetricsCalculator, DefaultMonitoringMetrics
    )
    container.register_class(MonitoringRegistry, InMemoryMonitoringRegistry)

    def _build_manager(resolver: Resolver) -> DefaultMonitoringManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultMonitoringManager(
            resolver.resolve(EventBus),
            resolver.resolve(MonitoringRegistry),
            resolver.resolve(Collector),
            resolver.resolve(Evaluator),
            resolver.resolve(AlertGenerator),
            resolver.resolve(MonitoringMetricsCalculator),
            logger=logger,
        )

    container.register_singleton(DefaultMonitoringManager, _build_manager)
    container.register_singleton(
        MonitoringManager, lambda r: r.resolve(DefaultMonitoringManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultMonitoringEngine:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultMonitoringEngine(
            resolver.resolve(MonitoringManager), logger=logger
        )

    container.register_singleton(DefaultMonitoringEngine, _build_engine)
    container.register_singleton(
        MonitoringEngine, lambda r: r.resolve(DefaultMonitoringEngine)
    )
