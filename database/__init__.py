"""Persistence layer for Binance AI Hedge Fund OS.

Exposes the repository interfaces, their in-memory implementations, the
:class:`~database.service.PersistenceService`, and the DI wiring helper. Business
code should depend on the interfaces and the service — never on a concrete
repository implementation.
"""

from __future__ import annotations

from database.interfaces import (
    OrderRepository,
    PositionRepository,
    Repository,
    TradeRepository,
)
from database.memory import (
    InMemoryOrderRepository,
    InMemoryPositionRepository,
    InMemoryRepository,
    InMemoryTradeRepository,
)
from database.registration import register_persistence
from database.service import PersistenceService

__all__ = [
    "Repository",
    "OrderRepository",
    "TradeRepository",
    "PositionRepository",
    "InMemoryRepository",
    "InMemoryOrderRepository",
    "InMemoryTradeRepository",
    "InMemoryPositionRepository",
    "PersistenceService",
    "register_persistence",
]
