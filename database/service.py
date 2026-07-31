"""Persistence Service.

:class:`PersistenceService` is the single coordination point through which the
rest of the system persists and retrieves domain entities. It depends only on
the repository *interfaces* (injected via the constructor), so it is unaware of
any concrete storage engine.

It is deliberately decoupled from the Event Bus. The service exposes plain
methods (``save_order``, ``record_trade``, …) that an event subscriber can call
in a later task — the subscriber will live elsewhere and translate domain events
into these calls, so neither this module nor the repositories import
:mod:`events`.

Logging is an *optional* collaborator: when a :class:`~core.logging.LoggerFactory`
is supplied (wired by :func:`database.registration.register_persistence`), the
service emits structured debug logs for each persistence operation. When it is
omitted the service behaves exactly as before, so integrating logging never
changes existing call sites. The repositories themselves remain logging-free.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from database.interfaces import (
    OrderRepository,
    PositionRepository,
    TradeRepository,
)
from models import Order, Position, Trade

if TYPE_CHECKING:
    from core.logging import LoggerFactory

__all__ = ["PersistenceService"]


class PersistenceService:
    """Coordinates persistence across the order, trade, and position stores.

    Args:
        orders: Repository for orders.
        trades: Repository for trades.
        positions: Repository for positions.

    The parameters are interfaces, so the container injects whichever concrete
    implementation is registered (in-memory now, a database repository later).
    """

    def __init__(
        self,
        orders: OrderRepository,
        trades: TradeRepository,
        positions: PositionRepository,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._orders = orders
        self._trades = trades
        self._positions = positions
        # Optional: resolve a module logger only when a factory is provided.
        self._log = logger.get_logger("persistence") if logger is not None else None

    # -- orders -------------------------------------------------------------

    def save_order(self, order: Order) -> None:
        """Persist (insert or update) an order."""
        if self._log is not None:
            self._log.debug(
                "save_order", extra={"order_id": order.id, "symbol": order.symbol}
            )
        self._orders.add(order)

    def get_order(self, order_id: str) -> Order | None:
        """Return the order with ``order_id`` if present."""
        return self._orders.get(order_id)

    def list_orders(self) -> list[Order]:
        """Return all persisted orders."""
        return self._orders.list()

    # -- trades -------------------------------------------------------------

    def record_trade(self, trade: Trade) -> None:
        """Persist an executed trade (fill)."""
        if self._log is not None:
            self._log.debug(
                "record_trade", extra={"trade_id": trade.id, "symbol": trade.symbol}
            )
        self._trades.add(trade)

    def list_trades(self) -> list[Trade]:
        """Return all persisted trades."""
        return self._trades.list()

    # -- positions ----------------------------------------------------------

    def save_position(self, position: Position) -> None:
        """Persist (insert or update) a position, keyed by symbol."""
        self._positions.add(position)

    def get_position(self, symbol: str) -> Position | None:
        """Return the open position for ``symbol`` if present."""
        return self._positions.get(symbol)

    def list_positions(self) -> list[Position]:
        """Return all persisted positions."""
        return self._positions.list()
