"""Unit tests for the Workflow Orchestration Framework (stdlib unittest)."""

from __future__ import annotations

import socket
import threading
import unittest
from decimal import Decimal
from unittest.mock import patch

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.workflow_fakes import (
    make_context,
    make_definition,
    make_dependency,
    make_step,
)
from workflows import (
    Collector,
    DefaultCollector,
    DefaultDispatcher,
    DefaultPlanner,
    DefaultWorkflowEngine,
    DefaultWorkflowManager,
    DefaultWorkflowMetrics,
    Dispatcher,
    InMemoryWorkflowRegistry,
    Planner,
    WorkflowCancelled,
    WorkflowCompleted,
    WorkflowEngine,
    WorkflowError,
    WorkflowEvent,
    WorkflowManager,
    WorkflowParameters,
    WorkflowRegistry,
    WorkflowResultStatus,
    register_workflows,
)
from workflows.events import WorkflowErrorOccurred
from workflows.exceptions import (
    CollectionError,
    DispatchError,
    PlanningError,
    RegistryError,
)
from workflows.models import (
    SUPPORTED_HANDOFF_TARGETS,
    WorkflowBatch,
    WorkflowHistory,
    WorkflowPlan,
    WorkflowPlanEntry,
    WorkflowRecord,
    WorkflowRequest,
    WorkflowStep,
)
from workflows.state import VALID_TRANSITIONS, WorkflowState, can_transition


def _manager(bus: EventBus, **overrides: object) -> DefaultWorkflowManager:
    return DefaultWorkflowManager(
        bus,
        InMemoryWorkflowRegistry(),
        overrides.get("collector", DefaultCollector()),  # type: ignore[arg-type]
        DefaultPlanner(),
        DefaultDispatcher(),
        DefaultWorkflowMetrics(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# State & models
# ---------------------------------------------------------------------------
class StateModelTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(
            can_transition(WorkflowState.CREATED, WorkflowState.COLLECTING)
        )
        self.assertTrue(can_transition(WorkflowState.PLANNED, WorkflowState.PLANNED))
        self.assertEqual(VALID_TRANSITIONS[WorkflowState.COMPLETED], frozenset())

    def test_history_append_immutable(self) -> None:
        history = WorkflowHistory()
        new = history.append(WorkflowBatch())
        self.assertEqual(len(history.batches), 0)
        self.assertEqual(len(new.batches), 1)

    def test_step_metadata_immutable(self) -> None:
        step = make_step("a")
        with self.assertRaises(TypeError):
            step.metadata["x"] = 1  # type: ignore[index]


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------
class CollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.collector = DefaultCollector()

    def test_collects_definitions_preserving_supplied_order(self) -> None:
        batch = self.collector.collect(
            make_context(definitions=(make_definition("z"), make_definition("a")))
        )
        self.assertEqual([d.workflow_id for d in batch.definitions], ["z", "a"])

    def test_max_items_caps(self) -> None:
        defs = tuple(make_definition(f"w{i}") for i in range(10))
        batch = self.collector.collect(
            make_context(
                definitions=defs, parameters=WorkflowParameters(max_items=3)
            )
        )
        self.assertEqual(len(batch.definitions), 3)


# ---------------------------------------------------------------------------
# Planner — dependency validation and step-level ordering
# ---------------------------------------------------------------------------
class PlannerOrderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = DefaultPlanner()

    def _plan(self, *definitions: object) -> object:
        return self.planner.plan(
            WorkflowBatch(definitions=tuple(definitions)),  # type: ignore[arg-type]
            make_context(),
        )

    def test_topological_ordering_respects_dependencies(self) -> None:
        steps = (make_step("c"), make_step("a"), make_step("b"))
        deps = (make_dependency("c", "b"), make_dependency("b", "a"))
        definition = make_definition("w1", steps=steps, dependencies=deps)
        plan = self._plan(definition)
        self.assertEqual([e.step.step_id for e in plan.entries], ["a", "b", "c"])  # type: ignore[attr-defined]

    def test_step_priority_tiebreak_among_ready_steps(self) -> None:
        steps = (make_step("a", "1"), make_step("b", "5"))
        plan = self._plan(make_definition("w1", steps=steps))
        self.assertEqual([e.step.step_id for e in plan.entries], ["b", "a"])  # type: ignore[attr-defined]

    def test_step_id_lexical_tiebreak_when_priority_ties(self) -> None:
        steps = (make_step("b", "5"), make_step("a", "5"))
        plan = self._plan(make_definition("w1", steps=steps))
        self.assertEqual([e.step.step_id for e in plan.entries], ["a", "b"])  # type: ignore[attr-defined]

    def test_duplicate_step_identifier_rejected(self) -> None:
        steps = (make_step("a"), make_step("a"))
        with self.assertRaises(PlanningError):
            self._plan(make_definition("w1", steps=steps))

    def test_missing_dependency_rejected(self) -> None:
        steps = (make_step("a"),)
        deps = (make_dependency("a", "ghost"),)
        with self.assertRaises(PlanningError):
            self._plan(make_definition("w1", steps=steps, dependencies=deps))

    def test_self_dependency_rejected(self) -> None:
        steps = (make_step("a"),)
        deps = (make_dependency("a", "a"),)
        with self.assertRaises(PlanningError):
            self._plan(make_definition("w1", steps=steps, dependencies=deps))

    def test_cycle_rejected(self) -> None:
        steps = (make_step("a"), make_step("b"))
        deps = (make_dependency("a", "b"), make_dependency("b", "a"))
        with self.assertRaises(PlanningError):
            self._plan(make_definition("w1", steps=steps, dependencies=deps))

    def test_cross_workflow_dependency_rejected(self) -> None:
        # w1's step "a" claims to depend on "x" — a step that only exists
        # on w2's independent graph, never on w1's own.
        w1 = make_definition(
            "w1", steps=(make_step("a"),), dependencies=(make_dependency("a", "x"),)
        )
        w2 = make_definition("w2", steps=(make_step("x"),))
        with self.assertRaises(PlanningError):
            self._plan(w1, w2)

    def test_invalid_handoff_target_rejected(self) -> None:
        definition = make_definition(
            "w1", steps=(make_step("a", handoff_target="not_a_target"),)
        )
        with self.assertRaises(PlanningError):
            self._plan(definition)

    def test_supported_handoff_targets_are_exactly_four(self) -> None:
        self.assertEqual(
            SUPPORTED_HANDOFF_TARGETS,
            frozenset({"agents", "model_gateway", "scheduler", "workers"}),
        )

    def test_invalid_definition_produces_no_partial_plan(self) -> None:
        good = make_definition("w0", steps=(make_step("a"),))
        bad = make_definition("w1", steps=(make_step("a"), make_step("a")))
        with self.assertRaises(PlanningError):
            self._plan(good, bad)

    def test_dependency_canonicalization_order_independent(self) -> None:
        steps = (make_step("c"), make_step("a"), make_step("b"))
        deps_forward = (make_dependency("c", "a"), make_dependency("c", "b"))
        deps_reversed = tuple(reversed(deps_forward))
        forward = self._plan(
            make_definition("w1", steps=steps, dependencies=deps_forward)
        )
        backward = self._plan(
            make_definition("w1", steps=steps, dependencies=deps_reversed)
        )
        forward_entry = next(
            e for e in forward.entries if e.step.step_id == "c"  # type: ignore[attr-defined]
        )
        backward_entry = next(
            e for e in backward.entries if e.step.step_id == "c"  # type: ignore[attr-defined]
        )
        # Canonicalized lexical ascending, regardless of declaration order.
        self.assertEqual(forward_entry.dependencies, ("a", "b"))
        self.assertEqual(forward_entry.dependencies, backward_entry.dependencies)

    def test_step_ordering_independent_of_insertion_order(self) -> None:
        steps = (make_step("a"), make_step("b"), make_step("c"))
        deps = (make_dependency("b", "a"), make_dependency("c", "b"))
        forward = self._plan(
            make_definition("w1", steps=steps, dependencies=deps)
        )
        backward = self._plan(
            make_definition(
                "w1", steps=tuple(reversed(steps)), dependencies=tuple(reversed(deps))
            )
        )
        self.assertEqual(
            [e.step.step_id for e in forward.entries],  # type: ignore[attr-defined]
            [e.step.step_id for e in backward.entries],  # type: ignore[attr-defined]
        )


# ---------------------------------------------------------------------------
# Planner — multi-workflow (workflow-level) ordering
# ---------------------------------------------------------------------------
class MultiWorkflowOrderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = DefaultPlanner()

    def _plan(self, *definitions: object) -> object:
        return self.planner.plan(
            WorkflowBatch(definitions=tuple(definitions)),  # type: ignore[arg-type]
            make_context(),
        )

    def test_duplicate_workflow_ids_rejected(self) -> None:
        w1 = make_definition("dup")
        w2 = make_definition("dup")
        with self.assertRaises(PlanningError):
            self._plan(w1, w2)

    def test_workflow_priority_ordering(self) -> None:
        low = make_definition("low", workflow_priority="1")
        high = make_definition("high", workflow_priority="9")
        plan = self._plan(low, high)
        self.assertEqual(plan.entries[0].workflow_id, "high")  # type: ignore[attr-defined]

    def test_workflow_id_lexical_tiebreak_when_priority_ties(self) -> None:
        w_b = make_definition("b", workflow_priority="5")
        w_a = make_definition("a", workflow_priority="5")
        plan = self._plan(w_b, w_a)
        self.assertEqual(plan.entries[0].workflow_id, "a")  # type: ignore[attr-defined]

    def test_multiple_definitions_resolved_independently(self) -> None:
        w1 = make_definition(
            "w1",
            steps=(make_step("a"), make_step("b")),
            dependencies=(make_dependency("b", "a"),),
        )
        w2 = make_definition(
            "w2",
            steps=(make_step("x"), make_step("y")),
            dependencies=(make_dependency("y", "x"),),
        )
        plan = self._plan(w1, w2)
        by_workflow: dict[str, list[str]] = {}
        for entry in plan.entries:  # type: ignore[attr-defined]
            by_workflow.setdefault(entry.workflow_id, []).append(entry.step.step_id)
        self.assertEqual(by_workflow["w1"], ["a", "b"])
        self.assertEqual(by_workflow["w2"], ["x", "y"])

    def test_workflow_priority_never_influences_step_ordering(self) -> None:
        definition = make_definition(
            "wlow",
            workflow_priority="1",
            steps=(make_step("b", "0"), make_step("a", "0")),
        )
        plan = self._plan(definition)
        # Ties on step priority resolve lexically by step id, regardless of
        # how high or low the owning workflow's priority is.
        self.assertEqual(
            [e.step.step_id for e in plan.entries], ["a", "b"]  # type: ignore[attr-defined]
        )

    def test_workflow_ordering_independent_of_definition_insertion_order(
        self,
    ) -> None:
        w1 = make_definition("w1", workflow_priority="1")
        w2 = make_definition("w2", workflow_priority="9")
        forward = self._plan(w1, w2)
        backward = self._plan(w2, w1)
        self.assertEqual(
            [e.workflow_id for e in forward.entries],  # type: ignore[attr-defined]
            [e.workflow_id for e in backward.entries],  # type: ignore[attr-defined]
        )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
class DispatcherTests(unittest.TestCase):
    def test_dispatch_produces_one_request_per_plan_entry_in_order(self) -> None:
        definition = make_definition(
            "w1",
            steps=(
                make_step("a", "1", handoff_target="scheduler"),
                make_step("b", "5", handoff_target="workers"),
            ),
        )
        plan = DefaultPlanner().plan(
            WorkflowBatch(definitions=(definition,)), make_context()
        )
        requests = DefaultDispatcher().dispatch(plan, make_context())
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].subject, "b")  # higher priority resolved first
        self.assertEqual(requests[0].handoff_target, "workers")
        self.assertEqual(requests[0].source, "w1")
        self.assertEqual(requests[0].position, 0)
        self.assertEqual(requests[1].subject, "a")
        self.assertEqual(requests[1].position, 1)

    def test_dispatch_rejects_invalid_handoff_target_defence_in_depth(self) -> None:
        """A manually constructed plan (bypassing the Planner's primary
        validation) with an invalid handoff target must still be rejected —
        and must construct zero ``WorkflowRequest`` objects in doing so."""
        bad_step = WorkflowStep(step_id="a", handoff_target="not_a_target")
        plan = WorkflowPlan(
            entries=(
                WorkflowPlanEntry(
                    position=0,
                    workflow_id="w1",
                    workflow_priority=Decimal("0"),
                    step=bad_step,
                ),
            )
        )
        import workflows.dispatcher as dispatcher_module

        with patch.object(dispatcher_module, "WorkflowRequest") as mock_request:
            with self.assertRaises(DispatchError):
                DefaultDispatcher().dispatch(plan, make_context())
            mock_request.assert_not_called()

    def test_dispatch_rejects_invalid_target_among_otherwise_valid_entries(
        self,
    ) -> None:
        """No partial result: one invalid entry among valid ones still
        raises, and produces no requests at all."""
        good_step = WorkflowStep(step_id="a", handoff_target="agents")
        bad_step = WorkflowStep(step_id="b", handoff_target="not_a_target")
        plan = WorkflowPlan(
            entries=(
                WorkflowPlanEntry(
                    position=0, workflow_id="w1", workflow_priority=Decimal("0"),
                    step=good_step,
                ),
                WorkflowPlanEntry(
                    position=1, workflow_id="w1", workflow_priority=Decimal("0"),
                    step=bad_step,
                ),
            )
        )
        with self.assertRaises(DispatchError):
            DefaultDispatcher().dispatch(plan, make_context())


# ---------------------------------------------------------------------------
# No execution / credential behavior
# ---------------------------------------------------------------------------
class NoExecutionOrCredentialTests(unittest.TestCase):
    _FORBIDDEN = {
        "manager", "engine", "callback", "callable",
        "api_key", "access_token", "token", "password", "secret",
        "credential", "connection", "client", "session", "socket",
    }

    def test_workflow_step_has_no_manager_or_credential_fields(self) -> None:
        fields = set(WorkflowStep.__dataclass_fields__)
        self.assertTrue(self._FORBIDDEN.isdisjoint(fields))

    def test_workflow_request_has_no_manager_or_credential_fields(self) -> None:
        fields = set(WorkflowRequest.__dataclass_fields__)
        self.assertTrue(self._FORBIDDEN.isdisjoint(fields))

    def test_dispatch_never_opens_a_socket(self) -> None:
        definition = make_definition("w1")
        plan = DefaultPlanner().plan(
            WorkflowBatch(definitions=(definition,)), make_context()
        )
        with patch.object(
            socket, "socket", side_effect=AssertionError("socket() called")
        ):
            requests = DefaultDispatcher().dispatch(plan, make_context())
        self.assertEqual(len(requests), 2)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class MetricsTests(unittest.TestCase):
    def test_highest_lowest_and_dispatch_ratio(self) -> None:
        definition = make_definition(
            "w1", steps=(make_step("cpu", "5"), make_step("mem", "-3"))
        )
        batch = WorkflowBatch(definitions=(definition,))
        requests = (
            WorkflowRequest(subject="cpu", source="w1", handoff_target="agents"),
        )
        record = WorkflowRecord(
            id="wf1",
            state=WorkflowState.PLANNED,
            batch=batch,
            requests=requests,
            step_count=2,
            request_count=1,
        )
        metrics = DefaultWorkflowMetrics().calculate(record)
        self.assertEqual(metrics.highest_priority_step, "cpu")
        self.assertEqual(metrics.lowest_priority_step, "mem")
        self.assertEqual(metrics.pending_requests_count, 1)
        self.assertEqual(metrics.suppressed_requests_count, 1)
        self.assertEqual(metrics.dispatch_ratio, Decimal("0.5"))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = InMemoryWorkflowRegistry()
        self.record = WorkflowRecord(id="wf1", state=WorkflowState.COLLECTING)

    def test_register_and_get(self) -> None:
        self.registry.register(self.record)
        self.assertTrue(self.registry.exists("wf1"))
        self.assertEqual(self.registry.get("wf1"), self.record)
        self.assertEqual(self.registry.list(), [self.record])

    def test_get_missing_raises(self) -> None:
        with self.assertRaises(RegistryError):
            self.registry.get("nope")

    def test_unregister_and_clear(self) -> None:
        self.registry.register(self.record)
        self.registry.unregister("wf1")
        self.assertFalse(self.registry.exists("wf1"))
        self.registry.register(self.record)
        self.registry.clear()
        self.assertEqual(self.registry.list(), [])

    def test_concurrent_registration_is_thread_safe(self) -> None:
        def _register(i: int) -> None:
            self.registry.register(
                WorkflowRecord(id=f"wf{i}", state=WorkflowState.COLLECTING)
            )

        threads = [threading.Thread(target=_register, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(self.registry.list()), 20)


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_composes_and_accumulates(self) -> None:
        bus = EventBus()
        completed = FakeSubscriber()
        bus.subscribe(WorkflowCompleted, completed.handle)
        manager = _manager(bus)

        first = await manager.compose(make_context(workflow_id="wf1"))
        second = await manager.compose(make_context(workflow_id="wf1"))

        self.assertEqual(second.status, WorkflowResultStatus.SUCCESS)
        assert second.record is not None and second.metrics is not None
        self.assertEqual(second.record.step_count, 4)  # 2 steps per input
        self.assertTrue(second.requests)
        self.assertEqual(len(completed.received), 2)
        self.assertEqual(first.metrics.total_requests, 2)  # type: ignore[union-attr]

    async def test_cancellation(self) -> None:
        bus = EventBus()
        cancelled = FakeSubscriber()
        bus.subscribe(WorkflowCancelled, cancelled.handle)
        manager = _manager(bus)
        result = await manager.compose(
            make_context(workflow_id="wf1", cancel=True)
        )
        self.assertEqual(result.status, WorkflowResultStatus.CANCELLED)
        self.assertEqual(len(cancelled.received), 1)

    async def test_terminal_rejected(self) -> None:
        manager = _manager(EventBus())
        await manager.compose(make_context(workflow_id="wf1", cancel=True))
        result = await manager.compose(make_context(workflow_id="wf1"))
        self.assertEqual(result.status, WorkflowResultStatus.FAILED)

    async def test_error_isolated(self) -> None:
        class _Boom:
            def collect(self, context: object) -> object:
                raise CollectionError("boom")

        bus = EventBus()
        errors = FakeSubscriber()
        bus.subscribe(WorkflowErrorOccurred, errors.handle)
        manager = _manager(bus, collector=_Boom())
        result = await manager.compose(make_context(workflow_id="wf1"))
        self.assertEqual(result.status, WorkflowResultStatus.FAILED)
        self.assertEqual(len(errors.received), 1)

    async def test_planning_failure_leaves_registry_state_unchanged(self) -> None:
        bus = EventBus()
        manager = _manager(bus)
        good = await manager.compose(make_context(workflow_id="wf1"))
        assert good.record is not None
        before = good.record

        bad_definition = make_definition(
            "w1", steps=(make_step("a"), make_step("a"))
        )
        result = await manager.compose(
            make_context(workflow_id="wf1", definitions=(bad_definition,))
        )
        self.assertEqual(result.status, WorkflowResultStatus.FAILED)
        registry = manager._registry  # type: ignore[attr-defined]
        self.assertEqual(registry.get("wf1"), before)

    async def test_events_published(self) -> None:
        bus = EventBus()
        allev = FakeSubscriber()
        bus.subscribe(WorkflowEvent, allev.handle)
        manager = _manager(bus)
        await manager.compose(make_context(workflow_id="wf1"))
        names = [type(e).__name__ for e in allev.received]
        self.assertEqual(names[0], "WorkflowStarted")
        self.assertIn("StepsCollected", names)
        self.assertIn("WorkflowPlanned", names)
        self.assertIn("RequestsDispatched", names)
        self.assertIn("WorkflowCompleted", names)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_delegates(self) -> None:
        engine = DefaultWorkflowEngine(
            _manager(EventBus()), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        result = await engine.compose(make_context(workflow_id="wf1"))
        await engine.stop()
        self.assertEqual(result.status, WorkflowResultStatus.SUCCESS)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class RegistrationTests(unittest.TestCase):
    def test_registers_and_binds(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_workflows(container)
        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(
            container.resolve(WorkflowEngine), DefaultWorkflowEngine
        )
        self.assertIsInstance(
            container.resolve(WorkflowManager), DefaultWorkflowManager
        )
        self.assertIsInstance(container.resolve(Collector), DefaultCollector)
        self.assertIsInstance(container.resolve(Planner), DefaultPlanner)
        self.assertIsInstance(container.resolve(Dispatcher), DefaultDispatcher)
        self.assertIsInstance(
            container.resolve(WorkflowRegistry), InMemoryWorkflowRegistry
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ExceptionTests(unittest.TestCase):
    def test_hierarchy(self) -> None:
        for exc in (CollectionError, PlanningError, RegistryError):
            self.assertTrue(issubclass(exc, WorkflowError))


if __name__ == "__main__":
    unittest.main()
