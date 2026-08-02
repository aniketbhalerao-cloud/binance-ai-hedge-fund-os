"""Fakes and helpers for Binance Spot adapter tests.

Standalone support module (existing support files unchanged). Fake transports so
tests never touch the network; deterministic payloads only.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from adapters.binance.client import HttpResponse
from adapters.binance.config import BinanceConfig
from exchange_adapters.models import ExchangeIdentifier, ExchangeRequest
from execution.models import ExecutionIdentifier, ExecutionRequest
from execution.state import ExecutionState
from models import OrderSide, OrderType
from order_management.models import OrderIdentifier, OrderRequest

__all__ = [
    "ORDER_PAYLOAD",
    "FakeHttpTransport",
    "FakeStreamTransport",
    "make_config",
    "make_exchange_request",
]

ORDER_PAYLOAD: dict[str, Any] = {
    "orderId": 123,
    "clientOrderId": "abc",
    "symbol": "BTCUSDT",
    "status": "NEW",
    "executedQty": "0",
}


class FakeHttpTransport:
    """Records requests and returns a canned :class:`HttpResponse`."""

    def __init__(self, status: int = 200, payload: Any = None, *, error: Exception | None = None) -> None:
        self._status = status
        self._payload = payload if payload is not None else ORDER_PAYLOAD
        self._error = error
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HttpResponse:
        self.calls.append((method, url, dict(headers or {})))
        if self._error is not None:
            raise self._error
        return HttpResponse(status=self._status, payload=self._payload)


class FakeStreamTransport:
    """In-memory stream transport for WebSocket tests."""

    def __init__(self, incoming: list[str] | None = None) -> None:
        self._connected = False
        self._incoming = list(incoming or [])
        self.sent: list[str] = []

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self, url: str) -> None:
        self._connected = True

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def receive(self) -> str:
        return self._incoming.pop(0) if self._incoming else ""

    async def close(self) -> None:
        self._connected = False


def make_config(*, creds: bool = True) -> BinanceConfig:
    """Return a BinanceConfig (with or without credentials)."""
    if creds:
        return BinanceConfig(api_key="key", secret_key="secretsecret")
    return BinanceConfig()


def make_exchange_request(
    *,
    exchange: str = "binance",
    symbol: str = "BTCUSDT",
    order_type: OrderType = OrderType.MARKET,
    price: Decimal | None = None,
) -> ExchangeRequest:
    """Build a deterministic ExchangeRequest wrapping a market order."""
    order = OrderRequest(
        identifier=OrderIdentifier(),
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=order_type,
        quantity=Decimal("1"),
        price=price,
    )
    exec_request = ExecutionRequest(
        identifier=ExecutionIdentifier(),
        order_request=order,
        exchange=exchange,
        symbol=symbol,
        state=ExecutionState.READY,
    )
    return ExchangeRequest(
        identifier=ExchangeIdentifier(),
        execution_request=exec_request,
        exchange=exchange,
        symbol=symbol,
    )
