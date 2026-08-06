"""Notification Framework — deterministic notification requests from the system.

Consumes standardized outputs produced by the existing system (monitoring,
dashboard, optimization, and learning readings, assembled into a
:class:`NotificationContext`), collects a batch, formats it, and produces
deterministic notification requests and metrics. The Registry owns the running
:class:`NotificationRecord`; the Manager loads it, processes one input atomically,
and writes back a new immutable record. It publishes notification events on the
shared event bus, is exchange-independent, and **only requests** — it never sends a
real notification through any channel, modifies a strategy, agent, or portfolio,
trains a model, or makes a network/provider call. New collectors, formatters, and
dispatch policies plug in without changing the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from notification.collector import DefaultCollector
from notification.context import NotificationContext
from notification.dispatcher import DefaultDispatcher
from notification.engine import DefaultNotificationEngine
from notification.events import (
    NotificationCancelled,
    NotificationCollected,
    NotificationCompleted,
    NotificationErrorOccurred,
    NotificationEvent,
    NotificationFormatted,
    NotificationMetricsUpdated,
    NotificationSnapshotCreated,
    NotificationStarted,
    RequestsGenerated,
)
from notification.exceptions import (
    CollectionError,
    DispatchError,
    FormattingError,
    MetricsError,
    NotificationCancelledError,
    NotificationError,
    RegistryError,
)
from notification.formatter import DefaultFormatter
from notification.interfaces import (
    Collector,
    Dispatcher,
    Formatter,
    NotificationEngine,
    NotificationManager,
    NotificationMetricsCalculator,
    NotificationRegistry,
)
from notification.manager import DefaultNotificationManager
from notification.metrics import DefaultNotificationMetrics
from notification.models import (
    Notification,
    NotificationBatch,
    NotificationHistory,
    NotificationMetrics,
    NotificationParameters,
    NotificationRecord,
    NotificationRequest,
    NotificationResult,
    NotificationResultStatus,
    NotificationSnapshot,
    NotificationSource,
)
from notification.registry import InMemoryNotificationRegistry
from notification.state import NotificationState

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "NotificationContext",
    "NotificationState",
    "NotificationResultStatus",
    # models
    "NotificationParameters",
    "NotificationSource",
    "Notification",
    "NotificationBatch",
    "NotificationRequest",
    "NotificationHistory",
    "NotificationRecord",
    "NotificationMetrics",
    "NotificationSnapshot",
    "NotificationResult",
    # interfaces
    "Collector",
    "Formatter",
    "Dispatcher",
    "NotificationMetricsCalculator",
    "NotificationRegistry",
    "NotificationManager",
    "NotificationEngine",
    # implementations
    "DefaultCollector",
    "DefaultFormatter",
    "DefaultDispatcher",
    "DefaultNotificationMetrics",
    "InMemoryNotificationRegistry",
    "DefaultNotificationManager",
    "DefaultNotificationEngine",
    # events
    "NotificationEvent",
    "NotificationStarted",
    "NotificationCollected",
    "NotificationFormatted",
    "RequestsGenerated",
    "NotificationSnapshotCreated",
    "NotificationMetricsUpdated",
    "NotificationCompleted",
    "NotificationCancelled",
    "NotificationErrorOccurred",
    # exceptions
    "NotificationError",
    "CollectionError",
    "FormattingError",
    "DispatchError",
    "MetricsError",
    "RegistryError",
    "NotificationCancelledError",
    # wiring
    "register_notification",
]


def register_notification(container: Container) -> None:
    """Register the Notification Framework services into a DI container.

    Registers the stateless collector/formatter/dispatcher/metrics, the thread-safe
    registry, the manager, and the engine as singletons, bound to their
    abstractions (Dependency Inversion). ``EventBus`` is registered on demand;
    ``LoggerFactory`` is injected only if already registered. The framework never
    instantiates a model, provider, or network client.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(Collector, DefaultCollector)
    container.register_class(Formatter, DefaultFormatter)
    container.register_class(Dispatcher, DefaultDispatcher)
    container.register_class(
        NotificationMetricsCalculator, DefaultNotificationMetrics
    )
    container.register_class(NotificationRegistry, InMemoryNotificationRegistry)

    def _build_manager(resolver: Resolver) -> DefaultNotificationManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultNotificationManager(
            resolver.resolve(EventBus),
            resolver.resolve(NotificationRegistry),
            resolver.resolve(Collector),
            resolver.resolve(Formatter),
            resolver.resolve(Dispatcher),
            resolver.resolve(NotificationMetricsCalculator),
            logger=logger,
        )

    container.register_singleton(DefaultNotificationManager, _build_manager)
    container.register_singleton(
        NotificationManager, lambda r: r.resolve(DefaultNotificationManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultNotificationEngine:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultNotificationEngine(
            resolver.resolve(NotificationManager), logger=logger
        )

    container.register_singleton(DefaultNotificationEngine, _build_engine)
    container.register_singleton(
        NotificationEngine, lambda r: r.resolve(DefaultNotificationEngine)
    )
