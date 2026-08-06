"""Notification Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions so new
collectors, formatters, and dispatch policies plug in without modification
(Open/Closed). DI binds the ``Default*`` / ``InMemory*`` concretes to these keys
(Dependency Inversion).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from notification.context import NotificationContext
from notification.models import (
    NotificationBatch,
    NotificationMetrics,
    NotificationRecord,
    NotificationRequest,
    NotificationResult,
)

__all__ = [
    "Collector",
    "Formatter",
    "Dispatcher",
    "NotificationMetricsCalculator",
    "NotificationRegistry",
    "NotificationManager",
    "NotificationEngine",
]


@runtime_checkable
class Collector(Protocol):
    """Builds a notification batch from a context (stateless)."""

    def collect(self, context: NotificationContext) -> NotificationBatch: ...


@runtime_checkable
class Formatter(Protocol):
    """Formats a notification batch; never applies changes (stateless)."""

    def format(
        self, batch: NotificationBatch, context: NotificationContext
    ) -> NotificationBatch: ...


@runtime_checkable
class Dispatcher(Protocol):
    """Generates deterministic notification requests from a batch (stateless)."""

    def dispatch(
        self, batch: NotificationBatch, context: NotificationContext
    ) -> tuple[NotificationRequest, ...]: ...


@runtime_checkable
class NotificationMetricsCalculator(Protocol):
    """Derives notification metrics from a record (stateless)."""

    def calculate(self, record: NotificationRecord) -> NotificationMetrics: ...


@runtime_checkable
class NotificationRegistry(Protocol):
    """Thread-safe store that owns the running records (never creates them)."""

    def register(self, record: NotificationRecord) -> None: ...
    def unregister(self, record_id: str) -> None: ...
    def get(self, record_id: str) -> NotificationRecord: ...
    def exists(self, record_id: str) -> bool: ...
    def list(self) -> list[NotificationRecord]: ...
    def clear(self) -> None: ...


@runtime_checkable
class NotificationManager(Protocol):
    """Processes one input atomically and publishes events."""

    async def notify(self, context: NotificationContext) -> NotificationResult: ...


@runtime_checkable
class NotificationEngine(Protocol):
    """Public entry point coordinating notification."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def notify(self, context: NotificationContext) -> NotificationResult: ...
