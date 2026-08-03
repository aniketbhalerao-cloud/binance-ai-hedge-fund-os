"""Helpers for Performance Framework tests.

Standalone support module (existing support files unchanged). Builds a
deterministic :class:`PerformanceContext` from standardized upstream results and
analytical series; no network, exchange, or timing dependency.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from performance.context import PerformanceContext
from portfolio.models import (
    Portfolio,
    PortfolioAllocation,
    PortfolioPerformance,
    PortfolioResult,
    PortfolioResultStatus,
    PortfolioSnapshot,
    PortfolioValue,
)
from portfolio.state import PortfolioState
from positions.models import PositionSide
from trades.models import Trade, TradeResult, TradeResultStatus, TradeSnapshot
from trades.state import TradeState

__all__ = [
    "FIXED_TIME",
    "make_portfolio_result",
    "make_trade",
    "make_trade_result",
    "make_performance_context",
    "decimals",
]

FIXED_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def decimals(*values: str) -> tuple[Decimal, ...]:
    """Convenience: build a tuple of Decimals from string literals."""
    return tuple(Decimal(v) for v in values)


def make_portfolio_result(
    *,
    cost_basis: str = "1000",
    unrealized_pnl: str = "50",
    realized_pnl: str = "100",
    total_value: str = "1150",
    daily_return: str = "0.01",
    total_return: str = "0.15",
    roi: str = "0.15",
    cumulative_return: str = "0.15",
) -> PortfolioResult:
    """Build a successful portfolio result with a full valuation snapshot."""
    value = PortfolioValue(
        cash_value=Decimal("500"),
        holdings_value=Decimal(total_value) - Decimal("500"),
        cost_basis=Decimal(cost_basis),
        unrealized_pnl=Decimal(unrealized_pnl),
        realized_pnl=Decimal(realized_pnl),
        total_value=Decimal(total_value),
    )
    performance = PortfolioPerformance(
        daily_return=Decimal(daily_return),
        total_return=Decimal(total_return),
        roi=Decimal(roi),
        cumulative_return=Decimal(cumulative_return),
    )
    portfolio = Portfolio(id="pf-1", state=PortfolioState.ACTIVE)
    snapshot = PortfolioSnapshot(
        portfolio=portfolio,
        value=value,
        allocation=PortfolioAllocation(weights={}, cash_weight=Decimal("1")),
        performance=performance,
        timestamp=FIXED_TIME,
    )
    return PortfolioResult(
        status=PortfolioResultStatus.SUCCESS, portfolio=portfolio, snapshot=snapshot
    )


def make_trade(
    *,
    trade_id: str = "pos-1",
    symbol: str = "BTCUSDT",
    realized_pnl: str = "10",
    entry_quantity: str = "1",
    exit_quantity: str = "1",
    state: TradeState = TradeState.CLOSED,
    hold_seconds: int = 3600,
) -> Trade:
    """Build a completed trade with the given realized P&L and holding time."""
    return Trade(
        id=trade_id,
        symbol=symbol,
        side=PositionSide.LONG,
        state=state,
        entry_quantity=Decimal(entry_quantity),
        exit_quantity=Decimal(exit_quantity),
        average_entry=Decimal("100"),
        average_exit=Decimal("110"),
        realized_pnl=Decimal(realized_pnl),
        fill_count=2,
        opened_at=FIXED_TIME,
        closed_at=FIXED_TIME + timedelta(seconds=hold_seconds),
        updated_at=FIXED_TIME + timedelta(seconds=hold_seconds),
    )


def make_trade_result(trade: Trade | None = None) -> TradeResult:
    """Wrap a trade in a successful trade result with a snapshot."""
    trade = trade or make_trade()
    from trades.models import TradeAnalytics

    snapshot = TradeSnapshot(
        trade=trade,
        analytics=TradeAnalytics(
            gross_profit=trade.realized_pnl,
            net_profit=trade.realized_pnl,
            won=trade.realized_pnl > 0,
        ),
        fill_count=trade.fill_count,
        timestamp=FIXED_TIME,
    )
    return TradeResult(
        status=TradeResultStatus.SUCCESS, trade=trade, snapshot=snapshot
    )


def make_performance_context(
    *,
    portfolio_result: PortfolioResult | None = None,
    trades: Sequence[Trade] | None = None,
    trade_result: TradeResult | None = None,
    returns: Sequence[Decimal] | None = None,
    equity_curve: Sequence[Decimal] | None = None,
    benchmark_returns: Sequence[Decimal] | None = None,
    risk_free_rate: str = "0",
    periods_per_year: int = 365,
    correlation_id: str | None = "corr-1",
) -> PerformanceContext:
    """Build a deterministic :class:`PerformanceContext`."""
    return PerformanceContext(
        portfolio_result=portfolio_result
        if portfolio_result is not None
        else make_portfolio_result(),
        trade_result=trade_result,
        trades=tuple(trades) if trades is not None else (),
        returns=tuple(returns) if returns is not None else (),
        equity_curve=tuple(equity_curve) if equity_curve is not None else (),
        benchmark_returns=tuple(benchmark_returns)
        if benchmark_returns is not None
        else (),
        risk_free_rate=Decimal(risk_free_rate),
        periods_per_year=periods_per_year,
        correlation_id=correlation_id,
    )
