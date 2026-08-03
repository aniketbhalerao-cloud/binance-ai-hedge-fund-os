"""Backtest metrics.

:class:`DefaultBacktestMetrics` derives the backtest performance metrics. It is a
thin, reuse-first component: the heavy analytics (returns, risk, trading
statistics) are already produced by the Performance Analytics Framework during
the run, so this calculator reads them from the in-pipeline
:class:`~performance.models.PerformanceResult` and layers only the
backtest-specific aggregate (average trade). Metrics are derived, never stored
independently.

Stateless and pure: all arithmetic is :class:`~decimal.Decimal`.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from backtesting.exceptions import MetricsError
from backtesting.models import BacktestMetrics
from performance.models import PerformanceResult
from trades.models import Trade

__all__ = ["DefaultBacktestMetrics"]

_ZERO = Decimal("0")


class DefaultBacktestMetrics:
    """Stateless backtest metrics derived from performance + trades."""

    def calculate(
        self,
        performance_result: PerformanceResult | None,
        trades: Sequence[Trade],
        equity_curve: Sequence[Decimal],
        total_commission: Decimal,
    ) -> BacktestMetrics:
        """Return :class:`BacktestMetrics` for the run.

        Raises:
            MetricsError: If an unexpected failure occurs.
        """
        try:
            return self._calculate(performance_result, trades)
        except MetricsError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise MetricsError(str(exc)) from exc

    def _calculate(
        self, performance_result: PerformanceResult | None, trades: Sequence[Trade]
    ) -> BacktestMetrics:
        average_trade = _mean([t.realized_pnl for t in trades])
        if performance_result is None or performance_result.metrics is None:
            return BacktestMetrics(average_trade=average_trade)

        metrics = performance_result.metrics
        returns = metrics.returns
        risk = metrics.risk
        stats = metrics.statistics
        return BacktestMetrics(
            cagr=returns.cagr,
            annual_return=returns.cagr,
            total_return=returns.total_return,
            sharpe_ratio=risk.sharpe_ratio,
            sortino_ratio=risk.sortino_ratio,
            max_drawdown=risk.max_drawdown,
            win_rate=stats.win_rate,
            profit_factor=stats.profit_factor,
            recovery_factor=risk.recovery_factor,
            average_trade=average_trade,
            average_holding_time=stats.average_holding_time,
            expectancy=stats.expectancy,
        )


def _mean(xs: Sequence[Decimal]) -> Decimal:
    if not xs:
        return _ZERO
    return sum(xs, _ZERO) / Decimal(len(xs))
