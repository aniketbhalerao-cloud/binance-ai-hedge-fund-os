"""Risk calculator.

:class:`DefaultRiskCalculator` derives risk analytics from the standardized
returns series and equity curve in a
:class:`~performance.context.PerformanceContext`: volatility, Sharpe / Sortino /
Calmar ratios, drawdowns, downside deviation, capture, risk/reward, and recovery
factor. It is stateless and pure — no returns or statistics logic here — and all
arithmetic is :class:`~decimal.Decimal` (``sqrt`` via ``Decimal.sqrt``). Every
metric degrades to zero when the series is too short to be meaningful.

The small numeric helpers are kept local (not shared with sibling components) so
each calculator stays fully independent, per the framework's isolation rule.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from performance.context import PerformanceContext
from performance.exceptions import RiskCalculationError
from performance.models import RiskMetrics

__all__ = ["DefaultRiskCalculator"]

_ZERO = Decimal("0")
_ONE = Decimal("1")


class DefaultRiskCalculator:
    """Stateless risk analytics."""

    def calculate(self, context: PerformanceContext) -> RiskMetrics:
        """Return :class:`RiskMetrics` for ``context``.

        Raises:
            RiskCalculationError: If an unexpected failure occurs.
        """
        try:
            return self._calculate(context)
        except RiskCalculationError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise RiskCalculationError(str(exc)) from exc

    def _calculate(self, context: PerformanceContext) -> RiskMetrics:
        returns = context.returns
        curve = context.equity_curve
        rf = context.risk_free_rate

        volatility = _stdev(returns)
        excess = [r - rf for r in returns]
        mean_excess = _mean(excess)
        downside = _downside_deviation(returns, rf)

        sharpe = mean_excess / volatility if volatility > _ZERO else _ZERO
        sortino = mean_excess / downside if downside > _ZERO else _ZERO

        dds = _drawdowns(curve)
        max_dd = max(dds) if dds else _ZERO
        avg_dd = _mean(dds)

        cagr = _annualized(curve, context.periods_per_year)
        cumulative = _cumulative(curve)
        calmar = cagr / max_dd if max_dd > _ZERO else _ZERO
        recovery = cumulative / max_dd if max_dd > _ZERO else _ZERO

        return RiskMetrics(
            volatility=volatility,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown=max_dd,
            average_drawdown=avg_dd,
            downside_deviation=downside,
            upside_capture=_upside_capture(returns, context.benchmark_returns),
            risk_reward_ratio=_risk_reward(returns),
            recovery_factor=recovery,
        )


def _mean(xs: Sequence[Decimal]) -> Decimal:
    if not xs:
        return _ZERO
    return sum(xs, _ZERO) / Decimal(len(xs))


def _stdev(xs: Sequence[Decimal]) -> Decimal:
    n = len(xs)
    if n < 2:
        return _ZERO
    m = _mean(xs)
    var = sum(((x - m) * (x - m) for x in xs), _ZERO) / Decimal(n - 1)
    return var.sqrt() if var > _ZERO else _ZERO


def _downside_deviation(xs: Sequence[Decimal], mar: Decimal) -> Decimal:
    if not xs:
        return _ZERO
    sq = _ZERO
    for x in xs:
        d = x - mar
        if d < _ZERO:
            sq += d * d
    return (sq / Decimal(len(xs))).sqrt() if sq > _ZERO else _ZERO


def _drawdowns(curve: Sequence[Decimal]) -> list[Decimal]:
    peak: Decimal | None = None
    dds: list[Decimal] = []
    for v in curve:
        if peak is None or v > peak:
            peak = v
        dd = (peak - v) / peak if peak > _ZERO else _ZERO
        dds.append(dd)
    return dds


def _cumulative(curve: Sequence[Decimal]) -> Decimal:
    if len(curve) < 2 or curve[0] <= _ZERO:
        return _ZERO
    return curve[-1] / curve[0] - _ONE


def _annualized(curve: Sequence[Decimal], periods_per_year: int) -> Decimal:
    n = len(curve)
    if n < 2 or periods_per_year <= 0 or curve[0] <= _ZERO or curve[-1] <= _ZERO:
        return _ZERO
    years = Decimal(n - 1) / Decimal(periods_per_year)
    if years <= _ZERO:
        return _ZERO
    ratio = curve[-1] / curve[0]
    return (ratio.ln() / years).exp() - _ONE


def _upside_capture(
    returns: Sequence[Decimal], benchmark: Sequence[Decimal]
) -> Decimal:
    if not returns or len(returns) != len(benchmark):
        return _ZERO
    port_up = [p for p, b in zip(returns, benchmark, strict=True) if b > _ZERO]
    bench_up = [b for b in benchmark if b > _ZERO]
    bench_mean = _mean(bench_up)
    if bench_mean == _ZERO:
        return _ZERO
    return _mean(port_up) / bench_mean


def _risk_reward(returns: Sequence[Decimal]) -> Decimal:
    wins = [r for r in returns if r > _ZERO]
    losses = [r for r in returns if r < _ZERO]
    avg_loss = _mean(losses)
    if avg_loss == _ZERO:
        return _ZERO
    return _mean(wins) / abs(avg_loss)
