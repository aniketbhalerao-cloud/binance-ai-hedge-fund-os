"""Unit tests for the Exchange Adapter Framework."""

from __future__ import annotations

import dataclasses
import unittest
from decimal import Decimal

from core.container import ServiceContainer
from events.base import Event
from events.bus import EventBus
from exchange_adapters import (
    AuthenticationState,
    ConnectionState,
    DefaultExchangeConnection,
    DefaultExchangeEngine,
    DefaultExchangeManager,
    DefaultExchangeRouter,
    DefaultExchangeValidator,
    ExchangeAdapterRegistered,
    ExchangeAdapterRegistry,
    ExchangeConnectionOpened,
    ExchangeEngine,
    ExchangeManager,
    ExchangeMetadata,
    ExchangeRequest,
    ExchangeStatus,
    register_exchange_adapters,
)
from exchange_adapters.authentication import DefaultExchangeAuthentication
from exchange_adapters.exceptions import DuplicateAdapterError, ExchangeError
from exchange_adapters.models import ExchangeIdentifier
from execution.models import ExecutionIdentifier, ExecutionRequest
from execution.state import ExecutionState
from models import OrderSide, OrderType
from order_management.models import OrderIdentifier, OrderRequest
from tests.support.exchange_fakes import (
    FakeAuthentication,
    FakeConnection,
    FakeExchangeAdapter,
    make_exchange_context,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber


def _exchange_request(**kw: object) -> ExchangeRequest:
    order = OrderRequest(
        identifier=OrderIdentifier(),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
    )
    exec_req = ExecutionRequest(
        identifier=ExecutionIdentifier(),
        order_request=order,
        exchange="sim",
        symbol="BTCUSDT",
        state=ExecutionState.READY,
    )
    base = dict(
        identifier=ExchangeIdentifier(),
        execution_request=exec_req,
        exchange="sim",
        symbol="BTCUSDT",
    )
    base.update(kw)
    return ExchangeRequest(**base)  # type: ignore[arg-type]


class StateTests(unittest.TestCase):
    def test_enums_exist(self) -> None:
        self.assertEqual(AuthenticationState.AUTHENTICATED.value, "authenticated")
        self.assertEqual(ConnectionState.CONNECTED.value, "connected")


class ModelTests(unittest.TestCase):
    def test_request_is_immutable(self) -> None:
        req = _exchange_request()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            req.symbol = "X"  # type: ignore[misc]

    def test_metadata_read_only(self) -> None:
        meta = ExchangeMetadata({"a": 1})
        with self.assertRaises(TypeError):
            meta.data["b"] = 2  # type: ignore[index]


class RegistryTests(unittest.TestCase):
    def test_register_get_list_unregister(self) -> None:
        reg = ExchangeAdapterRegistry()
        adapter = FakeExchangeAdapter("a")
        reg.register(adapter)
        self.assertTrue(reg.exists("a"))
        self.assertIs(reg.get("a"), adapter)
        self.assertEqual(reg.list(), [adapter])
        reg.unregister("a")
        self.assertFalse(reg.exists("a"))

    def test_duplicate_raises(self) -> None:
        reg = ExchangeAdapterRegistry()
        reg.register(FakeExchangeAdapter("a"))
        with self.assertRaises(DuplicateAdapterError):
            reg.register(FakeExchangeAdapter("a"))


class ComponentTests(unittest.IsolatedAsyncioTestCase):
    async def test_auth_and_connection_defaults(self) -> None:
        ctx = make_exchange_context()
        self.assertEqual(
            await DefaultExchangeAuthentication().authenticate(ctx),
            AuthenticationState.AUTHENTICATED,
        )
        conn = DefaultExchangeConnection()
        self.assertEqual(await conn.open(ctx), ConnectionState.CONNECTED)
        self.assertEqual(await conn.close(), ConnectionState.CLOSED)

    def test_validator_and_router(self) -> None:
        self.assertTrue(DefaultExchangeValidator().validate(_exchange_request()).valid)
        route = DefaultExchangeRouter().route(make_exchange_context())
        self.assertEqual(route.adapter_name, "default")


class EventAndExceptionTests(unittest.TestCase):
    def test_events_inherit_event(self) -> None:
        self.assertIsInstance(ExchangeAdapterRegistered(name="a"), Event)

    def test_exception_hierarchy(self) -> None:
        self.assertTrue(issubclass(DuplicateAdapterError, ExchangeError))


class ManagerTests(unittest.IsolatedAsyncioTestCase):
    def _manager(
        self, *, auth=None, conn=None, registry=None
    ) -> tuple[DefaultExchangeManager, EventBus, ExchangeAdapterRegistry]:
        bus = EventBus()
        registry = registry or ExchangeAdapterRegistry()
        manager = DefaultExchangeManager(
            bus,
            auth or DefaultExchangeAuthentication(),
            conn or DefaultExchangeConnection(),
            DefaultExchangeValidator(),
            DefaultExchangeRouter(),
            registry,
            logger=FakeLoggerFactory(),
        )
        return manager, bus, registry

    async def test_ready_without_adapter(self) -> None:
        manager, bus, _ = self._manager()
        opened = FakeSubscriber()
        bus.subscribe(ExchangeConnectionOpened, opened.handle)
        result = await manager.process(make_exchange_context())
        self.assertEqual(result.status, ExchangeStatus.READY)
        self.assertEqual(len(opened.received), 1)

    async def test_adapter_submit_when_registered(self) -> None:
        registry = ExchangeAdapterRegistry()
        adapter = FakeExchangeAdapter("default")
        registry.register(adapter)
        manager, bus, _ = self._manager(registry=registry)
        result = await manager.process(make_exchange_context())
        self.assertEqual(result.status, ExchangeStatus.READY)
        self.assertEqual(len(adapter.submitted), 1)

    async def test_auth_failure_isolated(self) -> None:
        manager, bus, _ = self._manager(
            auth=FakeAuthentication(AuthenticationState.FAILED)
        )
        result = await manager.process(make_exchange_context())
        self.assertEqual(result.status, ExchangeStatus.FAILED)

    async def test_connection_failure_isolated(self) -> None:
        manager, bus, _ = self._manager(conn=FakeConnection(ConnectionState.CLOSED))
        result = await manager.process(make_exchange_context())
        self.assertEqual(result.status, ExchangeStatus.FAILED)

    async def test_not_ready_execution_fails(self) -> None:
        manager, bus, _ = self._manager()
        result = await manager.process(make_exchange_context(ready=False))
        self.assertEqual(result.status, ExchangeStatus.FAILED)

    async def test_adapter_error_isolated(self) -> None:
        registry = ExchangeAdapterRegistry()
        registry.register(FakeExchangeAdapter("default", error=ExchangeError("boom")))
        manager, bus, _ = self._manager(registry=registry)
        result = await manager.process(make_exchange_context())
        self.assertEqual(result.status, ExchangeStatus.FAILED)


class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifecycle_and_process(self) -> None:
        bus = EventBus()
        manager = DefaultExchangeManager(
            bus,
            DefaultExchangeAuthentication(),
            DefaultExchangeConnection(),
            DefaultExchangeValidator(),
            DefaultExchangeRouter(),
            ExchangeAdapterRegistry(),
        )
        engine = DefaultExchangeEngine(manager, bus)
        result = await engine.process(make_exchange_context())
        self.assertTrue(result.ready)
        await engine.start()
        await engine.stop()


class DependencyInjectionTests(unittest.TestCase):
    def test_registration_resolves_singletons(self) -> None:
        container = ServiceContainer()
        register_exchange_adapters(container)
        engine = container.resolve(DefaultExchangeEngine)
        self.assertIs(container.resolve(DefaultExchangeEngine), engine)
        self.assertIs(container.resolve(ExchangeEngine), engine)
        self.assertIsInstance(
            container.resolve(ExchangeManager), DefaultExchangeManager
        )


if __name__ == "__main__":
    unittest.main()
