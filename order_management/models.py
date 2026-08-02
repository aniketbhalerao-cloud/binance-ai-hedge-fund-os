"""Order Framework domain models.

Immutable, exchange-independent value objects: the canonical order request the
framework produces, plus the validation/routing/result records. Order side,
type, and time-in-force reuse the neutral domain enums from :mod:`models` — this
framework introduces no exchange-specific fields.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from models import OrderSide, OrderType, TimeInForce
from order_management.state import OrderState

__all__ = [
    "OrderIdentifier",
    "OrderMetadata",
    "OrderRequest",
    "OrderValidationResult",
    "OrderRoute",
    "OrderResult",
]


@dataclass(frozen=True, slots=True)
class OrderIdentifier:
    """A neutral, application-level order identifier."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    client_order_id: str | None = None


@dataclass(frozen=True, slots=True)
class OrderMetadata:
    """Immutable, free-form metadata attached to order models."""

    data: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """A standardized, immutable order request (no exchange fields).

    Attributes:
        identifier: Application-level identifier.
        symbol: Instrument to trade.
        side: Buy or sell.
        order_type: Market/limit/stop/stop-limit.
        quantity: Base-asset amount.
        price: Limit price (for limit / stop-limit orders).
        stop_price: Trigger price (for stop / stop-limit orders).
        time_in_force: Expiry policy.
        state: Current lifecycle state.
        metadata: Optional metadata.
    """

    identifier: OrderIdentifier
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.GTC
    state: OrderState = OrderState.CREATED
    metadata: OrderMetadata = field(default_factory=OrderMetadata)


@dataclass(frozen=True, slots=True)
class OrderValidationResult:
    """The outcome of validating an :class:`OrderRequest`."""

    valid: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OrderRoute:
    """Prepared routing information (no exchange connection is made)."""

    destination: str
    metadata: OrderMetadata = field(default_factory=OrderMetadata)


@dataclass(frozen=True, slots=True)
class OrderResult:
    """The immutable outcome of processing an order through the framework."""

    state: OrderState
    request: OrderRequest | None = None
    validation: OrderValidationResult | None = None
    route: OrderRoute | None = None
    errors: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        """Return ``True`` when the order is ready for execution."""
        return self.state is OrderState.READY_FOR_EXECUTION

    @property
    def order_id(self) -> str | None:
        """Return the order id, if a request was created."""
        return self.request.identifier.id if self.request is not None else None
