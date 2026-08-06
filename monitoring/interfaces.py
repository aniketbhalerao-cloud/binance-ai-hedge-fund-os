"""Monitoring Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions so
new collectors, diagnostics, and alerting policies plug in without modification
(Open/Closed). DI binds the ``Default*`` / ``InMemory*`` concretes to these keys
(Dependency Inversion).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from monitoring.context import MonitoringContext
from monitoring.models import (
    Alert,
    HealthReport,
    MonitoringMetrics,
    MonitoringRecord,
    MonitoringResult,
)

__all__ = [
    "Collector",
    "Evaluator",
    "AlertGenerator",
    "MonitoringMetricsCalculator",
    "MonitoringRegistry",
    "MonitoringManager",
    "MonitoringEngine",
]


@runtime_checkable
class Collector(Protocol):
    """Builds a health report from a context (stateless)."""

    def collect(self, context: MonitoringContext) -> HealthReport: ...


@runtime_checkable
class Evaluator(Protocol):
    """Evaluates a health report; never applies changes (stateless)."""

    def evaluate(
        self, report: HealthReport, context: MonitoringContext
    ) -> HealthReport: ...


@runtime_checkable
class AlertGenerator(Protocol):
    """Generates deterministic alerts from a report (stateless)."""

    def generate(
        self, report: HealthReport, context: MonitoringContext
    ) -> tuple[Alert, ...]: ...


@runtime_checkable
class MonitoringMetricsCalculator(Protocol):
    """Derives monitoring metrics from a record (stateless)."""

    def calculate(self, record: MonitoringRecord) -> MonitoringMetrics: ...


@runtime_checkable
class MonitoringRegistry(Protocol):
    """Thread-safe store that owns the running records (never creates them)."""

    def register(self, record: MonitoringRecord) -> None: ...
    def unregister(self, record_id: str) -> None: ...
    def get(self, record_id: str) -> MonitoringRecord: ...
    def exists(self, record_id: str) -> bool: ...
    def list(self) -> list[MonitoringRecord]: ...
    def clear(self) -> None: ...


@runtime_checkable
class MonitoringManager(Protocol):
    """Processes one input atomically and publishes events."""

    async def monitor(self, context: MonitoringContext) -> MonitoringResult: ...


@runtime_checkable
class MonitoringEngine(Protocol):
    """Public entry point coordinating monitoring."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def monitor(self, context: MonitoringContext) -> MonitoringResult: ...
