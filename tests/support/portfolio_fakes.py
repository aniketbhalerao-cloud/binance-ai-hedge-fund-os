"""Helpers for Portfolio Framework tests.

Standalone support module (existing support files unchanged). Builds a completed
execution context deterministically; no network or exchange dependency.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from execution.models import ExecutionIdentifier, ExecutionRequest, ExecutionResult, ExecutionStatus
from execution.state import ExecutionState
from models import OrderSide, OrderType, TimeInForce
from order_management.models import OrderIdentifier, OrderRequest
from portfolio.context import PortfolioContext

__all__ = ["make_portfolio_context"]


def make_portfolio_context(
    *,
    portfolio_id: str = "pf-1",
    symbol: str = "BTCUSDT",
    side: OrderSide = OrderSide.BUY,
    quantity: Decimal = Decimal("1"),
    price: Decimal = Decimal("100"),
    prices: Mapping[str, Decimal] | None = None,
    initial_cash: Decimal = Decimal("1000"),
) -> PortfolioContext:
    """Build a deterministic PortfolioContext wrapping a completed execution."""
    order = OrderRequest(
        identifier=OrderIdentifier(),
        symbol=symbol,
        side=side,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        price=price,
        time_in_force=TimeInForce.GTC,
    )
    exec_request = ExecutionRequest(
        identifier=ExecutionIdentifier(),
        order_request=order,
        exchange="binance",
        symbol=symbol,
        state=ExecutionState.READY,
    )
    exec_result = ExecutionResult(
        status=ExecutionStatus.READY,
        state=ExecutionState.READY,
        request=exec_request,
    )
    return PortfolioContext(
        portfolio_id=portfolio_id,
        execution_result=exec_result,
        prices=prices if prices is not None else {symbol: price},
        initial_cash=initial_cash,
    )
