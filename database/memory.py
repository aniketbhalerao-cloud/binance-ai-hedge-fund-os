"""In-memory repository implementations.

Thread-safe, dependency-free implementations of the repository interfaces,
backed by a plain dictionary. They are the default storage for development,
tests, and paper trading, and serve as the reference implementation that a
future SQLite/PostgreSQL repository must behave like.

No database driver, Event Bus, or exchange code is used — only the standard
library and the domain models.
"""

from __future__ import annotations

from abc import abstractmethod
from threading import RLock
from typing import Generic, TypeVar

from database.interfaces import (
    OrderRepository,
    PositionRepository,
    Repository,
    TradeRepository,
)
from models import Order, Position, Trade

T = TypeVar("T")

__all__ = [
    "InMemoryRepository",
    "InMemoryOrderRepository",
    "InMemoryTradeRepository",
    "InMemoryPositionRepository",
]


class InMemoryRepository(Repository[T], Generic[T]):
    """A thread-safe, dictionary-backed base repository.

    Concrete subclasses only need to define :meth:`_identity` — how an entity
    maps to its storage key.
    """

    def __init__(self) -> None:
        self._items: dict[str, T] = {}
        self._lock = RLock()

    @abstractmethod
    def _identity(self, entity: T) -> str:
        """Return the storage key for ``entity``."""

    def add(self, entity: T) -> None:
        """Insert or replace ``entity`` keyed by its identity."""
        with self._lock:
            self._items[self._identity(entity)] = entity

    def get(self, key: str) -> T | None:
        """Return the entity for ``key``, or ``None`` if absent."""
        with self._lock:
            return self._items.get(key)

    def list(self) -> list[T]:
        """Return a snapshot list of all stored entities."""
        with self._lock:
            return list(self._items.values())

    def remove(self, key: str) -> bool:
        """Remove the entity for ``key``; return whether one was removed."""
        with self._lock:
            return self._items.pop(key, None) is not None

    def clear(self) -> None:
        """Remove all entities."""
        with self._lock:
            self._items.clear()


class InMemoryOrderRepository(InMemoryRepository[Order], OrderRepository):
    """In-memory :class:`~database.interfaces.OrderRepository` (keyed by order id)."""

    def _identity(self, entity: Order) -> str:
        return entity.id

    def list_by_symbol(self, symbol: str) -> list[Order]:
        """Return all stored orders for ``symbol``."""
        with self._lock:
            return [order for order in self._items.values() if order.symbol == symbol]


class InMemoryTradeRepository(InMemoryRepository[Trade], TradeRepository):
    """In-memory :class:`~database.interfaces.TradeRepository` (keyed by trade id)."""

    def _identity(self, entity: Trade) -> str:
        return entity.id

    def list_by_symbol(self, symbol: str) -> list[Trade]:
        """Return all stored trades for ``symbol``."""
        with self._lock:
            return [trade for trade in self._items.values() if trade.symbol == symbol]


class InMemoryPositionRepository(InMemoryRepository[Position], PositionRepository):
    """In-memory :class:`~database.interfaces.PositionRepository` (keyed by symbol)."""

    def _identity(self, entity: Position) -> str:
        return entity.symbol
