"""Paper Trading Framework — live simulation over the existing architecture.

Consumes live market data and drives it through the real frameworks (Feed →
Strategy → Risk → Order → Execution → Portfolio → Position → Trade → Performance),
using a deterministic Paper Broker for simulated fills *after* Execution has
coordinated each order, and never placing a real order. The Registry owns the
running :class:`PaperSession`; the Manager loads it, processes one live update
atomically, and writes back a new immutable session. The framework publishes
paper-trading events on the shared event bus, is exchange-independent (never
contacts Binance or any exchange), and reuses every upstream framework through
dependency injection without modifying any of them. New capabilities (fill
models, feeds, metric families) plug in without changing the framework
(Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from paper_trading.broker import DefaultPaperBroker
from paper_trading.context import PaperTradingContext
from paper_trading.engine import DefaultPaperTradingEngine
from paper_trading.events import (
    MarketDataProcessed,
    PaperMetricsUpdated,
    PaperOrderFilled,
    PaperSessionCancelled,
    PaperSessionCompleted,
    PaperSnapshotCreated,
    PaperTradeExecuted,
    PaperTradingErrorOccurred,
    PaperTradingEvent,
    PaperTradingStarted,
    PaperTradingStopped,
)
from paper_trading.exceptions import (
    BrokerError,
    FeedError,
    HistoryError,
    MetricsError,
    PaperSessionCancelledError,
    PaperTradingError,
    RegistryError,
)
from paper_trading.feed import DefaultFeed
from paper_trading.history import DefaultPaperTradingHistory
from paper_trading.interfaces import (
    Broker,
    Feed,
    PaperTradingEngine,
    PaperTradingHistoryService,
    PaperTradingManager,
    PaperTradingMetricsCalculator,
    PaperTradingRegistry,
)
from paper_trading.manager import DefaultPaperTradingManager
from paper_trading.metrics import DefaultPaperTradingMetrics
from paper_trading.models import (
    PaperFill,
    PaperSession,
    PaperTradingHistory,
    PaperTradingMetrics,
    PaperTradingResult,
    PaperTradingResultStatus,
    PaperTradingSnapshot,
    PaperTradingSummary,
    SessionParameters,
)
from paper_trading.registry import InMemoryPaperTradingRegistry
from paper_trading.state import SessionState

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "PaperTradingContext",
    "SessionState",
    "PaperTradingResultStatus",
    # models
    "SessionParameters",
    "PaperFill",
    "PaperTradingHistory",
    "PaperSession",
    "PaperTradingMetrics",
    "PaperTradingSummary",
    "PaperTradingSnapshot",
    "PaperTradingResult",
    # interfaces
    "Feed",
    "Broker",
    "PaperTradingMetricsCalculator",
    "PaperTradingHistoryService",
    "PaperTradingRegistry",
    "PaperTradingManager",
    "PaperTradingEngine",
    # implementations
    "DefaultFeed",
    "DefaultPaperBroker",
    "DefaultPaperTradingMetrics",
    "DefaultPaperTradingHistory",
    "InMemoryPaperTradingRegistry",
    "DefaultPaperTradingManager",
    "DefaultPaperTradingEngine",
    # events
    "PaperTradingEvent",
    "PaperTradingStarted",
    "PaperTradingStopped",
    "MarketDataProcessed",
    "PaperOrderFilled",
    "PaperTradeExecuted",
    "PaperSnapshotCreated",
    "PaperMetricsUpdated",
    "PaperSessionCompleted",
    "PaperSessionCancelled",
    "PaperTradingErrorOccurred",
    # exceptions
    "PaperTradingError",
    "FeedError",
    "BrokerError",
    "MetricsError",
    "HistoryError",
    "RegistryError",
    "PaperSessionCancelledError",
    # wiring
    "register_paper_trading",
]


def register_paper_trading(container: Container) -> None:
    """Register the Paper Trading Framework services into a DI container.

    Registers the stateless components, the thread-safe registry, the manager,
    and the engine as singletons, bound to their abstractions (Dependency
    Inversion). ``EventBus`` is registered on demand; ``LoggerFactory`` and every
    upstream engine are injected only if already registered, so paper trading
    reuses whatever of the spine is wired without requiring all of it.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(Feed, DefaultFeed)
    container.register_class(Broker, DefaultPaperBroker)
    container.register_class(
        PaperTradingMetricsCalculator, DefaultPaperTradingMetrics
    )
    container.register_class(
        PaperTradingHistoryService, DefaultPaperTradingHistory
    )
    container.register_class(PaperTradingRegistry, InMemoryPaperTradingRegistry)

    def _build_manager(resolver: Resolver) -> DefaultPaperTradingManager:
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
        return DefaultPaperTradingManager(
            resolver.resolve(EventBus),
            resolver.resolve(PaperTradingRegistry),
            resolver.resolve(Feed),
            resolver.resolve(Broker),
            resolver.resolve(PaperTradingMetricsCalculator),
            resolver.resolve(PaperTradingHistoryService),
            logger=logger,
            risk_engine=opt(RiskEngine),  # type: ignore[arg-type]
            order_engine=opt(OrderEngine),  # type: ignore[arg-type]
            execution_engine=opt(ExecutionEngine),  # type: ignore[arg-type]
            portfolio_engine=opt(PortfolioEngine),  # type: ignore[arg-type]
            position_engine=opt(PositionEngine),  # type: ignore[arg-type]
            trade_engine=opt(TradeEngine),  # type: ignore[arg-type]
            performance_engine=opt(PerformanceEngine),  # type: ignore[arg-type]
        )

    container.register_singleton(DefaultPaperTradingManager, _build_manager)
    container.register_singleton(
        PaperTradingManager, lambda r: r.resolve(DefaultPaperTradingManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultPaperTradingEngine:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultPaperTradingEngine(
            resolver.resolve(EventBus),
            resolver.resolve(PaperTradingManager),
            logger=logger,
        )

    container.register_singleton(DefaultPaperTradingEngine, _build_engine)
    container.register_singleton(
        PaperTradingEngine, lambda r: r.resolve(DefaultPaperTradingEngine)
    )
