"""Scheduler Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions
so new collectors, planners, and dispatch policies plug in without
modification (Open/Closed). DI binds the ``Default*`` / ``InMemory*``
concretes to these keys (Dependency Inversion).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from scheduler.context import SchedulerContext
from scheduler.models import (
    ScheduleBatch,
    ScheduleRequest,
    SchedulerMetrics,
    SchedulerRecord,
    SchedulerResult,
)

__all__ = [
    "Collector",
    "Planner",
    "Dispatcher",
    "SchedulerMetricsCalculator",
    "SchedulerRegistry",
    "SchedulerManager",
    "SchedulerEngine",
]


@runtime_checkable
class Collector(Protocol):
    """Builds a schedule batch from a context (stateless)."""

    def collect(self, context: SchedulerContext) -> ScheduleBatch: ...


@runtime_checkable
class Planner(Protocol):
    """Plans schedule entries; never applies changes (stateless)."""

    def plan(
        self, batch: ScheduleBatch, context: SchedulerContext
    ) -> ScheduleBatch: ...


@runtime_checkable
class Dispatcher(Protocol):
    """Produces deterministic, immutable schedule requests from a batch (stateless)."""

    def dispatch(
        self, batch: ScheduleBatch, context: SchedulerContext
    ) -> tuple[ScheduleRequest, ...]: ...


@runtime_checkable
class SchedulerMetricsCalculator(Protocol):
    """Derives scheduler metrics from a record (stateless)."""

    def calculate(self, record: SchedulerRecord) -> SchedulerMetrics: ...


@runtime_checkable
class SchedulerRegistry(Protocol):
    """Thread-safe store that owns the running records (never creates them)."""

    def register(self, record: SchedulerRecord) -> None: ...
    def unregister(self, record_id: str) -> None: ...
    def get(self, record_id: str) -> SchedulerRecord: ...
    def exists(self, record_id: str) -> bool: ...
    def list(self) -> list[SchedulerRecord]: ...
    def clear(self) -> None: ...


@runtime_checkable
class SchedulerManager(Protocol):
    """Processes one input atomically and publishes events."""

    async def schedule(self, context: SchedulerContext) -> SchedulerResult: ...


@runtime_checkable
class SchedulerEngine(Protocol):
    """Public entry point coordinating scheduling."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def schedule(self, context: SchedulerContext) -> SchedulerResult: ...
