"""Binance Spot adapter — first concrete Exchange Adapter Framework implementation.

Implements the Binance Spot API integration (authentication + HMAC-SHA256
signing, a reusable REST client, a WebSocket client, request translation,
response parsing, validation, and connection management) behind the framework's
:class:`~exchange_adapters.adapter.BaseExchangeAdapter`, keeping the rest of the
system exchange-independent. Network transports are injected, so nothing here
forces a real connection; secrets are never logged, evented, or rendered.

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from adapters.binance.adapter import BINANCE_ADAPTER_NAME, BinanceSpotAdapter
from adapters.binance.authentication import BinanceAuthentication
from adapters.binance.client import (
    HttpResponse,
    HttpTransport,
    NullStreamTransport,
    StreamTransport,
    UrllibHttpTransport,
)
from adapters.binance.config import BinanceConfig
from adapters.binance.connection import BinanceConnection
from adapters.binance.converters import BinanceRequestTranslator
from adapters.binance.errors import (
    BinanceAuthenticationError,
    BinanceConnectionError,
    BinanceError,
    BinanceRateLimitError,
    BinanceRequestError,
    BinanceResponseError,
    BinanceTimeoutError,
    BinanceWebSocketError,
)
from adapters.binance.events import (
    BinanceAuthenticated,
    BinanceAuthenticationFailed,
    BinanceConnected,
    BinanceDisconnected,
    BinanceErrorOccurred,
    BinanceEvent,
    BinanceHeartbeatReceived,
    BinanceOrderCancelled,
    BinanceOrderSubmitted,
    BinanceRateLimitReached,
    BinanceReconnectStarted,
    BinanceReconnectSucceeded,
    BinanceRequestSent,
    BinanceResponseReceived,
    BinanceWebSocketConnected,
    BinanceWebSocketDisconnected,
)
from adapters.binance.models import (
    BinanceAccount,
    BinanceBalance,
    BinanceOrderStatus,
    BinanceOrderType,
    BinanceSide,
    BinanceTimeInForce,
)
from adapters.binance.parser import BinanceResponseParser
from adapters.binance.registry import register_binance_adapter
from adapters.binance.requests import (
    BinanceCancelRequest,
    BinanceOrderRequest,
    BinanceRequestValidator,
)
from adapters.binance.responses import BinanceOrderResponse
from adapters.binance.rest import BinanceRESTClient
from adapters.binance.signer import BinanceSigner
from adapters.binance.websocket import BinanceWebSocketClient

__all__ = [
    # config / signer / auth
    "BinanceConfig",
    "BinanceSigner",
    "BinanceAuthentication",
    # transports / clients
    "HttpResponse",
    "HttpTransport",
    "StreamTransport",
    "UrllibHttpTransport",
    "NullStreamTransport",
    "BinanceRESTClient",
    "BinanceWebSocketClient",
    "BinanceConnection",
    # translation / parsing / validation / models
    "BinanceRequestTranslator",
    "BinanceResponseParser",
    "BinanceRequestValidator",
    "BinanceOrderRequest",
    "BinanceCancelRequest",
    "BinanceOrderResponse",
    "BinanceSide",
    "BinanceOrderType",
    "BinanceTimeInForce",
    "BinanceOrderStatus",
    "BinanceBalance",
    "BinanceAccount",
    # adapter
    "BinanceSpotAdapter",
    "BINANCE_ADAPTER_NAME",
    # events
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
    # exceptions
    "BinanceError",
    "BinanceAuthenticationError",
    "BinanceConnectionError",
    "BinanceRateLimitError",
    "BinanceRequestError",
    "BinanceResponseError",
    "BinanceTimeoutError",
    "BinanceWebSocketError",
    # wiring
    "register_binance_adapter",
]
