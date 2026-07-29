"""Position domain model.

A :class:`Position` describes current exposure to a single instrument. It is a
venue-independent snapshot: prices and P&L are *stored* values supplied by the
caller, never computed here (computation is the job of higher layers such as the
Portfolio/Performance engine).

Only structural validation lives in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

__all__ = ["PositionSide", "Position"]


class PositionSide(str, Enum):
    """Direction of exposure held by a position."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass(frozen=True, slots=True)
class Position:
    """An immutable snapshot of exposure to one instrument.

    Attributes:
        symbol: The instrument/pair the position is held in.
        side: Long, short, or flat.
        quantity: Size of the position in the base asset (non-negative;
            ``0`` for a flat position).
        entry_price: Average entry price in the quote asset (non-negative).
        current_price: Latest mark price, if known (supplied, not computed).
        unrealized_pnl: Mark-to-market P&L, if known (supplied, not computed).

    Raises:
        ValueError: If quantity or prices are negative.
    """

    symbol: str
    side: PositionSide
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal | None = None
    unrealized_pnl: Decimal | None = None

    def __post_init__(self) -> None:
        """Validate structural invariants (no business rules)."""
        if self.quantity < 0:
            raise ValueError("Position.quantity must not be negative.")
        if self.entry_price < 0:
            raise ValueError("Position.entry_price must not be negative.")
        if self.current_price is not None and self.current_price < 0:
            raise ValueError("Position.current_price must not be negative.")
