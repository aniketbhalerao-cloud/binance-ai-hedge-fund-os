"""Integration tests for the Reporting Framework via the DI container.

Wires the reporting engine into a container and runs the report-loop input by
input over normalized source readings. The Registry owns the running record
across calls. No network, no sleeps, no randomness, no model training, and
nothing is ever saved, written to a file, or sent.
"""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from reporting import (
    DefaultReportingEngine,
    ReportingCompleted,
    ReportingRegistry,
    ReportingResultStatus,
    register_reporting,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.reporting_fakes import make_context, make_source


class ReportingIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        c = ServiceContainer()
        c.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_reporting(c)
        return c

    async def test_report_loop_produces_exports(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultReportingEngine)
        registry = c.resolve(ReportingRegistry)
        bus = c.resolve(EventBus)
        done = FakeSubscriber()
        bus.subscribe(ReportingCompleted, done.handle)

        result = await engine.report(make_context(reporting_id="r1"))

        self.assertEqual(result.status, ReportingResultStatus.SUCCESS)
        assert result.metrics is not None
        self.assertTrue(result.exports)
        self.assertEqual(result.metrics.highest_priority_report, "cpu")
        self.assertEqual(result.metrics.lowest_priority_report, "mem")
        self.assertEqual(registry.get("r1").report_count, 2)
        self.assertEqual(len(done.received), 1)

    async def test_record_accumulates_across_inputs(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultReportingEngine)
        registry = c.resolve(ReportingRegistry)
        await engine.report(make_context(reporting_id="r1"))
        await engine.report(
            make_context(reporting_id="r1", monitoring=(make_source("disk", "2"),))
        )
        self.assertEqual(registry.get("r1").report_count, 3)

    async def test_sessions_isolated(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultReportingEngine)
        registry = c.resolve(ReportingRegistry)
        await engine.report(make_context(reporting_id="a"))
        await engine.report(make_context(reporting_id="b"))
        self.assertEqual(len(registry.list()), 2)


if __name__ == "__main__":
    unittest.main()
