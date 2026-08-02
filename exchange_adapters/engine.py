"""Exchange engine — the public entry point of the Exchange Adapter Framework.

:class:`DefaultExchangeEngine` coordinates the framework by delegating to an
injected :class:`ExchangeManager`. It exposes a start/stop lifecycle (publishing
``ExchangeEngineStarted`` / ``ExchangeEngineStopped``) and holds references to the
upstream frameworks for integration. It contains **no** broker-specific logic and
never talks to an exchange — real broker work is delegated to future adapters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from exchange_adapters.context import ExchangeContext
from exchange_adapters.events import (
    ExchangeEngineStarted,
    ExchangeEngineStopped,
)
from exchange_adapters.interfaces import ExchangeManager
from exchange_adapters.models import ExchangeResult

if TYPE_CHECKING:
    from execution.interfaces import ExecutionEngine
    from trading.engine import TradingEngine

__all__ = ["DefaultExchangeEngine"]


class DefaultExchangeEngine:
    """Public exchange engine coordinating processing and lifecycle.

    Args:
        manager: The exchange manager that runs the pipeline (abstraction).
        bus: The event bus used to publish lifecycle events.
        logger: Optional logger factory for framework logs.
        trading_engine: Optional Trading Engine reference (integration only).
        execution_engine: Optional Execution Engine reference (integration only).
    """

    def __init__(
        self,
        manager: ExchangeManager,
        bus: EventBus,
        logger: LoggerFactory | None = None,
        trading_engine: TradingEngine | None = None,
        execution_engine: ExecutionEngine | None = None,
    ) -> None:
        self._manager = manager
        self._bus = bus
        self._trading_engine = trading_engine
        self._execution_engine = execution_engine
        self._log = logger.get_logger("exchange.engine") if logger else None

    async def start(self) -> None:
        """Announce the engine start on the event bus."""
        self._info("Exchange engine started")
        await self._bus.publish(ExchangeEngineStarted())

    async def stop(self) -> None:
        """Announce the engine stop on the event bus."""
        self._info("Exchange engine stopped")
        await self._bus.publish(ExchangeEngineStopped())

    async def process(self, context: ExchangeContext) -> ExchangeResult:
        """Process ``context`` via the manager and return the result."""
        return await self._manager.process(context)

    def _info(self, message: str) -> None:
        if self._log is not None:
            self._log.info(message)
