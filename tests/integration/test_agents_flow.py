"""Integration tests for the AI Decision Engine via the DI container.

Wires the decision engine into a container (with the default agents pre-registered)
and produces decisions from standardized inputs. No network, no sleeps, no
randomness, and no model/provider calls.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from agents import (
    AgentRole,
    DecisionMade,
    DecisionResultStatus,
    DefaultDecisionEngine,
    InMemoryAgentRegistry,
    register_agents,
)
from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from strategies.signals import SignalDirection
from tests.support.agents_fakes import make_decision_context, make_signal
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber


class AgentsIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        c = ServiceContainer()
        c.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_agents(c)
        return c

    async def test_decision_via_container(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultDecisionEngine)
        bus = c.resolve(EventBus)
        made = FakeSubscriber()
        bus.subscribe(DecisionMade, made.handle)

        result = await engine.decide(
            make_decision_context(open_="100", close="110", risk_approved=True)
        )

        self.assertEqual(result.status, DecisionResultStatus.SUCCESS)
        assert result.decision is not None
        self.assertEqual(result.decision.direction, SignalDirection.BUY)
        self.assertTrue(result.decision.approved)
        self.assertEqual(len(made.received), 1)

    async def test_all_five_agents_participate(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultDecisionEngine)
        registry = c.resolve(InMemoryAgentRegistry)
        self.assertEqual(len(registry.list()), 5)

        result = await engine.decide(make_decision_context())
        assert result.decision is not None
        self.assertEqual(len(result.decision.opinions), 5)
        roles = {op.role for op in result.decision.opinions}
        self.assertEqual(roles, set(AgentRole))

    async def test_risk_rejected_is_not_approved(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultDecisionEngine)
        result = await engine.decide(
            make_decision_context(risk_approved=False)
        )
        assert result.decision is not None
        self.assertFalse(result.decision.approved)

    async def test_sell_signals_produce_sell_decision(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultDecisionEngine)
        result = await engine.decide(
            make_decision_context(
                open_="110",
                close="100",
                signals=(make_signal(SignalDirection.SELL, 0.9),),
            )
        )
        assert result.decision is not None
        self.assertEqual(result.decision.direction, SignalDirection.SELL)

    async def test_metrics_accumulate(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultDecisionEngine)
        await engine.decide(make_decision_context())
        result = await engine.decide(make_decision_context())
        assert result.metrics is not None
        self.assertEqual(result.metrics.total_decisions, 2)
        self.assertGreater(result.metrics.average_confidence, Decimal("0"))


if __name__ == "__main__":
    unittest.main()
