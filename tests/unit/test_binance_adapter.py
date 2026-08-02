"""Unit tests for the Binance Spot adapter."""

from __future__ import annotations

import unittest
from decimal import Decimal

from adapters.binance import (
    BinanceAuthentication,
    BinanceConfig,
    BinanceConnection,
    BinanceError,
    BinanceRequestTranslator,
    BinanceRequestValidator,
    BinanceResponseParser,
    BinanceRESTClient,
    BinanceSigner,
    BinanceSpotAdapter,
    BinanceWebSocketClient,
    register_binance_adapter,
)
from adapters.binance.errors import (
    BinanceAuthenticationError,
    BinanceRateLimitError,
    BinanceRequestError,
    translate_http_error,
)
from adapters.binance.events import BinanceConnected, BinanceOrderSubmitted
from adapters.binance.models import BinanceOrderType, BinanceSide
from adapters.binance.requests import BinanceOrderRequest
from adapters.binance.routes import ORDER
from core.container import ServiceContainer
from events.base import Event
from events.bus import EventBus
from exchange_adapters.exceptions import ExchangeError
from tests.support.binance_fakes import (
    ORDER_PAYLOAD,
    FakeHttpTransport,
    FakeStreamTransport,
    make_config,
    make_exchange_request,
)
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber


class SignerAuthTests(unittest.TestCase):
    def test_sign_is_deterministic_hex(self) -> None:
        s = BinanceSigner()
        sig = s.sign("symbol=BTCUSDT", "secret")
        self.assertEqual(sig, s.sign("symbol=BTCUSDT", "secret"))
        self.assertEqual(len(sig), 64)

    def test_build_query_omits_none(self) -> None:
        self.assertEqual(BinanceSigner().build_query({"a": 1, "b": None}), "a=1")

    def test_sign_request_adds_signature(self) -> None:
        auth = BinanceAuthentication(make_config(), BinanceSigner())
        signed = auth.sign_request({"symbol": "BTCUSDT"})
        self.assertIn("signature", signed)
        self.assertIn("timestamp", signed)

    def test_missing_credentials_raise(self) -> None:
        auth = BinanceAuthentication(make_config(creds=False), BinanceSigner())
        self.assertFalse(auth.validate_credentials())
        with self.assertRaises(BinanceAuthenticationError):
            auth.authenticate()


class ConfigTests(unittest.TestCase):
    def test_secret_not_in_repr(self) -> None:
        cfg = BinanceConfig(api_key="k", secret_key="topsecret")
        self.assertNotIn("topsecret", repr(cfg))
        self.assertTrue(cfg.masked_secret().startswith("***"))


class ErrorTests(unittest.TestCase):
    def test_translate_http_error(self) -> None:
        self.assertIsInstance(translate_http_error(429), BinanceRateLimitError)
        self.assertIsInstance(translate_http_error(401), BinanceAuthenticationError)
        self.assertIsInstance(translate_http_error(400), BinanceRequestError)

    def test_binance_error_is_framework_error(self) -> None:
        self.assertTrue(issubclass(BinanceError, ExchangeError))


class TranslatorValidatorParserTests(unittest.TestCase):
    def test_translate_market_order(self) -> None:
        req = BinanceRequestTranslator().translate(make_exchange_request())
        self.assertEqual(req.side, BinanceSide.BUY)
        self.assertEqual(req.type, BinanceOrderType.MARKET)

    def test_validator_flags_bad_quantity(self) -> None:
        bad = BinanceOrderRequest(
            symbol="BTCUSDT",
            side=BinanceSide.BUY,
            type=BinanceOrderType.MARKET,
            quantity=Decimal("0"),
        )
        self.assertTrue(BinanceRequestValidator().validate(bad))

    def test_parser_standardizes(self) -> None:
        parser = BinanceResponseParser()
        order = parser.parse_order(ORDER_PAYLOAD)
        resp = parser.to_exchange_response(order)
        self.assertTrue(resp.accepted)
        self.assertEqual(resp.metadata.get("order_id"), "123")


class RestClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_signed_post_sends_apikey_and_returns_payload(self) -> None:
        bus = EventBus()
        transport = FakeHttpTransport()
        rest = BinanceRESTClient(
            transport,
            make_config(),
            BinanceAuthentication(make_config(), BinanceSigner()),
            bus,
            logger=FakeLoggerFactory(),
        )
        payload = await rest.post(ORDER, {"symbol": "BTCUSDT"})
        self.assertEqual(payload, ORDER_PAYLOAD)
        method, url, headers = transport.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("signature=", url)
        self.assertEqual(headers.get("X-MBX-APIKEY"), "key")

    async def test_error_status_translates(self) -> None:
        rest = BinanceRESTClient(
            FakeHttpTransport(status=429, payload={"msg": "too many"}),
            make_config(),
            BinanceAuthentication(make_config(), BinanceSigner()),
            EventBus(),
        )
        with self.assertRaises(BinanceRateLimitError):
            await rest.post(ORDER, {"symbol": "BTCUSDT"})


class WebSocketConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_ws_connect_subscribe_reconnect(self) -> None:
        stream = FakeStreamTransport()
        ws = BinanceWebSocketClient(stream, make_config(), EventBus())
        await ws.connect()
        self.assertTrue(ws.connected)
        await ws.subscribe("btcusdt@trade")
        await ws.reconnect(attempt=1)
        self.assertIn('"SUBSCRIBE"', "".join(stream.sent))

    async def test_connection_lifecycle_events(self) -> None:
        bus = EventBus()
        conn = BinanceConnection(bus)
        seen = FakeSubscriber()
        bus.subscribe(BinanceConnected, seen.handle)
        await conn.connect()
        await conn.reconnect()
        await conn.close()
        self.assertGreaterEqual(len(seen.received), 2)


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    def _adapter(
        self, *, transport: FakeHttpTransport | None = None, creds: bool = True
    ) -> tuple[BinanceSpotAdapter, EventBus]:
        bus = EventBus()
        config = make_config(creds=creds)
        auth = BinanceAuthentication(config, BinanceSigner())
        rest = BinanceRESTClient(transport or FakeHttpTransport(), config, auth, bus)
        adapter = BinanceSpotAdapter(
            auth,
            BinanceConnection(bus),
            rest,
            BinanceRequestTranslator(),
            BinanceRequestValidator(),
            BinanceResponseParser(),
            bus,
            config,
            logger=FakeLoggerFactory(),
        )
        return adapter, bus

    async def test_submit_returns_accepted_response(self) -> None:
        adapter, bus = self._adapter()
        submitted = FakeSubscriber()
        bus.subscribe(BinanceOrderSubmitted, submitted.handle)
        response = await adapter.submit(make_exchange_request())
        self.assertTrue(response.accepted)
        self.assertEqual(len(submitted.received), 1)

    async def test_submit_without_credentials_raises(self) -> None:
        adapter, bus = self._adapter(creds=False)
        with self.assertRaises(BinanceAuthenticationError):
            await adapter.submit(make_exchange_request())

    async def test_cancel_order(self) -> None:
        adapter, bus = self._adapter()
        response = await adapter.cancel_order("BTCUSDT", "123")
        self.assertTrue(response.accepted)

    async def test_get_account(self) -> None:
        transport = FakeHttpTransport(
            payload={
                "canTrade": True,
                "balances": [{"asset": "USDT", "free": "100", "locked": "0"}],
            }
        )
        adapter, bus = self._adapter(transport=transport)
        account = await adapter.get_account()
        self.assertTrue(account.can_trade)
        self.assertEqual(account.balances[0].asset, "USDT")


class EventTests(unittest.TestCase):
    def test_events_inherit_event(self) -> None:
        self.assertIsInstance(BinanceOrderSubmitted(symbol="X", order_id="1"), Event)


class DependencyInjectionTests(unittest.TestCase):
    def test_registration_resolves_adapter(self) -> None:
        container = ServiceContainer()
        register_binance_adapter(
            container, make_config(), transport=FakeHttpTransport()
        )
        adapter = container.resolve(BinanceSpotAdapter)
        self.assertIs(container.resolve(BinanceSpotAdapter), adapter)
        self.assertIsInstance(container.resolve(BinanceRESTClient), BinanceRESTClient)


if __name__ == "__main__":
    unittest.main()
