"""Reporting Framework — deterministic, immutable report objects from the system.

Consumes standardized outputs produced by the existing system (dashboard,
notification, monitoring, performance analytics, and learning readings,
assembled into a :class:`ReportingContext`), collects a batch, builds it into
report domain objects, and produces deterministic export requests and metrics.
The Registry owns the running :class:`ReportingRecord`; the Manager loads it,
processes one input atomically, and writes back a new immutable record. It
publishes reporting events on the shared event bus, is exchange-independent,
and **only builds and exports domain objects** — it never saves a report to
disk, writes a PDF/Excel/CSV file, emails or uploads a report, opens a network
connection, executes a trade, modifies a strategy, agent, or portfolio, trains
a model, or modifies any other framework. New collectors, builders, and export
policies plug in without changing the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from reporting.builder import DefaultBuilder
from reporting.collector import DefaultCollector
from reporting.context import ReportingContext
from reporting.engine import DefaultReportingEngine
from reporting.events import (
    ReportBuilt,
    ReportingCancelled,
    ReportingCollected,
    ReportingCompleted,
    ReportingErrorOccurred,
    ReportingEvent,
    ReportingMetricsUpdated,
    ReportingSnapshotCreated,
    ReportingStarted,
    ReportsExported,
)
from reporting.exceptions import (
    BuildError,
    CollectionError,
    ExportError,
    MetricsError,
    RegistryError,
    ReportingCancelledError,
    ReportingError,
)
from reporting.exporter import DefaultExporter
from reporting.interfaces import (
    Builder,
    Collector,
    Exporter,
    ReportingEngine,
    ReportingManager,
    ReportingMetricsCalculator,
    ReportingRegistry,
)
from reporting.manager import DefaultReportingManager
from reporting.metrics import DefaultReportingMetrics
from reporting.models import (
    SUPPORTED_REPORT_TYPES,
    ExportRequest,
    Report,
    ReportingBatch,
    ReportingHistory,
    ReportingMetrics,
    ReportingParameters,
    ReportingRecord,
    ReportingResult,
    ReportingResultStatus,
    ReportingSnapshot,
    ReportingSource,
)
from reporting.registry import InMemoryReportingRegistry
from reporting.state import ReportingState

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "ReportingContext",
    "ReportingState",
    "ReportingResultStatus",
    "SUPPORTED_REPORT_TYPES",
    # models
    "ReportingParameters",
    "ReportingSource",
    "Report",
    "ReportingBatch",
    "ExportRequest",
    "ReportingHistory",
    "ReportingRecord",
    "ReportingMetrics",
    "ReportingSnapshot",
    "ReportingResult",
    # interfaces
    "Collector",
    "Builder",
    "Exporter",
    "ReportingMetricsCalculator",
    "ReportingRegistry",
    "ReportingManager",
    "ReportingEngine",
    # implementations
    "DefaultCollector",
    "DefaultBuilder",
    "DefaultExporter",
    "DefaultReportingMetrics",
    "InMemoryReportingRegistry",
    "DefaultReportingManager",
    "DefaultReportingEngine",
    # events
    "ReportingEvent",
    "ReportingStarted",
    "ReportingCollected",
    "ReportBuilt",
    "ReportsExported",
    "ReportingSnapshotCreated",
    "ReportingMetricsUpdated",
    "ReportingCompleted",
    "ReportingCancelled",
    "ReportingErrorOccurred",
    # exceptions
    "ReportingError",
    "CollectionError",
    "BuildError",
    "ExportError",
    "MetricsError",
    "RegistryError",
    "ReportingCancelledError",
    # wiring
    "register_reporting",
]


def register_reporting(container: Container) -> None:
    """Register the Reporting Framework services into a DI container.

    Registers the stateless collector/builder/exporter/metrics, the thread-safe
    registry, the manager, and the engine as singletons, bound to their
    abstractions (Dependency Inversion). ``EventBus`` is registered on demand;
    ``LoggerFactory`` is injected only if already registered. The framework
    never instantiates a model, provider, or network client.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(Collector, DefaultCollector)
    container.register_class(Builder, DefaultBuilder)
    container.register_class(Exporter, DefaultExporter)
    container.register_class(ReportingMetricsCalculator, DefaultReportingMetrics)
    container.register_class(ReportingRegistry, InMemoryReportingRegistry)

    def _build_manager(resolver: Resolver) -> DefaultReportingManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultReportingManager(
            resolver.resolve(EventBus),
            resolver.resolve(ReportingRegistry),
            resolver.resolve(Collector),
            resolver.resolve(Builder),
            resolver.resolve(Exporter),
            resolver.resolve(ReportingMetricsCalculator),
            logger=logger,
        )

    container.register_singleton(DefaultReportingManager, _build_manager)
    container.register_singleton(
        ReportingManager, lambda r: r.resolve(DefaultReportingManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultReportingEngine:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultReportingEngine(
            resolver.resolve(ReportingManager), logger=logger
        )

    container.register_singleton(DefaultReportingEngine, _build_engine)
    container.register_singleton(
        ReportingEngine, lambda r: r.resolve(DefaultReportingEngine)
    )
