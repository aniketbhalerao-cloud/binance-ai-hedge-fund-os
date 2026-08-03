"""Statistics calculator.

:class:`DefaultStatisticsCalculator` derives trading statistics from the set of
completed trades carried by a :class:`~performance.context.PerformanceContext`:
counts, win/loss rates, average and extreme P&L, profit factor, expectancy,
average size/duration, and best/worst period. It is stateless and pure — no
returns or risk logic here — and all monetary arithmetic is
:class:`~decimal.Decimal`.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from performance.context import PerformanceContext
from performance.exceptions import StatisticsCalculationError
from performance.models import StatisticsMetrics
from trades.models import Trade
from trades.state import TradeState

__all__ = ["DefaultStatisticsCalculator"]

_ZERO = Decimal("0")
_TERMINAL = (TradeState.CLOSED, TradeState.CANCELLED)


class DefaultStatisticsCalculator:
    """Stateless trading-statistics analytics."""

    def calculate(self, context: PerformanceContext) -> StatisticsMetrics:
        """Return :class:`StatisticsMetrics` for ``context``.

        Raises:
            StatisticsCalculationError: If an unexpected failure occurs.
        """
        try:
            return self._calculate(context)
        except StatisticsCalculationError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise StatisticsCalculationError(str(exc)) from exc

    def _calculate(self, context: PerformanceContext) -> StatisticsMetrics:
        trades = context.completed_trades()
        total = len(trades)
        if total == 0:
            return StatisticsMetrics()

        pnls = [t.realized_pnl for t in trades]
        wins = [p for p in pnls if p > _ZERO]
        losses = [p for p in pnls if p < _ZERO]
        closed = sum(1 for t in trades if t.state is TradeState.CLOSED)
        open_trades = sum(1 for t in trades if t.state not in _TERMINAL)

        gross_win = sum(wins, _ZERO)
        gross_loss = sum(losses, _ZERO)
        profit_factor = gross_win / abs(gross_loss) if gross_loss < _ZERO else _ZERO

        holding = [_holding_seconds(t) for t in trades]
        best_day, worst_day = _best_worst(context.returns, wins, losses)

        return StatisticsMetrics(
            total_trades=total,
            winning_trades=len(wins),
            losing_trades=len(losses),
            open_trades=open_trades,
            closed_trades=closed,
            win_rate=Decimal(len(wins)) / Decimal(total),
            loss_rate=Decimal(len(losses)) / Decimal(total),
            average_win=_mean(wins),
            average_loss=_mean(losses),
            largest_winner=max(pnls) if pnls else _ZERO,
            largest_loser=min(pnls) if pnls else _ZERO,
            average_holding_time=_mean(holding),
            profit_factor=profit_factor,
            expectancy=_mean(pnls),
            average_position_size=_mean([t.entry_quantity for t in trades]),
            average_trade_duration=_mean(holding),
            best_day=best_day,
            worst_day=worst_day,
        )


def _mean(xs: Sequence[Decimal]) -> Decimal:
    if not xs:
        return _ZERO
    return sum(xs, _ZERO) / Decimal(len(xs))


def _holding_seconds(trade: Trade) -> Decimal:
    end = trade.closed_at or trade.updated_at
    if trade.opened_at is None or end is None:
        return _ZERO
    return Decimal(str((end - trade.opened_at).total_seconds()))


def _best_worst(
    returns: Sequence[Decimal], wins: Sequence[Decimal], losses: Sequence[Decimal]
) -> tuple[Decimal, Decimal]:
    """Best/worst period from the returns series, falling back to trade P&L."""
    if returns:
        return max(returns), min(returns)
    best = max(wins) if wins else _ZERO
    worst = min(losses) if losses else _ZERO
    return best, worst
