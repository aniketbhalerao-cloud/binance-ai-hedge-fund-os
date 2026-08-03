"""Integration tests for the Performance Framework via the DI container.

Exercises the read-only handoffs into performance analytics: real Trade results
(produced by the Position → Trade path) and standardized Portfolio results are
assembled into a ``PerformanceContext`` and analyzed through the Performance
Engine. No network, no sleeps — fully deterministic.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from execution import register_execution
from market_data import register_market_data
from models import OrderSide
from order_management import register_order_management
from performance import (
    DefaultPerformanceEngine,
    PerformanceAnalysisCompleted,
    PerformanceRegistry,
    PerformanceStatus,
    register_performance,
)
from performance.context import PerformanceContext
from portfolio import register_portfolio
from positions import DefaultPositionEngine, register_positions
from risk import register_risk
from strategies import register_strategies
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.market_data_fakes import FakeMarketDataProvider
from tests.support.performance_fakes import (
    decimals,
    make_performance_context,
    make_portfolio_result,
    make_trade,
)
from tests.support.position_fakes import make_position_context
from trades import DefaultTradeEngine, register_trades
from trades.context import TradeContext
from trading import register_trading_engine


class PerformanceIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_trading_engine(container)
        register_market_data(container, provider=FakeMarketDataProvider())
        register_strategies(container)
        register_risk(container)
        register_order_management(container)
        register_execution(container)
        register_portfolio(container)
        register_positions(container)
        register_trades(container)
        register_performance(container)
        return container

    async def _closed_trade_result(self, container: ServiceContainer):
        pos_engine = container.resolve(DefaultPositionEngine)
        trade_engine = container.resolve(DefaultTradeEngine)
        buy = await pos_engine.process(
            make_position_context(
                side=OrderSide.BUY, quantity=Decimal("1"), price=Decimal("100")
            )
        )
        await trade_engine.process(TradeContext(position_result=buy))
        sell = await pos_engine.process(
            make_position_context(
                side=OrderSide.SELL, quantity=Decimal("1"), price=Decimal("110")
            )
        )
        return await trade_engine.process(TradeContext(position_result=sell))

    async def test_trade_to_performance(self) -> None:
        container = self._container()
        engine = container.resolve(DefaultPerformanceEngine)

        trade_result = await self._closed_trade_result(container)
        assert trade_result.trade is not None
        ctx = PerformanceContext(
            trade_result=trade_result, trades=(trade_result.trade,)
        )
        result = await engine.analyze(ctx)

        self.assertEqual(result.status, PerformanceStatus.COMPLETED)
        assert result.metrics is not None
        self.assertEqual(result.metrics.statistics.total_trades, 1)
        self.assertEqual(result.metrics.statistics.winning_trades, 1)
        self.assertEqual(result.metrics.statistics.largest_winner, Decimal("10"))

    async def test_portfolio_to_performance(self) -> None:
        container = self._container()
        engine = container.resolve(DefaultPerformanceEngine)

        ctx = make_performance_context(portfolio_result=make_portfolio_result())
        result = await engine.analyze(ctx)

        self.assertEqual(result.status, PerformanceStatus.COMPLETED)
        assert result.metrics is not None
        self.assertEqual(result.metrics.returns.absolute_return, Decimal("150"))
        assert result.snapshot is not None
        self.assertEqual(result.snapshot.summary.total_value, Decimal("1150"))

    async def test_completed_event_published(self) -> None:
        container = self._container()
        engine = container.resolve(DefaultPerformanceEngine)
        bus = container.resolve(EventBus)
        done = FakeSubscriber()
        bus.subscribe(PerformanceAnalysisCompleted, done.handle)

        await engine.analyze(make_performance_context())
        self.assertEqual(len(done.received), 1)

    async def test_full_metrics_and_registry(self) -> None:
        container = self._container()
        engine = container.resolve(DefaultPerformanceEngine)
        registry = container.resolve(PerformanceRegistry)

        ctx = make_performance_context(
            trades=(make_trade(realized_pnl="10"), make_trade(realized_pnl="-4")),
            returns=decimals("0.1", "-0.05", "0.1"),
            equity_curve=decimals("1000", "1100", "1045", "1150"),
            benchmark_returns=decimals("0.05", "-0.02", "0.06"),
        )
        result = await engine.analyze(ctx)

        self.assertEqual(result.status, PerformanceStatus.COMPLETED)
        assert result.metrics is not None
        self.assertGreater(result.metrics.risk.max_drawdown, Decimal("0"))
        self.assertGreater(result.metrics.risk.volatility, Decimal("0"))
        self.assertNotEqual(result.metrics.benchmark.benchmark_return, Decimal("0"))
        self.assertEqual(len(registry.list()), 1)

    async def test_multiple_analyses_registered(self) -> None:
        container = self._container()
        engine = container.resolve(DefaultPerformanceEngine)
        registry = container.resolve(PerformanceRegistry)

        await engine.analyze(make_performance_context())
        await engine.analyze(make_performance_context())
        self.assertEqual(len(registry.list()), 2)

    async def test_engine_coexists_with_upstream(self) -> None:
        container = self._container()
        # Performance engine resolves alongside the whole spine without clashes.
        self.assertIsInstance(
            container.resolve(DefaultPerformanceEngine), DefaultPerformanceEngine
        )
        self.assertIsInstance(
            container.resolve(DefaultTradeEngine), DefaultTradeEngine
        )


if __name__ == "__main__":
    unittest.main()
