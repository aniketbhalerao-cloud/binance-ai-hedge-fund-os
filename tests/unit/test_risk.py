"""Unit tests for the Risk Framework."""

from __future__ import annotations

import dataclasses
import unittest

from core.container import ServiceContainer
from events.base import Event
from events.bus import EventBus
from risk import (
    DefaultRiskPolicy,
    DuplicateRiskRule,
    RiskDecision,
    RiskDecisionApproved,
    RiskDecisionRejected,
    RiskDecisionType,
    RiskEngine,
    RiskEngineStarted,
    RiskError,
    RiskEvaluationEngine,
    RiskEvaluationManager,
    RiskManager,
    RiskResult,
    RiskRuleFailed,
    RiskValidator,
    RuleRiskValidator,
    register_risk,
)
from risk.exceptions import InvalidRiskContext
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.risk_fakes import ErrorRule, PassRule, RejectRule, make_risk_context


class ModelTests(unittest.TestCase):
    def test_decision_is_immutable(self) -> None:
        decision = RiskDecision(id="d", decision_type=RiskDecisionType.APPROVED)
        self.assertTrue(decision.approved)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            decision.decision_type = RiskDecisionType.REJECTED  # type: ignore[misc]

    def test_result_evaluated_rules(self) -> None:
        result = RiskResult(passed=True, passed_rules=("a", "b"))
        self.assertEqual(result.evaluated_rules, ("a", "b"))


class ContextTests(unittest.TestCase):
    def test_metadata_is_read_only(self) -> None:
        ctx = make_risk_context()
        with self.assertRaises(TypeError):
            ctx.metadata["k"] = "v"  # type: ignore[index]


class ExceptionAndEventTests(unittest.TestCase):
    def test_hierarchy_and_event_inheritance(self) -> None:
        self.assertTrue(issubclass(DuplicateRiskRule, RiskError))
        self.assertIsInstance(RiskEngineStarted(), Event)


class ValidatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_collects_violations(self) -> None:
        validator = RuleRiskValidator()
        validator.add_rule(PassRule("p"))
        validator.add_rule(RejectRule("r"))
        result = await validator.validate(make_risk_context())
        self.assertFalse(result.passed)
        self.assertEqual(len(result.violations), 1)
        self.assertIn("p", result.passed_rules)

    async def test_error_is_isolated(self) -> None:
        validator = RuleRiskValidator()
        validator.add_rule(ErrorRule("e"))
        validator.add_rule(PassRule("p"))
        result = await validator.validate(make_risk_context())
        self.assertEqual(len(result.errors), 1)
        self.assertIn("p", result.passed_rules)  # other rule still ran

    async def test_disabled_rule_not_run(self) -> None:
        validator = RuleRiskValidator()
        validator.add_rule(RejectRule("r"))
        validator.disable("r")
        result = await validator.validate(make_risk_context())
        self.assertTrue(result.passed)

    async def test_duplicate_and_none_context(self) -> None:
        validator = RuleRiskValidator()
        validator.add_rule(PassRule("p"))
        with self.assertRaises(DuplicateRiskRule):
            validator.add_rule(PassRule("p"))
        with self.assertRaises(InvalidRiskContext):
            await validator.validate(None)  # type: ignore[arg-type]


class PolicyTests(unittest.TestCase):
    def test_default_policy(self) -> None:
        policy = DefaultRiskPolicy()
        ctx = make_risk_context()
        approved = policy.decide(RiskResult(passed=True), ctx)
        self.assertEqual(approved.decision_type, RiskDecisionType.APPROVED)


class ManagerTests(unittest.IsolatedAsyncioTestCase):
    def _manager(self) -> tuple[RiskEvaluationManager, EventBus, RuleRiskValidator]:
        bus = EventBus()
        validator = RuleRiskValidator()
        manager = RiskEvaluationManager(
            bus, validator, DefaultRiskPolicy(), logger=FakeLoggerFactory()
        )
        return manager, bus, validator

    async def test_rejection_publishes_events_and_returns_decision(self) -> None:
        manager, bus, validator = self._manager()
        validator.add_rule(RejectRule("r"))
        rejected, failed = FakeSubscriber(), FakeSubscriber()
        bus.subscribe(RiskDecisionRejected, rejected.handle)
        bus.subscribe(RiskRuleFailed, failed.handle)

        decision = await manager.evaluate(make_risk_context())

        self.assertEqual(decision.decision_type, RiskDecisionType.REJECTED)
        self.assertEqual(len(rejected.received), 1)
        self.assertEqual(len(failed.received), 1)

    async def test_approval_flow(self) -> None:
        manager, bus, validator = self._manager()
        validator.add_rule(PassRule("p"))
        approved = FakeSubscriber()
        bus.subscribe(RiskDecisionApproved, approved.handle)
        decision = await manager.evaluate(make_risk_context())
        self.assertTrue(decision.approved)
        self.assertEqual(len(approved.received), 1)


class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifecycle_and_evaluate(self) -> None:
        bus = EventBus()
        validator = RuleRiskValidator()
        manager = RiskEvaluationManager(bus, validator, DefaultRiskPolicy())
        engine = RiskEvaluationEngine(manager, bus)
        started = FakeSubscriber()
        bus.subscribe(RiskEngineStarted, started.handle)

        await engine.start()
        decision = await engine.evaluate(make_risk_context())

        self.assertEqual(len(started.received), 1)
        self.assertTrue(decision.approved)  # no rules => approved
        await engine.stop()


class DependencyInjectionTests(unittest.TestCase):
    def test_registration_resolves_singletons(self) -> None:
        container = ServiceContainer()
        register_risk(container)
        engine = container.resolve(RiskEvaluationEngine)
        self.assertIs(container.resolve(RiskEvaluationEngine), engine)
        self.assertIs(container.resolve(RiskEngine), engine)
        self.assertIsInstance(container.resolve(RiskManager), RiskEvaluationManager)
        self.assertIsInstance(container.resolve(RiskValidator), RuleRiskValidator)


if __name__ == "__main__":
    unittest.main()
