"""Portfolio Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions so
future portfolio modules plug in without modification (Open/Closed). Calculator
protocols are named distinctly from the model classes they return.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Protocol, runtime_checkable

from models import OrderSide

from portfolio.context import PortfolioContext
from portfolio.models import (
    LedgerEntry,
    Portfolio,
    PortfolioAllocation,
    PortfolioCash,
    PortfolioPerformance,
    PortfolioPosition,
    PortfolioResult,
    PortfolioValue,
)

__all__ = [
    "HoldingsManager",
    "CashManager",
    "AccountingService",
    "ValuationService",
    "AllocationService",
    "PerformanceService",
    "PortfolioRegistry",
    "PortfolioManager",
    "PortfolioEngine",
]


@runtime_checkable
class HoldingsManager(Protocol):
    """Applies an execution to a position (add/update/close), stateless."""

    def apply(
        self,
        position: PortfolioPosition | None,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        price: Decimal,
    ) -> PortfolioPosition | None: ...


@runtime_checkable
class CashManager(Protocol):
    """Applies an execution to cash, and supports deposits/withdrawals."""

    def apply(
        self, cash: PortfolioCash, side: OrderSide, quantity: Decimal, price: Decimal
    ) -> PortfolioCash: ...
    def deposit(self, cash: PortfolioCash, amount: Decimal) -> PortfolioCash: ...
    def withdraw(self, cash: PortfolioCash, amount: Decimal) -> PortfolioCash: ...


@runtime_checkable
class AccountingService(Protocol):
    """Produces a ledger entry from a completed execution (stateless)."""

    def entry(self, context: PortfolioContext) -> LedgerEntry: ...


@runtime_checkable
class ValuationService(Protocol):
    """Values a portfolio from standardized prices (stateless)."""

    def value(
        self, portfolio: Portfolio, prices: Mapping[str, Decimal]
    ) -> PortfolioValue: ...


@runtime_checkable
class AllocationService(Protocol):
    """Derives allocation weights from a valued portfolio (stateless)."""

    def allocate(
        self, portfolio: Portfolio, value: PortfolioValue
    ) -> PortfolioAllocation: ...


@runtime_checkable
class PerformanceService(Protocol):
    """Derives performance from valuation outputs (stateless)."""

    def measure(
        self, value: PortfolioValue, previous: PortfolioValue | None
    ) -> PortfolioPerformance: ...


@runtime_checkable
class PortfolioRegistry(Protocol):
    """Thread-safe store of portfolios (never creates them)."""

    def register(self, portfolio: Portfolio) -> None: ...
    def update(self, portfolio: Portfolio) -> None: ...
    def get(self, portfolio_id: str) -> Portfolio: ...
    def exists(self, portfolio_id: str) -> bool: ...
    def list(self) -> list[Portfolio]: ...
    def remove(self, portfolio_id: str) -> None: ...


@runtime_checkable
class PortfolioManager(Protocol):
    """Coordinates the portfolio update pipeline and publishes events."""

    async def update(self, context: PortfolioContext) -> PortfolioResult: ...


@runtime_checkable
class PortfolioEngine(Protocol):
    """Public entry point coordinating portfolio updates."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def process(self, context: PortfolioContext) -> PortfolioResult: ...
