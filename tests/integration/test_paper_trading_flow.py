"""Integration tests for the Paper Trading Framework via the DI container.

Wires the whole spine plus paper trading into one container and drives a live
session update-by-update. Upstream approval (risk/order/execution) is provided by
fakes so the post-Execution pipeline (Paper Broker → Portfolio → Position → Trade
→ Performance) runs deterministically end-to-end; the real downstream engines are
used as-is. The Registry owns the running session across updates. No network, no
sleeps, and no real orders are placed.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from execution import register_execution
from execution.interfaces import ExecutionEngine
from market_data import register_market_data
from order_management import register_order_management
from order_management.interfaces import OrderEngine
from paper_trading import (
    DefaultPaperTradingEngine,
    PaperSessionCompleted,
    PaperTradingRegistry,
    PaperTradingResultStatus,
    register_paper_trading,
)
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
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.market_data_fakes import FakeMarketDataProvider
from tests.support.paper_trading_fakes import make_context
from trades import register_trades
from trading import register_trading_engine


class PaperTradingIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
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
        c.register_instance(RiskEngine, FakeRiskEngine())  # type: ignore[arg-type]
        c.register_instance(OrderEngine, FakeOrderEngine())  # type: ignore[arg-type]
        c.register_instance(ExecutionEngine, FakeExecutionEngine())  # type: ignore[arg-type]
        register_paper_trading(c)
        return c

    async def test_live_session_completes_with_fills(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultPaperTradingEngine)
        registry = c.resolve(PaperTradingRegistry)
        bus = c.resolve(EventBus)
        done = FakeSubscriber()
        bus.subscribe(PaperSessionCompleted, done.handle)

        await engine.process(
            make_context(
                session_id="s1", index=0, close="100", buy_on=(0,), sell_on=(2,)
            )
        )
        await engine.process(
            make_context(
                session_id="s1", index=1, close="110", buy_on=(0,), sell_on=(2,)
            )
        )
        result = await engine.process(
            make_context(
                session_id="s1", index=2, close="120", buy_on=(0,), sell_on=(2,),
                final=True,
            )
        )

        self.assertEqual(result.status, PaperTradingResultStatus.COMPLETED)
        assert result.snapshot is not None
        self.assertEqual(result.snapshot.summary.total_fills, 2)
        self.assertEqual(result.snapshot.summary.net_profit, Decimal("20"))
        # One running session is owned by the registry.
        self.assertEqual(len(registry.list()), 1)
        self.assertEqual(len(done.received), 1)

    async def test_registry_owns_session_across_updates(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultPaperTradingEngine)
        registry = c.resolve(PaperTradingRegistry)

        await engine.process(make_context(session_id="s1", index=0, buy_on=(0,)))
        self.assertEqual(registry.get("s1").update_count, 1)
        await engine.process(make_context(session_id="s1", index=1, buy_on=(0,)))
        self.assertEqual(registry.get("s1").update_count, 2)

    async def test_two_sessions_isolated(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultPaperTradingEngine)
        registry = c.resolve(PaperTradingRegistry)

        await engine.process(make_context(session_id="a", index=0, buy_on=(0,)))
        await engine.process(make_context(session_id="b", index=0, buy_on=(0,)))
        self.assertEqual(len(registry.list()), 2)


if __name__ == "__main__":
    unittest.main()
