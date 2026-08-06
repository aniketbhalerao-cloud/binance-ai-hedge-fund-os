"""Dashboard Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions so
new aggregators, composers, and widget policies plug in without modification
(Open/Closed). DI binds the ``Default*`` / ``InMemory*`` concretes to these keys
(Dependency Inversion).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from dashboard.context import DashboardContext
from dashboard.models import (
    DashboardMetrics,
    DashboardRecord,
    DashboardResult,
    DashboardView,
    Widget,
)

__all__ = [
    "Aggregator",
    "Composer",
    "WidgetGenerator",
    "DashboardMetricsCalculator",
    "DashboardRegistry",
    "DashboardManager",
    "DashboardEngine",
]


@runtime_checkable
class Aggregator(Protocol):
    """Builds a dashboard view from a context (stateless)."""

    def aggregate(self, context: DashboardContext) -> DashboardView: ...


@runtime_checkable
class Composer(Protocol):
    """Composes a dashboard view; never applies changes (stateless)."""

    def compose(
        self, view: DashboardView, context: DashboardContext
    ) -> DashboardView: ...


@runtime_checkable
class WidgetGenerator(Protocol):
    """Generates deterministic widgets from a view (stateless)."""

    def generate(
        self, view: DashboardView, context: DashboardContext
    ) -> tuple[Widget, ...]: ...


@runtime_checkable
class DashboardMetricsCalculator(Protocol):
    """Derives dashboard metrics from a record (stateless)."""

    def calculate(self, record: DashboardRecord) -> DashboardMetrics: ...


@runtime_checkable
class DashboardRegistry(Protocol):
    """Thread-safe store that owns the running records (never creates them)."""

    def register(self, record: DashboardRecord) -> None: ...
    def unregister(self, record_id: str) -> None: ...
    def get(self, record_id: str) -> DashboardRecord: ...
    def exists(self, record_id: str) -> bool: ...
    def list(self) -> list[DashboardRecord]: ...
    def clear(self) -> None: ...


@runtime_checkable
class DashboardManager(Protocol):
    """Processes one input atomically and publishes events."""

    async def render(self, context: DashboardContext) -> DashboardResult: ...


@runtime_checkable
class DashboardEngine(Protocol):
    """Public entry point coordinating rendering."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def render(self, context: DashboardContext) -> DashboardResult: ...
