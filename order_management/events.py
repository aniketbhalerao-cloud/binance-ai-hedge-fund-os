"""Order Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never strategy, risk, trade, portfolio, or
execution events.
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "OrderEvent",
    "OrderCreated",
    "OrderValidated",
    "OrderValidationFailed",
    "OrderRouted",
    "OrderReadyForExecution",
    "OrderRejected",
    "OrderEngineStarted",
    "OrderEngineStopped",
    "OrderErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderEvent(Event):
    """Base class for all order events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderCreated(OrderEvent):
    """An order request was created."""

    order_id: str
    symbol: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderValidated(OrderEvent):
    """An order request passed validation."""

    order_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderValidationFailed(OrderEvent):
    """An order request failed validation."""

    order_id: str
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderRouted(OrderEvent):
    """Routing information was prepared for an order."""

    order_id: str
    destination: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderReadyForExecution(OrderEvent):
    """An order is prepared and ready for the future Execution Layer."""

    order_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderRejected(OrderEvent):
    """An order was rejected during processing."""

    order_id: str | None
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderEngineStarted(OrderEvent):
    """The order engine started."""


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderEngineStopped(OrderEvent):
    """The order engine stopped."""


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderErrorOccurred(OrderEvent):
    """An error occurred during order processing."""

    order_id: str | None
    message: str
