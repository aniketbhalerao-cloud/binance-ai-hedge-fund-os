"""Performance analysis context.

An immutable input carrying the standardized upstream results (execution,
portfolio, position, trade) plus the standardized analytical series the
calculators need (equity curve, periodic returns, benchmark returns) and market
prices. It represents **one complete analytical snapshot**.

Only the four result snapshots and market/benchmark prices are strictly
required-by-spec; the sequences (``equity_curve`` / ``returns`` /
``benchmark_returns`` / ``trades``) are optional standardized analytical inputs —
without them the series-based metrics (volatility, Sharpe, drawdown, aggregate
trade statistics) degrade gracefully to zero rather than fabricating data. The
context never accesses infrastructure or external services.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from execution.models import ExecutionResult
from portfolio.models import PortfolioResult
from positions.models import PositionResult
from trades.models import Trade, TradeResult

__all__ = ["PerformanceContext"]


@dataclass(frozen=True, slots=True)
class PerformanceContext:
    """Immutable input for one performance analysis.

    Attributes:
        execution_result: Latest completed execution outcome (optional).
        portfolio_result: Latest completed portfolio update (optional).
        position_result: Latest completed position update (optional).
        trade_result: Latest completed trade update (optional).
        trades: Completed trades to aggregate for trading statistics.
        equity_curve: Historical portfolio total-value points (for drawdown).
        returns: Periodic portfolio returns series (for volatility / ratios).
        benchmark_returns: Periodic benchmark returns series (for comparison).
        market_prices: Standardized latest prices per symbol.
        benchmark_prices: Standardized latest benchmark prices per symbol.
        risk_free_rate: Per-period risk-free rate for Sharpe/Sortino/alpha.
        periods_per_year: Annualization factor (e.g. 365 for daily crypto).
        correlation_id: Optional correlation id propagated to the snapshot.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    execution_result: ExecutionResult | None = None
    portfolio_result: PortfolioResult | None = None
    position_result: PositionResult | None = None
    trade_result: TradeResult | None = None
    trades: tuple[Trade, ...] = ()
    equity_curve: tuple[Decimal, ...] = ()
    returns: tuple[Decimal, ...] = ()
    benchmark_returns: tuple[Decimal, ...] = ()
    market_prices: Mapping[str, Decimal] = field(
        default_factory=lambda: MappingProxyType({})
    )
    benchmark_prices: Mapping[str, Decimal] = field(
        default_factory=lambda: MappingProxyType({})
    )
    risk_free_rate: Decimal = Decimal("0")
    periods_per_year: int = 365
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "trades", tuple(self.trades))
        object.__setattr__(self, "equity_curve", tuple(self.equity_curve))
        object.__setattr__(self, "returns", tuple(self.returns))
        object.__setattr__(self, "benchmark_returns", tuple(self.benchmark_returns))
        object.__setattr__(
            self, "market_prices", MappingProxyType(dict(self.market_prices))
        )
        object.__setattr__(
            self, "benchmark_prices", MappingProxyType(dict(self.benchmark_prices))
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def completed_trades(self) -> tuple[Trade, ...]:
        """Return the trades to aggregate for statistics.

        Prefers the explicit ``trades`` collection; falls back to the single
        ``trade_result`` trade when only that is supplied.
        """
        if self.trades:
            return self.trades
        if self.trade_result is not None and self.trade_result.trade is not None:
            return (self.trade_result.trade,)
        return ()
