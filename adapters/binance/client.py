"""Low-level transport abstractions for the Binance adapter.

The REST and WebSocket clients depend on these transport *protocols* rather than
a concrete HTTP/WS library, so tests inject fakes and no live network call is
ever made from the framework or tests. A default stdlib HTTP transport is
provided for real use (no third-party dependency); the default stream transport
is a stub, since the stdlib ships no WebSocket client — a real one is injected
in production.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from urllib import error as urllib_error
from urllib import request as urllib_request

from adapters.binance.errors import BinanceConnectionError, BinanceTimeoutError

__all__ = [
    "HttpResponse",
    "HttpTransport",
    "StreamTransport",
    "UrllibHttpTransport",
    "NullStreamTransport",
]


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """A transport-level HTTP response (payload already JSON-decoded)."""

    status: int
    payload: Any = None


@runtime_checkable
class HttpTransport(Protocol):
    """Sends a single HTTP request and returns an :class:`HttpResponse`."""

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HttpResponse: ...


@runtime_checkable
class StreamTransport(Protocol):
    """A bidirectional message stream (WebSocket abstraction)."""

    @property
    def connected(self) -> bool: ...
    async def connect(self, url: str) -> None: ...
    async def send(self, message: str) -> None: ...
    async def receive(self) -> str: ...
    async def close(self) -> None: ...


class UrllibHttpTransport:
    """Default HTTP transport over the standard library (``urllib``).

    Runs the blocking request in a worker thread so it stays awaitable. Used only
    when a real transport is not injected; tests inject a fake instead.
    """

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HttpResponse:
        def _send() -> HttpResponse:
            req = urllib_request.Request(url, method=method, headers=dict(headers or {}))
            try:
                with urllib_request.urlopen(req, timeout=timeout) as resp:
                    body = resp.read().decode("utf-8")
                    payload = json.loads(body) if body else None
                    return HttpResponse(status=resp.status, payload=payload)
            except urllib_error.HTTPError as exc:  # 4xx/5xx
                body = exc.read().decode("utf-8") if exc.fp else ""
                payload = json.loads(body) if body else None
                return HttpResponse(status=exc.code, payload=payload)
            except TimeoutError as exc:
                raise BinanceTimeoutError("request timed out") from exc
            except urllib_error.URLError as exc:
                raise BinanceConnectionError("connection failed") from exc

        return await asyncio.to_thread(_send)


@dataclass(slots=True)
class NullStreamTransport:
    """Placeholder stream transport — the stdlib has no WebSocket client.

    Raises when used; production injects a real WebSocket transport.
    """

    _connected: bool = field(default=False, init=False)

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self, url: str) -> None:
        from adapters.binance.errors import BinanceWebSocketError

        raise BinanceWebSocketError("no stream transport configured")

    async def send(self, message: str) -> None:
        from adapters.binance.errors import BinanceWebSocketError

        raise BinanceWebSocketError("no stream transport configured")

    async def receive(self) -> str:
        from adapters.binance.errors import BinanceWebSocketError

        raise BinanceWebSocketError("no stream transport configured")

    async def close(self) -> None:
        self._connected = False
