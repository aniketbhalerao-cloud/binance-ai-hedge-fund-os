"""Unit tests for the Optimization Framework (stdlib unittest, deterministic)."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from optimization import (
    DefaultOptimizationEngine,
    DefaultOptimizationManager,
    DefaultOptimizationMetrics,
    DefaultOptimizer,
    DefaultPlanner,
    DefaultRecommendations,
    InMemoryOptimizationRegistry,
    OptimizationCancelled,
    OptimizationCompleted,
    OptimizationEngine,
    OptimizationError,
    OptimizationEvent,
    OptimizationManager,
    OptimizationParameters,
    OptimizationRegistry,
    OptimizationResultStatus,
    Optimizer,
    Planner,
    RecommendationGenerator,
    register_optimization,
)
from optimization.events import OptimizationErrorOccurred
from optimization.exceptions import PlanningError, RegistryError
from optimization.models import (
    OptimizationPlan,
    OptimizationRecord,
    OptimizationStep,
    OptimizationTarget,
)
from optimization.state import VALID_TRANSITIONS, OptimizationState, can_transition
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.optimization_fakes import make_context, make_strategy_eval

_ZERO = Decimal("0")
_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _manager(bus: EventBus, **overrides: object) -> DefaultOptimizationManager:
    return DefaultOptimizationManager(
        bus,
        InMemoryOptimizationRegistry(),
        overrides.get("planner", DefaultPlanner()),  # type: ignore[arg-type]
        DefaultOptimizer(),
        DefaultRecommendations(),
        DefaultOptimizationMetrics(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# State & models
# ---------------------------------------------------------------------------
class StateModelTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(
            can_transition(OptimizationState.CREATED, OptimizationState.PLANNING)
        )
        self.assertTrue(
            can_transition(OptimizationState.OPTIMIZED, OptimizationState.OPTIMIZED)
        )
        self.assertEqual(VALID_TRANSITIONS[OptimizationState.COMPLETED], frozenset())

    def test_history_append_immutable(self) -> None:
        from optimization.models import OptimizationHistory

        history = OptimizationHistory()
        new = history.append(OptimizationPlan())
        self.assertEqual(len(history.plans), 0)
        self.assertEqual(len(new.plans), 1)


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------
class PlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = DefaultPlanner()

    def test_ranks_worst_first_and_proposes_direction(self) -> None:
        plan = self.planner.plan(make_context())  # ema +5, rsi -3
        self.assertEqual(plan.targets[0].subject, "rsi")  # worst first
        actions = {s.target.subject: s.action for s in plan.steps}
        self.assertEqual(actions["rsi"], "decrease")
        self.assertEqual(actions["ema"], "increase")

    def test_hold_at_threshold(self) -> None:
        plan = self.planner.plan(
            make_context(strategies=(make_strategy_eval("flat", "0"),))
        )
        self.assertEqual(plan.steps[0].action, "hold")

    def test_max_targets_caps(self) -> None:
        strategies = tuple(
            make_strategy_eval(f"s{i}", str(i)) for i in range(10)
        )
        plan = self.planner.plan(
            make_context(
                strategies=strategies, parameters=OptimizationParameters(max_targets=3)
            )
        )
        self.assertEqual(len(plan.targets), 3)


# ---------------------------------------------------------------------------
# Optimizer & Recommendations
# ---------------------------------------------------------------------------
class OptimizerRecommendationTests(unittest.TestCase):
    def _plan(self) -> OptimizationPlan:
        t1 = OptimizationTarget(subject="ema", kind="strategy", score=Decimal("5"))
        t2 = OptimizationTarget(subject="flat", kind="strategy", score=_ZERO)
        return OptimizationPlan(
            targets=(t1, t2),
            steps=(
                OptimizationStep(
                    target=t1, action="increase", adjustment=Decimal("0.1")
                ),
                OptimizationStep(target=t2, action="hold", adjustment=_ZERO),
            ),
        )

    def test_optimizer_drops_holds(self) -> None:
        resolved = DefaultOptimizer().optimize(self._plan(), make_context())
        self.assertEqual(len(resolved.steps), 1)
        self.assertEqual(resolved.steps[0].action, "increase")

    def test_recommendations_one_per_step(self) -> None:
        resolved = DefaultOptimizer().optimize(self._plan(), make_context())
        recs = DefaultRecommendations().generate(resolved, make_context())
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].subject, "ema")
        self.assertEqual(recs[0].action, "increase")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class MetricsTests(unittest.TestCase):
    def test_best_worst_and_never_applied(self) -> None:
        t_best = OptimizationTarget(subject="ema", kind="strategy", score=Decimal("5"))
        t_worst = OptimizationTarget(
            subject="rsi", kind="strategy", score=Decimal("-3")
        )
        plan = OptimizationPlan(
            targets=(t_best, t_worst),
            steps=(
                OptimizationStep(
                    target=t_worst, action="decrease", adjustment=Decimal("-0.1")
                ),
            ),
        )
        from optimization.models import Recommendation

        record = OptimizationRecord(
            id="o1", state=OptimizationState.OPTIMIZED, plan=plan,
            recommendations=(
                Recommendation(subject="rsi", kind="strategy", action="decrease",
                               adjustment=Decimal("-0.1")),
            ),
            plan_count=1, recommendation_count=1,
        )
        metrics = DefaultOptimizationMetrics().calculate(record)
        self.assertEqual(metrics.best_target, "ema")
        self.assertEqual(metrics.worst_target, "rsi")
        self.assertEqual(metrics.applied_count, 0)  # never applied
        self.assertEqual(metrics.pending_count, 1)
        self.assertEqual(metrics.improvement_potential, Decimal("0.1"))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = InMemoryOptimizationRegistry()
        self.record = OptimizationRecord(id="o1", state=OptimizationState.PLANNING)

    def test_register_and_get(self) -> None:
        self.registry.register(self.record)
        self.assertTrue(self.registry.exists("o1"))
        self.assertEqual(self.registry.get("o1"), self.record)
        self.assertEqual(self.registry.list(), [self.record])

    def test_get_missing_raises(self) -> None:
        with self.assertRaises(RegistryError):
            self.registry.get("nope")

    def test_unregister_and_clear(self) -> None:
        self.registry.register(self.record)
        self.registry.unregister("o1")
        self.assertFalse(self.registry.exists("o1"))
        self.registry.register(self.record)
        self.registry.clear()
        self.assertEqual(self.registry.list(), [])


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_optimizes_and_accumulates(self) -> None:
        bus = EventBus()
        completed = FakeSubscriber()
        bus.subscribe(OptimizationCompleted, completed.handle)
        manager = _manager(bus)

        first = await manager.optimize(make_context(optimization_id="o1"))
        second = await manager.optimize(make_context(optimization_id="o1"))

        self.assertEqual(second.status, OptimizationResultStatus.SUCCESS)
        assert second.record is not None and second.metrics is not None
        self.assertEqual(second.record.plan_count, 2)
        self.assertTrue(second.recommendations)  # ema + rsi both actionable
        self.assertEqual(second.metrics.applied_count, 0)
        self.assertEqual(len(completed.received), 2)
        self.assertEqual(first.metrics.total_recommendations, 2)  # type: ignore[union-attr]

    async def test_cancellation(self) -> None:
        bus = EventBus()
        cancelled = FakeSubscriber()
        bus.subscribe(OptimizationCancelled, cancelled.handle)
        manager = _manager(bus)
        result = await manager.optimize(make_context(optimization_id="o1", cancel=True))
        self.assertEqual(result.status, OptimizationResultStatus.CANCELLED)
        self.assertEqual(len(cancelled.received), 1)

    async def test_terminal_rejected(self) -> None:
        manager = _manager(EventBus())
        await manager.optimize(make_context(optimization_id="o1", cancel=True))
        result = await manager.optimize(make_context(optimization_id="o1"))
        self.assertEqual(result.status, OptimizationResultStatus.FAILED)

    async def test_error_isolated(self) -> None:
        class _Boom:
            def plan(self, context: object) -> object:
                raise PlanningError("boom")

        bus = EventBus()
        errors = FakeSubscriber()
        bus.subscribe(OptimizationErrorOccurred, errors.handle)
        manager = _manager(bus, planner=_Boom())
        result = await manager.optimize(make_context(optimization_id="o1"))
        self.assertEqual(result.status, OptimizationResultStatus.FAILED)
        self.assertEqual(len(errors.received), 1)

    async def test_events_published(self) -> None:
        bus = EventBus()
        allev = FakeSubscriber()
        bus.subscribe(OptimizationEvent, allev.handle)
        manager = _manager(bus)
        await manager.optimize(make_context(optimization_id="o1"))
        names = [type(e).__name__ for e in allev.received]
        self.assertEqual(names[0], "OptimizationStarted")
        self.assertIn("PlanCreated", names)
        self.assertIn("RecommendationsGenerated", names)
        self.assertIn("OptimizationCompleted", names)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_delegates(self) -> None:
        engine = DefaultOptimizationEngine(
            _manager(EventBus()), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        result = await engine.optimize(make_context(optimization_id="o1"))
        await engine.stop()
        self.assertEqual(result.status, OptimizationResultStatus.SUCCESS)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class RegistrationTests(unittest.TestCase):
    def test_registers_and_binds(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_optimization(container)
        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(
            container.resolve(OptimizationEngine), DefaultOptimizationEngine
        )
        self.assertIsInstance(
            container.resolve(OptimizationManager), DefaultOptimizationManager
        )
        self.assertIsInstance(container.resolve(Planner), DefaultPlanner)
        self.assertIsInstance(container.resolve(Optimizer), DefaultOptimizer)
        self.assertIsInstance(
            container.resolve(RecommendationGenerator), DefaultRecommendations
        )
        self.assertIsInstance(
            container.resolve(OptimizationRegistry), InMemoryOptimizationRegistry
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ExceptionTests(unittest.TestCase):
    def test_hierarchy(self) -> None:
        for exc in (PlanningError, RegistryError):
            self.assertTrue(issubclass(exc, OptimizationError))


if __name__ == "__main__":
    unittest.main()
