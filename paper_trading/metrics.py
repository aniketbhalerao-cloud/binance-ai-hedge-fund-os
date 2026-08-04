"""Paper trading metrics.

:class:`DefaultPaperTradingMetrics` derives live session metrics. It is a thin,
reuse-first component: the heavy analytics (returns, risk, trading statistics)
are already produced by the Performance Analytics Framework during each update,
so this calculator reads them from the in-pipeline
:class:`~performance.models.PerformanceResult` and layers only the
paper-trading-specific aggregate (average trade). Metrics are derived, never
stored independently.

Stateless and pure: all arithmetic is :class:`~decimal.Decimal`.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from paper_trading.exceptions import MetricsError
from paper_trading.models import PaperTradingMetrics
from performance.models import PerformanceResult
from trades.models import Trade

__all__ = ["DefaultPaperTradingMetrics"]

_ZERO = Decimal("0")


class DefaultPaperTradingMetrics:
    """Stateless live metrics derived from performance + trades."""

    def calculate(
        self,
        performance_result: PerformanceResult | None,
        trades: Sequence[Trade],
        equity_curve: Sequence[Decimal],
        total_commission: Decimal,
    ) -> PaperTradingMetrics:
        """Return :class:`PaperTradingMetrics` for the session.

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
    ) -> PaperTradingMetrics:
        average_trade = _mean([t.realized_pnl for t in trades])
        realized = sum((t.realized_pnl for t in trades), _ZERO)
        if performance_result is None or performance_result.metrics is None:
            return PaperTradingMetrics(
                realized_pnl=realized, average_trade=average_trade
            )

        metrics = performance_result.metrics
        returns = metrics.returns
        risk = metrics.risk
        stats = metrics.statistics
        return PaperTradingMetrics(
            total_return=returns.total_return,
            realized_pnl=returns.realized_return,
            unrealized_pnl=returns.unrealized_return,
            sharpe_ratio=risk.sharpe_ratio,
            max_drawdown=risk.max_drawdown,
            win_rate=stats.win_rate,
            profit_factor=stats.profit_factor,
            average_trade=average_trade,
            average_holding_time=stats.average_holding_time,
            expectancy=stats.expectancy,
        )


def _mean(xs: Sequence[Decimal]) -> Decimal:
    if not xs:
        return _ZERO
    return sum(xs, _ZERO) / Decimal(len(xs))
