"""Performance Analytics Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions so
future analytics (new benchmarks, additional metric families) plug in without
modification (Open/Closed). DI binds the ``Default*`` / ``InMemory*`` concretes to
these keys (Dependency Inversion).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from performance.context import PerformanceContext
from performance.models import (
    BenchmarkMetrics,
    PerformanceResult,
    PerformanceSnapshot,
    ReturnsMetrics,
    RiskMetrics,
    StatisticsMetrics,
)

__all__ = [
    "ReturnsCalculator",
    "RiskCalculator",
    "StatisticsCalculator",
    "BenchmarkingService",
    "PerformanceRegistry",
    "PerformanceManager",
    "PerformanceEngine",
]


@runtime_checkable
class ReturnsCalculator(Protocol):
    """Computes return metrics from a context (stateless, pure)."""

    def calculate(self, context: PerformanceContext) -> ReturnsMetrics: ...


@runtime_checkable
class RiskCalculator(Protocol):
    """Computes risk metrics from a context (stateless, pure)."""

    def calculate(self, context: PerformanceContext) -> RiskMetrics: ...


@runtime_checkable
class StatisticsCalculator(Protocol):
    """Computes trading statistics from a context (stateless, pure)."""

    def calculate(self, context: PerformanceContext) -> StatisticsMetrics: ...


@runtime_checkable
class BenchmarkingService(Protocol):
    """Compares performance against a benchmark (stateless, pure).

    The benchmark itself is abstract — supplied to the context as a standardized
    returns series / prices — so new benchmarks (BTC, ETH, S&P 500, a paper
    index, a custom index) plug in without changing this component.
    """

    def compare(self, context: PerformanceContext) -> BenchmarkMetrics: ...


@runtime_checkable
class PerformanceRegistry(Protocol):
    """Thread-safe store of performance snapshots (never creates them)."""

    def register(self, snapshot: PerformanceSnapshot) -> None: ...
    def unregister(self, snapshot_id: str) -> None: ...
    def get(self, snapshot_id: str) -> PerformanceSnapshot: ...
    def exists(self, snapshot_id: str) -> bool: ...
    def list(self) -> list[PerformanceSnapshot]: ...
    def clear(self) -> None: ...


@runtime_checkable
class PerformanceManager(Protocol):
    """Coordinates the analysis pipeline and publishes events."""

    async def analyze(self, context: PerformanceContext) -> PerformanceResult: ...


@runtime_checkable
class PerformanceEngine(Protocol):
    """Public entry point coordinating performance analysis."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def analyze(self, context: PerformanceContext) -> PerformanceResult: ...
