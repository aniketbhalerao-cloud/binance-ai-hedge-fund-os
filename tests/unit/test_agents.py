"""Unit tests for the AI Decision Engine (stdlib unittest, deterministic)."""

from __future__ import annotations

import unittest
from decimal import Decimal

from agents import (
    AgentRole,
    ConsensusResolver,
    DecisionContext,
    DecisionEngine,
    DecisionError,
    DecisionEvent,
    DecisionMade,
    DecisionManager,
    DecisionRejected,
    DecisionResultStatus,
    DefaultCEOAgent,
    DefaultConsensus,
    DefaultDecisionEngine,
    DefaultDecisionHistory,
    DefaultDecisionManager,
    DefaultDecisionMetrics,
    DefaultMarketAgent,
    DefaultPortfolioAgent,
    DefaultRiskAgent,
    DefaultStrategyAgent,
    InMemoryAgentRegistry,
    register_agents,
)
from agents.events import AgentErrorOccurred
from agents.exceptions import AgentNotFoundError, ConsensusError, RegistryError
from agents.models import (
    AgentOpinion,
    Decision,
    DecisionHistory,
    DecisionParameters,
)
from agents.state import VALID_TRANSITIONS, DecisionState, can_transition
from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from strategies.signals import SignalDirection
from tests.support.agents_fakes import (
    FakeAgent,
    make_decision_context,
    make_signal,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber

_ZERO = Decimal("0")


def _opinion(
    role: AgentRole,
    direction: SignalDirection,
    confidence: str = "1",
    approve: bool = True,
) -> AgentOpinion:
    return AgentOpinion(
        role=role, direction=direction, confidence=Decimal(confidence), approve=approve
    )


def _full_registry() -> InMemoryAgentRegistry:
    registry = InMemoryAgentRegistry()
    registry.register(DefaultMarketAgent())
    registry.register(DefaultStrategyAgent())
    registry.register(DefaultRiskAgent())
    registry.register(DefaultPortfolioAgent())
    registry.register(DefaultCEOAgent())
    return registry


def _manager(bus: EventBus, registry: InMemoryAgentRegistry | None = None):
    return DefaultDecisionManager(
        bus,
        registry or _full_registry(),
        DefaultConsensus(),
        DefaultDecisionMetrics(),
        DefaultDecisionHistory(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# State & models
# ---------------------------------------------------------------------------
class StateModelTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(
            can_transition(DecisionState.REQUESTED, DecisionState.EVALUATING)
        )
        self.assertEqual(VALID_TRANSITIONS[DecisionState.RESOLVED], frozenset())

    def test_history_append_immutable(self) -> None:
        history = DecisionHistory()
        decision = Decision(
            id="d1", symbol="BTCUSDT", direction=SignalDirection.BUY,
            confidence=_ZERO, approved=True, opinions=(), timestamp=None,  # type: ignore[arg-type]
        )
        new = history.append(decision)
        self.assertEqual(len(history.decisions), 0)
        self.assertEqual(len(new.decisions), 1)

    def test_parameters_weight_for(self) -> None:
        params = DecisionParameters()
        self.assertEqual(params.weight_for(AgentRole.CEO), Decimal("2"))
        self.assertEqual(params.weight_for(AgentRole.RISK), _ZERO)


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
class AgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_market_agent_up_and_down(self) -> None:
        agent = DefaultMarketAgent()
        up = await agent.evaluate(make_decision_context(open_="100", close="110"))
        self.assertEqual(up.direction, SignalDirection.BUY)
        self.assertGreater(up.confidence, _ZERO)
        down = await agent.evaluate(make_decision_context(open_="110", close="100"))
        self.assertEqual(down.direction, SignalDirection.SELL)

    async def test_strategy_agent_votes(self) -> None:
        agent = DefaultStrategyAgent()
        ctx = make_decision_context(
            signals=(make_signal(SignalDirection.BUY, 0.9),)
        )
        opinion = await agent.evaluate(ctx)
        self.assertEqual(opinion.direction, SignalDirection.BUY)

    async def test_risk_agent_vetoes(self) -> None:
        agent = DefaultRiskAgent()
        approved = await agent.evaluate(make_decision_context(risk_approved=True))
        rejected = await agent.evaluate(make_decision_context(risk_approved=False))
        self.assertTrue(approved.approve)
        self.assertFalse(rejected.approve)

    async def test_portfolio_agent_neutral(self) -> None:
        opinion = await DefaultPortfolioAgent().evaluate(make_decision_context())
        self.assertEqual(opinion.direction, SignalDirection.HOLD)
        self.assertTrue(opinion.approve)

    async def test_ceo_agent_arbitrates(self) -> None:
        ctx = make_decision_context().with_opinions(
            [
                _opinion(AgentRole.MARKET, SignalDirection.BUY),
                _opinion(AgentRole.STRATEGY, SignalDirection.BUY),
            ]
        )
        opinion = await DefaultCEOAgent().evaluate(ctx)
        self.assertEqual(opinion.direction, SignalDirection.BUY)


# ---------------------------------------------------------------------------
# Consensus
# ---------------------------------------------------------------------------
class ConsensusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.consensus = DefaultConsensus()
        self.params = DecisionParameters()

    def test_buy_majority_approved(self) -> None:
        opinions = [
            _opinion(AgentRole.MARKET, SignalDirection.BUY),
            _opinion(AgentRole.STRATEGY, SignalDirection.BUY),
            _opinion(AgentRole.CEO, SignalDirection.BUY),
        ]
        result = self.consensus.resolve(opinions, self.params)
        self.assertEqual(result.direction, SignalDirection.BUY)
        self.assertTrue(result.approved)
        self.assertEqual(result.agreement_rate, Decimal("1"))

    def test_risk_veto_blocks_approval(self) -> None:
        opinions = [
            _opinion(AgentRole.MARKET, SignalDirection.BUY),
            _opinion(AgentRole.RISK, SignalDirection.HOLD, approve=False),
        ]
        result = self.consensus.resolve(opinions, self.params)
        self.assertFalse(result.approved)

    def test_tie_is_hold(self) -> None:
        opinions = [
            _opinion(AgentRole.MARKET, SignalDirection.BUY),
            _opinion(AgentRole.STRATEGY, SignalDirection.SELL),
        ]
        result = self.consensus.resolve(opinions, self.params)
        self.assertEqual(result.direction, SignalDirection.HOLD)
        self.assertFalse(result.approved)

    def test_empty_is_hold(self) -> None:
        result = self.consensus.resolve([], self.params)
        self.assertEqual(result.direction, SignalDirection.HOLD)


# ---------------------------------------------------------------------------
# Metrics & History
# ---------------------------------------------------------------------------
class MetricsHistoryTests(unittest.TestCase):
    def _decision(self, direction: SignalDirection, approved: bool) -> Decision:
        return Decision(
            id="d", symbol="BTCUSDT", direction=direction, confidence=Decimal("0.8"),
            approved=approved,
            opinions=(_opinion(AgentRole.MARKET, direction),),
            timestamp=None,  # type: ignore[arg-type]
        )

    def test_metrics_aggregate(self) -> None:
        decisions = [
            self._decision(SignalDirection.BUY, True),
            self._decision(SignalDirection.SELL, False),
        ]
        metrics = DefaultDecisionMetrics().calculate(decisions)
        self.assertEqual(metrics.total_decisions, 2)
        self.assertEqual(metrics.approval_rate, Decimal("0.5"))
        self.assertEqual(metrics.buy_decisions, 1)
        self.assertEqual(metrics.sell_decisions, 1)

    def test_metrics_empty(self) -> None:
        self.assertEqual(DefaultDecisionMetrics().calculate([]).total_decisions, 0)

    def test_history_service_appends(self) -> None:
        decision = self._decision(SignalDirection.BUY, True)
        history = DefaultDecisionHistory().append(DecisionHistory(), decision)
        self.assertEqual(history.decisions, (decision,))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = InMemoryAgentRegistry()

    def test_register_by_role(self) -> None:
        agent = FakeAgent(AgentRole.MARKET)
        self.registry.register(agent)
        self.assertTrue(self.registry.exists(AgentRole.MARKET))
        self.assertIs(self.registry.get(AgentRole.MARKET), agent)
        self.assertEqual(self.registry.list(), [agent])

    def test_get_missing_raises(self) -> None:
        with self.assertRaises(AgentNotFoundError):
            self.registry.get(AgentRole.CEO)

    def test_unregister_and_clear(self) -> None:
        self.registry.register(FakeAgent(AgentRole.MARKET))
        self.registry.unregister(AgentRole.MARKET)
        self.assertFalse(self.registry.exists(AgentRole.MARKET))
        self.registry.register(FakeAgent(AgentRole.RISK))
        self.registry.clear()
        self.assertEqual(self.registry.list(), [])


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_decision_made_and_approved(self) -> None:
        bus = EventBus()
        made = FakeSubscriber()
        bus.subscribe(DecisionMade, made.handle)
        manager = _manager(bus)

        result = await manager.decide(make_decision_context(risk_approved=True))

        self.assertEqual(result.status, DecisionResultStatus.SUCCESS)
        assert result.decision is not None
        self.assertEqual(result.decision.direction, SignalDirection.BUY)
        self.assertTrue(result.decision.approved)
        self.assertEqual(len(made.received), 1)

    async def test_risk_veto_rejects_decision(self) -> None:
        bus = EventBus()
        rejected = FakeSubscriber()
        bus.subscribe(DecisionRejected, rejected.handle)
        manager = _manager(bus)

        result = await manager.decide(make_decision_context(risk_approved=False))

        self.assertEqual(result.status, DecisionResultStatus.SUCCESS)
        assert result.decision is not None
        self.assertFalse(result.decision.approved)
        self.assertEqual(len(rejected.received), 1)

    async def test_history_accumulates_across_calls(self) -> None:
        manager = _manager(EventBus())
        await manager.decide(make_decision_context())
        result = await manager.decide(make_decision_context())
        assert result.metrics is not None
        self.assertEqual(result.metrics.total_decisions, 2)

    async def test_agent_failure_isolated(self) -> None:
        class _Boom:
            @property
            def role(self) -> AgentRole:
                return AgentRole.MARKET

            async def evaluate(self, context: DecisionContext) -> AgentOpinion:
                raise RuntimeError("boom")

        bus = EventBus()
        errors = FakeSubscriber()
        bus.subscribe(AgentErrorOccurred, errors.handle)
        registry = InMemoryAgentRegistry()
        registry.register(_Boom())  # type: ignore[arg-type]
        manager = _manager(bus, registry)

        result = await manager.decide(make_decision_context())
        self.assertEqual(result.status, DecisionResultStatus.FAILED)
        self.assertEqual(len(errors.received), 1)

    async def test_events_published_in_order(self) -> None:
        bus = EventBus()
        allev = FakeSubscriber()
        bus.subscribe(DecisionEvent, allev.handle)
        manager = _manager(bus)
        await manager.decide(make_decision_context())
        names = [type(e).__name__ for e in allev.received]
        self.assertEqual(names[0], "DecisionRequested")
        self.assertIn("ConsensusReached", names)
        self.assertIn("DecisionSnapshotCreated", names)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_delegates(self) -> None:
        bus = EventBus()
        engine = DefaultDecisionEngine(
            _manager(bus), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        result = await engine.decide(make_decision_context())
        await engine.stop()
        self.assertEqual(result.status, DecisionResultStatus.SUCCESS)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class RegistrationTests(unittest.TestCase):
    def test_registers_and_binds(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_agents(container)
        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(
            container.resolve(DecisionEngine), DefaultDecisionEngine
        )
        self.assertIsInstance(
            container.resolve(DecisionManager), DefaultDecisionManager
        )
        self.assertIsInstance(container.resolve(ConsensusResolver), DefaultConsensus)

    def test_registry_prepopulated_with_agents(self) -> None:
        container = ServiceContainer()
        register_agents(container)
        registry = container.resolve(InMemoryAgentRegistry)
        self.assertEqual(len(registry.list()), 5)
        self.assertTrue(registry.exists(AgentRole.CEO))


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ExceptionTests(unittest.TestCase):
    def test_hierarchy(self) -> None:
        for exc in (ConsensusError, RegistryError, AgentNotFoundError):
            self.assertTrue(issubclass(exc, DecisionError))


if __name__ == "__main__":
    unittest.main()
