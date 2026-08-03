"""Backtest simulator.

:class:`DefaultSimulator` simulates a historical fill for an execution that the
Execution Framework has already coordinated. It is deliberately narrow: it does
**not** validate, route, size, or coordinate the order (that is Execution's job),
and it never contacts an exchange or adapter (that is the Exchange Adapter's job).
Given a *ready* :class:`~execution.models.ExecutionResult` and the historical
candle, it computes only the fill economics — fill price with slippage,
commission, and recorded latency — deterministically from
:class:`~backtesting.models.SimulationParameters`.

Stateless and pure: no randomness, no time, no network.
"""

from __future__ import annotations

from decimal import Decimal

from backtesting.exceptions import SimulationError
from backtesting.models import SimulatedFill, SimulationParameters
from execution.models import ExecutionResult
from market_data.models import OHLCV
from models import OrderSide

__all__ = ["DefaultSimulator"]

_ZERO = Decimal("0")
_BPS = Decimal("10000")


class DefaultSimulator:
    """Stateless historical fill simulation (post-Execution)."""

    def simulate(
        self,
        execution_result: ExecutionResult,
        candle: OHLCV,
        parameters: SimulationParameters,
    ) -> SimulatedFill:
        """Return the :class:`SimulatedFill` for a ready execution + ``candle``.

        Raises:
            SimulationError: If the execution is not ready to be filled.
        """
        if not execution_result.ready or execution_result.request is None:
            raise SimulationError("execution is not ready to fill")

        order = execution_result.request.order_request
        quantity = order.quantity
        if quantity <= _ZERO:
            raise SimulationError("cannot fill a non-positive quantity")

        # Slippage moves the fill against the taker: up for a buy, down for a sell.
        slippage = candle.close * parameters.slippage_bps / _BPS
        if order.side is OrderSide.BUY:
            fill_price = candle.close + slippage
        else:
            fill_price = candle.close - slippage

        commission = fill_price * quantity * parameters.commission_bps / _BPS
        return SimulatedFill(
            symbol=order.symbol,
            side=order.side,
            quantity=quantity,
            price=fill_price,
            commission=commission,
            slippage=slippage,
            latency_steps=parameters.latency_steps,
            timestamp=candle.close_time,
        )
