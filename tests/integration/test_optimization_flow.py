"""Integration tests for the Optimization Framework via the DI container.

Wires the optimization engine into a container and runs the optimize-loop input by
input over Learning evaluations. The Registry owns the running record across calls.
No network, no sleeps, no randomness, no model training, and no recommendation is
ever applied.
"""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from optimization import (
    DefaultOptimizationEngine,
    OptimizationCompleted,
    OptimizationRegistry,
    OptimizationResultStatus,
    register_optimization,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.optimization_fakes import make_context, make_strategy_eval


class OptimizationIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        c = ServiceContainer()
        c.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_optimization(c)
        return c

    async def test_optimize_loop_produces_recommendations(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultOptimizationEngine)
        registry = c.resolve(OptimizationRegistry)
        bus = c.resolve(EventBus)
        done = FakeSubscriber()
        bus.subscribe(OptimizationCompleted, done.handle)

        result = await engine.optimize(make_context(optimization_id="o1"))

        self.assertEqual(result.status, OptimizationResultStatus.SUCCESS)
        assert result.metrics is not None
        self.assertTrue(result.recommendations)
        self.assertEqual(result.metrics.applied_count, 0)  # never applied
        self.assertEqual(result.metrics.best_target, "ema")
        self.assertEqual(result.metrics.worst_target, "rsi")
        self.assertEqual(registry.get("o1").plan_count, 1)
        self.assertEqual(len(done.received), 1)

    async def test_record_accumulates_across_inputs(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultOptimizationEngine)
        registry = c.resolve(OptimizationRegistry)
        await engine.optimize(make_context(optimization_id="o1"))
        await engine.optimize(
            make_context(
                optimization_id="o1", strategies=(make_strategy_eval("macd", "2"),)
            )
        )
        self.assertEqual(registry.get("o1").plan_count, 2)

    async def test_sessions_isolated(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultOptimizationEngine)
        registry = c.resolve(OptimizationRegistry)
        await engine.optimize(make_context(optimization_id="a"))
        await engine.optimize(make_context(optimization_id="b"))
        self.assertEqual(len(registry.list()), 2)


if __name__ == "__main__":
    unittest.main()
