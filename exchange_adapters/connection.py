"""Connection abstraction.

:class:`DefaultExchangeConnection` represents broker connectivity as framework
state only — it opens/closes no REST, WebSocket, or SDK connection and sends no
heartbeats. ``open`` reports ``CONNECTED`` and ``close`` reports ``CLOSED``; a
future broker adapter provides real connectivity behind the same
:class:`~exchange_adapters.interfaces.ExchangeConnection` protocol. It keeps no
mutable shared state.
"""

from __future__ import annotations

from exchange_adapters.context import ExchangeContext
from exchange_adapters.state import ConnectionState

__all__ = ["DefaultExchangeConnection"]


class DefaultExchangeConnection:
    """Framework-level connection (no real socket)."""

    async def open(self, context: ExchangeContext) -> ConnectionState:
        """Report the connection as opened (abstraction — no I/O)."""
        return ConnectionState.CONNECTED

    async def close(self) -> ConnectionState:
        """Report the connection as closed (abstraction — no I/O)."""
        return ConnectionState.CLOSED
