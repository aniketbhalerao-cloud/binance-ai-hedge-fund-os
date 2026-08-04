"""Unit tests for the Learning Framework (stdlib unittest, deterministic)."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal

from agents.models import AgentRole
from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from learning import (
    DefaultEvaluator,
    DefaultFeedback,
    DefaultJournal,
    DefaultLearningEngine,
    DefaultLearningManager,
    DefaultLearningMetrics,
    Evaluator,
    FeedbackGenerator,
    InMemoryLearningRegistry,
    Journal,
    LearningCancelled,
    LearningEngine,
    LearningError,
    LearningEvent,
    LearningManager,
    LearningRegistry,
    LearningResultStatus,
    register_learning,
)
from learning.events import LearningErrorOccurred
from learning.exceptions import EvaluationError, RegistryError
from learning.models import (
    JournalEntry,
    LearningHistory,
    LearningOutcome,
    LearningParameters,
    LearningRecord,
    StrategyEvaluation,
)
from learning.state import VALID_TRANSITIONS, LearningState, can_transition
from strategies.signals import SignalDirection
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.learning_fakes import make_context

_ZERO = Decimal("0")
_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _outcome(
    strategy: str = "ema",
    role: AgentRole = AgentRole.STRATEGY,
    pnl: str = "10",
    won: bool = True,
) -> LearningOutcome:
    return LearningOutcome(
        strategy_name=strategy,
        agent_role=role,
        direction=SignalDirection.BUY,
        realized_pnl=Decimal(pnl),
        won=won,
        approved=True,
        timestamp=_TIME,
    )


def _history(*outcomes: LearningOutcome) -> LearningHistory:
    return LearningHistory(
        tuple(JournalEntry(index=i, outcome=o) for i, o in enumerate(outcomes))
    )


def _manager(bus: EventBus, **overrides: object) -> DefaultLearningManager:
    return DefaultLearningManager(
        bus,
        overrides.get("registry", InMemoryLearningRegistry()),  # type: ignore[arg-type]
        DefaultJournal(),
        overrides.get("evaluator", DefaultEvaluator()),  # type: ignore[arg-type]
        DefaultFeedback(),
        DefaultLearningMetrics(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# State & models
# ---------------------------------------------------------------------------
class StateModelTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(
            can_transition(LearningState.CREATED, LearningState.RECORDING)
        )
        self.assertTrue(
            can_transition(LearningState.EVALUATED, LearningState.EVALUATED)
        )
        self.assertEqual(VALID_TRANSITIONS[LearningState.COMPLETED], frozenset())

    def test_history_append_immutable(self) -> None:
        history = LearningHistory()
        new = history.append(JournalEntry(index=0, outcome=_outcome()))
        self.assertEqual(len(history.entries), 0)
        self.assertEqual(len(new.entries), 1)

    def test_parameters_defaults(self) -> None:
        params = LearningParameters()
        self.assertEqual(params.min_samples, 3)
        self.assertEqual(params.adjustment_step, Decimal("0.1"))


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------
class JournalTests(unittest.TestCase):
    def test_records_with_index(self) -> None:
        journal = DefaultJournal()
        history = journal.record(LearningHistory(), _outcome())
        history = journal.record(history, _outcome(pnl="5"))
        self.assertEqual(len(history.entries), 2)
        self.assertEqual(history.entries[1].index, 1)


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------
class EvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evaluator = DefaultEvaluator()

    def test_strategy_evaluation(self) -> None:
        entries = _history(
            _outcome("ema", pnl="10", won=True),
            _outcome("ema", pnl="-5", won=False),
        ).entries
        (evaluation,) = self.evaluator.evaluate_strategies(entries)
        self.assertEqual(evaluation.strategy_name, "ema")
        self.assertEqual(evaluation.samples, 2)
        self.assertEqual(evaluation.wins, 1)
        self.assertEqual(evaluation.win_rate, Decimal("0.5"))
        self.assertEqual(evaluation.total_pnl, Decimal("5"))
        self.assertEqual(evaluation.score, Decimal("2.5"))

    def test_agent_evaluation_groups_by_role(self) -> None:
        entries = _history(
            _outcome(role=AgentRole.STRATEGY, pnl="10"),
            _outcome(role=AgentRole.MARKET, pnl="20"),
        ).entries
        evaluations = self.evaluator.evaluate_agents(entries)
        self.assertEqual(len(evaluations), 2)


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------
class FeedbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.feedback = DefaultFeedback()
        self.params = LearningParameters()

    def test_increase_when_positive_and_enough_samples(self) -> None:
        strategies = (
            StrategyEvaluation(strategy_name="ema", samples=3, score=Decimal("5")),
        )
        (rec,) = self.feedback.generate(strategies, (), self.params)
        self.assertEqual(rec.action, "increase")
        self.assertEqual(rec.adjustment, Decimal("0.1"))

    def test_decrease_when_negative(self) -> None:
        strategies = (
            StrategyEvaluation(strategy_name="ema", samples=3, score=Decimal("-5")),
        )
        (rec,) = self.feedback.generate(strategies, (), self.params)
        self.assertEqual(rec.action, "decrease")
        self.assertEqual(rec.adjustment, Decimal("-0.1"))

    def test_skips_below_min_samples(self) -> None:
        strategies = (
            StrategyEvaluation(strategy_name="ema", samples=2, score=Decimal("5")),
        )
        self.assertEqual(self.feedback.generate(strategies, (), self.params), ())


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class MetricsTests(unittest.TestCase):
    def test_best_and_worst_strategy(self) -> None:
        record = LearningRecord(
            id="l1",
            state=LearningState.EVALUATED,
            history=_history(_outcome("ema", won=True), _outcome("rsi", won=False)),
            strategy_evaluations=(
                StrategyEvaluation(strategy_name="ema", samples=1, score=Decimal("10")),
                StrategyEvaluation(strategy_name="rsi", samples=1, score=Decimal("-3")),
            ),
        )
        metrics = DefaultLearningMetrics().calculate(record)
        self.assertEqual(metrics.total_outcomes, 2)
        self.assertEqual(metrics.best_strategy, "ema")
        self.assertEqual(metrics.worst_strategy, "rsi")
        self.assertEqual(metrics.win_rate, Decimal("0.5"))

    def test_empty_record(self) -> None:
        record = LearningRecord(id="l1", state=LearningState.RECORDING)
        self.assertEqual(DefaultLearningMetrics().calculate(record).total_outcomes, 0)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = InMemoryLearningRegistry()
        self.record = LearningRecord(id="l1", state=LearningState.RECORDING)

    def test_register_and_get(self) -> None:
        self.registry.register(self.record)
        self.assertTrue(self.registry.exists("l1"))
        self.assertEqual(self.registry.get("l1"), self.record)
        self.assertEqual(self.registry.list(), [self.record])

    def test_get_missing_raises(self) -> None:
        with self.assertRaises(RegistryError):
            self.registry.get("nope")

    def test_unregister_and_clear(self) -> None:
        self.registry.register(self.record)
        self.registry.unregister("l1")
        self.assertFalse(self.registry.exists("l1"))
        self.registry.register(self.record)
        self.registry.clear()
        self.assertEqual(self.registry.list(), [])


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_learns_and_accumulates_across_calls(self) -> None:
        bus = EventBus()
        registry = InMemoryLearningRegistry()
        manager = _manager(bus, registry=registry)

        for _ in range(3):
            result = await manager.learn(
                make_context(learning_id="l1", realized_pnl="10")
            )

        self.assertEqual(result.status, LearningResultStatus.SUCCESS)
        assert result.record is not None and result.metrics is not None
        self.assertEqual(result.record.outcome_count, 3)
        self.assertEqual(registry.get("l1").outcome_count, 3)
        self.assertEqual(result.metrics.total_outcomes, 3)
        self.assertTrue(result.feedback)  # min_samples reached

    async def test_feedback_gated_by_min_samples(self) -> None:
        manager = _manager(EventBus())
        first = await manager.learn(make_context(learning_id="l1"))
        self.assertEqual(first.feedback, ())  # only 1 sample
        await manager.learn(make_context(learning_id="l1"))
        third = await manager.learn(make_context(learning_id="l1"))
        self.assertTrue(third.feedback)

    async def test_cancellation(self) -> None:
        bus = EventBus()
        cancelled = FakeSubscriber()
        bus.subscribe(LearningCancelled, cancelled.handle)
        manager = _manager(bus)
        result = await manager.learn(make_context(learning_id="l1", cancel=True))
        self.assertEqual(result.status, LearningResultStatus.CANCELLED)
        self.assertEqual(len(cancelled.received), 1)

    async def test_terminal_record_rejected(self) -> None:
        manager = _manager(EventBus())
        await manager.learn(make_context(learning_id="l1", cancel=True))
        result = await manager.learn(make_context(learning_id="l1"))
        self.assertEqual(result.status, LearningResultStatus.FAILED)

    async def test_error_isolated(self) -> None:
        class _Boom:
            def evaluate_strategies(self, entries: object) -> tuple:
                raise EvaluationError("boom")

            def evaluate_agents(self, entries: object) -> tuple:
                return ()

        bus = EventBus()
        errors = FakeSubscriber()
        bus.subscribe(LearningErrorOccurred, errors.handle)
        manager = _manager(bus, evaluator=_Boom())
        result = await manager.learn(make_context(learning_id="l1"))
        self.assertEqual(result.status, LearningResultStatus.FAILED)
        self.assertEqual(len(errors.received), 1)

    async def test_events_published(self) -> None:
        bus = EventBus()
        allev = FakeSubscriber()
        bus.subscribe(LearningEvent, allev.handle)
        manager = _manager(bus)
        await manager.learn(make_context(learning_id="l1"))
        names = [type(e).__name__ for e in allev.received]
        self.assertEqual(names[0], "LearningStarted")
        self.assertIn("OutcomeRecorded", names)
        self.assertIn("LearningCompleted", names)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_delegates(self) -> None:
        engine = DefaultLearningEngine(
            _manager(EventBus()), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        result = await engine.learn(make_context(learning_id="l1"))
        await engine.stop()
        self.assertEqual(result.status, LearningResultStatus.SUCCESS)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class RegistrationTests(unittest.TestCase):
    def test_registers_and_binds(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_learning(container)
        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(
            container.resolve(LearningEngine), DefaultLearningEngine
        )
        self.assertIsInstance(
            container.resolve(LearningManager), DefaultLearningManager
        )
        self.assertIsInstance(container.resolve(Journal), DefaultJournal)
        self.assertIsInstance(container.resolve(Evaluator), DefaultEvaluator)
        self.assertIsInstance(
            container.resolve(FeedbackGenerator), DefaultFeedback
        )
        self.assertIsInstance(
            container.resolve(LearningRegistry), InMemoryLearningRegistry
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ExceptionTests(unittest.TestCase):
    def test_hierarchy(self) -> None:
        for exc in (EvaluationError, RegistryError):
            self.assertTrue(issubclass(exc, LearningError))


if __name__ == "__main__":
    unittest.main()
