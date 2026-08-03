"""Backtesting Framework — historical simulation over the existing architecture.

Replays historical market data through the real frameworks (Strategy → Risk →
Order → Execution → Portfolio → Position → Trade → Performance), using a
deterministic Simulator for historical fills *after* Execution has coordinated
each order, and produces immutable backtest metrics and snapshots. It publishes
backtest events on the shared event bus, is exchange-independent (never contacts
Binance or any exchange), and reuses every upstream framework through dependency
injection without modifying any of them. New capabilities (fill models,
schedulers, metric families) plug in without changing the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backtesting.context import BacktestingContext
from backtesting.engine import DefaultBacktestEngine
from backtesting.events import (
    BacktestCancelled,
    BacktestCompleted,
    BacktestErrorOccurred,
    BacktestEvent,
    BacktestMetricsUpdated,
    BacktestPaused,
    BacktestProgress,
    BacktestResumed,
    BacktestSnapshotCreated,
    BacktestStarted,
    SimulationStepCompleted,
)
from backtesting.exceptions import (
    BacktestCancelledError,
    BacktestError,
    HistoryError,
    MetricsError,
    RegistryError,
    SchedulerError,
    SimulationError,
)
from backtesting.history import DefaultBacktestHistory
from backtesting.interfaces import (
    BacktestEngine,
    BacktestHistoryService,
    BacktestManager,
    BacktestMetricsCalculator,
    BacktestRegistry,
    Scheduler,
    Simulator,
)
from backtesting.manager import DefaultBacktestManager
from backtesting.metrics import DefaultBacktestMetrics
from backtesting.models import (
    Backtest,
    BacktestHistory,
    BacktestMetrics,
    BacktestResult,
    BacktestResultStatus,
    BacktestSnapshot,
    BacktestSummary,
    SimulatedFill,
    SimulationParameters,
    SimulationStep,
)
from backtesting.registry import InMemoryBacktestRegistry
from backtesting.scheduler import DefaultScheduler
from backtesting.simulator import DefaultSimulator
from backtesting.state import SimulationState
from core.logging import LoggerFactory
from events.bus import EventBus

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "BacktestingContext",
    "SimulationState",
    "BacktestResultStatus",
    # models
    "SimulationParameters",
    "SimulatedFill",
    "SimulationStep",
    "Backtest",
    "BacktestMetrics",
    "BacktestSummary",
    "BacktestSnapshot",
    "BacktestHistory",
    "BacktestResult",
    # interfaces
    "Scheduler",
    "Simulator",
    "BacktestMetricsCalculator",
    "BacktestHistoryService",
    "BacktestRegistry",
    "BacktestManager",
    "BacktestEngine",
    # implementations
    "DefaultScheduler",
    "DefaultSimulator",
    "DefaultBacktestMetrics",
    "DefaultBacktestHistory",
    "InMemoryBacktestRegistry",
    "DefaultBacktestManager",
    "DefaultBacktestEngine",
    # events
    "BacktestEvent",
    "BacktestStarted",
    "BacktestProgress",
    "BacktestPaused",
    "BacktestResumed",
    "BacktestCompleted",
    "BacktestCancelled",
    "SimulationStepCompleted",
    "BacktestSnapshotCreated",
    "BacktestMetricsUpdated",
    "BacktestErrorOccurred",
    # exceptions
    "BacktestError",
    "SimulationError",
    "SchedulerError",
    "MetricsError",
    "HistoryError",
    "RegistryError",
    "BacktestCancelledError",
    # wiring
    "register_backtesting",
]


def register_backtesting(container: Container) -> None:
    """Register the Backtesting Framework services into a DI container.

    Registers the stateless components, the thread-safe registry, the manager,
    and the engine as singletons, bound to their abstractions (Dependency
    Inversion). ``EventBus`` is registered on demand; ``LoggerFactory`` and every
    upstream engine are injected only if already registered, so backtesting reuses
    whatever of the spine is wired without requiring all of it.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(Scheduler, DefaultScheduler)
    container.register_class(Simulator, DefaultSimulator)
    container.register_class(BacktestMetricsCalculator, DefaultBacktestMetrics)
    container.register_class(BacktestHistoryService, DefaultBacktestHistory)
    container.register_class(BacktestRegistry, InMemoryBacktestRegistry)

    def _build_manager(resolver: Resolver) -> DefaultBacktestManager:
        from execution.interfaces import ExecutionEngine
        from order_management.interfaces import OrderEngine
        from performance.interfaces import PerformanceEngine
        from portfolio.interfaces import PortfolioEngine
        from positions.interfaces import PositionEngine
        from risk.interfaces import RiskEngine
        from trades.interfaces import TradeEngine

        def opt(key: type[object]) -> object | None:
            return resolver.resolve(key) if resolver.has(key) else None

        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultBacktestManager(
            resolver.resolve(EventBus),
            resolver.resolve(BacktestRegistry),
            resolver.resolve(Scheduler),
            resolver.resolve(Simulator),
            resolver.resolve(BacktestMetricsCalculator),
            resolver.resolve(BacktestHistoryService),
            logger=logger,
            risk_engine=opt(RiskEngine),  # type: ignore[arg-type]
            order_engine=opt(OrderEngine),  # type: ignore[arg-type]
            execution_engine=opt(ExecutionEngine),  # type: ignore[arg-type]
            portfolio_engine=opt(PortfolioEngine),  # type: ignore[arg-type]
            position_engine=opt(PositionEngine),  # type: ignore[arg-type]
            trade_engine=opt(TradeEngine),  # type: ignore[arg-type]
            performance_engine=opt(PerformanceEngine),  # type: ignore[arg-type]
        )

    container.register_singleton(DefaultBacktestManager, _build_manager)
    container.register_singleton(
        BacktestManager, lambda r: r.resolve(DefaultBacktestManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultBacktestEngine:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultBacktestEngine(resolver.resolve(BacktestManager), logger=logger)

    container.register_singleton(DefaultBacktestEngine, _build_engine)
    container.register_singleton(
        BacktestEngine, lambda r: r.resolve(DefaultBacktestEngine)
    )
