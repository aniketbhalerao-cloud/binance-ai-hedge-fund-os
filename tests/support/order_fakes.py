"""Fakes and helpers for Order Management Framework tests.

A new, standalone support module (existing support files are unchanged). Fakes
only — no exchange adapters or execution logic.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from order_management.context import OrderContext
from order_management.models import (
    OrderIdentifier,
    OrderRequest,
    OrderRoute,
    OrderValidationResult,
)
from models import OrderSide, OrderType
from risk.models import RiskDecision, RiskDecisionType
from strategies.signals import SignalDirection, TradingSignal

__all__ = [
    "FakeOrderFactory",
    "FakeOrderValidator",
    "FakeOrderRouter",
    "make_order_context",
]

_FIXED = datetime(2026, 1, 1, tzinfo=UTC)


class FakeOrderFactory:
    """Returns a fixed order request (optionally raising)."""

    def __init__(self, request: OrderRequest | None = None, *, error: Exception | None = None) -> None:
        self._request = request
        self._error = error

    def create(self, context: OrderContext) -> OrderRequest:
        if self._error is not None:
            raise self._error
        if self._request is not None:
            return self._request
        side = (
            OrderSide.SELL
            if context.signal.direction is SignalDirection.SELL
            else OrderSide.BUY
        )
        return OrderRequest(
            identifier=OrderIdentifier(),
            symbol=context.symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=Decimal("1"),
        )


class FakeOrderValidator:
    """Returns a configurable validation result."""

    def __init__(self, *, valid: bool = True, errors: tuple[str, ...] = ()) -> None:
        self._result = OrderValidationResult(valid=valid, errors=errors)

    def validate(self, request: OrderRequest) -> OrderValidationResult:
        return self._result


class FakeOrderRouter:
    """Returns a fixed route (optionally raising)."""

    def __init__(self, destination: str = "fake", *, error: Exception | None = None) -> None:
        self._destination = destination
        self._error = error

    def route(self, request: OrderRequest) -> OrderRoute:
        if self._error is not None:
            raise self._error
        return OrderRoute(destination=self._destination)


def make_order_context(
    *,
    exchange: str = "sim",
    symbol: str = "BTCUSDT",
    direction: SignalDirection = SignalDirection.BUY,
    approved: bool = True,
) -> OrderContext:
    """Build a deterministic OrderContext wrapping an approved decision."""
    signal = TradingSignal(
        id=uuid.uuid4().hex,
        strategy_name="test",
        symbol=symbol,
        direction=direction,
        confidence=0.5,
        timestamp=_FIXED,
    )
    decision = RiskDecision(
        id=uuid.uuid4().hex,
        decision_type=(
            RiskDecisionType.APPROVED if approved else RiskDecisionType.REJECTED
        ),
        timestamp=_FIXED,
    )
    return OrderContext(
        risk_decision=decision,
        signal=signal,
        exchange=exchange,
        symbol=symbol,
        timestamp=_FIXED,
    )
