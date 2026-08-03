"""Benchmarking service.

:class:`DefaultBenchmarkingService` compares portfolio performance against a
benchmark supplied to the context as a standardized returns series. It computes
relative/excess return, alpha, beta, tracking error, information ratio, and
benchmark drawdown. It is stateless and pure — no returns, risk, or statistics
logic of its own beyond the comparison — and all arithmetic is
:class:`~decimal.Decimal`.

The benchmark is deliberately abstract: BTC, ETH, S&P 500, NASDAQ, a paper
index, or a custom index all plug in simply by supplying a different
``benchmark_returns`` series (and optional ``benchmark_prices``) on the context —
no code change here (Open/Closed).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from performance.context import PerformanceContext
from performance.exceptions import BenchmarkCalculationError
from performance.models import BenchmarkMetrics

__all__ = ["DefaultBenchmarkingService"]

_ZERO = Decimal("0")
_ONE = Decimal("1")


class DefaultBenchmarkingService:
    """Stateless benchmark comparison."""

    def compare(self, context: PerformanceContext) -> BenchmarkMetrics:
        """Return :class:`BenchmarkMetrics` for ``context``.

        Raises:
            BenchmarkCalculationError: If an unexpected failure occurs.
        """
        try:
            return self._compare(context)
        except BenchmarkCalculationError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise BenchmarkCalculationError(str(exc)) from exc

    def _compare(self, context: PerformanceContext) -> BenchmarkMetrics:
        returns = context.returns
        benchmark = context.benchmark_returns
        rf = context.risk_free_rate

        benchmark_return = _compound(benchmark)
        portfolio_return = (
            _compound(returns) if returns else _portfolio_total_return(context)
        )
        relative = portfolio_return - benchmark_return

        beta = _beta(returns, benchmark)
        alpha = _alpha(returns, benchmark, rf, beta)
        tracking_error = _tracking_error(returns, benchmark)
        info_ratio = (
            _mean(_diff(returns, benchmark)) / tracking_error
            if tracking_error > _ZERO
            else _ZERO
        )

        return BenchmarkMetrics(
            benchmark_return=benchmark_return,
            relative_return=relative,
            alpha=alpha,
            beta=beta,
            tracking_error=tracking_error,
            information_ratio=info_ratio,
            benchmark_drawdown=_max_drawdown_from_returns(benchmark),
            excess_return=relative,
        )


def _portfolio_total_return(context: PerformanceContext) -> Decimal:
    pr = context.portfolio_result
    if pr is None or pr.snapshot is None:
        return _ZERO
    return pr.snapshot.performance.total_return


def _paired(a: Sequence[Decimal], b: Sequence[Decimal]) -> bool:
    return len(a) >= 2 and len(a) == len(b)


def _mean(xs: Sequence[Decimal]) -> Decimal:
    if not xs:
        return _ZERO
    return sum(xs, _ZERO) / Decimal(len(xs))


def _compound(returns: Sequence[Decimal]) -> Decimal:
    acc = _ONE
    for r in returns:
        acc *= _ONE + r
    return acc - _ONE if returns else _ZERO


def _diff(a: Sequence[Decimal], b: Sequence[Decimal]) -> list[Decimal]:
    if not _paired(a, b):
        return []
    return [x - y for x, y in zip(a, b, strict=True)]


def _tracking_error(a: Sequence[Decimal], b: Sequence[Decimal]) -> Decimal:
    diffs = _diff(a, b)
    n = len(diffs)
    if n < 2:
        return _ZERO
    m = _mean(diffs)
    var = sum(((d - m) * (d - m) for d in diffs), _ZERO) / Decimal(n - 1)
    return var.sqrt() if var > _ZERO else _ZERO


def _beta(port: Sequence[Decimal], bench: Sequence[Decimal]) -> Decimal:
    if not _paired(port, bench):
        return _ZERO
    n = len(port)
    mp, mb = _mean(port), _mean(bench)
    cov = sum(
        ((p - mp) * (b - mb) for p, b in zip(port, bench, strict=True)), _ZERO
    ) / Decimal(n - 1)
    var = sum(((b - mb) * (b - mb) for b in bench), _ZERO) / Decimal(n - 1)
    return cov / var if var > _ZERO else _ZERO


def _alpha(
    port: Sequence[Decimal], bench: Sequence[Decimal], rf: Decimal, beta: Decimal
) -> Decimal:
    if not _paired(port, bench):
        return _ZERO
    # CAPM (per-period): alpha = mean(port - rf) - beta * mean(bench - rf)
    return _mean([p - rf for p in port]) - beta * _mean([b - rf for b in bench])


def _max_drawdown_from_returns(returns: Sequence[Decimal]) -> Decimal:
    if not returns:
        return _ZERO
    peak = _ONE
    equity = _ONE
    max_dd = _ZERO
    for r in returns:
        equity *= _ONE + r
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak > _ZERO else _ZERO
        if dd > max_dd:
            max_dd = dd
    return max_dd
