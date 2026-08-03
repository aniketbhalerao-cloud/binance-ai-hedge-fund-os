"""Unit tests for the Backtesting Framework (stdlib unittest, deterministic)."""

from __future__ import annotations

import unittest
from decimal import Decimal

from backtesting import (
    Backtest,
    BacktestCompleted,
    BacktestError,
    BacktestErrorOccurred,
    BacktestEvent,
    BacktestManager,
    BacktestRegistry,
    BacktestResultStatus,
    DefaultBacktestEngine,
    DefaultBacktestHistory,
    DefaultBacktestManager,
    DefaultBacktestMetrics,
    DefaultScheduler,
    DefaultSimulator,
    InMemoryBacktestRegistry,
    SimulationParameters,
    SimulationState,
    register_backtesting,
)
from backtesting.exceptions import RegistryError, SchedulerError, SimulationError
from backtesting.models import (
    BacktestHistory,
    BacktestMetrics,
    BacktestResult,
    BacktestSnapshot,
    BacktestSummary,
    SimulationStep,
)
from backtesting.state import VALID_TRANSITIONS, can_transition
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
from tests.support.backtesting_fakes import (
    FakeExecutionEngine,
    FakeOrderEngine,
    FakeRiskEngine,
    make_backtesting_context,
    make_candle,
    make_candles,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
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
        exchange="backtest",
        symbol="BTCUSDT",
    )
    return ExecutionResult(
        status=ExecutionStatus.READY, state=ExecutionState.READY, request=request
    )


def _perf_result() -> PerformanceResult:
    metrics = PerformanceMetrics(
        returns=ReturnsMetrics(cagr=Decimal("0.2"), total_return=Decimal("0.15")),
        risk=RiskMetrics(
            sharpe_ratio=Decimal("1.5"),
            max_drawdown=Decimal("0.1"),
            recovery_factor=Decimal("1.5"),
        ),
        statistics=StatisticsMetrics(
            win_rate=Decimal("0.6"),
            profit_factor=Decimal("2"),
            expectancy=Decimal("5"),
            average_holding_time=Decimal("3600"),
        ),
        benchmark=BenchmarkMetrics(),
    )
    return PerformanceResult(status=PerformanceStatus.COMPLETED, metrics=metrics)


def _bare_manager(bus: EventBus, **kw: object) -> DefaultBacktestManager:
    return DefaultBacktestManager(
        bus,
        InMemoryBacktestRegistry(),
        kw.get("scheduler", DefaultScheduler()),  # type: ignore[arg-type]
        kw.get("simulator", DefaultSimulator()),  # type: ignore[arg-type]
        DefaultBacktestMetrics(),
        DefaultBacktestHistory(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
    )


def _downstream_container() -> ServiceContainer:
    c = ServiceContainer()
    c.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
    register_portfolio(c)
    register_positions(c)
    register_trades(c)
    register_performance(c)
    return c


def _full_manager(bus: EventBus) -> DefaultBacktestManager:
    c = _downstream_container()
    return DefaultBacktestManager(
        bus,
        InMemoryBacktestRegistry(),
        DefaultScheduler(),
        DefaultSimulator(),
        DefaultBacktestMetrics(),
        DefaultBacktestHistory(),
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
class SimulationStateTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(
            can_transition(SimulationState.CREATED, SimulationState.RUNNING)
        )
        self.assertTrue(
            can_transition(SimulationState.RUNNING, SimulationState.COMPLETED)
        )
        self.assertTrue(
            can_transition(SimulationState.RUNNING, SimulationState.RUNNING)
        )

    def test_terminal(self) -> None:
        self.assertEqual(VALID_TRANSITIONS[SimulationState.COMPLETED], frozenset())
        self.assertFalse(
            can_transition(SimulationState.COMPLETED, SimulationState.RUNNING)
        )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ModelTests(unittest.TestCase):
    def test_history_append_immutable(self) -> None:
        history = BacktestHistory("b1")
        step = SimulationStep(
            index=0, timestamp=make_candle(0, "100").close_time,
            close=Decimal("100"), equity=Decimal("1000"),
        )
        new = history.append(step)
        self.assertEqual(len(history.steps), 0)
        self.assertEqual(len(new.steps), 1)

    def test_result_succeeded(self) -> None:
        ok = BacktestResult(status=BacktestResultStatus.COMPLETED)
        bad = BacktestResult(status=BacktestResultStatus.FAILED, errors=("x",))
        self.assertTrue(ok.succeeded)
        self.assertFalse(bad.succeeded)


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
class SchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scheduler = DefaultScheduler()

    def test_iterates_all(self) -> None:
        candles = make_candles(["1", "2", "3"])
        steps = self.scheduler.iterate(candles, 1)
        self.assertEqual([i for i, _ in steps], [0, 1, 2])

    def test_replay_speed_strides(self) -> None:
        candles = make_candles(["1", "2", "3", "4"])
        steps = self.scheduler.iterate(candles, 2)
        self.assertEqual([i for i, _ in steps], [0, 2])

    def test_invalid_speed_raises(self) -> None:
        with self.assertRaises(SchedulerError):
            self.scheduler.iterate(make_candles(["1"]), 0)


# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------
class SimulatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sim = DefaultSimulator()
        self.candle = make_candle(0, "100")

    def test_buy_fill_adds_slippage_and_commission(self) -> None:
        params = SimulationParameters(
            slippage_bps=Decimal("10"), commission_bps=Decimal("5")
        )
        fill = self.sim.simulate(
            _ready_execution(OrderSide.BUY, "2"), self.candle, params
        )
        self.assertEqual(fill.price, Decimal("100.1"))  # 100 + 0.1%
        expected_commission = (
            Decimal("100.1") * Decimal("2") * Decimal("5") / Decimal("10000")
        )
        self.assertEqual(fill.commission, expected_commission)
        self.assertEqual(fill.side, OrderSide.BUY)

    def test_sell_fill_subtracts_slippage(self) -> None:
        params = SimulationParameters(slippage_bps=Decimal("10"))
        fill = self.sim.simulate(_ready_execution(OrderSide.SELL), self.candle, params)
        self.assertEqual(fill.price, Decimal("99.9"))

    def test_not_ready_raises(self) -> None:
        not_ready = ExecutionResult(
            status=ExecutionStatus.PENDING, state=ExecutionState.CREATED
        )
        with self.assertRaises(SimulationError):
            self.sim.simulate(not_ready, self.candle, SimulationParameters())


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class MetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = DefaultBacktestMetrics()

    def test_derives_from_performance(self) -> None:
        trades = [make_trade(realized_pnl="10"), make_trade(realized_pnl="20")]
        metrics = self.calc.calculate(_perf_result(), trades, [], _ZERO)
        self.assertEqual(metrics.cagr, Decimal("0.2"))
        self.assertEqual(metrics.sharpe_ratio, Decimal("1.5"))
        self.assertEqual(metrics.win_rate, Decimal("0.6"))
        self.assertEqual(metrics.average_trade, Decimal("15"))

    def test_no_performance_is_zero(self) -> None:
        metrics = self.calc.calculate(None, [], [], _ZERO)
        self.assertEqual(metrics.cagr, _ZERO)


# ---------------------------------------------------------------------------
# History & Registry
# ---------------------------------------------------------------------------
class HistoryRegistryTests(unittest.TestCase):
    def test_history_service_appends(self) -> None:
        service = DefaultBacktestHistory()
        step = SimulationStep(
            index=0, timestamp=make_candle(0, "1").close_time,
            close=Decimal("1"), equity=Decimal("1"),
        )
        self.assertEqual(service.append(BacktestHistory("b1"), step).steps, (step,))

    def _snapshot(self, bid: str) -> BacktestSnapshot:
        backtest = Backtest(
            id=bid, exchange="backtest", symbol="BTCUSDT",
            state=SimulationState.COMPLETED,
        )
        return BacktestSnapshot(
            backtest=backtest, metrics=BacktestMetrics(), summary=BacktestSummary(),
            timestamp=make_candle(0, "1").close_time,
        )

    def test_registry_lifecycle(self) -> None:
        registry = InMemoryBacktestRegistry()
        snap = self._snapshot("b1")
        registry.register(snap)
        self.assertTrue(registry.exists("b1"))
        self.assertEqual(registry.get("b1"), snap)
        self.assertEqual(registry.list(), [snap])
        registry.unregister("b1")
        self.assertFalse(registry.exists("b1"))

    def test_registry_missing_raises(self) -> None:
        with self.assertRaises(RegistryError):
            InMemoryBacktestRegistry().get("nope")

    def test_registry_clear(self) -> None:
        registry = InMemoryBacktestRegistry()
        registry.register(self._snapshot("b1"))
        registry.clear()
        self.assertEqual(registry.list(), [])


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_pipeline_produces_fills_and_profit(self) -> None:
        bus = EventBus()
        done = FakeSubscriber()
        bus.subscribe(BacktestCompleted, done.handle)
        manager = _full_manager(bus)

        result = await manager.run(
            make_backtesting_context(
                closes=["100", "110", "120"], buy_on=(0,), sell_on=(2,)
            )
        )

        self.assertEqual(result.status, BacktestResultStatus.COMPLETED)
        assert result.snapshot is not None
        self.assertEqual(result.snapshot.summary.total_fills, 2)
        self.assertEqual(result.snapshot.summary.total_trades, 1)
        self.assertEqual(result.snapshot.summary.net_profit, Decimal("20"))
        self.assertEqual(result.metrics.average_trade, Decimal("20"))  # type: ignore[union-attr]
        self.assertEqual(len(done.received), 1)

    async def test_no_strategy_completes_with_no_fills(self) -> None:
        bus = EventBus()
        manager = _bare_manager(bus)
        from backtesting.context import BacktestingContext

        result = await manager.run(
            BacktestingContext(candles=make_candles(["100", "110"]))
        )
        self.assertEqual(result.status, BacktestResultStatus.COMPLETED)
        assert result.snapshot is not None
        self.assertEqual(result.snapshot.summary.total_fills, 0)

    async def test_cancellation(self) -> None:
        bus = EventBus()
        manager = _full_manager(bus)
        result = await manager.run(
            make_backtesting_context(
                closes=["100", "110", "120", "130"],
                buy_on=(0,),
                parameters=SimulationParameters(cancel_after_steps=1),
            )
        )
        self.assertEqual(result.status, BacktestResultStatus.CANCELLED)

    async def test_simulator_failure_isolated(self) -> None:
        class _Boom:
            def simulate(self, *_a: object, **_k: object) -> object:
                raise SimulationError("boom")

        bus = EventBus()
        errors = FakeSubscriber()
        bus.subscribe(BacktestErrorOccurred, errors.handle)
        c = _downstream_container()
        manager = DefaultBacktestManager(
            bus,
            InMemoryBacktestRegistry(),
            DefaultScheduler(),
            _Boom(),  # type: ignore[arg-type]
            DefaultBacktestMetrics(),
            DefaultBacktestHistory(),
            logger=FakeLoggerFactory(),  # type: ignore[arg-type]
            risk_engine=FakeRiskEngine(),  # type: ignore[arg-type]
            order_engine=FakeOrderEngine(),  # type: ignore[arg-type]
            execution_engine=FakeExecutionEngine(),  # type: ignore[arg-type]
            portfolio_engine=c.resolve(PortfolioEngine),
        )
        result = await manager.run(make_backtesting_context(buy_on=(0,)))
        self.assertEqual(result.status, BacktestResultStatus.FAILED)
        self.assertEqual(len(errors.received), 1)

    async def test_step_events_published(self) -> None:
        bus = EventBus()
        allev = FakeSubscriber()
        bus.subscribe(BacktestEvent, allev.handle)
        manager = _full_manager(bus)
        await manager.run(make_backtesting_context(closes=["100", "110"], buy_on=(0,)))
        names = [type(e).__name__ for e in allev.received]
        self.assertEqual(names[0], "BacktestStarted")
        self.assertIn("SimulationStepCompleted", names)
        self.assertIn("BacktestCompleted", names)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_delegates(self) -> None:
        bus = EventBus()
        engine = DefaultBacktestEngine(
            _full_manager(bus), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        result = await engine.run_backtest(
            make_backtesting_context(closes=["100", "120"], buy_on=(0,), sell_on=(1,))
        )
        await engine.stop()
        self.assertEqual(result.status, BacktestResultStatus.COMPLETED)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class RegistrationTests(unittest.TestCase):
    def test_registers_and_binds(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_backtesting(container)
        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(
            container.resolve(DefaultBacktestEngine), DefaultBacktestEngine
        )
        self.assertIsInstance(
            container.resolve(BacktestManager), DefaultBacktestManager
        )
        self.assertIsInstance(
            container.resolve(BacktestRegistry), InMemoryBacktestRegistry
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ExceptionTests(unittest.TestCase):
    def test_hierarchy(self) -> None:
        for exc in (SimulationError, SchedulerError, RegistryError):
            self.assertTrue(issubclass(exc, BacktestError))


if __name__ == "__main__":
    unittest.main()
