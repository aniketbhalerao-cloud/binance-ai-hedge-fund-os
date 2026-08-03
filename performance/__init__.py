"""Performance Analytics Framework — read-only analysis of trading activity.

Consumes completed, standardized upstream results (execution, portfolio,
position, trade) plus standardized analytical series (via a
:class:`PerformanceContext`) and produces immutable performance analytics:
returns, risk, trading statistics, and benchmark comparison, packaged as an
immutable :class:`PerformanceSnapshot` / :class:`PerformanceResult`. It publishes
performance events on the shared event bus. It is exchange-, broker-, and
strategy-independent, strictly read-only (it never executes trades, manages
positions, or mutates portfolio state), and terminal on the processing spine.
New analytics (benchmarks, metric families, reports) plug in without changing the
framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from performance.benchmarking import DefaultBenchmarkingService
from performance.context import PerformanceContext
from performance.engine import DefaultPerformanceEngine
from performance.events import (
    BenchmarkCalculated,
    PerformanceAnalysisCompleted,
    PerformanceAnalysisStarted,
    PerformanceEngineStarted,
    PerformanceEngineStopped,
    PerformanceErrorOccurred,
    PerformanceEvent,
    PerformanceSnapshotCreated,
    ReturnsCalculated,
    RiskCalculated,
    StatisticsCalculated,
)
from performance.exceptions import (
    BenchmarkCalculationError,
    DuplicatePerformanceError,
    PerformanceError,
    PerformanceNotFoundError,
    PerformanceRegistryError,
    ReturnsCalculationError,
    RiskCalculationError,
    StatisticsCalculationError,
)
from performance.interfaces import (
    BenchmarkingService,
    PerformanceEngine,
    PerformanceManager,
    PerformanceRegistry,
    ReturnsCalculator,
    RiskCalculator,
    StatisticsCalculator,
)
from performance.manager import DefaultPerformanceManager
from performance.models import (
    BenchmarkMetrics,
    PerformanceIdentifier,
    PerformanceMetadata,
    PerformanceMetrics,
    PerformanceResult,
    PerformanceSnapshot,
    PerformanceSummary,
    PerformanceValue,
    ReturnsMetrics,
    RiskMetrics,
    StatisticsMetrics,
)
from performance.registry import InMemoryPerformanceRegistry
from performance.returns import DefaultReturnsCalculator
from performance.risk import DefaultRiskCalculator
from performance.state import PerformanceStatus
from performance.statistics import DefaultStatisticsCalculator

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "PerformanceContext",
    "PerformanceStatus",
    # models
    "PerformanceIdentifier",
    "PerformanceValue",
    "ReturnsMetrics",
    "RiskMetrics",
    "StatisticsMetrics",
    "BenchmarkMetrics",
    "PerformanceMetrics",
    "PerformanceSummary",
    "PerformanceMetadata",
    "PerformanceSnapshot",
    "PerformanceResult",
    # interfaces
    "ReturnsCalculator",
    "RiskCalculator",
    "StatisticsCalculator",
    "BenchmarkingService",
    "PerformanceRegistry",
    "PerformanceManager",
    "PerformanceEngine",
    # implementations
    "DefaultReturnsCalculator",
    "DefaultRiskCalculator",
    "DefaultStatisticsCalculator",
    "DefaultBenchmarkingService",
    "InMemoryPerformanceRegistry",
    "DefaultPerformanceManager",
    "DefaultPerformanceEngine",
    # events
    "PerformanceEvent",
    "PerformanceAnalysisStarted",
    "ReturnsCalculated",
    "RiskCalculated",
    "StatisticsCalculated",
    "BenchmarkCalculated",
    "PerformanceSnapshotCreated",
    "PerformanceAnalysisCompleted",
    "PerformanceEngineStarted",
    "PerformanceEngineStopped",
    "PerformanceErrorOccurred",
    # exceptions
    "PerformanceError",
    "ReturnsCalculationError",
    "RiskCalculationError",
    "StatisticsCalculationError",
    "BenchmarkCalculationError",
    "PerformanceRegistryError",
    "DuplicatePerformanceError",
    "PerformanceNotFoundError",
    # wiring
    "register_performance",
]


def register_performance(container: Container) -> None:
    """Register the Performance Framework services into a DI container.

    Registers the stateless calculators, the thread-safe registry, the manager,
    and the engine as singletons, bound to their abstractions (Dependency
    Inversion). ``EventBus`` is registered on demand; ``LoggerFactory`` and the
    Trade/Position/Portfolio engines are injected only if already registered, so
    wiring order stays forgiving.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(ReturnsCalculator, DefaultReturnsCalculator)
    container.register_class(RiskCalculator, DefaultRiskCalculator)
    container.register_class(StatisticsCalculator, DefaultStatisticsCalculator)
    container.register_class(BenchmarkingService, DefaultBenchmarkingService)
    container.register_class(PerformanceRegistry, InMemoryPerformanceRegistry)

    def _build_manager(resolver: Resolver) -> DefaultPerformanceManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultPerformanceManager(
            resolver.resolve(EventBus),
            resolver.resolve(PerformanceRegistry),
            resolver.resolve(ReturnsCalculator),
            resolver.resolve(RiskCalculator),
            resolver.resolve(StatisticsCalculator),
            resolver.resolve(BenchmarkingService),
            logger=logger,
        )

    container.register_singleton(DefaultPerformanceManager, _build_manager)
    container.register_singleton(
        PerformanceManager, lambda r: r.resolve(DefaultPerformanceManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultPerformanceEngine:
        from portfolio.interfaces import PortfolioEngine
        from positions.interfaces import PositionEngine
        from trades.interfaces import TradeEngine

        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultPerformanceEngine(
            resolver.resolve(EventBus),
            resolver.resolve(PerformanceManager),
            logger=logger,
            trade_engine=(
                resolver.resolve(TradeEngine) if resolver.has(TradeEngine) else None
            ),
            position_engine=(
                resolver.resolve(PositionEngine)
                if resolver.has(PositionEngine)
                else None
            ),
            portfolio_engine=(
                resolver.resolve(PortfolioEngine)
                if resolver.has(PortfolioEngine)
                else None
            ),
        )

    container.register_singleton(DefaultPerformanceEngine, _build_engine)
    container.register_singleton(
        PerformanceEngine, lambda r: r.resolve(DefaultPerformanceEngine)
    )
