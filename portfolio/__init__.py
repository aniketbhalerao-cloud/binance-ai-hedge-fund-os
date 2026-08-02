"""Portfolio Management Framework — maintains portfolio state after executions.

Consumes completed executions (via a :class:`PortfolioContext`) and updates
standardized, immutable portfolio models: holdings, cash, valuation, allocation,
and performance. It publishes portfolio events on the shared event bus. It is
exchange-, strategy-, execution-, and risk-independent — it only accounts for
what already happened. New portfolio capabilities plug in without changing the
framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from portfolio.accounting import (
    DefaultHoldingsManager,
    DefaultPortfolioAccounting,
)
from portfolio.allocations import DefaultPortfolioAllocation
from portfolio.cash import DefaultCashManager
from portfolio.context import PortfolioContext
from portfolio.engine import DefaultPortfolioEngine
from portfolio.events import (
    AllocationUpdated,
    CashUpdated,
    HoldingsUpdated,
    PerformanceUpdated,
    PortfolioClosed,
    PortfolioCreated,
    PortfolioErrorOccurred,
    PortfolioEvent,
    PortfolioSnapshotCreated,
    PortfolioUpdated,
    PortfolioValuationCompleted,
)
from portfolio.exceptions import (
    AccountingError,
    AllocationError,
    CashError,
    HoldingsError,
    InvalidPortfolioStateError,
    PerformanceError,
    PortfolioClosedError,
    PortfolioError,
    PortfolioNotFoundError,
    ValuationError,
)
from portfolio.interfaces import (
    AccountingService,
    AllocationService,
    CashManager,
    HoldingsManager,
    PerformanceService,
    PortfolioEngine,
    PortfolioManager,
    PortfolioRegistry,
    ValuationService,
)
from portfolio.manager import DefaultPortfolioManager
from portfolio.models import (
    LedgerEntry,
    Portfolio,
    PortfolioAllocation,
    PortfolioCash,
    PortfolioPerformance,
    PortfolioPosition,
    PortfolioResult,
    PortfolioResultStatus,
    PortfolioSnapshot,
    PortfolioValue,
)
from portfolio.performance import DefaultPortfolioPerformance
from portfolio.registry import InMemoryPortfolioRegistry
from portfolio.state import PortfolioState
from portfolio.valuation import DefaultPortfolioValuation

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # context & state
    "PortfolioContext",
    "PortfolioState",
    "PortfolioResultStatus",
    # models
    "LedgerEntry",
    "PortfolioPosition",
    "PortfolioCash",
    "PortfolioValue",
    "PortfolioAllocation",
    "PortfolioPerformance",
    "Portfolio",
    "PortfolioSnapshot",
    "PortfolioResult",
    # interfaces
    "HoldingsManager",
    "CashManager",
    "AccountingService",
    "ValuationService",
    "AllocationService",
    "PerformanceService",
    "PortfolioRegistry",
    "PortfolioManager",
    "PortfolioEngine",
    # implementations
    "DefaultHoldingsManager",
    "DefaultCashManager",
    "DefaultPortfolioAccounting",
    "DefaultPortfolioValuation",
    "DefaultPortfolioAllocation",
    "DefaultPortfolioPerformance",
    "InMemoryPortfolioRegistry",
    "DefaultPortfolioManager",
    "DefaultPortfolioEngine",
    # events
    "PortfolioEvent",
    "PortfolioCreated",
    "PortfolioUpdated",
    "HoldingsUpdated",
    "CashUpdated",
    "PortfolioValuationCompleted",
    "AllocationUpdated",
    "PerformanceUpdated",
    "PortfolioSnapshotCreated",
    "PortfolioClosed",
    "PortfolioErrorOccurred",
    # exceptions
    "PortfolioError",
    "PortfolioNotFoundError",
    "PortfolioClosedError",
    "InvalidPortfolioStateError",
    "HoldingsError",
    "CashError",
    "ValuationError",
    "AccountingError",
    "AllocationError",
    "PerformanceError",
    # wiring
    "register_portfolio",
]


def register_portfolio(container: Container) -> None:
    """Register the Portfolio Framework services into a DI container.

    Registers the stateless components, the thread-safe registry, the manager,
    and the engine as singletons, bound to their abstractions (Dependency
    Inversion). ``EventBus`` is registered on demand; ``LoggerFactory`` and the
    Trading/Execution/Exchange engines are injected only if already registered.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(HoldingsManager, DefaultHoldingsManager)
    container.register_class(CashManager, DefaultCashManager)
    container.register_class(AccountingService, DefaultPortfolioAccounting)
    container.register_class(ValuationService, DefaultPortfolioValuation)
    container.register_class(AllocationService, DefaultPortfolioAllocation)
    container.register_class(PerformanceService, DefaultPortfolioPerformance)
    container.register_class(PortfolioRegistry, InMemoryPortfolioRegistry)

    def _build_manager(resolver: Resolver) -> DefaultPortfolioManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultPortfolioManager(
            resolver.resolve(EventBus),
            resolver.resolve(PortfolioRegistry),
            resolver.resolve(AccountingService),
            resolver.resolve(HoldingsManager),
            resolver.resolve(CashManager),
            resolver.resolve(ValuationService),
            resolver.resolve(AllocationService),
            resolver.resolve(PerformanceService),
            logger=logger,
        )

    container.register_singleton(DefaultPortfolioManager, _build_manager)
    container.register_singleton(
        PortfolioManager, lambda r: r.resolve(DefaultPortfolioManager)
    )

    def _build_engine(resolver: Resolver) -> DefaultPortfolioEngine:
        from exchange_adapters.interfaces import ExchangeEngine
        from execution.interfaces import ExecutionEngine
        from trading.engine import TradingEngine

        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return DefaultPortfolioEngine(
            resolver.resolve(PortfolioManager),
            logger=logger,
            trading_engine=(
                resolver.resolve(TradingEngine) if resolver.has(TradingEngine) else None
            ),
            execution_engine=(
                resolver.resolve(ExecutionEngine)
                if resolver.has(ExecutionEngine)
                else None
            ),
            exchange_engine=(
                resolver.resolve(ExchangeEngine)
                if resolver.has(ExchangeEngine)
                else None
            ),
        )

    container.register_singleton(DefaultPortfolioEngine, _build_engine)
    container.register_singleton(
        PortfolioEngine, lambda r: r.resolve(DefaultPortfolioEngine)
    )
