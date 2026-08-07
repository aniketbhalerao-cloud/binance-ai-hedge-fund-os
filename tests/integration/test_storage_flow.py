"""Integration tests for the Storage Framework via the DI container.

Wires the storage engine into a container and runs the store-loop input by
input over normalized source readings. The Registry owns the running record
across calls. No network, no sleeps, no randomness, no model training, and
nothing is ever written, uploaded, or persisted.
"""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from storage import (
    DefaultStorageEngine,
    StorageCompleted,
    StorageRegistry,
    StorageResultStatus,
    register_storage,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.storage_fakes import make_context, make_source


class StorageIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        c = ServiceContainer()
        c.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_storage(c)
        return c

    async def test_store_loop_produces_requests(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultStorageEngine)
        registry = c.resolve(StorageRegistry)
        bus = c.resolve(EventBus)
        done = FakeSubscriber()
        bus.subscribe(StorageCompleted, done.handle)

        result = await engine.store(make_context(storage_id="s1"))

        self.assertEqual(result.status, StorageResultStatus.SUCCESS)
        assert result.metrics is not None
        self.assertTrue(result.requests)
        self.assertEqual(result.metrics.highest_priority_item, "cpu")
        self.assertEqual(result.metrics.lowest_priority_item, "mem")
        self.assertEqual(registry.get("s1").item_count, 2)
        self.assertEqual(len(done.received), 1)

    async def test_record_accumulates_across_inputs(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultStorageEngine)
        registry = c.resolve(StorageRegistry)
        await engine.store(make_context(storage_id="s1"))
        await engine.store(
            make_context(storage_id="s1", monitoring=(make_source("disk", "2"),))
        )
        self.assertEqual(registry.get("s1").item_count, 3)

    async def test_sessions_isolated(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultStorageEngine)
        registry = c.resolve(StorageRegistry)
        await engine.store(make_context(storage_id="a"))
        await engine.store(make_context(storage_id="b"))
        self.assertEqual(len(registry.list()), 2)


if __name__ == "__main__":
    unittest.main()
