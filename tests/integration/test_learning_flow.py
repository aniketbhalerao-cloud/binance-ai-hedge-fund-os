"""Integration tests for the Learning Framework via the DI container.

Wires the learning engine into a container and runs the learn-loop outcome by
outcome. The Registry owns the running learning record across calls. No network,
no sleeps, no randomness, and no model training.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from agents.models import AgentRole
from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from learning import (
    DefaultLearningEngine,
    LearningCompleted,
    LearningRegistry,
    LearningResultStatus,
    register_learning,
)
from strategies.signals import SignalDirection
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.learning_fakes import make_context


class LearningIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        c = ServiceContainer()
        c.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_learning(c)
        return c

    async def test_learn_loop_accumulates_and_feeds_back(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultLearningEngine)
        registry = c.resolve(LearningRegistry)
        bus = c.resolve(EventBus)
        done = FakeSubscriber()
        bus.subscribe(LearningCompleted, done.handle)

        for _ in range(3):
            result = await engine.learn(
                make_context(learning_id="s1", strategy_name="ema", realized_pnl="10")
            )

        self.assertEqual(result.status, LearningResultStatus.SUCCESS)
        assert result.record is not None and result.metrics is not None
        self.assertEqual(result.record.outcome_count, 3)
        self.assertEqual(registry.get("s1").outcome_count, 3)
        self.assertEqual(result.metrics.win_rate, Decimal("1"))
        self.assertEqual(result.metrics.best_strategy, "ema")
        self.assertTrue(result.feedback)
        self.assertEqual(len(done.received), 3)

    async def test_best_and_worst_across_strategies(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultLearningEngine)

        await engine.learn(
            make_context(learning_id="s1", strategy_name="ema", realized_pnl="20")
        )
        result = await engine.learn(
            make_context(
                learning_id="s1", strategy_name="rsi", realized_pnl="-5",
                direction=SignalDirection.SELL,
            )
        )
        assert result.metrics is not None
        self.assertEqual(result.metrics.best_strategy, "ema")
        self.assertEqual(result.metrics.worst_strategy, "rsi")

    async def test_sessions_isolated(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultLearningEngine)
        registry = c.resolve(LearningRegistry)
        await engine.learn(make_context(learning_id="a", agent_role=AgentRole.MARKET))
        await engine.learn(make_context(learning_id="b", agent_role=AgentRole.STRATEGY))
        self.assertEqual(len(registry.list()), 2)


if __name__ == "__main__":
    unittest.main()
