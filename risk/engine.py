"""Risk engine — the public entry point of the Risk Framework.

:class:`RiskEvaluationEngine` coordinates the complete evaluation process. It
delegates the actual evaluation to an injected :class:`RiskManager`, exposes a
start/stop lifecycle (publishing ``RiskEngineStarted`` / ``RiskEngineStopped``),
and holds references to the Trading Engine and Strategy Manager for integration.
It **never** executes trades — it only decides whether a signal is allowed to
proceed and returns a :class:`~risk.models.RiskDecision`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from risk.context import RiskContext
from risk.events import RiskEngineStarted, RiskEngineStopped
from risk.interfaces import RiskManager
from risk.models import RiskDecision

if TYPE_CHECKING:
    from strategies.interfaces import StrategyManager
    from trading.engine import TradingEngine

__all__ = ["RiskEvaluationEngine"]


class RiskEvaluationEngine:
    """Public risk engine coordinating evaluation and lifecycle.

    Args:
        manager: The risk manager that performs evaluations (abstraction).
        bus: The event bus used to publish lifecycle events.
        logger: Optional logger factory for framework logs.
        trading_engine: Optional Trading Engine reference (integration only).
        strategy_manager: Optional Strategy Manager reference (integration only);
            the risk engine consumes signals via a :class:`RiskContext`, never by
            reaching into the strategy framework.
    """

    def __init__(
        self,
        manager: RiskManager,
        bus: EventBus,
        logger: LoggerFactory | None = None,
        trading_engine: TradingEngine | None = None,
        strategy_manager: StrategyManager | None = None,
    ) -> None:
        self._manager = manager
        self._bus = bus
        self._engine = trading_engine
        self._strategy_manager = strategy_manager
        self._log = logger.get_logger("risk.engine") if logger else None

    async def start(self) -> None:
        """Announce the engine start on the event bus."""
        self._info("Risk engine started")
        await self._bus.publish(RiskEngineStarted())

    async def stop(self) -> None:
        """Announce the engine stop on the event bus."""
        self._info("Risk engine stopped")
        await self._bus.publish(RiskEngineStopped())

    async def evaluate(self, context: RiskContext) -> RiskDecision:
        """Evaluate ``context`` via the manager and return the decision."""
        return await self._manager.evaluate(context)

    def _info(self, message: str) -> None:
        if self._log is not None:
            self._log.info(message)
