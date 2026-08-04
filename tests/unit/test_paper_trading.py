"""Unit tests for the Paper Trading Framework (stdlib unittest, deterministic)."""

from __future__ import annotations

import unittest
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from execution.models import (
    ExecutionIdentifier,
    ExecutionRequest,
    ExecutionResult,
    ExecutionState,
    ExecutionStatus,
)
from models import OrderSide, OrderType
from order_management.models import OrderIdentifier, OrderRequest
from paper_trading import (
    Broker,
    DefaultFeed,
    DefaultPaperBroker,
    DefaultPaperTradingEngine,
    DefaultPaperTradingHistory,
    DefaultPaperTradingManager,
    DefaultPaperTradingMetrics,
    Feed,
    InMemoryPaperTradingRegistry,
    PaperOrderFilled,
    PaperSessionCancelled,
    PaperTradingError,
    PaperTradingEvent,
    PaperTradingManager,
    PaperTradingRegistry,
    PaperTradingResultStatus,
    SessionParameters,
    SessionState,
    register_paper_trading,
)
from paper_trading.exceptions import BrokerError, FeedError, RegistryError
from paper_trading.models import (
    PaperFill,
    PaperSession,
    PaperTradingHistory,
)
from paper_trading.state import VALID_TRANSITIONS, can_transition
from performance import register_performance
from performance.interfaces import PerformanceEngine
from performance.models import (
    BenchmarkMetrics,
    PerformanceMetrics,
    PerformanceResult,
    PerformanceStatus,
    ReturnsMetrics,
    RiskMetrics,
    StatisticsMetrics,
)
from portfolio import register_portfolio
from portfolio.interfaces import PortfolioEngine
from positions import register_positions
from positions.interfaces import PositionEngine
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.paper_trading_fakes import (
    FakeExecutionEngine,
    FakeOrderEngine,
    FakeRiskEngine,
    make_candle,
    make_context,
)
from tests.support.performance_fakes import make_trade
from trades import register_trades
from trades.interfaces import TradeEngine

_ZERO = Decimal("0")


def _ready_execution(side: OrderSide, qty: str = "1") -> ExecutionResult:
    order = OrderRequest(
        identifier=OrderIdentifier(),
        symbol="BTCUSDT",
        side=side,
        order_type=OrderType.MARKET,
        quantity=Decimal(qty),
    )
    request = ExecutionRequest(
        identifier=ExecutionIdentifier(),
        order_request=order,
        exchange="paper",
        symbol="BTCUSDT",
    )
    return ExecutionResult(
        status=ExecutionStatus.READY, state=ExecutionState.READY, request=request
    )


def _perf_result() -> PerformanceResult:
    metrics = PerformanceMetrics(
        returns=ReturnsMetrics(
            total_return=Decimal("0.15"), realized_return=Decimal("0.1")
        ),
        risk=RiskMetrics(sharpe_ratio=Decimal("1.5"), max_drawdown=Decimal("0.1")),
        statistics=StatisticsMetrics(
            win_rate=Decimal("0.6"), profit_factor=Decimal("2"), expectancy=Decimal("5")
        ),
        benchmark=BenchmarkMetrics(),
    )
    return PerformanceResult(status=PerformanceStatus.COMPLETED, metrics=metrics)


def _fill(side: OrderSide = OrderSide.BUY) -> PaperFill:
    return PaperFill(
        symbol="BTCUSDT",
        side=side,
        quantity=Decimal("1"),
        price=Decimal("100"),
        commission=_ZERO,
        slippage=_ZERO,
        latency_steps=0,
        timestamp=make_candle(0, "100").close_time,
    )


def _full_manager(bus: EventBus) -> DefaultPaperTradingManager:
    c = ServiceContainer()
    c.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
    register_portfolio(c)
    register_positions(c)
    register_trades(c)
    register_performance(c)
    return DefaultPaperTradingManager(
        bus,
        InMemoryPaperTradingRegistry(),
        DefaultFeed(),
        DefaultPaperBroker(),
        DefaultPaperTradingMetrics(),
        DefaultPaperTradingHistory(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
        risk_engine=FakeRiskEngine(),  # type: ignore[arg-type]
        order_engine=FakeOrderEngine(),  # type: ignore[arg-type]
        execution_engine=FakeExecutionEngine(),  # type: ignore[arg-type]
        portfolio_engine=c.resolve(PortfolioEngine),
        position_engine=c.resolve(PositionEngine),
        trade_engine=c.resolve(TradeEngine),
        performance_engine=c.resolve(PerformanceEngine),
    )


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class StateTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(can_transition(SessionState.CREATED, SessionState.RUNNING))
        self.assertTrue(can_transition(SessionState.RUNNING, SessionState.RUNNING))
        self.assertTrue(can_transition(SessionState.RUNNING, SessionState.COMPLETED))

    def test_terminal(self) -> None:
        self.assertEqual(VALID_TRANSITIONS[SessionState.COMPLETED], frozenset())
        self.assertFalse(
            can_transition(SessionState.COMPLETED, SessionState.RUNNING)
        )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ModelTests(unittest.TestCase):
    def test_history_append_immutable(self) -> None:
        history = PaperTradingHistory("s1")
        new = history.append(_fill())
        self.assertEqual(len(history.fills), 0)
        self.assertEqual(len(new.fills), 1)

    def test_result_succeeded(self) -> None:
        from paper_trading.models import PaperTradingResult

        processed = PaperTradingResult(status=PaperTradingResultStatus.PROCESSED)
        failed = PaperTradingResult(status=PaperTradingResultStatus.FAILED)
        self.assertTrue(processed.succeeded)
        self.assertFalse(failed.succeeded)


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------
class FeedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.feed = DefaultFeed()

    def test_normalizes_to_strategy_context(self) -> None:
        candle = make_candle(0, "100")
        ctx = make_context(candle=candle)
        strategy_ctx = self.feed.normalize(ctx, (candle,))
        self.assertEqual(strategy_ctx.symbol, "BTCUSDT")
        self.assertEqual(strategy_ctx.latest_candle, candle)
        self.assertEqual(strategy_ctx.recent_candles, (candle,))


# ---------------------------------------------------------------------------
# Broker
# ---------------------------------------------------------------------------
class BrokerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.broker = DefaultPaperBroker()
        self.candle = make_candle(0, "100")

    def test_buy_fill_slippage_and_commission(self) -> None:
        params = SessionParameters(
            slippage_bps=Decimal("10"), commission_bps=Decimal("5")
        )
        fill = self.broker.fill(
            _ready_execution(OrderSide.BUY, "2"), self.candle, params
        )
        self.assertEqual(fill.price, Decimal("100.1"))
        expected = Decimal("100.1") * Decimal("2") * Decimal("5") / Decimal("10000")
        self.assertEqual(fill.commission, expected)

    def test_sell_fill_slippage(self) -> None:
        params = SessionParameters(slippage_bps=Decimal("10"))
        fill = self.broker.fill(_ready_execution(OrderSide.SELL), self.candle, params)
        self.assertEqual(fill.price, Decimal("99.9"))

    def test_not_ready_raises(self) -> None:
        not_ready = ExecutionResult(
            status=ExecutionStatus.PENDING, state=ExecutionState.CREATED
        )
        with self.assertRaises(BrokerError):
            self.broker.fill(not_ready, self.candle, SessionParameters())


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class MetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = DefaultPaperTradingMetrics()

    def test_derives_from_performance(self) -> None:
        trades = [make_trade(realized_pnl="10"), make_trade(realized_pnl="20")]
        metrics = self.calc.calculate(_perf_result(), trades, [], _ZERO)
        self.assertEqual(metrics.total_return, Decimal("0.15"))
        self.assertEqual(metrics.sharpe_ratio, Decimal("1.5"))
        self.assertEqual(metrics.win_rate, Decimal("0.6"))
        self.assertEqual(metrics.average_trade, Decimal("15"))

    def test_no_performance_is_zero(self) -> None:
        metrics = self.calc.calculate(None, [], [], _ZERO)
        self.assertEqual(metrics.total_return, _ZERO)


# ---------------------------------------------------------------------------
# History & Registry
# ---------------------------------------------------------------------------
class HistoryRegistryTests(unittest.TestCase):
    def test_history_service_appends(self) -> None:
        service = DefaultPaperTradingHistory()
        fill = _fill()
        self.assertEqual(
            service.append(PaperTradingHistory("s1"), fill).fills, (fill,)
        )

    def _session(self, sid: str) -> PaperSession:
        return PaperSession(
            id=sid, exchange="paper", symbol="BTCUSDT", state=SessionState.RUNNING
        )

    def test_registry_lifecycle(self) -> None:
        registry = InMemoryPaperTradingRegistry()
        session = self._session("s1")
        registry.register(session)
        self.assertTrue(registry.exists("s1"))
        self.assertEqual(registry.get("s1"), session)
        self.assertEqual(registry.list(), [session])
        registry.unregister("s1")
        self.assertFalse(registry.exists("s1"))

    def test_registry_missing_raises(self) -> None:
        with self.assertRaises(RegistryError):
            InMemoryPaperTradingRegistry().get("nope")

    def test_registry_clear(self) -> None:
        registry = InMemoryPaperTradingRegistry()
        registry.register(self._session("s1"))
        registry.clear()
        self.assertEqual(registry.list(), [])


# ---------------------------------------------------------------------------
# Manager — registry-backed session persistence
# ---------------------------------------------------------------------------
class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_session_persists_across_updates_and_completes(self) -> None:
        bus = EventBus()
        filled = FakeSubscriber()
        bus.subscribe(PaperOrderFilled, filled.handle)
        manager = _full_manager(bus)

        r0 = await manager.process(
            make_context(
                session_id="s1", index=0, close="100", buy_on=(0,), sell_on=(2,)
            )
        )
        self.assertEqual(r0.status, PaperTradingResultStatus.PROCESSED)
        assert r0.session is not None
        self.assertEqual(r0.session.update_count, 1)
        self.assertEqual(r0.session.fill_count, 1)
        self.assertEqual(r0.session.state, SessionState.RUNNING)

        r1 = await manager.process(
            make_context(
                session_id="s1", index=1, close="110", buy_on=(0,), sell_on=(2,)
            )
        )
        assert r1.session is not None
        self.assertEqual(r1.session.update_count, 2)
        self.assertEqual(r1.session.fill_count, 1)  # no fill on the hold candle

        r2 = await manager.process(
            make_context(
                session_id="s1", index=2, close="120", buy_on=(0,), sell_on=(2,),
                final=True,
            )
        )
        self.assertEqual(r2.status, PaperTradingResultStatus.COMPLETED)
        assert r2.session is not None and r2.snapshot is not None
        self.assertEqual(r2.session.state, SessionState.COMPLETED)
        self.assertEqual(r2.snapshot.summary.total_fills, 2)
        self.assertEqual(r2.snapshot.summary.total_trades, 1)
        self.assertEqual(r2.snapshot.summary.net_profit, Decimal("20"))
        self.assertEqual(len(filled.received), 2)

    async def test_registry_owns_running_session(self) -> None:
        bus = EventBus()
        manager = _full_manager(bus)
        await manager.process(make_context(session_id="s1", buy_on=(0,)))
        # The manager wrote the running session back to its registry.
        self.assertTrue(manager._registry.exists("s1"))  # type: ignore[attr-defined]
        self.assertEqual(
            manager._registry.get("s1").update_count, 1  # type: ignore[attr-defined]
        )

    async def test_no_strategy_processes_without_fill(self) -> None:
        bus = EventBus()
        manager = _full_manager(bus)
        ctx = make_context(session_id="s1")
        ctx = ctx.__class__(session_id="s1", candle=ctx.candle, strategy=None)
        r = await manager.process(ctx)
        self.assertEqual(r.status, PaperTradingResultStatus.PROCESSED)
        assert r.session is not None
        self.assertEqual(r.session.fill_count, 0)

    async def test_cancellation(self) -> None:
        bus = EventBus()
        cancelled = FakeSubscriber()
        bus.subscribe(PaperSessionCancelled, cancelled.handle)
        manager = _full_manager(bus)
        params = SessionParameters(cancel_after_updates=1)
        await manager.process(make_context(session_id="s1", index=0, parameters=params))
        r1 = await manager.process(
            make_context(session_id="s1", index=1, parameters=params)
        )
        self.assertEqual(r1.status, PaperTradingResultStatus.CANCELLED)
        self.assertEqual(len(cancelled.received), 1)

    async def test_terminal_session_rejected(self) -> None:
        bus = EventBus()
        manager = _full_manager(bus)
        await manager.process(
            make_context(session_id="s1", index=0, buy_on=(0,), final=True)
        )
        r = await manager.process(make_context(session_id="s1", index=1))
        self.assertEqual(r.status, PaperTradingResultStatus.FAILED)

    async def test_broker_failure_isolated(self) -> None:
        class _Boom:
            def fill(self, *_a: object, **_k: object) -> object:
                raise BrokerError("boom")

        bus = EventBus()
        manager = DefaultPaperTradingManager(
            bus,
            InMemoryPaperTradingRegistry(),
            DefaultFeed(),
            _Boom(),  # type: ignore[arg-type]
            DefaultPaperTradingMetrics(),
            DefaultPaperTradingHistory(),
            logger=FakeLoggerFactory(),  # type: ignore[arg-type]
            risk_engine=FakeRiskEngine(),  # type: ignore[arg-type]
            order_engine=FakeOrderEngine(),  # type: ignore[arg-type]
            execution_engine=FakeExecutionEngine(),  # type: ignore[arg-type]
        )
        r = await manager.process(make_context(session_id="s1", buy_on=(0,)))
        self.assertEqual(r.status, PaperTradingResultStatus.FAILED)
        self.assertTrue(r.errors)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_stop_and_process(self) -> None:
        bus = EventBus()
        events = FakeSubscriber()
        bus.subscribe(PaperTradingEvent, events.handle)
        engine = DefaultPaperTradingEngine(
            bus, _full_manager(bus), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        result = await engine.process(make_context(session_id="s1", buy_on=(0,)))
        await engine.stop()
        self.assertEqual(result.status, PaperTradingResultStatus.PROCESSED)
        names = [type(e).__name__ for e in events.received]
        self.assertIn("PaperTradingStarted", names)
        self.assertIn("MarketDataProcessed", names)
        self.assertIn("PaperTradingStopped", names)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class RegistrationTests(unittest.TestCase):
    def test_registers_and_binds(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_paper_trading(container)
        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(
            container.resolve(DefaultPaperTradingEngine), DefaultPaperTradingEngine
        )
        self.assertIsInstance(
            container.resolve(PaperTradingManager), DefaultPaperTradingManager
        )
        self.assertIsInstance(container.resolve(Feed), DefaultFeed)
        self.assertIsInstance(container.resolve(Broker), DefaultPaperBroker)
        self.assertIsInstance(
            container.resolve(PaperTradingRegistry), InMemoryPaperTradingRegistry
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ExceptionTests(unittest.TestCase):
    def test_hierarchy(self) -> None:
        for exc in (FeedError, BrokerError, RegistryError):
            self.assertTrue(issubclass(exc, PaperTradingError))


if __name__ == "__main__":
    unittest.main()
