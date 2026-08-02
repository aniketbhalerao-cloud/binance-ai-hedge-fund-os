"""Position Management Framework — maintains position lifecycle after portfolio updates.

Consumes completed portfolio updates (via a :class:`PositionContext`) and
maintains standardized, immutable position models: tracking, lifecycle,
calculation (averages / P&L / duration), append-only history, and metrics. It
publishes position events on the shared event bus. It is exchange-, execution-,
valuation-, and strategy-independent. New position capabilities plug in without
changing the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from positions.calculator import DefaultPositionCalculator
from positions.context import PositionContext
from positions.engine import DefaultPositionEngine
from positions.events import (
    PositionClosed,
    PositionErrorOccurred,
    PositionEvent,
    PositionHistoryUpdated,
    PositionMetricsUpdated,
    PositionOpened,
    PositionPartiallyClosed,
    PositionSnapshotCreated,
    PositionStateChanged,
    PositionUpdated,
)
from positions.exceptions import (
    InvalidPositionStateError,
    PositionCalculationError,
    PositionClosedError,
    PositionError,
    PositionHistoryError,
    PositionMetricsError,
    PositionNotFoundError,
    PositionTrackerError,
)
from positions.history import DefaultPositionHistory
from positions.interfaces import (
    PositionCalculator,
    PositionEngine,
    PositionHistoryService,
    PositionLifecycle,
    PositionManager,
    PositionMetricsService,
    PositionRegistry,
    PositionTracker,
)
from positions.lifecycle import DefaultPositionLifecycle
from positions.manager import DefaultPositionManager
from positions.metrics import DefaultPositionMetrics
from positions.models import (
    Position,
    PositionCalculation,
    PositionHistory,
    PositionMetrics,
    PositionResult,
    PositionResultStatus,
    PositionSide,
    PositionSnapshot,
    PositionTrade,
)
from positions.registry import InMemoryPositionRegistry
from positions.state import PositionState
from positions.tracker import DefaultPositionTracker

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "PositionContext",
    "PositionState",
    "PositionResultStatus",
    "PositionSide",
    # models
    "PositionTrade",
    "PositionCalculation",
    "Position",
    "PositionHistory",
    "PositionMetrics",
    "PositionSnapshot",
    "PositionResult",
    # interfaces
    "PositionTracker",
    "PositionLifecycle",
    "PositionCalculator",
    "PositionHistoryService",
    "PositionMetricsService",
    "PositionRegistry",
    "PositionManager",
    "PositionEngine",
    # implementations
    "DefaultPositionTracker",
    "DefaultPositionLifecycle",
    "DefaultPositionCalculator",
    "DefaultPositionHistory",
    "DefaultPositionMetrics",
    "InMemoryPositionRegistry",
    "DefaultPositionManager",
    "DefaultPositionEngine",
    # events
    "PositionEvent",
    "PositionOpened",
    "PositionUpdated",
    "PositionPartiallyClosed",
    "PositionClosed",
    "PositionHistoryUpdated",
    "PositionMetricsUpdated",
    "PositionSnapshotCreated",
    "PositionStateChanged",
    "PositionErrorOccurred",
    # exceptions
    "PositionError",
    "PositionNotFoundError",
    "PositionClosedError",
    "InvalidPositionStateError",
    "PositionTrackerError",
    "PositionCalculationError",
    "PositionHistoryError",
    "PositionMetricsError",
    # wiring
    "register_positions",
]


def register_positions(container: Container) -> None:
    """Register the Position Framework services into a DI container.

    Registers the stateless components, the thread-safe registry, the manager,
    and the engine as singletons, bound to their abstractions (Dependency
    Inversion). ``EventBus`` is registered on demand; ``LoggerFactory`` and the
    Trading/Portfolio engines are injected only if already registered.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(PositionTracker, DefaultPositionTracker)
    container.register_class(PositionLifecycle, DefaultPositionLifecycle)
    container.register_class(PositionCalculator, DefaultPositionCalculator)
    container.register_class(PositionHistoryService, DefaultPositionHistory)
    container.register_class(PositionMetricsService, DefaultPositionMetrics)
    container.register_class(PositionRegistry, InMemoryPositionRegistry)

    def _build_manager(resolver: Resolver) -> DefaultPositionManager:
        logger = resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        return DefaultPositionManager(
            resolver.resolve(EventBus),
            resolver.resolve(PositionRegistry),
            resolver.resolve(PositionTracker),
            resolver.resolve(PositionLifecycle),
            resolver.resolve(PositionCalculator),
            resolver.resolve(PositionHistoryService),
            resolver.resolve(PositionMetricsService),
            logger=logger,
        )

    container.register_singleton(DefaultPositionManager, _build_manager)
    container.register_singleton(
        PositionManager, lambda r: r.resolve(DefaultPositionManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultPositionEngine:
        from portfolio.interfaces import PortfolioEngine
        from trading.engine import TradingEngine

        logger = resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        return DefaultPositionEngine(
            resolver.resolve(PositionManager),
            logger=logger,
            trading_engine=(
                resolver.resolve(TradingEngine) if resolver.has(TradingEngine) else None
            ),
            portfolio_engine=(
                resolver.resolve(PortfolioEngine)
                if resolver.has(PortfolioEngine)
                else None
            ),
        )

    container.register_singleton(DefaultPositionEngine, _build_engine)
    container.register_singleton(
        PositionEngine, lambda r: r.resolve(DefaultPositionEngine)
    )
