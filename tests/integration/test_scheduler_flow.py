"""Integration tests for the Scheduler Framework via the DI container.

Wires the scheduler engine into a container and runs the schedule-loop input
by input over normalized source readings. The Registry owns the running
record across calls. No network, no sleeps, no randomness, no model
training, and nothing is ever executed, run, or triggered.
"""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from scheduler import (
    DefaultSchedulerEngine,
    SchedulerCompleted,
    SchedulerRegistry,
    SchedulerResultStatus,
    register_scheduler,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.scheduler_fakes import make_context, make_source


class SchedulerIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        c = ServiceContainer()
        c.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_scheduler(c)
        return c

    async def test_schedule_loop_produces_requests(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultSchedulerEngine)
        registry = c.resolve(SchedulerRegistry)
        bus = c.resolve(EventBus)
        done = FakeSubscriber()
        bus.subscribe(SchedulerCompleted, done.handle)

        result = await engine.schedule(make_context(scheduler_id="s1"))

        self.assertEqual(result.status, SchedulerResultStatus.SUCCESS)
        assert result.metrics is not None
        self.assertTrue(result.requests)
        self.assertEqual(result.metrics.highest_priority_entry, "cpu")
        self.assertEqual(result.metrics.lowest_priority_entry, "mem")
        self.assertEqual(registry.get("s1").entry_count, 2)
        self.assertEqual(len(done.received), 1)

    async def test_record_accumulates_across_inputs(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultSchedulerEngine)
        registry = c.resolve(SchedulerRegistry)
        await engine.schedule(make_context(scheduler_id="s1"))
        await engine.schedule(
            make_context(scheduler_id="s1", monitoring=(make_source("disk", "2"),))
        )
        self.assertEqual(registry.get("s1").entry_count, 3)

    async def test_sessions_isolated(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultSchedulerEngine)
        registry = c.resolve(SchedulerRegistry)
        await engine.schedule(make_context(scheduler_id="a"))
        await engine.schedule(make_context(scheduler_id="b"))
        self.assertEqual(len(registry.list()), 2)


if __name__ == "__main__":
    unittest.main()
