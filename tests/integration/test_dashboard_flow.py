"""Integration tests for the Dashboard Framework via the DI container.

Wires the dashboard engine into a container and runs the render-loop input by input
over normalized source readings. The Registry owns the running record across calls.
No network, no sleeps, no randomness, no model training, and nothing is ever
rendered to a real display.
"""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from dashboard import (
    DashboardCompleted,
    DashboardRegistry,
    DashboardResultStatus,
    DefaultDashboardEngine,
    register_dashboard,
)
from events.bus import EventBus
from tests.support.dashboard_fakes import make_context, make_source
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber


class DashboardIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        c = ServiceContainer()
        c.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_dashboard(c)
        return c

    async def test_render_loop_produces_widgets(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultDashboardEngine)
        registry = c.resolve(DashboardRegistry)
        bus = c.resolve(EventBus)
        done = FakeSubscriber()
        bus.subscribe(DashboardCompleted, done.handle)

        result = await engine.render(make_context(dashboard_id="d1"))

        self.assertEqual(result.status, DashboardResultStatus.SUCCESS)
        assert result.metrics is not None
        self.assertTrue(result.widgets)
        self.assertEqual(result.metrics.best_panel, "ema")
        self.assertEqual(result.metrics.worst_panel, "rsi")
        self.assertEqual(registry.get("d1").panel_count, 2)
        self.assertEqual(len(done.received), 1)

    async def test_record_accumulates_across_inputs(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultDashboardEngine)
        registry = c.resolve(DashboardRegistry)
        await engine.render(make_context(dashboard_id="d1"))
        await engine.render(
            make_context(dashboard_id="d1", strategy=(make_source("macd", "2"),))
        )
        self.assertEqual(registry.get("d1").panel_count, 3)

    async def test_sessions_isolated(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultDashboardEngine)
        registry = c.resolve(DashboardRegistry)
        await engine.render(make_context(dashboard_id="a"))
        await engine.render(make_context(dashboard_id="b"))
        self.assertEqual(len(registry.list()), 2)


if __name__ == "__main__":
    unittest.main()
