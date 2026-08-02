"""Binance-specific enumerations and account models.

Binance domain values (sides, order types, statuses) and simple account models.
These are internal to the adapter; the rest of the system consumes only the
standardized :class:`~exchange_adapters.models.ExchangeResponse`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

__all__ = [
    "BinanceSide",
    "BinanceOrderType",
    "BinanceTimeInForce",
    "BinanceOrderStatus",
    "BinanceBalance",
    "BinanceAccount",
]


class BinanceSide(str, Enum):
    """Binance order side."""

    BUY = "BUY"
    SELL = "SELL"


class BinanceOrderType(str, Enum):
    """Binance Spot order type."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"


class BinanceTimeInForce(str, Enum):
    """Binance time-in-force."""

    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


class BinanceOrderStatus(str, Enum):
    """Binance order status."""

    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class BinanceBalance:
    """A single asset balance from a Binance account payload."""

    asset: str
    free: Decimal
    locked: Decimal


@dataclass(frozen=True, slots=True)
class BinanceAccount:
    """A parsed Binance account snapshot."""

    can_trade: bool
    balances: tuple[BinanceBalance, ...] = ()
