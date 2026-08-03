"""Performance engine — the public entry point of the Performance Framework.

:class:`DefaultPerformanceEngine` receives an assembled
:class:`~performance.context.PerformanceContext` and delegates the analysis to an
injected :class:`~performance.interfaces.PerformanceManager`. It publishes engine
lifecycle events and holds optional references to upstream engines for
integration only — it never executes trades, manages positions, values
portfolios, or talks to exchanges. Analysis is strictly read-only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from performance.context import PerformanceContext
from performance.events import PerformanceEngineStarted, PerformanceEngineStopped
from performance.interfaces import PerformanceManager
from performance.models import PerformanceResult

if TYPE_CHECKING:
    from portfolio.interfaces import PortfolioEngine
    from positions.interfaces import PositionEngine
    from trades.interfaces import TradeEngine

__all__ = ["DefaultPerformanceEngine"]


class DefaultPerformanceEngine:
    """Public performance engine coordinating analysis runs.

    Args:
        bus: Shared event bus (for engine lifecycle events).
        manager: The performance manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
        trade_engine: Optional Trade Engine reference (integration only).
        position_engine: Optional Position Engine reference (integration only).
        portfolio_engine: Optional Portfolio Engine reference (integration only).
    """

    def __init__(
        self,
        bus: EventBus,
        manager: PerformanceManager,
        logger: LoggerFactory | None = None,
        trade_engine: TradeEngine | None = None,
        position_engine: PositionEngine | None = None,
        portfolio_engine: PortfolioEngine | None = None,
    ) -> None:
        self._bus = bus
        self._manager = manager
        self._trade_engine = trade_engine
        self._position_engine = position_engine
        self._portfolio_engine = portfolio_engine
        self._log = logger.get_logger("performance.engine") if logger else None

    async def start(self) -> None:
        """Start the engine and publish a lifecycle event (no external I/O)."""
        if self._log is not None:
            self._log.info("Performance engine started")
        await self._bus.publish(PerformanceEngineStarted())

    async def stop(self) -> None:
        """Stop the engine and publish a lifecycle event (no external I/O)."""
        if self._log is not None:
            self._log.info("Performance engine stopped")
        await self._bus.publish(PerformanceEngineStopped())

    async def analyze(self, context: PerformanceContext) -> PerformanceResult:
        """Analyze ``context`` and return a :class:`PerformanceResult`."""
        return await self._manager.analyze(context)
