"""Order domain model.

An :class:`Order` is a venue-independent representation of an instruction to
buy or sell an instrument. It carries no broker- or exchange-specific fields, so
the Trading Engine, Risk Manager, and every Exchange Adapter can all speak in
terms of the same object.

The model is an immutable snapshot: state transitions (for example a fill
changing the status) are represented by constructing a new :class:`Order`
elsewhere, not by mutating an existing one. Only lightweight structural
validation lives here — no business logic, persistence, I/O, or logging.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

__all__ = ["OrderSide", "OrderType", "TimeInForce", "OrderStatus", "Order"]


class OrderSide(str, Enum):
    """Direction of an order."""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """How an order is priced and triggered."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForce(str, Enum):
    """How long an order remains active before expiring."""

    GTC = "gtc"  # Good 'til canceled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill


class OrderStatus(str, Enum):
    """Lifecycle state of an order."""

    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class Order:
    """An immutable snapshot of a trading order.

    Attributes:
        id: Application-level unique identifier for the order.
        symbol: The instrument/pair the order targets (e.g. ``"BTCUSDT"``).
        side: Buy or sell.
        type: Market, limit, stop, or stop-limit.
        quantity: Amount of the base asset to transact (must be positive).
        price: Limit/trigger price; required for non-market orders.
        status: Current lifecycle state.
        time_in_force: Expiry policy.
        filled_quantity: Amount already filled (``0`` .. ``quantity``).
        created_at: Creation timestamp (timezone-aware, UTC).
        client_order_id: Optional caller-supplied idempotency key.

    Raises:
        ValueError: If quantities or prices are inconsistent.
    """

    id: str
    symbol: str
    side: OrderSide
    type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    status: OrderStatus = OrderStatus.PENDING
    time_in_force: TimeInForce = TimeInForce.GTC
    filled_quantity: Decimal = Decimal("0")
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    client_order_id: str | None = None

    def __post_init__(self) -> None:
        """Validate structural invariants (no business rules)."""
        if self.quantity <= 0:
            raise ValueError("Order.quantity must be positive.")
        if self.filled_quantity < 0:
            raise ValueError("Order.filled_quantity must not be negative.")
        if self.filled_quantity > self.quantity:
            raise ValueError("Order.filled_quantity cannot exceed quantity.")
        if self.type is not OrderType.MARKET and self.price is None:
            raise ValueError(f"{self.type.value} orders require a price.")
        if self.price is not None and self.price <= 0:
            raise ValueError("Order.price must be positive when set.")
