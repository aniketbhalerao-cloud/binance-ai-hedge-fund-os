"""Paper trading broker.

:class:`DefaultPaperBroker` simulates a live fill for an execution that the
Execution Framework has already coordinated. It is deliberately narrow and
mirrors the backtesting Simulator's boundary exactly: it does **not** validate,
size, route, or coordinate the order (that is Execution's job), and it never
submits an order to any exchange or exchange adapter (that is the Exchange
Adapter's job). Given a *ready* :class:`~execution.models.ExecutionResult` and the
current live candle, it computes only the fill economics — fill price with
slippage, commission, and recorded latency — deterministically from
:class:`~paper_trading.models.SessionParameters`.

Stateless and pure: no randomness, no real time, no network. No real order is
ever placed.
"""

from __future__ import annotations

from decimal import Decimal

from execution.models import ExecutionResult
from market_data.models import OHLCV
from models import OrderSide
from paper_trading.exceptions import BrokerError
from paper_trading.models import PaperFill, SessionParameters

__all__ = ["DefaultPaperBroker"]

_ZERO = Decimal("0")
_BPS = Decimal("10000")


class DefaultPaperBroker:
    """Stateless simulated live fills (strictly post-Execution)."""

    def fill(
        self,
        execution_result: ExecutionResult,
        candle: OHLCV,
        parameters: SessionParameters,
    ) -> PaperFill:
        """Return the :class:`PaperFill` for a ready execution + live ``candle``.

        Raises:
            BrokerError: If the execution is not ready to be filled.
        """
        if not execution_result.ready or execution_result.request is None:
            raise BrokerError("execution is not ready to fill")

        order = execution_result.request.order_request
        quantity = order.quantity
        if quantity <= _ZERO:
            raise BrokerError("cannot fill a non-positive quantity")

        # Slippage moves the fill against the taker: up for a buy, down for a sell.
        slippage = candle.close * parameters.slippage_bps / _BPS
        if order.side is OrderSide.BUY:
            fill_price = candle.close + slippage
        else:
            fill_price = candle.close - slippage

        commission = fill_price * quantity * parameters.commission_bps / _BPS
        return PaperFill(
            symbol=order.symbol,
            side=order.side,
            quantity=quantity,
            price=fill_price,
            commission=commission,
            slippage=slippage,
            latency_steps=parameters.latency_steps,
            timestamp=candle.close_time,
        )
