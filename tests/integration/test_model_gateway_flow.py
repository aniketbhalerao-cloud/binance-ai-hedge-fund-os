"""Integration tests for the Model Provider Gateway Framework via the DI container.

Wires the model gateway engine into a container and runs the invoke-loop
input by input over normalized source readings and declared provider
profiles. The Registry owns the running record across calls. No network, no
sleeps, no randomness, no model training, no AI provider call, and no
credential material anywhere.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from model_gateway import (
    DefaultModelGatewayEngine,
    ModelGatewayCompleted,
    ModelGatewayRegistry,
    ModelGatewayResultStatus,
    register_model_gateway,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.model_gateway_fakes import make_context, make_profile, make_source


class ModelGatewayIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _container(self) -> ServiceContainer:
        c = ServiceContainer()
        c.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_model_gateway(c)
        return c

    async def test_invoke_loop_produces_requests(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultModelGatewayEngine)
        registry = c.resolve(ModelGatewayRegistry)
        bus = c.resolve(EventBus)
        done = FakeSubscriber()
        bus.subscribe(ModelGatewayCompleted, done.handle)

        result = await engine.invoke(make_context(model_gateway_id="g1"))

        self.assertEqual(result.status, ModelGatewayResultStatus.SUCCESS)
        assert result.metrics is not None
        self.assertTrue(result.requests)
        self.assertEqual(result.metrics.highest_priority_entry, "cpu")
        self.assertEqual(result.metrics.lowest_priority_entry, "mem")
        self.assertEqual(registry.get("g1").entry_count, 2)
        self.assertEqual(len(done.received), 1)

    async def test_record_accumulates_across_inputs(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultModelGatewayEngine)
        registry = c.resolve(ModelGatewayRegistry)
        await engine.invoke(make_context(model_gateway_id="g1"))
        await engine.invoke(
            make_context(model_gateway_id="g1", learning=(make_source("disk", "2"),))
        )
        self.assertEqual(registry.get("g1").entry_count, 3)

    async def test_sessions_isolated(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultModelGatewayEngine)
        registry = c.resolve(ModelGatewayRegistry)
        await engine.invoke(make_context(model_gateway_id="a"))
        await engine.invoke(make_context(model_gateway_id="b"))
        self.assertEqual(len(registry.list()), 2)

    async def test_end_to_end_routing_through_full_pipeline(self) -> None:
        c = self._container()
        engine = c.resolve(DefaultModelGatewayEngine)
        source = make_source(
            "analysis", "8", source="agents", required_capabilities=("text",)
        )
        profiles = (
            make_profile("a", "m1", capabilities=("text",), priority="1", cost="5"),
            make_profile("b", "m1", capabilities=("text",), priority="9", cost="1"),
        )
        result = await engine.invoke(
            make_context(
                model_gateway_id="g1",
                agent=(source,),
                learning=(),
                provider_profiles=profiles,
            )
        )
        self.assertEqual(result.status, ModelGatewayResultStatus.SUCCESS)
        self.assertEqual(len(result.requests), 1)
        request = result.requests[0]
        self.assertEqual(request.provider_id, "b")  # higher priority wins
        self.assertEqual(request.cost, Decimal("1"))
        self.assertEqual(request.capabilities, ("text",))


if __name__ == "__main__":
    unittest.main()
