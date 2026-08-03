"""Integration tests for the Backtesting Framework via the DI container.

Wires the whole spine plus backtesting into one container and runs a historical
simulation. Upstream approval (risk/order/execution) is provided by fakes so the
post-Execution pipeline (Simulator → Portfolio → Position → Trade → Performance)
runs deterministically end-to-end; the real downstream engines are used as-is.
No network, no sleeps.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from backtesting import (
    BacktestCompleted,
    BacktestRegistry,
    BacktestResultStatus,
    DefaultBacktestEngine,
    register_backtesting,
)
from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from execution import register_execution
from execution.interfaces import ExecutionEngine
from market_data import register_market_data
from order_management import register_order_management
from order_management.interfaces import OrderEngine
from performance import register_performance
from portfolio import register_portfolio
from positions import register_positions
from risk import register_risk
from risk.interfaces import RiskEngine
from strategies import register_strategies
from tests.support.backtesting_fakes import (
    FakeExecutionEngine,
    FakeOrderEngine,
    FakeRiskEngine,
    make_backtesting_context,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.market_data_fakes import FakeMarketDataProvider
from trades import register_trades
from trading import register_trading_engine


class BacktestingIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self, *, fake_upstream: bool = True) -> ServiceContainer:
        c = ServiceContainer()
        c.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_trading_engine(c)
        register_market_data(c, provider=FakeMarketDataProvider())
        register_strategies(c)
        register_risk(c)
        register_order_management(c)
        register_execution(c)
        register_portfolio(c)
        register_positions(c)
        register_trades(c)
        register_performance(c)
        if fake_upstream:
            # Force deterministic approvals/fills by overriding the upstream
            # engines with fakes before the backtest manager is built.
            c.register_instance(RiskEngine, FakeRiskEngine())  # type: ignore[arg-type]
            c.register_instance(OrderEngine, FakeOrderEngine())  # type: ignore[arg-type]
            c.register_instance(ExecutionEngine, FakeExecutionEngine())  # type: ignore[arg-type]
        register_backtesting(c)
        return c

    async def test_full_spine_backtest_completes_with_fills(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultBacktestEngine)
        registry = c.resolve(BacktestRegistry)
        bus = c.resolve(EventBus)
        done = FakeSubscriber()
        bus.subscribe(BacktestCompleted, done.handle)

        result = await engine.run_backtest(
            make_backtesting_context(
                closes=["100", "110", "120"], buy_on=(0,), sell_on=(2,)
            )
        )

        self.assertEqual(result.status, BacktestResultStatus.COMPLETED)
        assert result.snapshot is not None
        self.assertEqual(result.snapshot.summary.total_fills, 2)
        self.assertEqual(result.snapshot.summary.net_profit, Decimal("20"))
        self.assertEqual(len(registry.list()), 1)
        self.assertEqual(len(done.received), 1)

    async def test_real_upstream_backtest_runs_without_error(self) -> None:
        # No fakes: drive the real risk/order/execution engines. Fills may be
        # zero (default sizing/approval), but the run must complete cleanly.
        c = self._container(fake_upstream=False)
        engine = c.resolve(DefaultBacktestEngine)

        result = await engine.run_backtest(
            make_backtesting_context(closes=["100", "110", "120"], buy_on=(0,))
        )
        self.assertEqual(result.status, BacktestResultStatus.COMPLETED)
        assert result.metrics is not None

    async def test_multiple_backtests_registered(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultBacktestEngine)
        registry = c.resolve(BacktestRegistry)
        await engine.run_backtest(make_backtesting_context(buy_on=(0,)))
        await engine.run_backtest(make_backtesting_context(buy_on=(0,)))
        self.assertEqual(len(registry.list()), 2)


if __name__ == "__main__":
    unittest.main()
