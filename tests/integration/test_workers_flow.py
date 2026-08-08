"""Integration tests for the Background Workers Framework via the DI container.

Wires the worker engine into a container and runs the enqueue-loop input by
input over normalized source readings. The Registry owns the running record
across calls. No network, no sleeps, no randomness, no model training, and
nothing is ever executed, run, or triggered.
"""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.workers_fakes import make_context, make_source
from workers import (
    DefaultWorkerEngine,
    WorkerCompleted,
    WorkerRegistry,
    WorkerResultStatus,
    register_workers,
)


class WorkersIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        c = ServiceContainer()
        c.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_workers(c)
        return c

    async def test_enqueue_loop_produces_requests(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultWorkerEngine)
        registry = c.resolve(WorkerRegistry)
        bus = c.resolve(EventBus)
        done = FakeSubscriber()
        bus.subscribe(WorkerCompleted, done.handle)

        result = await engine.enqueue(make_context(worker_id="w1"))

        self.assertEqual(result.status, WorkerResultStatus.SUCCESS)
        assert result.metrics is not None
        self.assertTrue(result.requests)
        self.assertEqual(result.metrics.highest_priority_job, "cpu")
        self.assertEqual(result.metrics.lowest_priority_job, "mem")
        self.assertEqual(registry.get("w1").job_count, 2)
        self.assertEqual(len(done.received), 1)

    async def test_record_accumulates_across_inputs(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultWorkerEngine)
        registry = c.resolve(WorkerRegistry)
        await engine.enqueue(make_context(worker_id="w1"))
        await engine.enqueue(
            make_context(worker_id="w1", monitoring=(make_source("disk", "2"),))
        )
        self.assertEqual(registry.get("w1").job_count, 3)

    async def test_sessions_isolated(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultWorkerEngine)
        registry = c.resolve(WorkerRegistry)
        await engine.enqueue(make_context(worker_id="a"))
        await engine.enqueue(make_context(worker_id="b"))
        self.assertEqual(len(registry.list()), 2)


if __name__ == "__main__":
    unittest.main()
