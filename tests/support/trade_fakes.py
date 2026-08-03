"""Helpers for Trade Framework tests.

Standalone support module (existing support files unchanged). Builds a completed
position-update context deterministically; no network, exchange, or timing
dependency. The trade framework derives the incremental fill from the position's
aggregate ``total_bought`` / ``total_sold``, so these helpers drive those.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal

from positions.models import (
    Position,
    PositionResult,
    PositionResultStatus,
    PositionSide,
)
from positions.state import PositionState
from trades.context import TradeContext

__all__ = ["FIXED_TIME", "make_position", "make_trade_context"]

FIXED_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def make_position(
    *,
    position_id: str = "pos-1",
    symbol: str = "BTCUSDT",
    side: PositionSide = PositionSide.LONG,
    state: PositionState = PositionState.OPEN,
    quantity: Decimal = Decimal("1"),
    total_bought: Decimal = Decimal("1"),
    total_sold: Decimal = Decimal("0"),
    average_entry: Decimal = Decimal("100"),
    average_exit: Decimal = Decimal("0"),
    realized_pnl: Decimal = Decimal("0"),
    opened_at: datetime = FIXED_TIME,
    closed_at: datetime | None = None,
    updated_at: datetime = FIXED_TIME,
) -> Position:
    """Build a durable :class:`Position` with the given aggregate figures."""
    return Position(
        id=position_id,
        symbol=symbol,
        side=side,
        state=state,
        quantity=quantity,
        average_entry=average_entry,
        average_exit=average_exit,
        realized_pnl=realized_pnl,
        total_bought=total_bought,
        total_sold=total_sold,
        opened_at=opened_at,
        closed_at=closed_at,
        updated_at=updated_at,
    )


def make_trade_context(
    *,
    position: Position | None = None,
    succeeded: bool = True,
    prices: Mapping[str, Decimal] | None = None,
    **position_kwargs: object,
) -> TradeContext:
    """Wrap a :class:`Position` in a successful :class:`PositionResult` context.

    Extra keyword arguments are forwarded to :func:`make_position` when an
    explicit ``position`` is not supplied.
    """
    if position is None:
        position = make_position(**position_kwargs)  # type: ignore[arg-type]
    status = (
        PositionResultStatus.SUCCESS if succeeded else PositionResultStatus.FAILED
    )
    result = PositionResult(status=status, position=position)
    default_prices = {position.symbol: position.average_entry}
    return TradeContext(
        position_result=result,
        prices=prices if prices is not None else default_prices,
    )
