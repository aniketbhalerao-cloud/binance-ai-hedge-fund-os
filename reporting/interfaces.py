"""Reporting Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions so
new collectors, builders, and export policies plug in without modification
(Open/Closed). DI binds the ``Default*`` / ``InMemory*`` concretes to these keys
(Dependency Inversion).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from reporting.context import ReportingContext
from reporting.models import (
    ExportRequest,
    ReportingBatch,
    ReportingMetrics,
    ReportingRecord,
    ReportingResult,
)

__all__ = [
    "Collector",
    "Builder",
    "Exporter",
    "ReportingMetricsCalculator",
    "ReportingRegistry",
    "ReportingManager",
    "ReportingEngine",
]


@runtime_checkable
class Collector(Protocol):
    """Builds a reporting batch from a context (stateless)."""

    def collect(self, context: ReportingContext) -> ReportingBatch: ...


@runtime_checkable
class Builder(Protocol):
    """Builds immutable report domain objects; never applies changes (stateless)."""

    def build(
        self, batch: ReportingBatch, context: ReportingContext
    ) -> ReportingBatch: ...


@runtime_checkable
class Exporter(Protocol):
    """Produces deterministic, immutable export requests from a batch (stateless)."""

    def export(
        self, batch: ReportingBatch, context: ReportingContext
    ) -> tuple[ExportRequest, ...]: ...


@runtime_checkable
class ReportingMetricsCalculator(Protocol):
    """Derives reporting metrics from a record (stateless)."""

    def calculate(self, record: ReportingRecord) -> ReportingMetrics: ...


@runtime_checkable
class ReportingRegistry(Protocol):
    """Thread-safe store that owns the running records (never creates them)."""

    def register(self, record: ReportingRecord) -> None: ...
    def unregister(self, record_id: str) -> None: ...
    def get(self, record_id: str) -> ReportingRecord: ...
    def exists(self, record_id: str) -> bool: ...
    def list(self) -> list[ReportingRecord]: ...
    def clear(self) -> None: ...


@runtime_checkable
class ReportingManager(Protocol):
    """Processes one input atomically and publishes events."""

    async def report(self, context: ReportingContext) -> ReportingResult: ...


@runtime_checkable
class ReportingEngine(Protocol):
    """Public entry point coordinating reporting."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def report(self, context: ReportingContext) -> ReportingResult: ...
