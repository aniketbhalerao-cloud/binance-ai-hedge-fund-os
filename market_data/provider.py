"""Market-data provider base.

:class:`BaseMarketDataProvider` coordinates an incoming data source: it manages
connection state and relays raw payloads to a registered handler. It does
**nothing** else — no parsing (that is the normalizer's job), no caching, and no
event publishing (that is the service's job).

Concrete providers for specific sources (a live exchange feed, a CSV reader, a
historical-replay source, …) subclass this and call :meth:`_emit` with each raw
payload. This module implements no exchange-specific, WebSocket, or REST logic.
"""

from __future__ import annotations

from market_data.interfaces import RawHandler, RawPayload

__all__ = ["BaseMarketDataProvider"]


class BaseMarketDataProvider:
    """Base class that relays raw payloads and tracks connection state."""

    def __init__(self) -> None:
        self._handler: RawHandler | None = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Return ``True`` while the provider is connected."""
        return self._connected

    def on_data(self, handler: RawHandler) -> None:
        """Register the async handler that receives raw payloads."""
        self._handler = handler

    async def connect(self) -> None:
        """Mark the provider connected and run the subclass connect hook."""
        await self._on_connect()
        self._connected = True

    async def disconnect(self) -> None:
        """Mark the provider disconnected and run the subclass disconnect hook."""
        self._connected = False
        await self._on_disconnect()

    async def _emit(self, raw: RawPayload) -> None:
        """Relay a raw payload to the registered handler, if any."""
        if self._handler is not None:
            await self._handler(raw)

    async def _on_connect(self) -> None:
        """Subclass hook: establish the underlying source. No-op by default."""

    async def _on_disconnect(self) -> None:
        """Subclass hook: tear down the underlying source. No-op by default."""
