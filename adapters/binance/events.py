"""Binance adapter events.

Binance-specific events, each inheriting the existing :class:`events.base.Event`.
They carry no secrets, signatures, or auth headers. The framework/adapter
publishes only these — never strategy, risk, order, or execution events.
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "BinanceEvent",
    "BinanceAuthenticated",
    "BinanceAuthenticationFailed",
    "BinanceConnected",
    "BinanceDisconnected",
    "BinanceReconnectStarted",
    "BinanceReconnectSucceeded",
    "BinanceRequestSent",
    "BinanceResponseReceived",
    "BinanceOrderSubmitted",
    "BinanceOrderCancelled",
    "BinanceWebSocketConnected",
    "BinanceWebSocketDisconnected",
    "BinanceHeartbeatReceived",
    "BinanceRateLimitReached",
    "BinanceErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceEvent(Event):
    """Base class for all Binance adapter events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceAuthenticated(BinanceEvent):
    """Credentials validated locally."""


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceAuthenticationFailed(BinanceEvent):
    """Credential validation failed (no secret included)."""

    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceConnected(BinanceEvent):
    """The adapter connection opened."""


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceDisconnected(BinanceEvent):
    """The adapter connection closed."""


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceReconnectStarted(BinanceEvent):
    """A reconnection attempt began."""

    attempt: int = 1


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceReconnectSucceeded(BinanceEvent):
    """A reconnection attempt succeeded."""

    attempt: int = 1


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceRequestSent(BinanceEvent):
    """A REST request was sent (method + path only; no query/secret)."""

    method: str
    path: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceResponseReceived(BinanceEvent):
    """A REST response was received."""

    path: str
    status: int


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceOrderSubmitted(BinanceEvent):
    """An order was submitted."""

    symbol: str
    order_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceOrderCancelled(BinanceEvent):
    """An order was cancelled."""

    symbol: str
    order_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceWebSocketConnected(BinanceEvent):
    """The WebSocket stream connected."""


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceWebSocketDisconnected(BinanceEvent):
    """The WebSocket stream disconnected."""


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceHeartbeatReceived(BinanceEvent):
    """A heartbeat/ping was received."""


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceRateLimitReached(BinanceEvent):
    """A rate limit was reported by Binance."""


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceErrorOccurred(BinanceEvent):
    """An error occurred in the adapter (message is masked/safe)."""

    message: str
