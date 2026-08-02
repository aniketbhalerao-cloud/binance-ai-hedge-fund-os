"""Order Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions so
future factories, validators, routers, and execution engines plug in without
modification (Open/Closed).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from order_management.context import OrderContext
from order_management.models import (
    OrderRequest,
    OrderResult,
    OrderRoute,
    OrderValidationResult,
)

__all__ = [
    "OrderFactory",
    "OrderValidator",
    "OrderRouter",
    "OrderManager",
    "OrderEngine",
]


@runtime_checkable
class OrderFactory(Protocol):
    """Creates a standardized order request from an order context."""

    def create(self, context: OrderContext) -> OrderRequest: ...


@runtime_checkable
class OrderValidator(Protocol):
    """Validates an order request's consistency."""

    def validate(self, request: OrderRequest) -> OrderValidationResult: ...


@runtime_checkable
class OrderRouter(Protocol):
    """Prepares routing information for a validated order request."""

    def route(self, request: OrderRequest) -> OrderRoute: ...


@runtime_checkable
class OrderManager(Protocol):
    """Coordinates factory → validator → router and publishes order events."""

    async def process(self, context: OrderContext) -> OrderResult: ...


@runtime_checkable
class OrderEngine(Protocol):
    """Public entry point coordinating the order-management process."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def process(self, context: OrderContext) -> OrderResult: ...
