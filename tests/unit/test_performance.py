"""Unit tests for the Performance Analytics Framework (stdlib unittest)."""

from __future__ import annotations

import unittest
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from performance import (
    BenchmarkingService,
    DefaultBenchmarkingService,
    DefaultPerformanceEngine,
    DefaultPerformanceManager,
    DefaultReturnsCalculator,
    DefaultRiskCalculator,
    DefaultStatisticsCalculator,
    InMemoryPerformanceRegistry,
    PerformanceEngine,
    PerformanceError,
    PerformanceEvent,
    PerformanceManager,
    PerformanceRegistry,
    PerformanceStatus,
    ReturnsCalculator,
    register_performance,
)
from performance.events import (
    PerformanceEngineStarted,
    PerformanceErrorOccurred,
)
from performance.exceptions import (
    DuplicatePerformanceError,
    PerformanceNotFoundError,
    ReturnsCalculationError,
    RiskCalculationError,
)
from performance.models import (
    BenchmarkMetrics,
    PerformanceIdentifier,
    PerformanceMetadata,
    PerformanceSnapshot,
    PerformanceSummary,
    ReturnsMetrics,
    RiskMetrics,
    StatisticsMetrics,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.performance_fakes import (
    FIXED_TIME,
    decimals,
    make_performance_context,
    make_trade,
    make_trade_result,
)

_ZERO = Decimal("0")


def _tol(a: Decimal, b: str, eps: str = "0.0001") -> bool:
    return abs(a - Decimal(b)) < Decimal(eps)


def _snapshot(sid: str = "s1") -> PerformanceSnapshot:
    return PerformanceSnapshot(
        identifier=PerformanceIdentifier(
            id=sid, correlation_id=None, timestamp=FIXED_TIME
        ),
        timestamp=FIXED_TIME,
        returns=ReturnsMetrics(),
        risk=RiskMetrics(),
        statistics=StatisticsMetrics(),
        benchmark=BenchmarkMetrics(),
        summary=PerformanceSummary(),
        metadata=PerformanceMetadata(),
    )


def _manager(bus: EventBus | None = None) -> DefaultPerformanceManager:
    return DefaultPerformanceManager(
        bus or EventBus(),
        InMemoryPerformanceRegistry(),
        DefaultReturnsCalculator(),
        DefaultRiskCalculator(),
        DefaultStatisticsCalculator(),
        DefaultBenchmarkingService(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Returns
# ---------------------------------------------------------------------------
class ReturnsCalculatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = DefaultReturnsCalculator()

    def test_point_metrics_from_portfolio(self) -> None:
        metrics = self.calc.calculate(make_performance_context())
        self.assertTrue(_tol(metrics.roi, "0.15"))
        self.assertTrue(_tol(metrics.realized_return, "0.1"))
        self.assertTrue(_tol(metrics.unrealized_return, "0.05"))
        self.assertEqual(metrics.absolute_return, Decimal("150"))
        self.assertEqual(metrics.percentage_return, Decimal("15.00"))

    def test_compound_return_from_series(self) -> None:
        ctx = make_performance_context(returns=decimals("0.1", "0.1"))
        metrics = self.calc.calculate(ctx)
        self.assertTrue(_tol(metrics.compound_return, "0.21"))

    def test_cagr_from_equity_curve(self) -> None:
        ctx = make_performance_context(
            equity_curve=decimals("1000", "1210"), periods_per_year=1
        )
        # 1 period, 1 year → 21% growth annualized.
        self.assertTrue(_tol(self.calc.calculate(ctx).cagr, "0.21"))

    def test_empty_context_is_zero(self) -> None:
        from performance.context import PerformanceContext

        metrics = self.calc.calculate(PerformanceContext())
        self.assertEqual(metrics.roi, _ZERO)
        self.assertEqual(metrics.compound_return, _ZERO)


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------
class RiskCalculatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = DefaultRiskCalculator()

    def test_max_drawdown(self) -> None:
        ctx = make_performance_context(equity_curve=decimals("100", "120", "90", "130"))
        self.assertTrue(_tol(self.calc.calculate(ctx).max_drawdown, "0.25"))

    def test_volatility_and_sharpe(self) -> None:
        ctx = make_performance_context(returns=decimals("0.1", "-0.05", "0.1", "-0.05"))
        metrics = self.calc.calculate(ctx)
        self.assertGreater(metrics.volatility, _ZERO)
        self.assertNotEqual(metrics.sharpe_ratio, _ZERO)

    def test_short_series_is_zero(self) -> None:
        ctx = make_performance_context(returns=decimals("0.1"))
        self.assertEqual(self.calc.calculate(ctx).volatility, _ZERO)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
class StatisticsCalculatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = DefaultStatisticsCalculator()

    def test_aggregates_over_trades(self) -> None:
        trades = (
            make_trade(trade_id="a", realized_pnl="10"),
            make_trade(trade_id="b", realized_pnl="-5"),
            make_trade(trade_id="c", realized_pnl="20"),
        )
        metrics = self.calc.calculate(make_performance_context(trades=trades))
        self.assertEqual(metrics.total_trades, 3)
        self.assertEqual(metrics.winning_trades, 2)
        self.assertEqual(metrics.losing_trades, 1)
        self.assertEqual(metrics.closed_trades, 3)
        self.assertTrue(_tol(metrics.win_rate, "0.6667", "0.001"))
        self.assertEqual(metrics.profit_factor, Decimal("6"))
        self.assertEqual(metrics.average_win, Decimal("15"))
        self.assertEqual(metrics.average_loss, Decimal("-5"))
        self.assertEqual(metrics.largest_winner, Decimal("20"))
        self.assertEqual(metrics.largest_loser, Decimal("-5"))
        self.assertEqual(metrics.average_holding_time, Decimal("3600"))

    def test_single_trade_result_fallback(self) -> None:
        ctx = make_performance_context(trade_result=make_trade_result())
        metrics = self.calc.calculate(ctx)
        self.assertEqual(metrics.total_trades, 1)

    def test_no_trades_is_zero(self) -> None:
        metrics = self.calc.calculate(make_performance_context())
        self.assertEqual(metrics.total_trades, 0)


# ---------------------------------------------------------------------------
# Benchmarking
# ---------------------------------------------------------------------------
class BenchmarkingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.svc = DefaultBenchmarkingService()

    def test_benchmark_and_relative_return(self) -> None:
        ctx = make_performance_context(
            returns=decimals("0.1", "0.2"),
            benchmark_returns=decimals("0.05", "0.1"),
        )
        metrics = self.svc.compare(ctx)
        self.assertTrue(_tol(metrics.benchmark_return, "0.155"))
        self.assertTrue(_tol(metrics.relative_return, "0.165"))
        self.assertEqual(metrics.excess_return, metrics.relative_return)
        self.assertGreater(metrics.tracking_error, _ZERO)

    def test_no_benchmark_is_zero(self) -> None:
        metrics = self.svc.compare(make_performance_context())
        self.assertEqual(metrics.benchmark_return, _ZERO)
        self.assertEqual(metrics.beta, _ZERO)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class PerformanceRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = InMemoryPerformanceRegistry()

    def test_register_and_get(self) -> None:
        snap = _snapshot("s1")
        self.registry.register(snap)
        self.assertTrue(self.registry.exists("s1"))
        self.assertEqual(self.registry.get("s1"), snap)
        self.assertEqual(self.registry.list(), [snap])

    def test_duplicate_raises(self) -> None:
        self.registry.register(_snapshot("s1"))
        with self.assertRaises(DuplicatePerformanceError):
            self.registry.register(_snapshot("s1"))

    def test_get_missing_raises(self) -> None:
        with self.assertRaises(PerformanceNotFoundError):
            self.registry.get("nope")

    def test_unregister_and_clear(self) -> None:
        self.registry.register(_snapshot("s1"))
        self.registry.unregister("s1")
        self.assertFalse(self.registry.exists("s1"))
        self.registry.register(_snapshot("s2"))
        self.registry.clear()
        self.assertEqual(self.registry.list(), [])


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class PerformanceManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_success_publishes_ordered_events(self) -> None:
        bus = EventBus()
        sub = FakeSubscriber()
        bus.subscribe(PerformanceEvent, sub.handle)
        manager = _manager(bus)

        result = await manager.analyze(
            make_performance_context(
                trades=(make_trade(),),
                returns=decimals("0.1", "0.1"),
                equity_curve=decimals("1000", "1100", "1210"),
            )
        )

        self.assertEqual(result.status, PerformanceStatus.COMPLETED)
        assert result.snapshot is not None
        assert result.metrics is not None
        names = [type(e).__name__ for e in sub.received]
        self.assertEqual(names[0], "PerformanceAnalysisStarted")
        self.assertEqual(names[-1], "PerformanceAnalysisCompleted")
        self.assertIn("ReturnsCalculated", names)
        self.assertIn("PerformanceSnapshotCreated", names)

    async def test_snapshot_registered(self) -> None:
        registry = InMemoryPerformanceRegistry()
        manager = DefaultPerformanceManager(
            EventBus(),
            registry,
            DefaultReturnsCalculator(),
            DefaultRiskCalculator(),
            DefaultStatisticsCalculator(),
            DefaultBenchmarkingService(),
            logger=FakeLoggerFactory(),  # type: ignore[arg-type]
        )
        result = await manager.analyze(make_performance_context())
        assert result.snapshot is not None
        self.assertEqual(len(registry.list()), 1)
        self.assertTrue(registry.exists(result.snapshot.identifier.id))

    async def test_stage_failure_isolated(self) -> None:
        class _Boom:
            def calculate(self, context: object) -> ReturnsMetrics:
                raise ReturnsCalculationError("boom")

        bus = EventBus()
        errors = FakeSubscriber()
        bus.subscribe(PerformanceErrorOccurred, errors.handle)
        manager = DefaultPerformanceManager(
            bus,
            InMemoryPerformanceRegistry(),
            _Boom(),  # type: ignore[arg-type]
            DefaultRiskCalculator(),
            DefaultStatisticsCalculator(),
            DefaultBenchmarkingService(),
            logger=FakeLoggerFactory(),  # type: ignore[arg-type]
        )

        result = await manager.analyze(make_performance_context())

        self.assertEqual(result.status, PerformanceStatus.FAILED)
        self.assertTrue(result.errors)
        self.assertEqual(len(errors.received), 1)

    async def test_error_is_performance_error_subclass(self) -> None:
        self.assertTrue(issubclass(RiskCalculationError, PerformanceError))


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class PerformanceEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_stop_publish_lifecycle(self) -> None:
        bus = EventBus()
        started = FakeSubscriber()
        bus.subscribe(PerformanceEngineStarted, started.handle)
        engine = DefaultPerformanceEngine(
            bus, _manager(bus), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        await engine.stop()
        self.assertEqual(len(started.received), 1)

    async def test_analyze_delegates(self) -> None:
        bus = EventBus()
        engine = DefaultPerformanceEngine(bus, _manager(bus))
        result = await engine.analyze(make_performance_context())
        self.assertEqual(result.status, PerformanceStatus.COMPLETED)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class PerformanceRegistrationTests(unittest.TestCase):
    def test_registers_and_binds_abstractions(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_performance(container)

        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(
            container.resolve(PerformanceEngine), DefaultPerformanceEngine
        )
        self.assertIsInstance(
            container.resolve(PerformanceManager), DefaultPerformanceManager
        )
        self.assertIsInstance(
            container.resolve(ReturnsCalculator), DefaultReturnsCalculator
        )
        self.assertIsInstance(
            container.resolve(BenchmarkingService), DefaultBenchmarkingService
        )
        self.assertIsInstance(
            container.resolve(PerformanceRegistry), InMemoryPerformanceRegistry
        )

    def test_singletons(self) -> None:
        container = ServiceContainer()
        register_performance(container)
        self.assertIs(
            container.resolve(DefaultPerformanceEngine),
            container.resolve(DefaultPerformanceEngine),
        )


if __name__ == "__main__":
    unittest.main()
