"""Portfolio Framework domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Money uses :class:`~decimal.Decimal`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from models import OrderSide

from portfolio.state import PortfolioState

__all__ = [
    "PortfolioResultStatus",
    "LedgerEntry",
    "PortfolioPosition",
    "PortfolioCash",
    "PortfolioValue",
    "PortfolioAllocation",
    "PortfolioPerformance",
    "Portfolio",
    "PortfolioSnapshot",
    "PortfolioResult",
]

_ZERO = Decimal("0")


class PortfolioResultStatus(str, Enum):
    """Coarse outcome of a portfolio update."""

    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """A single accounting ledger entry for a completed execution."""

    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class PortfolioPosition:
    """A held position (holdings), tracked by quantity and average cost."""

    symbol: str
    quantity: Decimal
    average_cost: Decimal
    realized_pnl: Decimal = _ZERO

    @property
    def cost_basis(self) -> Decimal:
        """Return the total cost basis of the position."""
        return self.quantity * self.average_cost


@dataclass(frozen=True, slots=True)
class PortfolioCash:
    """Cash balances, independent of holdings."""

    available: Decimal = _ZERO
    reserved: Decimal = _ZERO

    @property
    def total(self) -> Decimal:
        """Return total cash (available + reserved)."""
        return self.available + self.reserved


@dataclass(frozen=True, slots=True)
class PortfolioValue:
    """A valuation snapshot."""

    cash_value: Decimal
    holdings_value: Decimal
    cost_basis: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    total_value: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioAllocation:
    """Derived weights of each position and cash."""

    weights: Mapping[str, Decimal]
    cash_weight: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioPerformance:
    """Derived performance metrics."""

    daily_return: Decimal = _ZERO
    total_return: Decimal = _ZERO
    roi: Decimal = _ZERO
    cumulative_return: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class Portfolio:
    """An immutable portfolio snapshot (holdings + cash + ledger)."""

    id: str
    state: PortfolioState = PortfolioState.EMPTY
    positions: tuple[PortfolioPosition, ...] = ()
    cash: PortfolioCash = field(default_factory=PortfolioCash)
    ledger: tuple[LedgerEntry, ...] = ()
    realized_pnl: Decimal = _ZERO
    updated_at: datetime | None = None

    def position(self, symbol: str) -> PortfolioPosition | None:
        """Return the position for ``symbol`` if held."""
        for pos in self.positions:
            if pos.symbol == symbol:
                return pos
        return None


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """A complete, cacheable portfolio snapshot."""

    portfolio: Portfolio
    value: PortfolioValue
    allocation: PortfolioAllocation
    performance: PortfolioPerformance
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class PortfolioResult:
    """The immutable outcome of a portfolio update."""

    status: PortfolioResultStatus
    portfolio: Portfolio | None = None
    snapshot: PortfolioSnapshot | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the update succeeded."""
        return self.status is PortfolioResultStatus.SUCCESS
