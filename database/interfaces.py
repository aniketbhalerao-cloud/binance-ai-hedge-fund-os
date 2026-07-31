"""Repository interfaces for domain persistence.

These abstractions define *what* can be persisted and retrieved, never *how*.
Business components (the Trading Engine, Risk Manager, …) depend only on these
interfaces, so the concrete storage — in-memory today, SQLite/PostgreSQL later —
can be swapped without touching any business logic (Dependency Inversion).

The interfaces are intentionally free of any Event Bus, database driver, or
exchange concern. They speak purely in terms of the domain models from
:mod:`models`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from models import Order, Position, Trade

#: The domain entity a repository stores.
T = TypeVar("T")

__all__ = [
    "Repository",
    "OrderRepository",
    "TradeRepository",
    "PositionRepository",
]


class Repository(ABC, Generic[T]):
    """Generic CRUD contract for a collection of domain entities.

    Entities are addressed by a string identity (an id or natural key such as a
    symbol); the meaning of the key is defined by each concrete repository.
    """

    @abstractmethod
    def add(self, entity: T) -> None:
        """Insert or replace ``entity`` in the store."""

    @abstractmethod
    def get(self, key: str) -> T | None:
        """Return the entity identified by ``key``, or ``None`` if absent."""

    @abstractmethod
    def list(self) -> list[T]:
        """Return all stored entities."""

    @abstractmethod
    def remove(self, key: str) -> bool:
        """Remove the entity identified by ``key``.

        Returns:
            ``True`` if an entity was removed, ``False`` if none matched.
        """

    @abstractmethod
    def clear(self) -> None:
        """Remove all entities from the store."""


class OrderRepository(Repository[Order], ABC):
    """Persistence contract for :class:`~models.order.Order` entities (keyed by id)."""

    @abstractmethod
    def list_by_symbol(self, symbol: str) -> list[Order]:
        """Return all orders for ``symbol``."""


class TradeRepository(Repository[Trade], ABC):
    """Persistence contract for :class:`~models.trade.Trade` entities (keyed by id)."""

    @abstractmethod
    def list_by_symbol(self, symbol: str) -> list[Trade]:
        """Return all trades for ``symbol``."""


class PositionRepository(Repository[Position], ABC):
    """Persistence contract for :class:`~models.position.Position` entities.

    Positions are keyed by their ``symbol`` (one open position per symbol).
    """
