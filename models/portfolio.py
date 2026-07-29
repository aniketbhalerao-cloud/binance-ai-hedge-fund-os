"""Portfolio domain model.

A :class:`Portfolio` is a venue-independent snapshot of all open positions plus
available cash at a point in time. Collections are stored as tuples so the
snapshot stays immutable. Aggregate figures (total value, exposure, …) are the
responsibility of higher layers and are not computed here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from models.position import Position

__all__ = ["Portfolio"]


@dataclass(frozen=True, slots=True)
class Portfolio:
    """An immutable snapshot of positions and cash.

    Attributes:
        positions: All open positions at ``as_of`` (immutable tuple).
        cash: Available cash in ``base_currency``.
        base_currency: The currency cash and valuations are denominated in.
        as_of: Snapshot timestamp (timezone-aware, UTC).

    Raises:
        ValueError: If ``base_currency`` is empty.
    """

    positions: tuple[Position, ...] = ()
    cash: Decimal = Decimal("0")
    base_currency: str = "USDT"
    as_of: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate structural invariants (no business rules)."""
        if not self.base_currency:
            raise ValueError("Portfolio.base_currency must not be empty.")
