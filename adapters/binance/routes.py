"""Binance Spot REST endpoint routes and HTTP methods.

Constants only — the official Spot API paths used by the REST client. No request
logic lives here.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "API_V3",
    "PING",
    "SERVER_TIME",
    "ACCOUNT",
    "ORDER",
    "OPEN_ORDERS",
    "TICKER_PRICE",
    "SIGNED_ROUTES",
]

API_V3: Final[str] = "/api/v3"

PING: Final[str] = f"{API_V3}/ping"
SERVER_TIME: Final[str] = f"{API_V3}/time"
ACCOUNT: Final[str] = f"{API_V3}/account"
ORDER: Final[str] = f"{API_V3}/order"
OPEN_ORDERS: Final[str] = f"{API_V3}/openOrders"
TICKER_PRICE: Final[str] = f"{API_V3}/ticker/price"

#: Routes that require an HMAC-signed request.
SIGNED_ROUTES: Final[frozenset[str]] = frozenset({ACCOUNT, ORDER, OPEN_ORDERS})
