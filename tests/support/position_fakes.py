"""Helpers for Position Framework tests.

Standalone support module (existing support files unchanged). Builds a completed
portfolio-update context deterministically; no network or exchange dependency.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal

from models import OrderSide
from portfolio.models import (
    LedgerEntry,
    Portfolio,
    PortfolioResult,
    PortfolioResultStatus,
)
from portfolio.state import PortfolioState
from positions.context import PositionContext

__all__ = ["make_position_context", "FIXED_TIME"]

FIXED_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def make_position_context(
    *,
    symbol: str = "BTCUSDT",
    side: OrderSide = OrderSide.BUY,
    quantity: Decimal = Decimal("1"),
    price: Decimal = Decimal("100"),
    prices: Mapping[str, Decimal] | None = None,
) -> PositionContext:
    """Build a PositionContext wrapping a portfolio result with one ledger entry."""
    entry = LedgerEntry(
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        timestamp=FIXED_TIME,
    )
    portfolio = Portfolio(
        id="pf-1",
        state=PortfolioState.ACTIVE,
        ledger=(entry,),
    )
    result = PortfolioResult(status=PortfolioResultStatus.SUCCESS, portfolio=portfolio)
    return PositionContext(
        portfolio_result=result,
        prices=prices if prices is not None else {symbol: price},
    )
