"""Integration tests for the Memory Framework via the DI container.

Wires the memory engine into a container and runs the remember-loop input by
input over normalized source readings. The Registry owns the running record
across calls. No network, no sleeps, no randomness, no model training, and
nothing is ever embedded, persisted, or sent to a vector store.
"""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from memory import (
    DefaultMemoryEngine,
    MemoryCompleted,
    MemoryRegistry,
    MemoryResultStatus,
    register_memory,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.memory_fakes import make_context, make_source


class MemoryIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        c = ServiceContainer()
        c.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_memory(c)
        return c

    async def test_remember_loop_produces_requests(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultMemoryEngine)
        registry = c.resolve(MemoryRegistry)
        bus = c.resolve(EventBus)
        done = FakeSubscriber()
        bus.subscribe(MemoryCompleted, done.handle)

        result = await engine.remember(make_context(memory_id="m1"))

        self.assertEqual(result.status, MemoryResultStatus.SUCCESS)
        assert result.metrics is not None
        self.assertTrue(result.requests)
        self.assertEqual(result.metrics.highest_priority_entry, "cpu")
        self.assertEqual(result.metrics.lowest_priority_entry, "mem")
        self.assertEqual(registry.get("m1").entry_count, 2)
        self.assertEqual(len(done.received), 1)

    async def test_record_accumulates_across_inputs(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultMemoryEngine)
        registry = c.resolve(MemoryRegistry)
        await engine.remember(make_context(memory_id="m1"))
        await engine.remember(
            make_context(memory_id="m1", learning=(make_source("disk", "2"),))
        )
        self.assertEqual(registry.get("m1").entry_count, 3)

    async def test_sessions_isolated(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultMemoryEngine)
        registry = c.resolve(MemoryRegistry)
        await engine.remember(make_context(memory_id="a"))
        await engine.remember(make_context(memory_id="b"))
        self.assertEqual(len(registry.list()), 2)


if __name__ == "__main__":
    unittest.main()
