"""Dependency-injection wiring for the persistence layer.

Binds each repository *interface* to its in-memory implementation and registers
the :class:`~database.service.PersistenceService`, all as singletons in the
existing DI container. Business code depends on the interfaces; this module is
the one place that names concrete implementations, so switching to a database
repository later is a change here and nowhere else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from database.interfaces import (
    OrderRepository,
    PositionRepository,
    TradeRepository,
)
from database.memory import (
    InMemoryOrderRepository,
    InMemoryPositionRepository,
    InMemoryTradeRepository,
)
from database.service import PersistenceService

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = ["register_persistence"]


def register_persistence(container: Container, *, enable_logging: bool = False) -> None:
    """Register repositories and the persistence service with ``container``.

    Each repository interface is bound to its in-memory implementation as a
    singleton, and :class:`PersistenceService` is registered for constructor
    injection (it receives the repositories by their interface types).

    Args:
        container: The DI container to register into.
        enable_logging: When ``True``, the persistence service is wired with the
            :class:`~core.logging.LoggerFactory` resolved from ``container`` so
            it emits structured logs. The caller must have registered logging
            first (e.g. via :func:`core.logging.register_logging`). Defaults to
            ``False``, preserving the previous behaviour exactly.
    """
    container.register_class(OrderRepository, InMemoryOrderRepository)
    container.register_class(TradeRepository, InMemoryTradeRepository)
    container.register_class(PositionRepository, InMemoryPositionRepository)

    if enable_logging:
        from core.logging import LoggerFactory

        def _build_service(resolver: Resolver) -> PersistenceService:
            return PersistenceService(
                resolver.resolve(OrderRepository),
                resolver.resolve(TradeRepository),
                resolver.resolve(PositionRepository),
                logger=resolver.resolve(LoggerFactory),
            )

        container.register_singleton(PersistenceService, _build_service)
    else:
        container.register_class(PersistenceService)
