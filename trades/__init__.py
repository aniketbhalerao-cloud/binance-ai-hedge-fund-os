"""Trade Lifecycle Framework — maintains trade lifecycle after position updates.

Consumes completed position updates (via a :class:`TradeContext`) and maintains
standardized, immutable trade models: tracking (fill aggregation), entry/exit
matching, lifecycle state management, append-only history, and derived analytics.
It publishes trade events on the shared event bus. It is exchange-, execution-,
valuation-, and strategy-independent, and never executes trades or talks to
exchanges. New trade capabilities (multi-leg, options, futures, basket, trade
attribution) plug in without changing the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from trades.analytics import DefaultTradeAnalytics
from trades.context import TradeContext
from trades.engine import DefaultTradeEngine
from trades.events import (
    TradeAnalyticsUpdated,
    TradeClosed,
    TradeErrorOccurred,
    TradeEvent,
    TradeFilled,
    TradeHistoryUpdated,
    TradeMatched,
    TradeOpened,
    TradePartiallyFilled,
    TradeStateChanged,
    TradeUpdated,
)
from trades.exceptions import (
    InvalidTradeStateError,
    TradeAnalyticsError,
    TradeClosedError,
    TradeError,
    TradeHistoryError,
    TradeMatchingError,
    TradeNotFoundError,
    TradeTrackerError,
)
from trades.history import DefaultTradeHistory
from trades.interfaces import (
    TradeAnalyticsService,
    TradeEngine,
    TradeHistoryService,
    TradeLifecycle,
    TradeManager,
    TradeMatcher,
    TradeRegistry,
    TradeTracker,
)
from trades.lifecycle import DefaultTradeLifecycle
from trades.manager import DefaultTradeManager
from trades.matcher import DefaultTradeMatcher
from trades.models import (
    Trade,
    TradeAnalytics,
    TradeFill,
    TradeHistory,
    TradeMatch,
    TradeResult,
    TradeResultStatus,
    TradeSnapshot,
)
from trades.registry import InMemoryTradeRegistry
from trades.state import TradeState
from trades.tracker import DefaultTradeTracker

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "TradeContext",
    "TradeState",
    "TradeResultStatus",
    # models
    "TradeFill",
    "Trade",
    "TradeHistory",
    "TradeMatch",
    "TradeAnalytics",
    "TradeSnapshot",
    "TradeResult",
    # interfaces
    "TradeTracker",
    "TradeMatcher",
    "TradeLifecycle",
    "TradeHistoryService",
    "TradeAnalyticsService",
    "TradeRegistry",
    "TradeManager",
    "TradeEngine",
    # implementations
    "DefaultTradeTracker",
    "DefaultTradeMatcher",
    "DefaultTradeLifecycle",
    "DefaultTradeHistory",
    "DefaultTradeAnalytics",
    "InMemoryTradeRegistry",
    "DefaultTradeManager",
    "DefaultTradeEngine",
    # events
    "TradeEvent",
    "TradeOpened",
    "TradeUpdated",
    "TradeMatched",
    "TradePartiallyFilled",
    "TradeFilled",
    "TradeClosed",
    "TradeHistoryUpdated",
    "TradeAnalyticsUpdated",
    "TradeStateChanged",
    "TradeErrorOccurred",
    # exceptions
    "TradeError",
    "TradeNotFoundError",
    "TradeClosedError",
    "InvalidTradeStateError",
    "TradeTrackerError",
    "TradeMatchingError",
    "TradeHistoryError",
    "TradeAnalyticsError",
    # wiring
    "register_trades",
]


def register_trades(container: Container) -> None:
    """Register the Trade Framework services into a DI container.

    Registers the stateless components, the thread-safe registry, the manager,
    and the engine as singletons, bound to their abstractions (Dependency
    Inversion). ``EventBus`` is registered on demand; ``LoggerFactory`` and the
    Position/Trading engines are injected only if already registered, so wiring
    order stays forgiving.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(TradeTracker, DefaultTradeTracker)
    container.register_class(TradeMatcher, DefaultTradeMatcher)
    container.register_class(TradeLifecycle, DefaultTradeLifecycle)
    container.register_class(TradeHistoryService, DefaultTradeHistory)
    container.register_class(TradeAnalyticsService, DefaultTradeAnalytics)
    container.register_class(TradeRegistry, InMemoryTradeRegistry)

    def _build_manager(resolver: Resolver) -> DefaultTradeManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultTradeManager(
            resolver.resolve(EventBus),
            resolver.resolve(TradeRegistry),
            resolver.resolve(TradeTracker),
            resolver.resolve(TradeMatcher),
            resolver.resolve(TradeLifecycle),
            resolver.resolve(TradeHistoryService),
            resolver.resolve(TradeAnalyticsService),
            logger=logger,
        )

    container.register_singleton(DefaultTradeManager, _build_manager)
    container.register_singleton(
        TradeManager, lambda r: r.resolve(DefaultTradeManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultTradeEngine:
        from positions.interfaces import PositionEngine
        from trading.engine import TradingEngine

        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultTradeEngine(
            resolver.resolve(TradeManager),
            logger=logger,
            position_engine=(
                resolver.resolve(PositionEngine)
                if resolver.has(PositionEngine)
                else None
            ),
            trading_engine=(
                resolver.resolve(TradingEngine)
                if resolver.has(TradingEngine)
                else None
            ),
        )

    container.register_singleton(DefaultTradeEngine, _build_engine)
    container.register_singleton(TradeEngine, lambda r: r.resolve(DefaultTradeEngine))
