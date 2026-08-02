"""Binance Spot WebSocket client.

Wraps an injected :class:`~adapters.binance.client.StreamTransport` to provide
connect/disconnect/subscribe/unsubscribe/receive with automatic reconnect. It is
independent from the REST client. No real WebSocket library is used here — the
transport is injected (a real one in production, a fake in tests).
"""

from __future__ import annotations

from threading import Lock

from adapters.binance.client import StreamTransport
from adapters.binance.config import BinanceConfig
from adapters.binance.errors import BinanceWebSocketError
from adapters.binance.events import (
    BinanceReconnectStarted,
    BinanceReconnectSucceeded,
    BinanceWebSocketConnected,
    BinanceWebSocketDisconnected,
)
from core.logging import LoggerFactory
from events.bus import EventBus

__all__ = ["BinanceWebSocketClient"]


class BinanceWebSocketClient:
    """Coordinates a Binance Spot stream over an injected transport.

    Args:
        transport: The stream transport (abstraction; injected).
        config: Adapter configuration (WebSocket URL).
        bus: Event bus for connection events.
        logger: Optional logger factory.
    """

    def __init__(
        self,
        transport: StreamTransport,
        config: BinanceConfig,
        bus: EventBus,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._transport = transport
        self._config = config
        self._bus = bus
        self._log = logger.get_logger("binance.ws") if logger else None
        self._subscriptions: set[str] = set()
        self._lock = Lock()

    @property
    def connected(self) -> bool:
        """Return ``True`` while the underlying transport is connected."""
        return self._transport.connected

    async def connect(self) -> None:
        """Open the stream."""
        await self._transport.connect(self._config.ws_url)
        if self._log is not None:
            self._log.info("WebSocket connected")
        await self._bus.publish(BinanceWebSocketConnected())

    async def disconnect(self) -> None:
        """Close the stream."""
        await self._transport.close()
        if self._log is not None:
            self._log.info("WebSocket disconnected")
        await self._bus.publish(BinanceWebSocketDisconnected())

    async def subscribe(self, stream: str) -> None:
        """Subscribe to ``stream`` (thread-safe subscription set)."""
        with self._lock:
            self._subscriptions.add(stream)
        await self._transport.send(f'{{"method":"SUBSCRIBE","params":["{stream}"]}}')

    async def unsubscribe(self, stream: str) -> None:
        """Unsubscribe from ``stream``."""
        with self._lock:
            self._subscriptions.discard(stream)
        await self._transport.send(f'{{"method":"UNSUBSCRIBE","params":["{stream}"]}}')

    async def receive(self) -> str:
        """Receive the next raw message."""
        return await self._transport.receive()

    async def reconnect(self, attempt: int = 1) -> None:
        """Reconnect the stream and re-subscribe to active streams."""
        await self._bus.publish(BinanceReconnectStarted(attempt=attempt))
        await self._transport.close()
        try:
            await self._transport.connect(self._config.ws_url)
        except BinanceWebSocketError:
            raise
        with self._lock:
            streams = tuple(self._subscriptions)
        for stream in streams:
            await self._transport.send(
                f'{{"method":"SUBSCRIBE","params":["{stream}"]}}'
            )
        await self._bus.publish(BinanceReconnectSucceeded(attempt=attempt))
