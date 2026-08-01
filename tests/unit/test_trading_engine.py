"""Unit tests for the trading engine orchestration layer."""

from __future__ import annotations

import unittest

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from trading import (
    EngineAlreadyRunningError,
    EngineInitializationError,
    EngineNotRunningError,
    EngineState,
    LifecycleManager,
    LifecycleTransitionError,
    RuntimeState,
    TradingCoordinator,
    TradingEngine,
    register_trading_engine,
)
from trading.exceptions import ServiceRegistrationError
from trading.lifecycle import EngineFailed, EngineStarted
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber


class _RaisingCoordinator:
    """Coordinator stub whose start_services raises, to test fail-safety."""

    async def start_services(self) -> None:
        raise RuntimeError("boom")

    async def stop_services(self) -> None:  # pragma: no cover - unused
        pass

    def register_service(self, name, service) -> None:  # pragma: no cover
        pass

    def unregister_service(self, name) -> None:  # pragma: no cover
        pass

    async def publish_event(self, event) -> None:
        self.events = getattr(self, "events", [])
        self.events.append(event)


class RuntimeStateTests(unittest.TestCase):
    def test_defaults_and_statistics(self) -> None:
        state = RuntimeState()
        self.assertEqual(state.state, EngineState.CREATED)
        self.assertIsNone(state.started_at)
        self.assertEqual(
            state.statistics(),
            {"orders_processed": 0, "trades_processed": 0, "signals_processed": 0},
        )

    def test_is_immutable(self) -> None:
        import dataclasses

        with self.assertRaises(dataclasses.FrozenInstanceError):
            RuntimeState().state = EngineState.RUNNING  # type: ignore[misc]


class LifecycleManagerTests(unittest.TestCase):
    def test_valid_transition_sequence(self) -> None:
        lm = LifecycleManager()
        self.assertEqual(lm.current_state(), EngineState.CREATED)
        lm.transition(EngineState.INITIALIZING)
        lm.transition(EngineState.STARTING)
        lm.transition(EngineState.RUNNING)
        self.assertTrue(lm.is_running)

    def test_invalid_transition_raises(self) -> None:
        lm = LifecycleManager()
        with self.assertRaises(LifecycleTransitionError):
            lm.transition(EngineState.RUNNING)  # CREATED -> RUNNING is illegal

    def test_can_transition_and_reset(self) -> None:
        lm = LifecycleManager()
        self.assertTrue(lm.can_transition(EngineState.INITIALIZING))
        self.assertFalse(lm.can_transition(EngineState.STOPPED))
        lm.transition(EngineState.INITIALIZING)
        lm.reset()
        self.assertEqual(lm.current_state(), EngineState.CREATED)

    def test_fail_from_any_state(self) -> None:
        lm = LifecycleManager()
        lm.fail()
        self.assertEqual(lm.current_state(), EngineState.FAILED)


class CoordinatorRegistrationTests(unittest.TestCase):
    def test_register_and_reject_duplicate(self) -> None:
        coord = TradingCoordinator(EventBus())

        class _Svc:
            async def start(self) -> None: ...
            async def stop(self) -> None: ...

        coord.register_service("svc", _Svc())
        with self.assertRaises(ServiceRegistrationError):
            coord.register_service("svc", _Svc())
        coord.unregister_service("svc")
        with self.assertRaises(ServiceRegistrationError):
            coord.unregister_service("svc")


class TradingEngineLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def _engine(self, *, logger: FakeLoggerFactory | None = None) -> TradingEngine:
        bus = EventBus()
        coordinator = TradingCoordinator(bus, logger=logger)
        return TradingEngine(coordinator, LifecycleManager(), logger=logger)

    async def test_full_lifecycle(self) -> None:
        engine = self._engine()
        self.assertEqual(engine.state(), EngineState.CREATED)
        await engine.start()
        self.assertEqual(engine.state(), EngineState.RUNNING)
        self.assertTrue(engine.health())
        await engine.pause()
        self.assertEqual(engine.state(), EngineState.PAUSED)
        await engine.resume()
        self.assertEqual(engine.state(), EngineState.RUNNING)
        await engine.stop()
        self.assertEqual(engine.state(), EngineState.STOPPED)

    async def test_double_start_and_stop_guards(self) -> None:
        engine = self._engine()
        await engine.start()
        with self.assertRaises(EngineAlreadyRunningError):
            await engine.start()
        await engine.stop()
        with self.assertRaises(EngineNotRunningError):
            await engine.stop()

    async def test_pause_requires_running(self) -> None:
        engine = self._engine()
        with self.assertRaises(EngineNotRunningError):
            await engine.pause()

    async def test_restart_from_stopped(self) -> None:
        engine = self._engine()
        await engine.start()
        await engine.stop()
        await engine.start()
        self.assertEqual(engine.state(), EngineState.RUNNING)
        await engine.stop()

    async def test_statistics_and_uptime(self) -> None:
        engine = self._engine()
        await engine.start()
        self.assertEqual(engine.statistics()["orders_processed"], 0)
        self.assertGreaterEqual(engine.uptime(), 0.0)
        self.assertIsInstance(engine.status(), RuntimeState)
        await engine.stop()

    async def test_lifecycle_is_logged(self) -> None:
        logger = FakeLoggerFactory()
        engine = self._engine(logger=logger)
        await engine.start()
        await engine.stop()
        messages = logger.logger.messages()
        self.assertIn("Engine started", messages)
        self.assertIn("Engine stopped", messages)

    async def test_failure_is_safe(self) -> None:
        coordinator = _RaisingCoordinator()
        engine = TradingEngine(coordinator, LifecycleManager())
        with self.assertRaises(EngineInitializationError):
            await engine.start()
        self.assertEqual(engine.state(), EngineState.FAILED)
        self.assertIsNotNone(engine.status().last_error)
        self.assertTrue(any(isinstance(e, EngineFailed) for e in coordinator.events))


class DependencyInjectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_registration_resolves_singletons(self) -> None:
        container = ServiceContainer()
        register_trading_engine(container)

        engine = container.resolve(TradingEngine)
        self.assertIs(container.resolve(TradingEngine), engine)
        self.assertIsInstance(container.resolve(LifecycleManager), LifecycleManager)
        self.assertIsInstance(container.resolve(TradingCoordinator), TradingCoordinator)

        subscriber = FakeSubscriber()
        bus = container.resolve(EventBus)
        bus.subscribe(EngineStarted, subscriber.handle)
        await engine.start()
        self.assertTrue(any(isinstance(e, EngineStarted) for e in subscriber.received))
        await engine.stop()


if __name__ == "__main__":
    unittest.main()
