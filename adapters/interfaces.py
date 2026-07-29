"""Exchange adapter abstraction.

This module defines the single contract that *every* exchange adapter (Binance,
Zerodha, a paper-trading simulator, …) must implement. The Trading Engine and
every higher layer depend only on :class:`ExchangeInterface` — never on a
concrete broker SDK — which is what makes the platform exchange-agnostic
(Dependency Inversion Principle).

The module contains **only** abstractions:

* small, immutable :mod:`dataclasses` value objects describing the data that
  crosses the boundary (balances, prices, orders, positions); and
* the :class:`ExchangeInterface` abstract base class enumerating the operations
  an adapter must provide.

No concrete adapter, broker SDK call, or business logic lives here. Methods are
declared with :func:`abc.abstractmethod` and are intentionally unimplemented.

I/O-bound operations are declared ``async`` because real exchange calls are
network round-trips; the connection-state check :meth:`ExchangeInterface.is_connected`
is synchronous as it only inspects local state.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

__all__ = [
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "TimeInForce",
    "Balance",
    "MarketPrice",
    "OrderRequest",
    "Order",
    "Position",
    "ExchangeInterface",
]


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class OrderSide(str, Enum):
    """The direction of an order."""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """How an order is priced and matched."""

    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    """Lifecycle state of an order as reported by the venue."""

    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(str, Enum):
    """How long an order remains active before it expires."""

    GTC = "gtc"  # Good 'til canceled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill


# ---------------------------------------------------------------------------
# Value objects (boundary DTOs)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Balance:
    """A single asset balance held on the exchange.

    Attributes:
        asset: The asset symbol (e.g. ``"USDT"``, ``"BTC"``).
        free: Amount available to trade.
        locked: Amount reserved by open orders.
    """

    asset: str
    free: Decimal
    locked: Decimal


@dataclass(frozen=True, slots=True)
class MarketPrice:
    """The latest known price for a trading symbol.

    Attributes:
        symbol: The trading pair (e.g. ``"BTCUSDT"``).
        price: The current price expressed in the quote asset.
        timestamp: When the price was observed (UTC).
    """

    symbol: str
    price: Decimal
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """An instruction to open an order, independent of any venue.

    Attributes:
        symbol: The trading pair to trade.
        side: Buy or sell.
        type: Market or limit.
        quantity: Amount of the base asset to transact.
        price: Limit price; ``None`` for market orders.
        time_in_force: Expiry policy for the order.
        client_order_id: Optional caller-supplied idempotency key.
    """

    symbol: str
    side: OrderSide
    type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.GTC
    client_order_id: str | None = None


@dataclass(frozen=True, slots=True)
class Order:
    """The venue's view of an order.

    Attributes:
        order_id: Exchange-assigned identifier.
        symbol: The trading pair.
        side: Buy or sell.
        type: Market or limit.
        status: Current lifecycle state.
        quantity: Total ordered amount of the base asset.
        filled_quantity: Amount filled so far.
        price: Limit price, if applicable.
        average_fill_price: Volume-weighted fill price, if any fills occurred.
        created_at: When the order was created (UTC).
        client_order_id: Caller-supplied idempotency key, if provided.
    """

    order_id: str
    symbol: str
    side: OrderSide
    type: OrderType
    status: OrderStatus
    quantity: Decimal
    filled_quantity: Decimal
    price: Decimal | None
    average_fill_price: Decimal | None
    created_at: datetime
    client_order_id: str | None = None


@dataclass(frozen=True, slots=True)
class Position:
    """An open position on the exchange.

    Attributes:
        symbol: The trading pair.
        side: Direction of the position.
        quantity: Size of the position in the base asset.
        entry_price: Average entry price.
        unrealized_pnl: Mark-to-market profit/loss in the quote asset.
    """

    symbol: str
    side: OrderSide
    quantity: Decimal
    entry_price: Decimal
    unrealized_pnl: Decimal


# ---------------------------------------------------------------------------
# The exchange contract
# ---------------------------------------------------------------------------


class ExchangeInterface(ABC):
    """Contract every exchange adapter must implement.

    Concrete adapters (Binance, Zerodha, paper-trading, …) subclass this and
    translate these venue-neutral operations into the specific broker's API.
    Consumers such as the Trading Engine depend on this abstraction alone, so
    swapping or adding an exchange never changes their code.
    """

    # -- connection lifecycle ----------------------------------------------

    @abstractmethod
    async def connect(self) -> None:
        """Establish a connection/session with the exchange.

        Raises:
            Exception: Implementations may raise on authentication or network
                failure. (No concrete errors are defined at the interface.)
        """

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection/session and release any held resources."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Return ``True`` if the adapter currently holds a live connection."""

    # -- account -----------------------------------------------------------

    @abstractmethod
    async def get_balance(self) -> list[Balance]:
        """Return the account's asset balances.

        Returns:
            One :class:`Balance` per asset held on the account.
        """

    # -- market data -------------------------------------------------------

    @abstractmethod
    async def get_market_price(self, symbol: str) -> MarketPrice:
        """Return the latest price for ``symbol``.

        Args:
            symbol: The trading pair to quote (e.g. ``"BTCUSDT"``).

        Returns:
            The most recent :class:`MarketPrice` for ``symbol``.
        """

    # -- order management --------------------------------------------------

    @abstractmethod
    async def place_order(self, request: OrderRequest) -> Order:
        """Submit an order described by ``request``.

        Args:
            request: The venue-neutral order instruction.

        Returns:
            The resulting :class:`Order` as acknowledged by the exchange.
        """

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> Order:
        """Cancel a previously placed order.

        Args:
            symbol: The trading pair the order belongs to.
            order_id: Exchange-assigned identifier of the order to cancel.

        Returns:
            The :class:`Order` in its post-cancellation state.
        """

    @abstractmethod
    async def get_order_status(self, symbol: str, order_id: str) -> Order:
        """Fetch the current state of a single order.

        Args:
            symbol: The trading pair the order belongs to.
            order_id: Exchange-assigned identifier of the order.

        Returns:
            The current :class:`Order`.
        """

    @abstractmethod
    async def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        """Return currently open (unfilled or partially filled) orders.

        Args:
            symbol: Restrict to a single trading pair; ``None`` returns open
                orders across all pairs.

        Returns:
            The list of open :class:`Order` records.
        """

    # -- positions ---------------------------------------------------------

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Return all currently open positions.

        Returns:
            One :class:`Position` per open position on the account.
        """
