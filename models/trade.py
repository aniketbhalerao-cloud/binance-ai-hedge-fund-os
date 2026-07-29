"""Trade (execution / fill) domain model.

A :class:`Trade` records a single execution that resulted from an order — an
immutable historical fact. Like every other domain model it is
exchange-independent: the same shape describes a fill whether it came from
Binance, Zerodha, or the paper-trading simulator.

Only structural validation lives here; there is no persistence, I/O, logging,
or business logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from models.order import OrderSide

__all__ = ["Trade"]


@dataclass(frozen=True, slots=True)
class Trade:
    """An immutable record of a single fill.

    Attributes:
        id: Application-level unique identifier for the trade.
        order_id: Identifier of the :class:`~models.order.Order` that produced
            this fill.
        symbol: The instrument/pair that was traded.
        side: Buy or sell.
        quantity: Amount of the base asset filled (must be positive).
        price: Execution price in the quote asset (must be positive).
        fee: Fee charged for the execution (in ``fee_currency``).
        fee_currency: Asset in which the fee was charged.
        executed_at: Execution timestamp (timezone-aware, UTC).

    Raises:
        ValueError: If quantity, price, or fee are invalid.
    """

    id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    fee: Decimal = Decimal("0")
    fee_currency: str = ""
    executed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate structural invariants (no business rules)."""
        if self.quantity <= 0:
            raise ValueError("Trade.quantity must be positive.")
        if self.price <= 0:
            raise ValueError("Trade.price must be positive.")
        if self.fee < 0:
            raise ValueError("Trade.fee must not be negative.")
