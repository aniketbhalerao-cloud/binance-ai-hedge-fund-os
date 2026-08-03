"""Returns calculator.

:class:`DefaultReturnsCalculator` derives return metrics from a
:class:`~performance.context.PerformanceContext`. Point metrics (ROI, realized /
unrealized / total return) come from the portfolio valuation snapshot; periodic
and compounded metrics come from the standardized returns series and equity
curve. It is stateless and pure — no risk or statistics logic here — and all
arithmetic is :class:`~decimal.Decimal` (CAGR uses ``Decimal.ln``/``exp`` to
stay float-free).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from performance.context import PerformanceContext
from performance.exceptions import ReturnsCalculationError
from performance.models import ReturnsMetrics

__all__ = ["DefaultReturnsCalculator"]

_ZERO = Decimal("0")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")


class DefaultReturnsCalculator:
    """Stateless returns analytics."""

    def calculate(self, context: PerformanceContext) -> ReturnsMetrics:
        """Return :class:`ReturnsMetrics` for ``context``.

        Raises:
            ReturnsCalculationError: If an unexpected failure occurs.
        """
        try:
            return self._calculate(context)
        except ReturnsCalculationError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise ReturnsCalculationError(str(exc)) from exc

    def _calculate(self, context: PerformanceContext) -> ReturnsMetrics:
        cost_basis, unrealized, realized, _total = _portfolio_value(context)
        pf_daily, pf_total, pf_roi, _pf_cum = _portfolio_performance(context)

        roi = (
            (unrealized + realized) / cost_basis if cost_basis > _ZERO else pf_roi
        )
        realized_return = realized / cost_basis if cost_basis > _ZERO else _ZERO
        unrealized_return = unrealized / cost_basis if cost_basis > _ZERO else _ZERO
        total_return = pf_total if pf_total != _ZERO else roi

        returns = context.returns
        daily = returns[-1] if returns else pf_daily
        return ReturnsMetrics(
            daily_return=daily,
            weekly_return=_trailing(returns, 7),
            monthly_return=_trailing(returns, 30),
            quarterly_return=_trailing(returns, 91),
            yearly_return=_trailing(returns, 365),
            total_return=total_return,
            compound_return=_compound(returns),
            cagr=_cagr(context.equity_curve, context.periods_per_year),
            absolute_return=unrealized + realized,
            percentage_return=roi * _HUNDRED,
            realized_return=realized_return,
            unrealized_return=unrealized_return,
            roi=roi,
        )


def _portfolio_value(
    context: PerformanceContext,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Return (cost_basis, unrealized_pnl, realized_pnl, total_value)."""
    pr = context.portfolio_result
    if pr is None or pr.snapshot is None:
        return _ZERO, _ZERO, _ZERO, _ZERO
    v = pr.snapshot.value
    return v.cost_basis, v.unrealized_pnl, v.realized_pnl, v.total_value


def _portfolio_performance(
    context: PerformanceContext,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Return (daily_return, total_return, roi, cumulative_return)."""
    pr = context.portfolio_result
    if pr is None or pr.snapshot is None:
        return _ZERO, _ZERO, _ZERO, _ZERO
    p = pr.snapshot.performance
    return p.daily_return, p.total_return, p.roi, p.cumulative_return


def _compound(returns: Sequence[Decimal]) -> Decimal:
    """Compound a periodic returns series into a total return."""
    acc = _ONE
    for r in returns:
        acc *= _ONE + r
    return acc - _ONE if returns else _ZERO


def _trailing(returns: Sequence[Decimal], window: int) -> Decimal:
    """Compound the trailing ``window`` periodic returns (bounded by length)."""
    if not returns:
        return _ZERO
    return _compound(returns[-window:])


def _cagr(equity_curve: Sequence[Decimal], periods_per_year: int) -> Decimal:
    """Compound annual growth rate from an equity curve (float-free)."""
    n = len(equity_curve)
    if n < 2 or periods_per_year <= 0:
        return _ZERO
    first, last = equity_curve[0], equity_curve[-1]
    if first <= _ZERO or last <= _ZERO:
        return _ZERO
    years = Decimal(n - 1) / Decimal(periods_per_year)
    if years <= _ZERO:
        return _ZERO
    ratio = last / first
    # ratio ** (1/years) == exp(ln(ratio) / years)
    return (ratio.ln() / years).exp() - _ONE
