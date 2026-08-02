"""Order engine — the public entry point of the Order Management Framework.

:class:`DefaultOrderEngine` coordinates the complete order-management process by
delegating to an injected :class:`OrderManager`. It exposes a start/stop
lifecycle (publishing ``OrderEngineStarted`` / ``OrderEngineStopped``) and holds
references to the Trading Engine, Strategy Manager, and Risk Engine for
integration. It **never** executes orders — it only prepares them for the future
Execution Layer and returns an :class:`OrderResult`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from order_management.context import OrderContext
from order_management.events import OrderEngineStarted, OrderEngineStopped
from order_management.interfaces import OrderManager
from order_management.models import OrderResult

if TYPE_CHECKING:
    from risk.interfaces import RiskEngine
    from strategies.interfaces import StrategyManager
    from trading.engine import TradingEngine

__all__ = ["DefaultOrderEngine"]


class DefaultOrderEngine:
    """Public order engine coordinating processing and lifecycle.

    Args:
        manager: The order manager that runs the pipeline (abstraction).
        bus: The event bus used to publish lifecycle events.
        logger: Optional logger factory for framework logs.
        trading_engine: Optional Trading Engine reference (integration only).
        strategy_manager: Optional Strategy Manager reference (integration only).
        risk_engine: Optional Risk Engine reference (integration only). Orders
            are created from an :class:`OrderContext`, not by calling these.
    """

    def __init__(
        self,
        manager: OrderManager,
        bus: EventBus,
        logger: LoggerFactory | None = None,
        trading_engine: TradingEngine | None = None,
        strategy_manager: StrategyManager | None = None,
        risk_engine: RiskEngine | None = None,
    ) -> None:
        self._manager = manager
        self._bus = bus
        self._trading_engine = trading_engine
        self._strategy_manager = strategy_manager
        self._risk_engine = risk_engine
        self._log = logger.get_logger("order.engine") if logger else None

    async def start(self) -> None:
        """Announce the engine start on the event bus."""
        self._info("Order engine started")
        await self._bus.publish(OrderEngineStarted())

    async def stop(self) -> None:
        """Announce the engine stop on the event bus."""
        self._info("Order engine stopped")
        await self._bus.publish(OrderEngineStopped())

    async def process(self, context: OrderContext) -> OrderResult:
        """Process ``context`` via the manager and return the result."""
        return await self._manager.process(context)

    def _info(self, message: str) -> None:
        if self._log is not None:
            self._log.info(message)
