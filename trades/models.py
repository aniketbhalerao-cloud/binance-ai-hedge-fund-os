"""Trade Framework domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Money/quantities use
:class:`~decimal.Decimal`; timestamps are timezone-aware UTC. State changes
produce **new** objects — nothing here is ever mutated in place.

A *trade* here is the round-trip lifecycle of a single instrument position: it
opens on the first entry fill, aggregates subsequent fills, is matched
entry-against-exit, and completes when fully closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from models import OrderSide
from positions.models import PositionSide
from trades.state import TradeState

__all__ = [
    "TradeResultStatus",
    "TradeFill",
    "Trade",
    "TradeHistory",
    "TradeMatch",
    "TradeAnalytics",
    "TradeSnapshot",
    "TradeResult",
]

_ZERO = Decimal("0")


class TradeResultStatus(str, Enum):
    """Coarse outcome of a trade update."""

    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TradeFill:
    """A single fill affecting a trade (an incremental entry or exit).

    ``realized_pnl`` is the profit/loss realized *by this fill* (non-zero only on
    exit fills that close matched quantity); it is not a running total.
    """

    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    realized_pnl: Decimal
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class Trade:
    """An immutable trade snapshot (durable state)."""

    id: str
    symbol: str
    side: PositionSide
    state: TradeState
    entry_quantity: Decimal = _ZERO
    exit_quantity: Decimal = _ZERO
    average_entry: Decimal = _ZERO
    average_exit: Decimal = _ZERO
    realized_pnl: Decimal = _ZERO
    fill_count: int = 0
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class TradeHistory:
    """Append-only record of a trade's fills."""

    trade_id: str
    fills: tuple[TradeFill, ...] = ()

    def append(self, fill: TradeFill) -> TradeHistory:
        """Return a new history with ``fill`` appended (never mutates)."""
        return TradeHistory(self.trade_id, self.fills + (fill,))


@dataclass(frozen=True, slots=True)
class TradeMatch:
    """The output of the matcher: entry/exit correlation for a trade.

    Attributes:
        entry_quantity: Total quantity entered (bought) so far.
        exit_quantity: Total quantity exited (sold) so far.
        matched_quantity: Quantity matched entry-against-exit (``min`` of the two).
        is_entry: Whether the triggering fill increased the entry side.
        is_exit: Whether the triggering fill increased the exit side.
        completed: Whether the trade is a fully matched round trip.
    """

    entry_quantity: Decimal
    exit_quantity: Decimal
    matched_quantity: Decimal
    is_entry: bool
    is_exit: bool
    completed: bool


@dataclass(frozen=True, slots=True)
class TradeAnalytics:
    """Derived statistics for a trade (from its history + durable figures)."""

    holding_time_seconds: Decimal = _ZERO
    duration_seconds: Decimal = _ZERO
    gross_profit: Decimal = _ZERO
    net_profit: Decimal = _ZERO
    won: bool = False
    fill_count: int = 0
    entry_quantity: Decimal = _ZERO
    exit_quantity: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class TradeSnapshot:
    """A complete, cacheable trade snapshot (durable state + analytics)."""

    trade: Trade
    analytics: TradeAnalytics
    fill_count: int
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class TradeResult:
    """The immutable outcome of a trade update."""

    status: TradeResultStatus
    trade: Trade | None = None
    snapshot: TradeSnapshot | None = None
    fill: TradeFill | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the update succeeded."""
        return self.status is TradeResultStatus.SUCCESS
