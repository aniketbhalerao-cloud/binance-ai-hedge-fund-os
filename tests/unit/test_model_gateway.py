"""Unit tests for the Model Provider Gateway Framework (stdlib unittest)."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from model_gateway import (
    Collector,
    DefaultCollector,
    DefaultDispatcher,
    DefaultModelGatewayEngine,
    DefaultModelGatewayManager,
    DefaultModelGatewayMetrics,
    DefaultPlanner,
    Dispatcher,
    InMemoryModelGatewayRegistry,
    ModelGatewayCancelled,
    ModelGatewayCompleted,
    ModelGatewayEngine,
    ModelGatewayError,
    ModelGatewayEvent,
    ModelGatewayManager,
    ModelGatewayParameters,
    ModelGatewayRegistry,
    ModelGatewayResultStatus,
    Planner,
    register_model_gateway,
)
from model_gateway.events import ModelGatewayErrorOccurred
from model_gateway.exceptions import CollectionError, RegistryError
from model_gateway.models import (
    ModelInvocationBatch,
    ModelInvocationEntry,
    ModelInvocationRecord,
    ModelInvocationSource,
    ModelProviderProfile,
)
from model_gateway.state import VALID_TRANSITIONS, ModelGatewayState, can_transition
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.model_gateway_fakes import make_context, make_profile, make_source

_ZERO = Decimal("0")
_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _manager(bus: EventBus, **overrides: object) -> DefaultModelGatewayManager:
    return DefaultModelGatewayManager(
        bus,
        InMemoryModelGatewayRegistry(),
        overrides.get("collector", DefaultCollector()),  # type: ignore[arg-type]
        DefaultPlanner(),
        DefaultDispatcher(),
        DefaultModelGatewayMetrics(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# State & models
# ---------------------------------------------------------------------------
class StateModelTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(
            can_transition(ModelGatewayState.CREATED, ModelGatewayState.COLLECTING)
        )
        self.assertTrue(
            can_transition(ModelGatewayState.PLANNED, ModelGatewayState.PLANNED)
        )
        self.assertEqual(
            VALID_TRANSITIONS[ModelGatewayState.COMPLETED], frozenset()
        )

    def test_history_append_immutable(self) -> None:
        from model_gateway.models import ModelGatewayHistory

        history = ModelGatewayHistory()
        new = history.append(ModelInvocationBatch())
        self.assertEqual(len(history.batches), 0)
        self.assertEqual(len(new.batches), 1)


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------
class CollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.collector = DefaultCollector()

    def test_collects_highest_priority_first_across_sources(self) -> None:
        batch = self.collector.collect(
            make_context(
                learning=(make_source("cpu", "5"),),
                memory=(make_source("daily", "9", source="memory"),),
            )
        )
        self.assertEqual(batch.sources[0].name, "daily")  # highest priority first
        self.assertEqual(len(batch.entries), 2)

    def test_max_items_caps(self) -> None:
        learning = tuple(make_source(f"s{i}", str(i)) for i in range(10))
        batch = self.collector.collect(
            make_context(
                learning=learning,
                parameters=ModelGatewayParameters(max_items=3),
            )
        )
        self.assertEqual(len(batch.sources), 3)


# ---------------------------------------------------------------------------
# Planner & Dispatcher (routing-agnostic)
# ---------------------------------------------------------------------------
class PlannerDispatcherTests(unittest.TestCase):
    def _batch(self) -> ModelInvocationBatch:
        s_ok = ModelInvocationSource(
            name="cpu", source="learning", priority=Decimal("5")
        )
        s_bad = ModelInvocationSource(
            name="mem", source="learning", priority=Decimal("-3")
        )
        return ModelInvocationBatch(
            sources=(s_ok, s_bad),
            entries=(
                ModelInvocationEntry(source=s_ok),
                ModelInvocationEntry(source=s_bad),
            ),
        )

    def test_planner_resolves_dispatch(self) -> None:
        planned = DefaultPlanner().plan(self._batch(), make_context())
        dispatch = {e.source.name: e.dispatch for e in planned.entries}
        self.assertTrue(dispatch["cpu"])
        self.assertFalse(dispatch["mem"])

    def test_dispatcher_only_for_dispatchable(self) -> None:
        planned = DefaultPlanner().plan(self._batch(), make_context())
        requests = DefaultDispatcher().dispatch(planned, make_context())
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].subject, "cpu")
        self.assertEqual(requests[0].source, "learning")


# ---------------------------------------------------------------------------
# Deterministic Provider Routing
# ---------------------------------------------------------------------------
class RoutingTests(unittest.TestCase):
    """Covers the exact 9-dimension precedence from ``docs/prompts/task-36.md``:

    1. explicit provider/model identity, 2. capability requirements,
    3. context requirements, 4. routing policy priority, 5. provider/model
    priority, 6. cost/routing policy, 7. availability metadata,
    8. stable provider identifier, 9. stable model identifier, plus the
    final ``routing_id`` tie-break.
    """

    def _entry(self, source: ModelInvocationSource) -> ModelInvocationBatch:
        return ModelInvocationBatch(
            sources=(source,), entries=(ModelInvocationEntry(source=source),)
        )

    def _route(self, source, profiles):  # type: ignore[no-untyped-def]
        return DefaultDispatcher().dispatch(
            self._entry(source), make_context(provider_profiles=profiles)
        )

    # -- Dimensions 2/3: capability/context are hard elimination filters --

    def test_capability_filter_suppresses_ineligible_candidate(self) -> None:
        source = make_source("x", "5", required_capabilities=("vision",))
        profiles = (make_profile("a", "m1", capabilities=("text",)),)
        self.assertEqual(self._route(source, profiles), ())

    def test_context_filter_suppresses_ineligible_candidate(self) -> None:
        source = make_source("x", "5", required_context=("128k",))
        profiles = (make_profile("a", "m1", context_support=("32k",)),)
        self.assertEqual(self._route(source, profiles), ())

    def test_no_eligible_candidate_suppresses_entry(self) -> None:
        source = make_source("x", "5", required_capabilities=("vision",))
        self.assertEqual(self._route(source, ()), ())

    # -- Dimension 1: explicit provider/model identity --

    def test_dimension1_explicit_provider_beats_dimension4_5_6(self) -> None:
        """Explicit identity (1) outranks routing-policy priority, priority,
        and cost (4/5/6) even when another candidate wins on all three."""
        source = make_source("x", "5", preferred_provider_id="b")
        profiles = (
            make_profile(
                "a", "m1", routing_policy_priority="9", priority="9", cost="0"
            ),
            make_profile(
                "b", "m1", routing_policy_priority="0", priority="0", cost="9"
            ),
        )
        requests = self._route(source, profiles)
        self.assertEqual(requests[0].provider_id, "b")

    def test_explicit_preference_requires_exact_provider_and_model(self) -> None:
        """Item 13: an explicit preference names both provider *and* model —
        a provider match with a different, non-preferred model does not
        count as an explicit match."""
        source = make_source(
            "x", "5", preferred_provider_id="a", preferred_model_id="m2"
        )
        profiles = (
            make_profile("a", "m1", priority="9"),  # provider matches, model doesn't
            make_profile("a", "m2", priority="1"),  # exact provider + model match
        )
        requests = self._route(source, profiles)
        self.assertEqual(requests[0].model_id, "m2")

    def test_explicit_preference_does_not_override_capability_requirement(
        self,
    ) -> None:
        source = make_source(
            "x", "5", required_capabilities=("vision",), preferred_provider_id="a"
        )
        profiles = (
            make_profile("a", "m1", capabilities=()),  # preferred but ineligible
            make_profile("b", "m1", capabilities=("vision",)),
        )
        requests = self._route(source, profiles)
        self.assertEqual(requests[0].provider_id, "b")

    # -- Dimension 4 vs 5: routing policy priority outranks provider priority --

    def test_dimension4_routing_policy_priority_beats_dimension5_priority(
        self,
    ) -> None:
        source = make_source("x", "5")
        profiles = (
            make_profile("a", "m1", routing_policy_priority="1", priority="9"),
            make_profile("b", "m1", routing_policy_priority="9", priority="1"),
        )
        requests = self._route(source, profiles)
        self.assertEqual(requests[0].provider_id, "b")
        self.assertEqual(requests[0].routing_policy_priority, Decimal("9"))

    # -- Dimension 5 vs 6: provider priority outranks cost --

    def test_dimension5_priority_beats_dimension6_cost(self) -> None:
        source = make_source("x", "5")
        profiles = (
            make_profile("a", "m1", priority="1", cost="0"),
            make_profile("b", "m1", priority="9", cost="9"),
        )
        requests = self._route(source, profiles)
        self.assertEqual(requests[0].provider_id, "b")

    def test_cost_tiebreak_when_priority_ties(self) -> None:
        source = make_source("x", "5")
        profiles = (
            make_profile("a", "m1", priority="5", cost="3"),
            make_profile("b", "m1", priority="5", cost="1"),
        )
        requests = self._route(source, profiles)
        self.assertEqual(requests[0].provider_id, "b")
        self.assertEqual(requests[0].cost, Decimal("1"))

    # -- Dimension 6 vs 7: cost outranks availability --

    def test_dimension6_cost_beats_dimension7_availability(self) -> None:
        """Lower cost wins even against an unavailable candidate, since cost
        (6) outranks availability (7). Availability never hard-filters a
        candidate — only capability/context (2/3) do."""
        source = make_source("x", "5")
        profiles = (
            make_profile("a", "m1", cost="1", available=False),
            make_profile("b", "m1", cost="5", available=True),
        )
        requests = self._route(source, profiles)
        self.assertEqual(requests[0].provider_id, "a")
        self.assertFalse(requests[0].available)

    # -- Dimension 7: availability metadata, item 14 --

    def test_dimension7_available_beats_unavailable_when_tied_through_cost(
        self,
    ) -> None:
        source = make_source("x", "5")
        profiles = (
            make_profile("a", "m1", cost="1", available=False),
            make_profile("b", "m1", cost="1", available=True),
        )
        requests = self._route(source, profiles)
        self.assertEqual(requests[0].provider_id, "b")
        self.assertTrue(requests[0].available)

    def test_unavailable_candidate_is_selectable_as_sole_candidate(self) -> None:
        """Availability is a ranking dimension (7), not an elimination
        filter — an unavailable candidate can still be selected when it is
        the only eligible one, unlike a capability/context failure."""
        source = make_source("x", "5")
        profiles = (make_profile("a", "m1", available=False),)
        requests = self._route(source, profiles)
        self.assertEqual(requests[0].provider_id, "a")
        self.assertFalse(requests[0].available)

    def test_never_queries_live_availability(self) -> None:
        """Availability is declared domain input only; the dispatcher must
        never mutate or re-derive it."""
        source = make_source("x", "5")
        profiles = (make_profile("a", "m1", available=False),)
        requests = self._route(source, profiles)
        self.assertIs(requests[0].available, False)

    # -- Dimensions 8/9: stable lexical provider_id / model_id tie-break --

    def test_dimension8_provider_id_lexical_tiebreak(self) -> None:
        source = make_source("x", "5")
        profiles = (
            make_profile("zeta", "m1", priority="5", cost="1"),
            make_profile("alpha", "m1", priority="5", cost="1"),
        )
        requests = self._route(source, profiles)
        self.assertEqual(requests[0].provider_id, "alpha")

    def test_dimension9_model_id_lexical_tiebreak_when_provider_ties(self) -> None:
        source = make_source("x", "5")
        profiles = (
            make_profile("a", "zeta", priority="5", cost="1"),
            make_profile("a", "alpha", priority="5", cost="1"),
        )
        requests = self._route(source, profiles)
        self.assertEqual(requests[0].model_id, "alpha")

    # -- Final tie-break: routing_id --

    def test_routing_id_breaks_a_full_tie(self) -> None:
        """A stable routing_id resolves a tie that survives every other
        dimension (identical provider_id/model_id) — the entry is *not*
        suppressed, and the outcome is stable regardless of input order."""
        source = make_source("x", "5")
        profiles = (
            make_profile("a", "m1", priority="5", cost="1", routing_id="r2"),
            make_profile("a", "m1", priority="5", cost="1", routing_id="r1"),
        )
        forward = self._route(source, profiles)
        reversed_ = self._route(source, tuple(reversed(profiles)))
        self.assertEqual(len(forward), 1)
        self.assertEqual(forward, reversed_)

    def test_unresolvable_tie_without_routing_id_suppresses_entry(self) -> None:
        """Two candidates tied through dimension 9 with neither carrying a
        stable routing_id: 'the candidate is invalid and must not be
        selected' — the entry is suppressed, not arbitrarily resolved."""
        source = make_source("x", "5")
        profiles = (
            make_profile("a", "m1", priority="5", cost="1"),
            make_profile("a", "m1", priority="5", cost="1"),
        )
        requests = self._route(source, profiles)
        self.assertEqual(requests, ())

    # -- Item 12: order-independence --

    def test_routing_deterministic_regardless_of_profile_order(self) -> None:
        source = make_source("x", "5")
        profiles = (
            make_profile("a", "m1", priority="5", cost="1"),
            make_profile("b", "m1", priority="9", cost="1"),
            make_profile("c", "m1", priority="2", cost="1"),
        )
        forward = self._route(source, profiles)
        reversed_ = self._route(source, tuple(reversed(profiles)))
        self.assertEqual(forward, reversed_)
        self.assertEqual(forward[0].provider_id, "b")

    def test_full_precedence_chain_order_independent(self) -> None:
        """Item 12, exercised across every ranking dimension at once."""
        source = make_source("x", "5")
        profiles = (
            make_profile(
                "a", "m1", routing_policy_priority="5", priority="5",
                cost="1", available=True,
            ),
            make_profile(
                "b", "m1", routing_policy_priority="9", priority="1",
                cost="0", available=False,
            ),
            make_profile(
                "c", "m1", routing_policy_priority="9", priority="9",
                cost="0", available=True,
            ),
        )
        forward = self._route(source, profiles)
        shuffled = self._route(source, (profiles[2], profiles[0], profiles[1]))
        self.assertEqual(forward, shuffled)
        self.assertEqual(forward[0].provider_id, "c")


# ---------------------------------------------------------------------------
# No network / provider / credential behavior
# ---------------------------------------------------------------------------
class NoNetworkOrCredentialTests(unittest.TestCase):
    """Item 15: proves no network/provider/API-key behavior was introduced."""

    def test_provider_profile_has_no_credential_or_network_fields(self) -> None:
        forbidden = {
            "api_key", "access_token", "token", "password", "secret",
            "credential", "connection", "client", "session", "socket",
        }
        fields = set(ModelProviderProfile.__dataclass_fields__)
        self.assertTrue(forbidden.isdisjoint(fields))

    def test_model_invocation_request_has_no_credential_or_network_fields(
        self,
    ) -> None:
        from model_gateway.models import ModelInvocationRequest

        forbidden = {
            "api_key", "access_token", "token", "password", "secret",
            "credential", "connection", "client", "session", "socket",
        }
        fields = set(ModelInvocationRequest.__dataclass_fields__)
        self.assertTrue(forbidden.isdisjoint(fields))

    def test_dispatch_never_opens_a_socket(self) -> None:
        import socket
        from unittest.mock import patch

        source = make_source("x", "5")
        profiles = (make_profile("a", "m1"),)
        with patch.object(
            socket, "socket", side_effect=AssertionError("socket() called")
        ):
            requests = DefaultDispatcher().dispatch(
                ModelInvocationBatch(
                    sources=(source,),
                    entries=(ModelInvocationEntry(source=source),),
                ),
                make_context(provider_profiles=profiles),
            )
        self.assertEqual(len(requests), 1)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class MetricsTests(unittest.TestCase):
    def test_highest_lowest_and_actual_dispatch_ratio(self) -> None:
        s_hi = ModelInvocationSource(
            name="cpu", source="learning", priority=Decimal("5")
        )
        s_lo = ModelInvocationSource(
            name="mem", source="learning", priority=Decimal("-3")
        )
        # Both flagged dispatch=True by the planner, but only one produces a
        # request — metrics must reflect the actual outcome, not the flag.
        batch = ModelInvocationBatch(
            sources=(s_hi, s_lo),
            entries=(
                ModelInvocationEntry(source=s_hi, dispatch=True),
                ModelInvocationEntry(source=s_lo, dispatch=True),
            ),
        )
        from model_gateway.models import ModelInvocationRequest

        record = ModelInvocationRecord(
            id="g1", state=ModelGatewayState.PLANNED, batch=batch,
            requests=(
                ModelInvocationRequest(
                    subject="cpu", source="learning",
                    provider_id="a", model_id="m1",
                ),
            ),
            entry_count=2, request_count=1,
        )
        metrics = DefaultModelGatewayMetrics().calculate(record)
        self.assertEqual(metrics.highest_priority_entry, "cpu")
        self.assertEqual(metrics.lowest_priority_entry, "mem")
        self.assertEqual(metrics.pending_requests_count, 1)
        self.assertEqual(metrics.suppressed_requests_count, 1)
        self.assertEqual(metrics.dispatch_ratio, Decimal("0.5"))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = InMemoryModelGatewayRegistry()
        self.record = ModelInvocationRecord(
            id="g1", state=ModelGatewayState.COLLECTING
        )

    def test_register_and_get(self) -> None:
        self.registry.register(self.record)
        self.assertTrue(self.registry.exists("g1"))
        self.assertEqual(self.registry.get("g1"), self.record)
        self.assertEqual(self.registry.list(), [self.record])

    def test_get_missing_raises(self) -> None:
        with self.assertRaises(RegistryError):
            self.registry.get("nope")

    def test_unregister_and_clear(self) -> None:
        self.registry.register(self.record)
        self.registry.unregister("g1")
        self.assertFalse(self.registry.exists("g1"))
        self.registry.register(self.record)
        self.registry.clear()
        self.assertEqual(self.registry.list(), [])


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_invokes_and_accumulates(self) -> None:
        bus = EventBus()
        completed = FakeSubscriber()
        bus.subscribe(ModelGatewayCompleted, completed.handle)
        manager = _manager(bus)

        first = await manager.invoke(make_context(model_gateway_id="g1"))
        second = await manager.invoke(make_context(model_gateway_id="g1"))

        self.assertEqual(second.status, ModelGatewayResultStatus.SUCCESS)
        assert second.record is not None and second.metrics is not None
        self.assertEqual(second.record.entry_count, 4)  # 2 per input
        self.assertTrue(second.requests)  # cpu dispatchable and routable
        self.assertEqual(second.metrics.suppressed_requests_count, 1)  # mem suppressed
        self.assertEqual(len(completed.received), 2)
        self.assertEqual(first.metrics.total_requests, 1)  # type: ignore[union-attr]

    async def test_cancellation(self) -> None:
        bus = EventBus()
        cancelled = FakeSubscriber()
        bus.subscribe(ModelGatewayCancelled, cancelled.handle)
        manager = _manager(bus)
        result = await manager.invoke(
            make_context(model_gateway_id="g1", cancel=True)
        )
        self.assertEqual(result.status, ModelGatewayResultStatus.CANCELLED)
        self.assertEqual(len(cancelled.received), 1)

    async def test_terminal_rejected(self) -> None:
        manager = _manager(EventBus())
        await manager.invoke(make_context(model_gateway_id="g1", cancel=True))
        result = await manager.invoke(make_context(model_gateway_id="g1"))
        self.assertEqual(result.status, ModelGatewayResultStatus.FAILED)

    async def test_error_isolated(self) -> None:
        class _Boom:
            def collect(self, context: object) -> object:
                raise CollectionError("boom")

        bus = EventBus()
        errors = FakeSubscriber()
        bus.subscribe(ModelGatewayErrorOccurred, errors.handle)
        manager = _manager(bus, collector=_Boom())
        result = await manager.invoke(make_context(model_gateway_id="g1"))
        self.assertEqual(result.status, ModelGatewayResultStatus.FAILED)
        self.assertEqual(len(errors.received), 1)

    async def test_events_published(self) -> None:
        bus = EventBus()
        allev = FakeSubscriber()
        bus.subscribe(ModelGatewayEvent, allev.handle)
        manager = _manager(bus)
        await manager.invoke(make_context(model_gateway_id="g1"))
        names = [type(e).__name__ for e in allev.received]
        self.assertEqual(names[0], "ModelGatewayStarted")
        self.assertIn("InvocationsCollected", names)
        self.assertIn("RequestsDispatched", names)
        self.assertIn("ModelGatewayCompleted", names)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_delegates(self) -> None:
        engine = DefaultModelGatewayEngine(
            _manager(EventBus()), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        result = await engine.invoke(make_context(model_gateway_id="g1"))
        await engine.stop()
        self.assertEqual(result.status, ModelGatewayResultStatus.SUCCESS)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class RegistrationTests(unittest.TestCase):
    def test_registers_and_binds(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_model_gateway(container)
        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(
            container.resolve(ModelGatewayEngine), DefaultModelGatewayEngine
        )
        self.assertIsInstance(
            container.resolve(ModelGatewayManager), DefaultModelGatewayManager
        )
        self.assertIsInstance(container.resolve(Collector), DefaultCollector)
        self.assertIsInstance(container.resolve(Planner), DefaultPlanner)
        self.assertIsInstance(
            container.resolve(Dispatcher), DefaultDispatcher
        )
        self.assertIsInstance(
            container.resolve(ModelGatewayRegistry), InMemoryModelGatewayRegistry
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ExceptionTests(unittest.TestCase):
    def test_hierarchy(self) -> None:
        for exc in (CollectionError, RegistryError):
            self.assertTrue(issubclass(exc, ModelGatewayError))


if __name__ == "__main__":
    unittest.main()
