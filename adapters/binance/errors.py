"""Binance adapter exceptions.

Adapter-specific exceptions that translate Binance failures into the framework's
:class:`~exchange_adapters.exceptions.ExchangeError` hierarchy, so no raw Binance
error escapes the adapter. Definitions only — no handling logic.
"""

from __future__ import annotations

from exchange_adapters.exceptions import ExchangeError

__all__ = [
    "BinanceError",
    "BinanceAuthenticationError",
    "BinanceConnectionError",
    "BinanceRateLimitError",
    "BinanceRequestError",
    "BinanceResponseError",
    "BinanceTimeoutError",
    "BinanceWebSocketError",
    "translate_http_error",
]


class BinanceError(ExchangeError):
    """Base class for all Binance adapter errors (a framework ExchangeError)."""


class BinanceAuthenticationError(BinanceError):
    """Raised when authentication/credentials are invalid."""


class BinanceConnectionError(BinanceError):
    """Raised when connectivity fails."""


class BinanceRateLimitError(BinanceError):
    """Raised when Binance reports a rate limit (HTTP 418/429)."""


class BinanceRequestError(BinanceError):
    """Raised for a malformed or rejected request (HTTP 4xx)."""


class BinanceResponseError(BinanceError):
    """Raised when a response cannot be parsed or is unexpected."""


class BinanceTimeoutError(BinanceError):
    """Raised when a request exceeds the configured timeout."""


class BinanceWebSocketError(BinanceError):
    """Raised for WebSocket connectivity/streaming failures."""


def translate_http_error(status: int, message: str = "") -> BinanceError:
    """Translate an HTTP status into the appropriate Binance exception.

    Args:
        status: The HTTP status code.
        message: Optional context (never include secrets).

    Returns:
        A :class:`BinanceError` subclass appropriate for ``status``.
    """
    detail = f" ({message})" if message else ""
    if status in (418, 429):
        return BinanceRateLimitError(f"rate limited: {status}{detail}")
    if status in (401, 403):
        return BinanceAuthenticationError(f"authentication failed: {status}{detail}")
    if 400 <= status < 500:
        return BinanceRequestError(f"request rejected: {status}{detail}")
    return BinanceConnectionError(f"server error: {status}{detail}")
