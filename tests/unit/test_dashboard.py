"""Unit tests for the Dashboard Framework (stdlib unittest, deterministic)."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from dashboard import (
    Aggregator,
    Composer,
    DashboardCancelled,
    DashboardCompleted,
    DashboardEngine,
    DashboardError,
    DashboardEvent,
    DashboardManager,
    DashboardParameters,
    DashboardRegistry,
    DashboardResultStatus,
    DefaultAggregator,
    DefaultComposer,
    DefaultDashboardEngine,
    DefaultDashboardManager,
    DefaultDashboardMetrics,
    DefaultWidgets,
    InMemoryDashboardRegistry,
    WidgetGenerator,
    register_dashboard,
)
from dashboard.events import DashboardErrorOccurred
from dashboard.exceptions import AggregationError, RegistryError
from dashboard.models import (
    DashboardRecord,
    DashboardSource,
    DashboardView,
    Panel,
)
from dashboard.state import VALID_TRANSITIONS, DashboardState, can_transition
from events.bus import EventBus
from tests.support.dashboard_fakes import make_context, make_source
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber

_ZERO = Decimal("0")
_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _manager(bus: EventBus, **overrides: object) -> DefaultDashboardManager:
    return DefaultDashboardManager(
        bus,
        InMemoryDashboardRegistry(),
        overrides.get("aggregator", DefaultAggregator()),  # type: ignore[arg-type]
        DefaultComposer(),
        DefaultWidgets(),
        DefaultDashboardMetrics(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# State & models
# ---------------------------------------------------------------------------
class StateModelTests(unittest.TestCase):
    def test_transitions(self) -> None:
        self.assertTrue(
            can_transition(DashboardState.CREATED, DashboardState.AGGREGATING)
        )
        self.assertTrue(
            can_transition(DashboardState.COMPOSED, DashboardState.COMPOSED)
        )
        self.assertEqual(VALID_TRANSITIONS[DashboardState.COMPLETED], frozenset())

    def test_history_append_immutable(self) -> None:
        from dashboard.models import DashboardHistory

        history = DashboardHistory()
        new = history.append(DashboardView())
        self.assertEqual(len(history.views), 0)
        self.assertEqual(len(new.views), 1)


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------
class AggregatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.aggregator = DefaultAggregator()

    def test_aggregates_worst_first_across_sources(self) -> None:
        view = self.aggregator.aggregate(
            make_context(
                strategy=(make_source("ema", "5"),),
                monitoring=(make_source("cpu", "-3", source="monitoring"),),
            )
        )
        self.assertEqual(view.sources[0].name, "cpu")  # worst first
        self.assertEqual(len(view.panels), 2)

    def test_max_panels_caps(self) -> None:
        strategy = tuple(make_source(f"s{i}", str(i)) for i in range(10))
        view = self.aggregator.aggregate(
            make_context(
                strategy=strategy, parameters=DashboardParameters(max_panels=3)
            )
        )
        self.assertEqual(len(view.sources), 3)


# ---------------------------------------------------------------------------
# Composer & Widgets
# ---------------------------------------------------------------------------
class ComposerWidgetTests(unittest.TestCase):
    def _view(self) -> DashboardView:
        s_ok = DashboardSource(name="ema", source="strategy", score=Decimal("5"))
        s_bad = DashboardSource(name="rsi", source="strategy", score=Decimal("-3"))
        return DashboardView(
            sources=(s_ok, s_bad),
            panels=(Panel(source=s_ok), Panel(source=s_bad)),
        )

    def test_composer_resolves_visibility(self) -> None:
        composed = DefaultComposer().compose(self._view(), make_context())
        visible = {p.source.name: p.visible for p in composed.panels}
        self.assertTrue(visible["ema"])
        self.assertFalse(visible["rsi"])

    def test_widgets_only_for_visible(self) -> None:
        composed = DefaultComposer().compose(self._view(), make_context())
        widgets = DefaultWidgets().generate(composed, make_context())
        self.assertEqual(len(widgets), 1)
        self.assertEqual(widgets[0].subject, "ema")
        self.assertEqual(widgets[0].section, "strategy")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class MetricsTests(unittest.TestCase):
    def test_best_worst_coverage_and_hidden(self) -> None:
        s_best = DashboardSource(name="ema", source="strategy", score=Decimal("5"))
        s_worst = DashboardSource(name="rsi", source="strategy", score=Decimal("-3"))
        view = DashboardView(
            sources=(s_best, s_worst),
            panels=(
                Panel(source=s_best, visible=True),
                Panel(source=s_worst, visible=False),
            ),
        )
        from dashboard.models import Widget

        record = DashboardRecord(
            id="d1", state=DashboardState.COMPOSED, view=view,
            widgets=(Widget(subject="ema", source="strategy", section="strategy"),),
            panel_count=2, widget_count=1,
        )
        metrics = DefaultDashboardMetrics().calculate(record)
        self.assertEqual(metrics.best_panel, "ema")
        self.assertEqual(metrics.worst_panel, "rsi")
        self.assertEqual(metrics.visible_widgets_count, 1)
        self.assertEqual(metrics.hidden_widgets_count, 1)
        self.assertEqual(metrics.coverage_ratio, Decimal("0.5"))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = InMemoryDashboardRegistry()
        self.record = DashboardRecord(id="d1", state=DashboardState.AGGREGATING)

    def test_register_and_get(self) -> None:
        self.registry.register(self.record)
        self.assertTrue(self.registry.exists("d1"))
        self.assertEqual(self.registry.get("d1"), self.record)
        self.assertEqual(self.registry.list(), [self.record])

    def test_get_missing_raises(self) -> None:
        with self.assertRaises(RegistryError):
            self.registry.get("nope")

    def test_unregister_and_clear(self) -> None:
        self.registry.register(self.record)
        self.registry.unregister("d1")
        self.assertFalse(self.registry.exists("d1"))
        self.registry.register(self.record)
        self.registry.clear()
        self.assertEqual(self.registry.list(), [])


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_renders_and_accumulates(self) -> None:
        bus = EventBus()
        completed = FakeSubscriber()
        bus.subscribe(DashboardCompleted, completed.handle)
        manager = _manager(bus)

        first = await manager.render(make_context(dashboard_id="d1"))
        second = await manager.render(make_context(dashboard_id="d1"))

        self.assertEqual(second.status, DashboardResultStatus.SUCCESS)
        assert second.record is not None and second.metrics is not None
        self.assertEqual(second.record.panel_count, 4)  # 2 panels per input
        self.assertTrue(second.widgets)  # ema visible
        self.assertEqual(second.metrics.hidden_widgets_count, 1)  # rsi hidden
        self.assertEqual(len(completed.received), 2)
        self.assertEqual(first.metrics.total_widgets, 1)  # type: ignore[union-attr]

    async def test_cancellation(self) -> None:
        bus = EventBus()
        cancelled = FakeSubscriber()
        bus.subscribe(DashboardCancelled, cancelled.handle)
        manager = _manager(bus)
        result = await manager.render(make_context(dashboard_id="d1", cancel=True))
        self.assertEqual(result.status, DashboardResultStatus.CANCELLED)
        self.assertEqual(len(cancelled.received), 1)

    async def test_terminal_rejected(self) -> None:
        manager = _manager(EventBus())
        await manager.render(make_context(dashboard_id="d1", cancel=True))
        result = await manager.render(make_context(dashboard_id="d1"))
        self.assertEqual(result.status, DashboardResultStatus.FAILED)

    async def test_error_isolated(self) -> None:
        class _Boom:
            def aggregate(self, context: object) -> object:
                raise AggregationError("boom")

        bus = EventBus()
        errors = FakeSubscriber()
        bus.subscribe(DashboardErrorOccurred, errors.handle)
        manager = _manager(bus, aggregator=_Boom())
        result = await manager.render(make_context(dashboard_id="d1"))
        self.assertEqual(result.status, DashboardResultStatus.FAILED)
        self.assertEqual(len(errors.received), 1)

    async def test_events_published(self) -> None:
        bus = EventBus()
        allev = FakeSubscriber()
        bus.subscribe(DashboardEvent, allev.handle)
        manager = _manager(bus)
        await manager.render(make_context(dashboard_id="d1"))
        names = [type(e).__name__ for e in allev.received]
        self.assertEqual(names[0], "DashboardStarted")
        self.assertIn("DashboardViewCreated", names)
        self.assertIn("WidgetsGenerated", names)
        self.assertIn("DashboardCompleted", names)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_delegates(self) -> None:
        engine = DefaultDashboardEngine(
            _manager(EventBus()), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        result = await engine.render(make_context(dashboard_id="d1"))
        await engine.stop()
        self.assertEqual(result.status, DashboardResultStatus.SUCCESS)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class RegistrationTests(unittest.TestCase):
    def test_registers_and_binds(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_dashboard(container)
        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(
            container.resolve(DashboardEngine), DefaultDashboardEngine
        )
        self.assertIsInstance(
            container.resolve(DashboardManager), DefaultDashboardManager
        )
        self.assertIsInstance(container.resolve(Aggregator), DefaultAggregator)
        self.assertIsInstance(container.resolve(Composer), DefaultComposer)
        self.assertIsInstance(container.resolve(WidgetGenerator), DefaultWidgets)
        self.assertIsInstance(
            container.resolve(DashboardRegistry), InMemoryDashboardRegistry
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ExceptionTests(unittest.TestCase):
    def test_hierarchy(self) -> None:
        for exc in (AggregationError, RegistryError):
            self.assertTrue(issubclass(exc, DashboardError))


if __name__ == "__main__":
    unittest.main()
