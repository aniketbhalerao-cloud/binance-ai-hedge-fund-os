"""Integration tests for the Monitoring Framework via the DI container.

Wires the monitoring engine into a container and runs the observe-loop input by
input over normalized component readings. The Registry owns the running record
across calls. No network, no sleeps, no randomness, no model training, and no alert
is ever sent.
"""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from monitoring import (
    DefaultMonitoringEngine,
    MonitoringCompleted,
    MonitoringRegistry,
    MonitoringResultStatus,
    register_monitoring,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.monitoring_fakes import make_component, make_context


class MonitoringIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        c = ServiceContainer()
        c.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_monitoring(c)
        return c

    async def test_observe_loop_produces_alerts(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultMonitoringEngine)
        registry = c.resolve(MonitoringRegistry)
        bus = c.resolve(EventBus)
        done = FakeSubscriber()
        bus.subscribe(MonitoringCompleted, done.handle)

        result = await engine.monitor(make_context(monitoring_id="m1"))

        self.assertEqual(result.status, MonitoringResultStatus.SUCCESS)
        assert result.metrics is not None
        self.assertTrue(result.alerts)
        self.assertEqual(result.metrics.resolved_alerts_count, 0)  # never resolved
        self.assertEqual(result.metrics.best_component, "ema")
        self.assertEqual(result.metrics.worst_component, "rsi")
        self.assertEqual(registry.get("m1").check_count, 2)
        self.assertEqual(len(done.received), 1)

    async def test_record_accumulates_across_inputs(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultMonitoringEngine)
        registry = c.resolve(MonitoringRegistry)
        await engine.monitor(make_context(monitoring_id="m1"))
        await engine.monitor(
            make_context(
                monitoring_id="m1", strategy=(make_component("macd", "2"),)
            )
        )
        self.assertEqual(registry.get("m1").check_count, 3)

    async def test_sessions_isolated(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultMonitoringEngine)
        registry = c.resolve(MonitoringRegistry)
        await engine.monitor(make_context(monitoring_id="a"))
        await engine.monitor(make_context(monitoring_id="b"))
        self.assertEqual(len(registry.list()), 2)


if __name__ == "__main__":
    unittest.main()
