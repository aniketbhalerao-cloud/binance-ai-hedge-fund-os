"""Unit tests for the Strategy Framework."""

from __future__ import annotations

import dataclasses
import unittest

from core.container import ServiceContainer
from events.base import Event
from events.bus import EventBus
from strategies import (
    DefaultStrategyFactory,
    InMemoryStrategyRegistry,
    SignalDirection,
    SignalGenerated,
    StrategyErrorOccurred,
    StrategyExecutionManager,
    StrategyManager,
    StrategyRegistered,
    TradingSignal,
    register_strategies,
)
from strategies.exceptions import (
    DuplicateStrategyError,
    InvalidStrategyError,
    StrategyError,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.strategy_fakes import (
    BuyStrategy,
    FailingStrategy,
    FakeStrategy,
    make_context,
)


class SignalTests(unittest.TestCase):
    def test_confidence_bounds_enforced(self) -> None:
        with self.assertRaises(ValueError):
            TradingSignal(
                id="s",
                strategy_name="x",
                symbol="Y",
                direction=SignalDirection.BUY,
                confidence=1.5,
            )

    def test_signal_is_immutable(self) -> None:
        sig = TradingSignal(
            id="s", strategy_name="x", symbol="Y", direction=SignalDirection.HOLD
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            sig.confidence = 0.1  # type: ignore[misc]


class ContextTests(unittest.TestCase):
    def test_metadata_is_read_only(self) -> None:
        ctx = make_context()
        with self.assertRaises(TypeError):
            ctx.metadata["k"] = "v"  # type: ignore[index]


class RegistryTests(unittest.TestCase):
    def test_lifecycle_operations(self) -> None:
        reg = InMemoryStrategyRegistry()
        strat = FakeStrategy("a")
        reg.register(strat)
        self.assertTrue(reg.exists("a"))
        self.assertEqual(reg.get("a"), strat)
        self.assertEqual(reg.list_enabled(), [])
        reg.enable("a")
        self.assertEqual(reg.list_enabled(), [strat])
        reg.disable("a")
        self.assertEqual(reg.list_enabled(), [])
        reg.unregister("a")
        self.assertFalse(reg.exists("a"))

    def test_duplicate_and_missing_raise(self) -> None:
        reg = InMemoryStrategyRegistry()
        reg.register(FakeStrategy("a"))
        with self.assertRaises(DuplicateStrategyError):
            reg.register(FakeStrategy("a"))
        with self.assertRaises(InvalidStrategyError):
            reg.get("missing")


class FactoryTests(unittest.TestCase):
    def test_creates_via_di_container(self) -> None:
        container = ServiceContainer()
        factory = DefaultStrategyFactory(container)
        strat = factory.create(BuyStrategy)
        self.assertEqual(strat.name, "buy")


class EventAndExceptionTests(unittest.TestCase):
    def test_events_inherit_event(self) -> None:
        self.assertIsInstance(StrategyRegistered(name="a"), Event)

    def test_exception_hierarchy(self) -> None:
        self.assertTrue(issubclass(DuplicateStrategyError, StrategyError))
        self.assertTrue(issubclass(InvalidStrategyError, StrategyError))


class ManagerTests(unittest.IsolatedAsyncioTestCase):
    def _manager(
        self,
    ) -> tuple[StrategyExecutionManager, EventBus, InMemoryStrategyRegistry]:
        bus = EventBus()
        registry = InMemoryStrategyRegistry()
        factory = DefaultStrategyFactory(ServiceContainer())
        manager = StrategyExecutionManager(
            bus, registry, factory, logger=FakeLoggerFactory()
        )
        return manager, bus, registry

    async def test_executes_enabled_and_publishes_signals(self) -> None:
        manager, bus, registry = self._manager()
        signals_seen = FakeSubscriber()
        bus.subscribe(SignalGenerated, signals_seen.handle)

        enabled = FakeStrategy("on", SignalDirection.BUY)
        disabled = FakeStrategy("off", SignalDirection.SELL)
        await manager.register(enabled)
        await manager.register(disabled)
        await manager.enable("on")

        signals = await manager.execute(make_context())

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].direction, SignalDirection.BUY)
        self.assertEqual(len(signals_seen.received), 1)
        self.assertEqual(disabled.evaluate_calls, 0)  # disabled not executed

    async def test_failure_is_isolated(self) -> None:
        manager, bus, registry = self._manager()
        errors = FakeSubscriber()
        bus.subscribe(StrategyErrorOccurred, errors.handle)

        await manager.register(FailingStrategy("boom"))
        await manager.register(FakeStrategy("ok"))
        await manager.enable("boom")
        await manager.enable("ok")

        signals = await manager.execute(make_context())

        self.assertEqual(len(signals), 1)  # the healthy strategy still ran
        self.assertEqual(len(errors.received), 1)

    async def test_registration_publishes_event(self) -> None:
        manager, bus, registry = self._manager()
        registered = FakeSubscriber()
        bus.subscribe(StrategyRegistered, registered.handle)
        await manager.register(FakeStrategy("a"))
        self.assertEqual(len(registered.received), 1)


class DependencyInjectionTests(unittest.TestCase):
    def test_registration_resolves_singleton(self) -> None:
        container = ServiceContainer()
        register_strategies(container)
        manager = container.resolve(StrategyExecutionManager)
        self.assertIs(container.resolve(StrategyExecutionManager), manager)
        self.assertIs(container.resolve(StrategyManager), manager)


if __name__ == "__main__":
    unittest.main()
