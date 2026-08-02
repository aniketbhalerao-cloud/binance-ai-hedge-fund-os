"""Binance connection management.

Manages the adapter's connection state (connected/disconnected/connecting/
reconnecting) with heartbeat and reconnect support. State mutation is lock-guarded.
It implements the framework's
:class:`~exchange_adapters.interfaces.ExchangeConnection` protocol; transport
details never leak outside the adapter.
"""

from __future__ import annotations

from threading import Lock

from adapters.binance.events import (
    BinanceConnected,
    BinanceDisconnected,
    BinanceHeartbeatReceived,
    BinanceReconnectStarted,
    BinanceReconnectSucceeded,
)
from core.logging import LoggerFactory
from events.bus import EventBus
from exchange_adapters.context import ExchangeContext
from exchange_adapters.state import ConnectionState

__all__ = ["BinanceConnection"]


class BinanceConnection:
    """Tracks Binance connectivity state (no real socket here).

    Args:
        bus: Event bus for connection lifecycle events.
        logger: Optional logger factory.
    """

    def __init__(self, bus: EventBus, logger: LoggerFactory | None = None) -> None:
        self._bus = bus
        self._log = logger.get_logger("binance.connection") if logger else None
        self._state = ConnectionState.DISCONNECTED
        self._lock = Lock()

    @property
    def state(self) -> ConnectionState:
        """Return the current connection state."""
        with self._lock:
            return self._state

    async def open(self, context: ExchangeContext) -> ConnectionState:
        """Open the connection (framework ``ExchangeConnection`` entry point)."""
        return await self.connect()

    async def connect(self) -> ConnectionState:
        """Transition to CONNECTED and publish the event."""
        with self._lock:
            self._state = ConnectionState.CONNECTED
        if self._log is not None:
            self._log.info("Connected")
        await self._bus.publish(BinanceConnected())
        return ConnectionState.CONNECTED

    async def close(self) -> ConnectionState:
        """Transition to CLOSED and publish the event."""
        with self._lock:
            self._state = ConnectionState.CLOSED
        if self._log is not None:
            self._log.info("Disconnected")
        await self._bus.publish(BinanceDisconnected())
        return ConnectionState.CLOSED

    async def reconnect(self, attempt: int = 1) -> ConnectionState:
        """Reconnect: RECONNECTING → CONNECTED, publishing lifecycle events."""
        with self._lock:
            self._state = ConnectionState.RECONNECTING
        await self._bus.publish(BinanceReconnectStarted(attempt=attempt))
        state = await self.connect()
        await self._bus.publish(BinanceReconnectSucceeded(attempt=attempt))
        return state

    async def heartbeat(self) -> None:
        """Record a heartbeat/ping."""
        await self._bus.publish(BinanceHeartbeatReceived())
