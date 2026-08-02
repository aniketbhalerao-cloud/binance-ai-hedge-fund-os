"""Execution engine — the public entry point of the Execution Framework.

:class:`DefaultExecutionEngine` coordinates the complete execution-management
process by delegating to an injected :class:`ExecutionManager`. It exposes a
start/stop lifecycle (publishing ``ExecutionEngineStarted`` /
``ExecutionEngineStopped``) and holds references to the upstream frameworks for
integration. It contains **no** broker-specific logic and never communicates
with an exchange — actual broker work is delegated to future Exchange Adapters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from execution.context import ExecutionContext
from execution.events import ExecutionEngineStarted, ExecutionEngineStopped
from execution.interfaces import ExecutionManager
from execution.models import ExecutionResult

if TYPE_CHECKING:
    from order_management.interfaces import OrderEngine
    from risk.interfaces import RiskEngine
    from strategies.interfaces import StrategyManager
    from trading.engine import TradingEngine

__all__ = ["DefaultExecutionEngine"]


class DefaultExecutionEngine:
    """Public execution engine coordinating processing and lifecycle.

    Args:
        manager: The execution manager that runs the pipeline (abstraction).
        bus: The event bus used to publish lifecycle events.
        logger: Optional logger factory for framework logs.
        trading_engine: Optional Trading Engine reference (integration only).
        strategy_manager: Optional Strategy Manager reference (integration only).
        risk_engine: Optional Risk Engine reference (integration only).
        order_engine: Optional Order Engine reference (integration only).
    """

    def __init__(
        self,
        manager: ExecutionManager,
        bus: EventBus,
        logger: LoggerFactory | None = None,
        trading_engine: TradingEngine | None = None,
        strategy_manager: StrategyManager | None = None,
        risk_engine: RiskEngine | None = None,
        order_engine: OrderEngine | None = None,
    ) -> None:
        self._manager = manager
        self._bus = bus
        self._trading_engine = trading_engine
        self._strategy_manager = strategy_manager
        self._risk_engine = risk_engine
        self._order_engine = order_engine
        self._log = logger.get_logger("execution.engine") if logger else None

    async def start(self) -> None:
        """Announce the engine start on the event bus."""
        self._info("Execution engine started")
        await self._bus.publish(ExecutionEngineStarted())

    async def stop(self) -> None:
        """Announce the engine stop on the event bus."""
        self._info("Execution engine stopped")
        await self._bus.publish(ExecutionEngineStopped())

    async def process(self, context: ExecutionContext) -> ExecutionResult:
        """Process ``context`` via the manager and return the result."""
        return await self._manager.process(context)

    def _info(self, message: str) -> None:
        if self._log is not None:
            self._log.info(message)
