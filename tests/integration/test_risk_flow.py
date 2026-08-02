"""Integration tests for the Risk Framework, wired via the DI container."""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from market_data import register_market_data
from risk import (
    RiskDecisionApproved,
    RiskDecisionRejected,
    RiskDecisionType,
    RiskEvaluationEngine,
    RiskValidator,
    register_risk,
)
from strategies import register_strategies
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.market_data_fakes import FakeMarketDataProvider
from tests.support.risk_fakes import PassRule, RejectRule, make_risk_context
from trading import register_trading_engine


class RiskIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_trading_engine(container)
        register_market_data(container, provider=FakeMarketDataProvider())
        register_strategies(container)
        register_risk(container)
        return container

    async def test_validator_rules_and_bus(self) -> None:
        container = self._container()
        # Validator -> Rules: register a blocking rule.
        validator = container.resolve(RiskValidator)
        validator.add_rule(RejectRule("blocker"))

        engine = container.resolve(RiskEvaluationEngine)
        bus = container.resolve(EventBus)
        rejected = FakeSubscriber()
        bus.subscribe(RiskDecisionRejected, rejected.handle)

        # Strategy Framework -> Risk Engine: a signal (in the context) is judged.
        decision = await engine.evaluate(make_risk_context())

        self.assertEqual(decision.decision_type, RiskDecisionType.REJECTED)
        self.assertEqual(len(rejected.received), 1)

    async def test_decision_flow_approves_when_clean(self) -> None:
        container = self._container()
        container.resolve(RiskValidator).add_rule(PassRule("ok"))
        engine = container.resolve(RiskEvaluationEngine)
        bus = container.resolve(EventBus)
        approved = FakeSubscriber()
        bus.subscribe(RiskDecisionApproved, approved.handle)

        decision = await engine.evaluate(make_risk_context())

        self.assertTrue(decision.approved)
        self.assertEqual(len(approved.received), 1)

    async def test_risk_engine_singleton_shares_bus_with_engine(self) -> None:
        container = self._container()
        self.assertIs(
            container.resolve(RiskEvaluationEngine),
            container.resolve(RiskEvaluationEngine),
        )


if __name__ == "__main__":
    unittest.main()
