"""Order Framework exceptions.

Definitions only — no handling logic. These isolate order-processing failures so
the framework always produces an :class:`~order_management.models.OrderResult`.
"""

from __future__ import annotations

__all__ = [
    "OrderError",
    "OrderValidationError",
    "OrderRoutingError",
    "OrderFactoryError",
    "OrderEngineError",
    "InvalidOrderRequest",
]


class OrderError(Exception):
    """Base class for all Order Framework errors."""


class OrderValidationError(OrderError):
    """Raised when validation cannot be performed."""


class OrderRoutingError(OrderError):
    """Raised when routing information cannot be prepared."""


class OrderFactoryError(OrderError):
    """Raised when an order request cannot be created from a context."""


class OrderEngineError(OrderError):
    """Raised when the engine fails to coordinate order processing."""


class InvalidOrderRequest(OrderError):
    """Raised when an order request is structurally invalid."""
