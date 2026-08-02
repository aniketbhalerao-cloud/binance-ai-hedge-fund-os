"""Position Framework domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Money/quantities use
:class:`~decimal.Decimal`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from models import OrderSide

from positions.state import PositionState

__all__ = [
    "PositionResultStatus",
    "PositionSide",
    "PositionTrade",
    "PositionCalculation",
    "Position",
    "PositionHistory",
    "PositionMetrics",
    "PositionSnapshot",
    "PositionResult",
]

_ZERO = Decimal("0")


class PositionResultStatus(str, Enum):
    """Coarse outcome of a position update."""

    SUCCESS = "success"
    FAILED = "failed"


class PositionSide(str, Enum):
    """Direction of a position."""

    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True, slots=True)
class PositionTrade:
    """A single fill affecting a position."""

    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class PositionCalculation:
    """The output of the calculator: durable + transient position figures."""

    side: PositionSide
    quantity: Decimal
    total_bought: Decimal
    total_sold: Decimal
    average_entry: Decimal
    average_exit: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    duration_seconds: Decimal
    exit_count: int


@dataclass(frozen=True, slots=True)
class Position:
    """An immutable position snapshot (durable state)."""

    id: str
    symbol: str
    side: PositionSide
    state: PositionState
    quantity: Decimal = _ZERO
    average_entry: Decimal = _ZERO
    average_exit: Decimal = _ZERO
    realized_pnl: Decimal = _ZERO
    total_bought: Decimal = _ZERO
    total_sold: Decimal = _ZERO
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PositionHistory:
    """Append-only record of a position's trades."""

    position_id: str
    trades: tuple[PositionTrade, ...] = ()

    def append(self, trade: PositionTrade) -> "PositionHistory":
        """Return a new history with ``trade`` appended (never mutates)."""
        return PositionHistory(self.position_id, self.trades + (trade,))


@dataclass(frozen=True, slots=True)
class PositionMetrics:
    """Derived statistics for a position (from its history)."""

    trade_count: int = 0
    holding_time_seconds: Decimal = _ZERO
    win_rate: Decimal = _ZERO
    average_profit: Decimal = _ZERO
    average_loss: Decimal = _ZERO
    max_favorable_excursion: Decimal = _ZERO
    max_adverse_excursion: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    """A complete, cacheable position snapshot (durable + transient)."""

    position: Position
    metrics: PositionMetrics
    unrealized_pnl: Decimal
    duration_seconds: Decimal
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class PositionResult:
    """The immutable outcome of a position update."""

    status: PositionResultStatus
    position: Position | None = None
    snapshot: PositionSnapshot | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the update succeeded."""
        return self.status is PositionResultStatus.SUCCESS
