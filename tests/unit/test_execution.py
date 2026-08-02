"""Unit tests for the Execution Framework."""

from __future__ import annotations

import dataclasses
import unittest
from decimal import Decimal

from core.container import ServiceContainer
from events.base import Event
from events.bus import EventBus
from execution import (
    DefaultExecutionEngine,
    DefaultExecutionExecutor,
    DefaultExecutionManager,
    DefaultExecutionRouter,
    DefaultExecutionValidator,
    ExecutionCompleted,
    ExecutionEngine,
    ExecutionFailed,
    ExecutionIdentifier,
    ExecutionLifecycle,
    ExecutionManager,
    ExecutionRequest,
    ExecutionStarted,
    ExecutionState,
    ExecutionStatus,
    register_execution,
)
from execution.exceptions import ExecutionError, ExecutionLifecycleError, ExecutionRoutingError
from models import OrderSide, OrderType
from order_management.models import OrderIdentifier, OrderRequest
from tests.support.execution_fakes import (
    FakeExecutionExecutor,
    FakeExecutionRouter,
    FakeExecutionValidator,
    make_execution_context,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber


def _exec_request(**kw: object) -> ExecutionRequest:
    order = OrderRequest(
        identifier=OrderIdentifier(),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
    )
    base = dict(
        identifier=ExecutionIdentifier(),
        order_request=order,
        exchange="sim",
        symbol="BTCUSDT",
    )
    base.update(kw)
    return ExecutionRequest(**base)  # type: ignore[arg-type]


class StateAndLifecycleTests(unittest.TestCase):
    def test_valid_transition_and_invalid(self) -> None:
        lc = ExecutionLifecycle()
        lc.transition(ExecutionState.QUEUED)
        lc.transition(ExecutionState.READY)
        self.assertEqual(lc.current_state(), ExecutionState.READY)
        with self.assertRaises(ExecutionLifecycleError):
            lc.transition(ExecutionState.COMPLETED)  # not reachable from READY


class ModelTests(unittest.TestCase):
    def test_request_is_immutable(self) -> None:
        req = _exec_request()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            req.symbol = "X"  # type: ignore[misc]


class ValidatorTests(unittest.TestCase):
    def test_valid_and_invalid(self) -> None:
        v = DefaultExecutionValidator()
        self.assertTrue(v.validate(_exec_request()).valid)
        self.assertFalse(v.validate(_exec_request(state=ExecutionState.QUEUED)).valid)


class RouterTests(unittest.TestCase):
    def test_default_destination(self) -> None:
        self.assertEqual(DefaultExecutionRouter().route(_exec_request()).destination, "default")


class ExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_produces_ready_result(self) -> None:
        result = await DefaultExecutionExecutor().execute(_exec_request())
        self.assertEqual(result.status, ExecutionStatus.READY)


class EventAndExceptionTests(unittest.TestCase):
    def test_events_inherit_event(self) -> None:
        self.assertIsInstance(ExecutionStarted(execution_id="a", symbol="X"), Event)

    def test_exception_hierarchy(self) -> None:
        self.assertTrue(issubclass(ExecutionRoutingError, ExecutionError))


class ManagerTests(unittest.IsolatedAsyncioTestCase):
    def _manager(self, executor, validator, router) -> tuple[DefaultExecutionManager, EventBus]:
        bus = EventBus()
        manager = DefaultExecutionManager(
            bus, executor, validator, router, logger=FakeLoggerFactory()
        )
        return manager, bus

    async def test_happy_path_ready(self) -> None:
        manager, bus = self._manager(
            DefaultExecutionExecutor(), DefaultExecutionValidator(), DefaultExecutionRouter()
        )
        completed = FakeSubscriber()
        bus.subscribe(ExecutionCompleted, completed.handle)
        result = await manager.process(make_execution_context())
        self.assertTrue(result.ready)
        self.assertEqual(result.state, ExecutionState.READY)
        self.assertEqual(len(completed.received), 1)

    async def test_not_ready_order_fails(self) -> None:
        manager, bus = self._manager(
            DefaultExecutionExecutor(), DefaultExecutionValidator(), DefaultExecutionRouter()
        )
        failed = FakeSubscriber()
        bus.subscribe(ExecutionFailed, failed.handle)
        result = await manager.process(make_execution_context(ready=False))
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertEqual(len(failed.received), 1)

    async def test_validation_failure_isolated(self) -> None:
        manager, bus = self._manager(
            FakeExecutionExecutor(),
            FakeExecutionValidator(valid=False, errors=("bad",)),
            FakeExecutionRouter(),
        )
        result = await manager.process(make_execution_context())
        self.assertEqual(result.status, ExecutionStatus.FAILED)

    async def test_executor_failure_isolated(self) -> None:
        manager, bus = self._manager(
            FakeExecutionExecutor(error=ExecutionError("boom")),
            FakeExecutionValidator(),
            FakeExecutionRouter(),
        )
        result = await manager.process(make_execution_context())
        self.assertEqual(result.status, ExecutionStatus.FAILED)

    async def test_router_failure_isolated(self) -> None:
        manager, bus = self._manager(
            FakeExecutionExecutor(),
            FakeExecutionValidator(),
            FakeExecutionRouter(error=ExecutionRoutingError("no route")),
        )
        result = await manager.process(make_execution_context())
        self.assertEqual(result.status, ExecutionStatus.FAILED)


class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifecycle_and_process(self) -> None:
        bus = EventBus()
        manager = DefaultExecutionManager(
            bus, DefaultExecutionExecutor(), DefaultExecutionValidator(),
            DefaultExecutionRouter(),
        )
        engine = DefaultExecutionEngine(manager, bus)
        result = await engine.process(make_execution_context())
        self.assertTrue(result.ready)
        await engine.start()
        await engine.stop()


class DependencyInjectionTests(unittest.TestCase):
    def test_registration_resolves_singletons(self) -> None:
        container = ServiceContainer()
        register_execution(container)
        engine = container.resolve(DefaultExecutionEngine)
        self.assertIs(container.resolve(DefaultExecutionEngine), engine)
        self.assertIs(container.resolve(ExecutionEngine), engine)
        self.assertIsInstance(container.resolve(ExecutionManager), DefaultExecutionManager)


if __name__ == "__main__":
    unittest.main()
