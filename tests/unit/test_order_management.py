"""Unit tests for the Order Management Framework."""

from __future__ import annotations

import dataclasses
import unittest
from decimal import Decimal

from core.container import ServiceContainer
from events.base import Event
from events.bus import EventBus
from models import OrderSide, OrderType
from order_management import (
    DefaultOrderEngine,
    DefaultOrderFactory,
    DefaultOrderManager,
    DefaultOrderRouter,
    DefaultOrderValidator,
    LimitOrder,
    MarketOrder,
    OrderCreated,
    OrderEngine,
    OrderIdentifier,
    OrderManager,
    OrderReadyForExecution,
    OrderRejected,
    OrderRequest,
    OrderState,
    register_order_management,
)
from order_management.exceptions import OrderError, OrderFactoryError, OrderRoutingError
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.order_fakes import (
    FakeOrderFactory,
    FakeOrderRouter,
    FakeOrderValidator,
    make_order_context,
)


def _request(**kw: object) -> OrderRequest:
    base = dict(
        identifier=OrderIdentifier(),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
    )
    base.update(kw)
    return OrderRequest(**base)  # type: ignore[arg-type]


class ModelTests(unittest.TestCase):
    def test_request_is_immutable(self) -> None:
        req = _request()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            req.quantity = Decimal("2")  # type: ignore[misc]

    def test_standard_order_to_request(self) -> None:
        req = MarketOrder("BTCUSDT", OrderSide.BUY, Decimal("2")).to_request()
        self.assertEqual(req.order_type, OrderType.MARKET)
        self.assertEqual(req.quantity, Decimal("2"))
        lim = LimitOrder("ETHUSDT", OrderSide.SELL, Decimal("1"), Decimal("100")).to_request()
        self.assertEqual(lim.price, Decimal("100"))


class FactoryTests(unittest.TestCase):
    def test_creates_request_from_approved_context(self) -> None:
        req = DefaultOrderFactory().create(make_order_context())
        self.assertEqual(req.side, OrderSide.BUY)
        self.assertEqual(req.state, OrderState.CREATED)

    def test_rejects_unapproved_context(self) -> None:
        with self.assertRaises(OrderFactoryError):
            DefaultOrderFactory().create(make_order_context(approved=False))


class ValidatorTests(unittest.TestCase):
    def test_valid_and_invalid(self) -> None:
        v = DefaultOrderValidator()
        self.assertTrue(v.validate(_request()).valid)
        bad = v.validate(_request(quantity=Decimal("0")))
        self.assertFalse(bad.valid)
        limit_no_price = v.validate(_request(order_type=OrderType.LIMIT))
        self.assertFalse(limit_no_price.valid)


class RouterTests(unittest.TestCase):
    def test_default_destination(self) -> None:
        route = DefaultOrderRouter().route(_request())
        self.assertEqual(route.destination, "default")


class EventAndExceptionTests(unittest.TestCase):
    def test_events_inherit_event(self) -> None:
        self.assertIsInstance(OrderCreated(order_id="a", symbol="X"), Event)

    def test_exception_hierarchy(self) -> None:
        self.assertTrue(issubclass(OrderFactoryError, OrderError))
        self.assertTrue(issubclass(OrderRoutingError, OrderError))


class ManagerTests(unittest.IsolatedAsyncioTestCase):
    def _manager(self, factory, validator, router) -> tuple[DefaultOrderManager, EventBus]:
        bus = EventBus()
        manager = DefaultOrderManager(
            bus, factory, validator, router, logger=FakeLoggerFactory()
        )
        return manager, bus

    async def test_happy_path_ready_for_execution(self) -> None:
        manager, bus = self._manager(
            DefaultOrderFactory(), DefaultOrderValidator(), DefaultOrderRouter()
        )
        ready = FakeSubscriber()
        bus.subscribe(OrderReadyForExecution, ready.handle)
        result = await manager.process(make_order_context())
        self.assertEqual(result.state, OrderState.READY_FOR_EXECUTION)
        self.assertTrue(result.ready)
        self.assertEqual(len(ready.received), 1)

    async def test_validation_failure_returns_rejected(self) -> None:
        manager, bus = self._manager(
            FakeOrderFactory(), FakeOrderValidator(valid=False, errors=("bad",)),
            DefaultOrderRouter(),
        )
        rejected = FakeSubscriber()
        bus.subscribe(OrderRejected, rejected.handle)
        result = await manager.process(make_order_context())
        self.assertEqual(result.state, OrderState.REJECTED)
        self.assertEqual(len(rejected.received), 1)

    async def test_router_failure_is_isolated(self) -> None:
        manager, bus = self._manager(
            FakeOrderFactory(),
            FakeOrderValidator(valid=True),
            FakeOrderRouter(error=OrderRoutingError("no route")),
        )
        result = await manager.process(make_order_context())
        self.assertEqual(result.state, OrderState.REJECTED)  # produced a result, no crash

    async def test_factory_failure_is_isolated(self) -> None:
        manager, bus = self._manager(
            FakeOrderFactory(error=OrderFactoryError("boom")),
            FakeOrderValidator(),
            FakeOrderRouter(),
        )
        result = await manager.process(make_order_context())
        self.assertEqual(result.state, OrderState.REJECTED)
        self.assertIsNone(result.request)


class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifecycle_and_process(self) -> None:
        bus = EventBus()
        manager = DefaultOrderManager(
            bus, DefaultOrderFactory(), DefaultOrderValidator(), DefaultOrderRouter()
        )
        engine = DefaultOrderEngine(manager, bus)
        result = await engine.process(make_order_context())
        self.assertTrue(result.ready)
        await engine.start()
        await engine.stop()


class DependencyInjectionTests(unittest.TestCase):
    def test_registration_resolves_singletons(self) -> None:
        container = ServiceContainer()
        register_order_management(container)
        engine = container.resolve(DefaultOrderEngine)
        self.assertIs(container.resolve(DefaultOrderEngine), engine)
        self.assertIs(container.resolve(OrderEngine), engine)
        self.assertIsInstance(container.resolve(OrderManager), DefaultOrderManager)


if __name__ == "__main__":
    unittest.main()
