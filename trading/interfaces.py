"""Abstractions required by the trading engine.

Only Protocols (and one reused abstraction) — no implementations. The engine and
coordinator depend on these contracts rather than on concrete classes
(Dependency Inversion Principle), so future components plug in without any change
to the engine (Open/Closed Principle).

* :class:`Lifecycle` — anything with an explicit start/stop lifecycle.
* :class:`Coordinator` — the unit the engine drives to orchestrate services.
* :class:`EngineService` and the manager/service Protocols — the extension
  points future components (strategy, risk, orders, portfolio, market data,
  notifications, exchange) must satisfy to be coordinated by the engine.
* :class:`PersistenceService` — re-exported from :mod:`database.service`; the
  engine depends on the existing persistence abstraction rather than redefining
  it (reuse, not duplication).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

# Reuse the existing persistence abstraction rather than redefining it.
from database.service import PersistenceService as PersistenceService
from events.base import Event
from trading.state import EngineState

__all__ = [
    "Lifecycle",
    "Coordinator",
    "EngineService",
    "StrategyManager",
    "RiskManager",
    "OrderManager",
    "PortfolioManager",
    "MarketDataService",
    "NotificationService",
    "ExchangeService",
    "PersistenceService",
]


@runtime_checkable
class Lifecycle(Protocol):
    """A component with an explicit start/stop lifecycle."""

    @property
    def state(self) -> EngineState:
        """Return the component's current lifecycle state."""
        ...

    @property
    def is_running(self) -> bool:
        """Return ``True`` while the component is running."""
        ...

    async def start(self) -> None:
        """Start the component."""
        ...

    async def stop(self) -> None:
        """Stop the component."""
        ...


@runtime_checkable
class Coordinator(Protocol):
    """Coordinates infrastructure services on behalf of the engine."""

    async def start_services(self) -> None:
        """Start all coordinated infrastructure services."""
        ...

    async def stop_services(self) -> None:
        """Stop all coordinated infrastructure services."""
        ...

    def register_service(self, name: str, service: EngineService) -> None:
        """Register a pluggable service under ``name``."""
        ...

    def unregister_service(self, name: str) -> None:
        """Remove a previously registered service."""
        ...

    async def publish_event(self, event: Event) -> None:
        """Publish ``event`` on the event bus."""
        ...


@runtime_checkable
class EngineService(Protocol):
    """Base contract for any pluggable service coordinated by the engine.

    Future components implement this (and are registered with the coordinator)
    so they are started and stopped alongside the engine without the engine
    knowing their concrete types.
    """

    async def start(self) -> None:
        """Start the service."""
        ...

    async def stop(self) -> None:
        """Stop the service."""
        ...


@runtime_checkable
class StrategyManager(EngineService, Protocol):
    """Future component that owns strategy evaluation."""


@runtime_checkable
class RiskManager(EngineService, Protocol):
    """Future component that owns risk checks and limits."""


@runtime_checkable
class OrderManager(EngineService, Protocol):
    """Future component that owns order lifecycle management."""


@runtime_checkable
class PortfolioManager(EngineService, Protocol):
    """Future component that owns portfolio/position accounting."""


@runtime_checkable
class MarketDataService(EngineService, Protocol):
    """Future component that owns market-data ingestion."""


@runtime_checkable
class NotificationService(EngineService, Protocol):
    """Future component that owns outbound notifications."""


@runtime_checkable
class ExchangeService(EngineService, Protocol):
    """Future component that owns exchange connectivity."""
