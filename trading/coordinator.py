"""Trading coordinator.

:class:`TradingCoordinator` is the single place where the engine touches shared
infrastructure. It is constructed with its collaborators — the
:class:`~events.bus.EventBus` (required) and, optionally, a
:class:`~core.logging.LoggerFactory`, the existing
:class:`~database.service.PersistenceService`, and an
:class:`~adapters.interfaces.ExchangeInterface` — all supplied by the DI
container.

It *orchestrates*: it starts/stops registered services, publishes events, and
logs. It maintains a registry of pluggable services so future components plug in
without changing the engine (Open/Closed Principle). It performs **no** business
decisions — it never evaluates strategies, calculates signals/risk, places
trades, communicates with exchanges, or manages positions.
"""

from __future__ import annotations

from adapters.interfaces import ExchangeInterface
from core.logging import LoggerFactory
from database.service import PersistenceService
from events.base import Event
from events.bus import EventBus
from trading.exceptions import ServiceRegistrationError
from trading.interfaces import EngineService

__all__ = ["TradingCoordinator", "COMPONENT_NAME"]

#: Name reported by logs emitted by this coordinator.
COMPONENT_NAME = "trading-engine"


class TradingCoordinator:
    """Coordinates shared infrastructure on behalf of the trading engine.

    Args:
        bus: The event bus used to publish events.
        logger: Optional logger factory; when supplied, coordination is logged.
        persistence: Optional persistence service, held for future coordination.
        exchange: Optional exchange adapter, held for future coordination.
    """

    def __init__(
        self,
        bus: EventBus,
        *,
        logger: LoggerFactory | None = None,
        persistence: PersistenceService | None = None,
        exchange: ExchangeInterface | None = None,
    ) -> None:
        self._bus = bus
        self._persistence = persistence
        self._exchange = exchange
        self._log = logger.get_logger("trading.coordinator") if logger else None
        self._services: dict[str, EngineService] = {}

    @property
    def persistence(self) -> PersistenceService | None:
        """The persistence service available for coordination, if wired."""
        return self._persistence

    @property
    def exchange(self) -> ExchangeInterface | None:
        """The exchange adapter available for coordination, if wired."""
        return self._exchange

    def register_service(self, name: str, service: EngineService) -> None:
        """Register a pluggable service under ``name``.

        Args:
            name: Unique service name.
            service: A component satisfying :class:`EngineService`.

        Raises:
            ServiceRegistrationError: If ``name`` is already registered.
        """
        if name in self._services:
            raise ServiceRegistrationError(f"Service {name!r} is already registered.")
        self._services[name] = service

    def unregister_service(self, name: str) -> None:
        """Remove a previously registered service.

        Raises:
            ServiceRegistrationError: If ``name`` is not registered.
        """
        if name not in self._services:
            raise ServiceRegistrationError(f"Service {name!r} is not registered.")
        del self._services[name]

    async def start_services(self) -> None:
        """Start every registered service, in registration order."""
        if self._log is not None:
            self._log.info(
                "Starting coordinated services",
                extra={"component": COMPONENT_NAME, "count": len(self._services)},
            )
        for name, service in self._services.items():
            if self._log is not None:
                self._log.debug("Starting service", extra={"service": name})
            await service.start()

    async def stop_services(self) -> None:
        """Stop every registered service, in reverse registration order."""
        if self._log is not None:
            self._log.info(
                "Stopping coordinated services",
                extra={"component": COMPONENT_NAME, "count": len(self._services)},
            )
        for name, service in reversed(list(self._services.items())):
            if self._log is not None:
                self._log.debug("Stopping service", extra={"service": name})
            await service.stop()

    async def publish_event(self, event: Event) -> None:
        """Publish ``event`` on the shared event bus."""
        await self._bus.publish(event)
